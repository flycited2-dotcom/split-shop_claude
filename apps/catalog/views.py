from django.shortcuts import render, get_object_or_404
from django.core.paginator import Paginator
from django.db.models import Count, Q, F
from .models import Product, Category, Brand
from .filters import ProductFilter


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
    # Featured: only AC products in stock, sorted by stock quantity
    featured = (
        Product.objects
        .filter(is_active=True, category__sync_enabled=True, stock__quantity__gt=0)
        .select_related('brand', 'stock')
        .prefetch_related('images')
        .order_by(F('stock__quantity').desc(nulls_last=True))[:8]
    )
    show_price = request.user.is_authenticated and getattr(request.user, 'is_approved', False)
    return render(request, 'home.html', {
        'brands': brands,
        'categories': categories,
        'featured': featured,
        'show_price': show_price,
    })


def catalog(request):
    qs = Product.objects.filter(
        is_active=True, category__sync_enabled=True
    ).select_related('brand', 'category', 'stock').prefetch_related('images')
    f = ProductFilter(request.GET, queryset=qs)
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
        # Default: in-stock first, then by title
        ordered_qs = f.qs.order_by(F('stock__quantity').desc(nulls_last=True), 'title')
    paginator = Paginator(ordered_qs, 24)
    page = paginator.get_page(request.GET.get('page'))
    # Only show categories that actually have active products
    categories = (
        Category.objects
        .filter(sync_enabled=True)
        .annotate(product_count=Count('products', filter=Q(products__is_active=True)))
        .filter(product_count__gt=0)
        .order_by('-product_count')
    )
    show_price = request.user.is_authenticated and request.user.is_approved
    btu_options = [
        ('7', '7 000 BTU (до 20 м²)'),
        ('9', '9 000 BTU (до 25 м²)'),
        ('12', '12 000 BTU (до 35 м²)'),
        ('18', '18 000 BTU (до 50 м²)'),
        ('24', '24 000 BTU (до 70 м²)'),
    ]
    return render(request, 'catalog/index.html', {
        'filter': f,
        'page_obj': page,
        'categories': categories,
        'show_price': show_price,
        'current_ordering': ordering_key,
        'btu_options': btu_options,
    })


def product_detail(request, slug):
    product = get_object_or_404(
        Product.objects.select_related('brand', 'category', 'stock')
                       .prefetch_related('images', 'tech_values__spec'),
        slug=slug, is_active=True
    )
    show_price = request.user.is_authenticated and request.user.is_approved
    return render(request, 'catalog/product_detail.html', {
        'product': product,
        'show_price': show_price,
    })


def brands_list(request):
    brands = Brand.objects.all()
    return render(request, 'catalog/brands.html', {'brands': brands})
