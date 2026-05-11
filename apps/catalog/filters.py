import django_filters
from django import forms
from django.db.models import Q
from .models import Product, Brand, Category

_select_cls = 'w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-orange-400'
_input_cls = 'w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-orange-400'

# BTU code → 2-digit article code
_BTU_CODES = {'7': '07', '9': '09', '12': '12', '18': '18', '24': '24'}


class ProductFilter(django_filters.FilterSet):
    q = django_filters.CharFilter(
        method='filter_search', label='Поиск',
        widget=forms.TextInput(attrs={'class': _input_cls, 'placeholder': 'Модель, артикул...'}),
    )
    brand = django_filters.ModelChoiceFilter(
        queryset=Brand.objects.all().order_by('title'),
        label='Бренд', empty_label='Все бренды',
        widget=forms.Select(attrs={'class': _select_cls}),
    )
    category = django_filters.ModelChoiceFilter(
        queryset=Category.objects.filter(sync_enabled=True).order_by('title'),
        label='Тип', empty_label='Все типы',
        widget=forms.Select(attrs={'class': _select_cls}),
    )
    price_min = django_filters.NumberFilter(
        field_name='price_wholesale', lookup_expr='gte', label='Цена от',
        widget=forms.NumberInput(attrs={'class': _input_cls, 'placeholder': 'от ₽'}),
    )
    price_max = django_filters.NumberFilter(
        field_name='price_wholesale', lookup_expr='lte', label='Цена до',
        widget=forms.NumberInput(attrs={'class': _input_cls, 'placeholder': 'до ₽'}),
    )
    in_stock = django_filters.BooleanFilter(
        method='filter_in_stock', label='Только в наличии',
        widget=forms.CheckboxInput(attrs={'class': 'w-4 h-4 accent-orange-500'}),
    )
    # BTU quick filter: values 7 / 9 / 12 / 18 / 24
    btu = django_filters.CharFilter(method='filter_btu', label='Мощность BTU')
    # Inverter: 'yes' = inverter only, 'no' = non-inverter only
    inverter = django_filters.ChoiceFilter(
        choices=[('', 'Все'), ('yes', 'Инверторные'), ('no', 'Неинверторные')],
        method='filter_inverter', label='Тип управления',
        empty_label=None,
        widget=forms.Select(attrs={'class': _select_cls}),
    )
    # Black color
    black = django_filters.BooleanFilter(
        method='filter_black', label='Чёрный цвет',
        widget=forms.CheckboxInput(attrs={'class': 'w-4 h-4 accent-orange-500'}),
    )

    class Meta:
        model = Product
        fields = ['q', 'brand', 'category', 'price_min', 'price_max',
                  'in_stock', 'btu', 'inverter', 'black']

    def filter_search(self, queryset, name, value):
        return queryset.filter(Q(title__icontains=value) | Q(articul__icontains=value))

    def filter_in_stock(self, queryset, name, value):
        if value:
            return queryset.filter(stock__quantity__gt=0)
        return queryset

    def filter_btu(self, queryset, name, value):
        code = _BTU_CODES.get(str(value))
        if not code:
            return queryset
        # Match code as standalone 2-digit token in articul (e.g. "-07", "/07", "07H")
        return queryset.filter(
            Q(articul__iregex=rf'(^|[^0-9]){code}([^0-9]|$)')
        )

    def filter_inverter(self, queryset, name, value):
        inv_q = Q(title__icontains='инвертор') | Q(title__icontains='inverter')
        if value == 'yes':
            return queryset.filter(inv_q)
        if value == 'no':
            return queryset.exclude(inv_q)
        return queryset

    def filter_black(self, queryset, name, value):
        if value:
            return queryset.filter(Q(title__icontains='черн') | Q(title__icontains='black'))
        return queryset
