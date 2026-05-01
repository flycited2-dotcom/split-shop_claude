from django.contrib import admin
from .models import Cart, CartItem, Order, OrderItem


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ['product', 'quantity', 'price_at_order', 'ric_at_order']


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ['id', 'user', 'status', 'total', 'created_at']
    list_filter = ['status', 'created_at']
    search_fields = ['user__company_name', 'user__email', 'user__inn']
    readonly_fields = ['user', 'total', 'created_at', 'updated_at']
    inlines = [OrderItemInline]
    list_per_page = 50

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user')


@admin.register(Cart)
class CartAdmin(admin.ModelAdmin):
    list_display = ['user', 'count', 'updated_at']
    readonly_fields = ['created_at', 'updated_at']
    list_select_related = True

    def count(self, obj):
        return obj.count
    count.short_description = 'Товаров'
