from django.shortcuts import render, get_object_or_404
from django.core.paginator import Paginator
from .models import Product, Category, Brand
from .filters import ProductFilter


def home(request):
    brands = Brand.objects.all().order_by('order', 'title')[:16]
    categories = Category.objects.filter(parent=None).prefetch_related('children').order_by('order')
    featured = Product.objects.filter(
        is_active=True, stock__quantity__gt=0
    ).select_related('brand', 'stock').prefetch_related('images')[:8]
    show_price = request.user.is_authenticated and getattr(request.user, 'is_approved', False)
    return render(request, 'home.html', {
        'brands': brands,
        'categories': categories,
        'featured': featured,
        'show_price': show_price,
    })


_ORDERING_MAP = {
    'price': 'price_wholesale',
    '-price': '-price_wholesale',
    '-created': '-created_at',
    'stock': '-stock__quantity',
}


def catalog(request):
    qs = Product.objects.filter(is_active=True).select_related(
        'brand', 'category', 'stock'
    ).prefetch_related('images')
    f = ProductFilter(request.GET, queryset=qs)
    ordering_key = request.GET.get('ordering', '')
    ordered_qs = f.qs.order_by(_ORDERING_MAP.get(ordering_key, 'title'))
    paginator = Paginator(ordered_qs, 24)
    page = paginator.get_page(request.GET.get('page'))
    categories = Category.objects.filter(parent=None).prefetch_related('children')
    show_price = request.user.is_authenticated and request.user.is_approved
    return render(request, 'catalog/index.html', {
        'filter': f,
        'page_obj': page,
        'categories': categories,
        'show_price': show_price,
        'current_ordering': ordering_key,
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
