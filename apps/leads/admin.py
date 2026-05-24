from django.contrib import admin
from .models import QuickOrder, SelectionRequest, InstallationRequest, QuizResult


@admin.register(QuickOrder)
class QuickOrderAdmin(admin.ModelAdmin):
    list_display = ('name', 'phone', 'product', 'created_at')
    list_filter = ('created_at',)
    search_fields = ('name', 'phone')
    readonly_fields = ('created_at',)


@admin.register(SelectionRequest)
class SelectionRequestAdmin(admin.ModelAdmin):
    list_display = ('name', 'phone', 'city', 'area_sqm', 'needs_installation', 'created_at')
    list_filter = ('needs_installation', 'created_at')
    search_fields = ('name', 'phone', 'city')
    readonly_fields = ('created_at',)


@admin.register(InstallationRequest)
class InstallationRequestAdmin(admin.ModelAdmin):
    list_display = ('name', 'phone', 'address', 'has_equipment', 'created_at')
    list_filter = ('has_equipment', 'needs_channel', 'created_at')
    search_fields = ('name', 'phone', 'address')
    readonly_fields = ('created_at',)


@admin.register(QuizResult)
class QuizResultAdmin(admin.ModelAdmin):
    list_display = ('area_sqm', 'room_type', 'recommended_btu', 'budget_max',
                    'needs_inverter', 'needs_wifi', 'wanted_brand',
                    'contact_phone', 'created_at')
    list_filter = ('room_type', 'needs_inverter', 'needs_wifi', 'needs_heating',
                   'wanted_brand', 'created_at')
    search_fields = ('contact_name', 'contact_phone')
    readonly_fields = ('created_at', 'recommended_product_ids', 'needs_black')
