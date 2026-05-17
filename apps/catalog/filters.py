import django_filters
from django import forms
from django.db.models import Q

from .models import Product, Brand, Category


_select_cls = 'w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-orange-400'
_input_cls = 'w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-orange-400'


# BTU code (UI key) → 2-digit token expected inside `articul`
_BTU_CODES = {
    '7': '07', '9': '09', '12': '12', '18': '18', '24': '24',
    '27': '27', '30': '30', '36': '36', '42': '42', '48': '48', '60': '60',
}

# Stable order for UI rendering
BTU_VALUES = ['7', '9', '12', '18', '24', '27', '30', '36', '42', '48', '60']

INVERTER_CHOICES = [
    ('inverter', 'Инвертор'),
    ('onoff', 'Он-офф'),
]

COLOR_CHOICES = [
    ('black', 'Чёрный'),
    ('white', 'Белый'),
    ('silver', 'Silver'),
    ('green', 'Green'),
]

# Title substrings used by the color facet. Case-insensitive `icontains`.
_COLOR_NEEDLES = {
    'black':  ['черн', 'black'],
    'white':  ['бел', 'white'],
    'silver': ['silver'],
    'green':  ['green'],
}

# Компоненты мульти-сплит-систем (внутренний/наружный блок) — не самостоятельные
# кондиционеры. Их артикул содержит BTU-код, поэтому без явного исключения
# розничный каталог и квиз засоряются ими (≈40% активных AC). Исключаются из:
# catalog view, home featured, sitemap, quiz_logic.
MULTI_SPLIT_BLOCK_Q = (
    Q(title__iregex=r'мульти|multi')
    | Q(title__iregex=r'блок\s+(внутренний|наружный)')
)


def _btu_q(code_keys):
    """Build an OR-Q over `articul__iregex` for the given BTU UI keys."""
    q = Q()
    for k in code_keys:
        code = _BTU_CODES.get(str(k))
        if code:
            q |= Q(articul__iregex=rf'(^|[^0-9]){code}([^0-9]|$)')
    return q


def _inverter_filter(qs, value):
    """value: iterable of 'inverter' / 'onoff'. Both or none → no filter."""
    if not value:
        return qs
    chosen = set(value)
    if 'inverter' in chosen and 'onoff' in chosen:
        return qs
    inv_q = Q(title__iregex=r'инвертор|inverter')
    if 'inverter' in chosen:
        return qs.filter(inv_q)
    if 'onoff' in chosen:
        return qs.exclude(inv_q)
    return qs


def _color_q(color_keys):
    q = Q()
    for key in color_keys:
        for needle in _COLOR_NEEDLES.get(key, []):
            q |= Q(title__icontains=needle)
    return q


class ProductFilter(django_filters.FilterSet):
    q = django_filters.CharFilter(
        method='filter_search', label='Поиск',
        widget=forms.TextInput(attrs={'class': _input_cls, 'placeholder': 'Модель, артикул...'}),
    )
    brand = django_filters.ModelMultipleChoiceFilter(
        queryset=Brand.objects.all().order_by('title'),
        label='Бренд',
    )
    category = django_filters.ModelChoiceFilter(
        queryset=Category.objects.filter(sync_enabled=True).order_by('order', 'title'),
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
    btu = django_filters.MultipleChoiceFilter(
        choices=[(v, v) for v in BTU_VALUES],
        method='filter_btu', label='Мощность BTU', conjoined=False,
    )
    inverter = django_filters.MultipleChoiceFilter(
        choices=INVERTER_CHOICES,
        method='filter_inverter', label='Тип управления', conjoined=False,
    )
    color = django_filters.MultipleChoiceFilter(
        choices=COLOR_CHOICES,
        method='filter_color', label='Цвет', conjoined=False,
    )

    class Meta:
        model = Product
        fields = ['q', 'brand', 'category', 'price_min', 'price_max',
                  'in_stock', 'btu', 'inverter', 'color']

    def filter_search(self, queryset, name, value):
        return queryset.filter(Q(title__icontains=value) | Q(articul__icontains=value))

    def filter_in_stock(self, queryset, name, value):
        if value:
            return queryset.filter(stock__quantity__gt=0)
        return queryset

    def filter_btu(self, queryset, name, value):
        q = _btu_q(value or [])
        return queryset.filter(q) if q else queryset

    def filter_inverter(self, queryset, name, value):
        return _inverter_filter(queryset, value or [])

    def filter_color(self, queryset, name, value):
        q = _color_q(value or [])
        return queryset.filter(q) if q else queryset
