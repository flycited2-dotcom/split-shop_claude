from django.contrib import admin
from .models import Stock


@admin.register(Stock)
class StockAdmin(admin.ModelAdmin):
    list_display = ['product', 'quantity', 'warehouse', 'price_base', 'updated_at']
    list_filter = ['warehouse']
    search_fields = ['product__title', 'product__articul', 'product__nc_code']
    readonly_fields = ['updated_at']
    list_select_related = True
    list_per_page = 100
