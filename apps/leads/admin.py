from django.contrib import admin
from .models import QuickOrder, SelectionRequest, InstallationRequest


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
