import django_filters
from django import forms
from .models import Product, Brand, Category

_select_cls = 'w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-orange-400'
_input_cls = 'w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-orange-400'
_price_cls = 'w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-orange-400'


class ProductFilter(django_filters.FilterSet):
    q = django_filters.CharFilter(
        field_name='title', lookup_expr='icontains', label='Поиск',
        widget=forms.TextInput(attrs={'class': _input_cls, 'placeholder': 'Модель, артикул...'}),
    )
    brand = django_filters.ModelChoiceFilter(
        queryset=Brand.objects.all().order_by('title'),
        label='Бренд',
        empty_label='Все бренды',
        widget=forms.Select(attrs={'class': _select_cls}),
    )
    category = django_filters.ModelChoiceFilter(
        queryset=Category.objects.filter(sync_enabled=True).order_by('title'),
        label='Категория',
        empty_label='Все типы',
        widget=forms.Select(attrs={'class': _select_cls}),
    )
    price_min = django_filters.NumberFilter(
        field_name='price_wholesale', lookup_expr='gte', label='Цена от',
        widget=forms.NumberInput(attrs={'class': _price_cls, 'placeholder': 'от ₽'}),
    )
    price_max = django_filters.NumberFilter(
        field_name='price_wholesale', lookup_expr='lte', label='Цена до',
        widget=forms.NumberInput(attrs={'class': _price_cls, 'placeholder': 'до ₽'}),
    )
    in_stock = django_filters.BooleanFilter(
        method='filter_in_stock',
        label='Только в наличии',
        widget=forms.CheckboxInput(attrs={'class': 'w-4 h-4 accent-orange-500'}),
    )

    class Meta:
        model = Product
        fields = ['q', 'brand', 'category', 'price_min', 'price_max', 'in_stock']

    def filter_in_stock(self, queryset, name, value):
        if value:
            return queryset.filter(stock__quantity__gt=0)
        return queryset
