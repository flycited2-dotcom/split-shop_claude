import django_filters
from django import forms
from .models import Product, Brand, Category

_select_cls = 'w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-orange-400'
_input_cls = 'w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-orange-400'


class ProductFilter(django_filters.FilterSet):
    brand = django_filters.ModelChoiceFilter(
        queryset=Brand.objects.all().order_by('title'),
        label='Бренд',
        empty_label='Все бренды',
        widget=forms.Select(attrs={'class': _select_cls}),
    )
    category = django_filters.ModelChoiceFilter(
        queryset=Category.objects.filter(sync_enabled=True).order_by('title'),
        label='Категория',
        empty_label='Все категории',
        widget=forms.Select(attrs={'class': _select_cls}),
    )
    in_stock = django_filters.BooleanFilter(
        method='filter_in_stock',
        label='Только в наличии',
        widget=forms.CheckboxInput(attrs={'class': 'w-4 h-4 accent-orange-500'}),
    )
    q = django_filters.CharFilter(
        field_name='title', lookup_expr='icontains', label='Поиск',
        widget=forms.TextInput(attrs={'class': _input_cls, 'placeholder': 'Название товара...'}),
    )

    class Meta:
        model = Product
        fields = ['brand', 'category', 'in_stock', 'q']

    def filter_in_stock(self, queryset, name, value):
        if value:
            return queryset.filter(stock__quantity__gt=0)
        return queryset
