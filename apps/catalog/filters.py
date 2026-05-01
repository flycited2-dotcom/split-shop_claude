import django_filters
from .models import Product, Brand, Category


class ProductFilter(django_filters.FilterSet):
    brand = django_filters.ModelChoiceFilter(queryset=Brand.objects.all(),
                                             label='Бренд')
    category = django_filters.ModelChoiceFilter(queryset=Category.objects.all(),
                                                label='Категория')
    in_stock = django_filters.BooleanFilter(method='filter_in_stock',
                                            label='Только в наличии')
    q = django_filters.CharFilter(field_name='title', lookup_expr='icontains',
                                  label='Поиск')

    class Meta:
        model = Product
        fields = ['brand', 'category', 'in_stock', 'q']

    def filter_in_stock(self, queryset, name, value):
        if value:
            return queryset.filter(stock__quantity__gt=0)
        return queryset
