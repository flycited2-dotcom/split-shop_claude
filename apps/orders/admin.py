from django.contrib import admin
from .models import Cart, CartItem, Order, OrderItem


class CartItemInline(admin.TabularInline):
    model = CartItem
    extra = 0
    readonly_fields = ['product', 'quantity']


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ['product', 'quantity', 'price_at_order', 'ric_at_order']

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('product')


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ['id', 'user', 'status', 'total', 'created_at']
    list_filter = ['status', 'created_at']
    search_fields = ['user__company_name', 'user__email', 'user__inn']
    readonly_fields = ['user', 'total', 'created_at', 'updated_at']
    inlines = [OrderItemInline]
    list_per_page = 50
    fieldsets = (
        ('Заказ', {'fields': ('user', 'status', 'total', 'created_at', 'updated_at')}),
        ('Доставка', {'fields': ('delivery_address', 'comment')}),
        ('Менеджер', {'fields': ('manager_note',)}),
    )

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user')


@admin.register(Cart)
class CartAdmin(admin.ModelAdmin):
    list_display = ['user', 'item_count', 'updated_at']
    readonly_fields = ['created_at', 'updated_at']
    list_select_related = True
    inlines = [CartItemInline]

    def item_count(self, obj):
        return obj.count
    item_count.short_description = 'Товаров'
