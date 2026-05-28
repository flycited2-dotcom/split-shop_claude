import re

from django.shortcuts import render, get_object_or_404
from django.core.paginator import Paginator
from django.db.models import Count, Q, F, Sum, Value, Case, When, IntegerField
from django.db.models.functions import Coalesce
from .models import Product, Category, Brand
from .filters import ProductFilter, MULTI_SPLIT_BLOCK_Q, NON_RETAIL_Q
from .facets import compute_facets
from .btu import extract_btu, resolve_btu
from apps.leads.quiz_logic import _balance_by_source


def home(request):
    # Бренд-тикер на главной: топ-8 по числу активных AC-товаров в Крыму.
    # Без алфавитной выборки [:8] — она цепляла мусорные бренды («Al», «AKAI»
    # и т.п.) и не пускала туда Daichi/Hisense. Также exclude:
    # - title 1-2 символа (мусор в БД)
    # - ALFACOOL (правило владельца 28 мая)
    brands = (
        Brand.objects
        .annotate(n=Count('products', filter=Q(
            products__is_active=True,
            products__category__sync_enabled=True,
            products__stock__warehouse='Симферополь',
            products__stock__quantity__gt=0,
        )))
        .filter(n__gt=0)
        .exclude(title__iregex=r'^.{1,2}$')
        .exclude(title__iexact='ALFACOOL')
        .order_by('-n', 'title')[:8]
    )
    # Only show AC categories that have products
    categories = (
        Category.objects
        .filter(sync_enabled=True)
        .annotate(product_count=Count('products', filter=Q(products__is_active=True)))
        .filter(product_count__gt=0)
        .order_by('-product_count')[:8]
    )
    # Featured: 8 моделей, сбалансированных по поставщикам. Чтобы у Daichi
    # был шанс попасть в выдачу (у него запасы низкие, при общем order_by
    # stock он уходит в хвост), собираем буфер ОТ КАЖДОГО источника отдельно
    # — топ-15 по запасу и цене, — затем round-robin распределяем.
    # Только сплит-системы — без аксессуаров, осушителей, мобильных и пр.
    # ТОЛЬКО товары, физически лежащие на крымском складе (Симферополь) —
    # главная не должна продавать «под заказ из Москвы», правило владельца.
    # Brand ALFACOOL — exclude по решению владельца (2026-05-28): в каталоге
    # видны, на главной не нужны.
    base_qs = (
        Product.objects
        .filter(is_active=True, category__sync_enabled=True,
                stock__warehouse='Симферополь', stock__quantity__gt=0)
        .filter(category__title__iregex=r'сплит.?систем')
        .exclude(MULTI_SPLIT_BLOCK_Q)
        .exclude(NON_RETAIL_Q)
        .exclude(brand__title__iexact='ALFACOOL')
        .select_related('brand', 'stock')
        .prefetch_related('images', 'tech_values__spec')
        .order_by(F('stock__quantity').desc(nulls_last=True), 'ric')
    )
    featured_buffer = []
    for src in ('breeze', 'rusklimat', 'daichi'):
        featured_buffer.extend(list(base_qs.filter(source=src)[:15]))
    featured = _balance_by_source(featured_buffer, per_source=3, total=8)
    show_price = request.user.is_authenticated and getattr(request.user, 'is_approved', False)
    return render(request, 'home.html', {
        'brands': brands,
        'categories': categories,
        'featured': featured,
        'show_price': show_price,
    })


def catalog(request):
    # Stock.warehouse='Симферополь' выставляется в write_warehouse_stocks
    # ТОЛЬКО когда qty в Крыму > 0. Если в Крыму 0 — там warehouse=крупнейший
    # из Шерризон/Ростов/Краснодар (fallback «под заказ»). Поэтому первый
    # ключ — наличие Крыма, а не сам Stock.quantity.
    base_qs = (
        Product.objects.filter(is_active=True, category__sync_enabled=True)
        .exclude(MULTI_SPLIT_BLOCK_Q)
        .exclude(NON_RETAIL_Q)
        .annotate(
            is_crimea=Case(
                When(stock__warehouse='Симферополь', then=Value(1)),
                default=Value(0),
                output_field=IntegerField(),
            )
        )
        .select_related('brand', 'category', 'stock')
        .prefetch_related('images', 'tech_values__spec')
    )

    # Правило владельца (2026-05-24): по умолчанию каталог показывает только
    # то, что фактически лежит на крымском складе. Юзер может явно расширить
    # выдачу до «под заказ» через `?with_order=1`. Бэкап URL для фильтров,
    # категорий, поиска — без специальных условий, всё работает поверх
    # сокращённого base_qs.
    if not request.GET.get('with_order'):
        base_qs = base_qs.filter(stock__warehouse='Симферополь',
                                 stock__quantity__gt=0)

    f = ProductFilter(request.GET, queryset=base_qs)

    ordering_key = request.GET.get('ordering', '')
    # Сортировка по ric (РРЦ — цена, которую видит покупатель), не по
    # price_wholesale: на B2C-сайте оптовая цена скрыта, а ric может
    # отличаться (например у Rusklimat ric выше pw из-за маржи).
    ordering_map = {
        'price': F('ric').asc(nulls_last=True),
        '-price': F('ric').desc(nulls_last=True),
        '-created': F('created_at').desc(),
        'title': F('title').asc(),
    }
    if ordering_key in ordering_map:
        ordered_qs = f.qs.order_by(ordering_map[ordering_key])
    else:
        # 1) товары в Крыму (Stock.warehouse='Симферополь') первыми
        # 2) среди них — по qty в Крыму, далее под заказ — по сумме fallback
        # 3) title как тайбрейкер
        ordered_qs = f.qs.order_by(
            F('is_crimea').desc(),
            F('stock__quantity').desc(nulls_last=True),
            'title',
        )

    paginator = Paginator(ordered_qs, 16)
    page = paginator.get_page(request.GET.get('page'))

    categories = (
        Category.objects
        .filter(sync_enabled=True)
        .annotate(product_count=Count('products', filter=Q(products__is_active=True)))
        .filter(product_count__gt=0)
        .order_by('order', 'title')
    )

    facets = compute_facets(request.GET, base_qs)

    context = {
        'filter': f,
        'page_obj': page,
        'categories': categories,
        'show_price': request.user.is_authenticated and request.user.is_approved,
        'current_ordering': ordering_key,
        'facets': facets,
    }

    template = (
        'catalog/partials/_catalog_content.html'
        if request.headers.get('HX-Request') == 'true'
        else 'catalog/index.html'
    )
    return render(request, template, context)


