import re

from django.shortcuts import render, get_object_or_404
from django.core.paginator import Paginator
from django.db.models import Count, Q, F
from .models import Product, Category, Brand
from .filters import ProductFilter, MULTI_SPLIT_BLOCK_Q
from .facets import compute_facets
from .btu import extract_btu
from apps.leads.quiz_logic import _balance_by_source


def home(request):
    brands = Brand.objects.all().order_by('order', 'title')[:16]
    # Only show AC categories that have products
    categories = (
        Category.objects
        .filter(sync_enabled=True)
        .annotate(product_count=Count('products', filter=Q(products__is_active=True)))
        .filter(product_count__gt=0)
        .order_by('-product_count')[:8]
    )
    # Featured: 8 моделей, сбалансированных по поставщикам (round-robin
    # breeze/rusklimat/daichi). Берём буфер из 40 топ-товаров по запасу
    # и распределяем по 3 от каждого источника (4-й поставщик добавится позже).
    featured_buffer = list(
        Product.objects
        .filter(is_active=True, category__sync_enabled=True, stock__quantity__gt=0)
        .exclude(MULTI_SPLIT_BLOCK_Q)
        .select_related('brand', 'stock')
        .prefetch_related('images')
        .order_by(F('stock__quantity').desc(nulls_last=True))[:40]
    )
    featured = _balance_by_source(featured_buffer, per_source=3, total=8)
    show_price = request.user.is_authenticated and getattr(request.user, 'is_approved', False)
    return render(request, 'home.html', {
        'brands': brands,
        'categories': categories,
        'featured': featured,
        'show_price': show_price,
    })


def catalog(request):
    base_qs = (
        Product.objects.filter(is_active=True, category__sync_enabled=True)
        .exclude(MULTI_SPLIT_BLOCK_Q)
        .select_related('brand', 'category', 'stock')
        .prefetch_related('images')
    )

    f = ProductFilter(request.GET, queryset=base_qs)

    ordering_key = request.GET.get('ordering', '')
    ordering_map = {
        'price': F('price_wholesale').asc(nulls_last=True),
        '-price': F('price_wholesale').desc(nulls_last=True),
        '-created': F('created_at').desc(),
        'title': F('title').asc(),
    }
    if ordering_key in ordering_map:
        ordered_qs = f.qs.order_by(ordering_map[ordering_key])
    else:
        ordered_qs = f.qs.order_by(F('stock__quantity').desc(nulls_last=True), 'title')

    paginator = Paginator(ordered_qs, 24)
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


def product_detail(request, slug):
    product = get_object_or_404(
        Product.objects.select_related('brand', 'category', 'stock')
                       .prefetch_related('images', 'tech_values__spec'),
        slug=slug, is_active=True
    )
    show_price = request.user.is_authenticated and request.user.is_approved

    btu = extract_btu(product.articul)
    is_inverter = bool(re.search(r'инвертор|inverter', product.title, re.I))

    # Похожие: тот же BTU, та же категория, не мульти-блоки, в наличии — top 4.
    similar = (
        Product.objects.filter(is_active=True, category__sync_enabled=True)
        .exclude(pk=product.pk)
        .exclude(MULTI_SPLIT_BLOCK_Q)
    )
    if btu:
        similar = similar.filter(articul__iregex=rf'(^|[^0-9]){btu:02d}([^0-9]|$)')
    if product.category_id:
        similar = similar.filter(category_id=product.category_id)
    similar = (
        similar.select_related('brand', 'stock')
               .prefetch_related('images')
               .order_by(F('stock__quantity').desc(nulls_last=True), 'ric')[:4]
    )

    return render(request, 'catalog/product_detail.html', {
        'product': product,
        'show_price': show_price,
        'computed_btu': btu,
        'is_inverter': is_inverter,
        'similar_products': similar,
    })