def availability(request):
    """Публичная сводка остатков на крымском (или указанном) складе.

    Клиенты часто звонят узнать «есть ли в Симферополе X». Эта страница
    отвечает без звонка: список всех товаров с qty > 0 на нужном складе.
    По дефолту — Симферополь. Может быть переопределён через `?warehouse=...`.
    """
    from apps.stock.models import WarehouseStock

    warehouse = (request.GET.get('warehouse') or 'Симферополь').strip()
    stocks = (
        WarehouseStock.objects
        .filter(
            warehouse__iexact=warehouse,
            quantity__gt=0,
            product__is_active=True,
            product__category__sync_enabled=True,
        )
        .exclude(product__title__iregex=r'мульти|multi')
        .exclude(product__title__iregex=r'блок\s+(внутренний|наружный)')
        .select_related('product__brand', 'product__category')
        .order_by('-quantity', 'product__title')
    )
    return render(request, 'catalog/availability.html', {
        'warehouse': warehouse,
        'stocks': stocks,
        'total_items': stocks.count(),
        'total_qty': stocks.aggregate(s=Sum('quantity'))['s'] or 0,
    })


def product_detail(request, slug):
    product = get_object_or_404(
        Product.objects.select_related('brand', 'category', 'stock')
                       .prefetch_related('images', 'tech_values__spec', 'warehouse_stocks'),
        slug=slug, is_active=True
    )
    show_price = request.user.is_authenticated and request.user.is_approved

    # BTU с приоритетом tech_values «Холодопроизводительность (kBTU)» — артикул
    # XIGMA может содержать площадь, а не мощность (TXE27RHA = 27 м², 9 kBTU).
    btu = resolve_btu(product)
    is_inverter = bool(re.search(r'инвертор|inverter', product.title, re.I))

    # Похожие: тот же BTU, та же категория, не мульти-блоки, в наличии — top 4.
    # Сначала пытаемся найти только то, что физически на крымском складе —
    # рекомендуем «здесь и сейчас». Если в Крыму ничего нет — fallback на
    # любые наличия (чтобы блок «Похожие» не был пустым).
    similar_base = (
        Product.objects.filter(is_active=True, category__sync_enabled=True)
        .exclude(pk=product.pk)
        .exclude(MULTI_SPLIT_BLOCK_Q)
        .exclude(NON_RETAIL_Q)
        # SHUFT — это вентиляция (HRV/приточно-вытяжные), не AC. У поставщика
        # они попадают в категорию «Бытовые сплит-системы», но юзеру на
        # карточке кондиционера показывать рекуператор бессмысленно.
        .exclude(brand__title__iexact='SHUFT')
    )
    if btu:
        similar_base = similar_base.filter(btu_calc=btu)
    if product.category_id:
        similar_base = similar_base.filter(category_id=product.category_id)

    similar_crimea = (
        similar_base.filter(stock__warehouse='Симферополь',
                            stock__quantity__gt=0)
                    .select_related('brand', 'stock')
                    .prefetch_related('images', 'tech_values__spec')
                    .order_by(F('stock__quantity').desc(nulls_last=True), 'ric')[:4]
    )
    similar = list(similar_crimea)
    if not similar:
        # Fallback — любые подходящие, чтобы пользователь увидел хоть что-то.
        similar = list(
            similar_base.select_related('brand', 'stock')
                        .prefetch_related('images', 'tech_values__spec')
                        .order_by(F('stock__quantity').desc(nulls_last=True), 'ric')[:4]
        )

    return render(request, 'catalog/product_detail.html', {
        'product': product,
        'show_price': show_price,
        'computed_btu': btu,
        'is_inverter': is_inverter,
        'similar_products': similar,
    })
