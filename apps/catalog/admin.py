from django.contrib import admin, messages
from django.utils.html import format_html
from .models import Category, Brand, Product, ProductImage, TechSpec, ProductTech


def _run_sync(category_ids):
    from apps.sync.tasks import sync_products
    sync_products.delay(category_ids=list(category_ids))


@admin.action(description='▶ Синхронизировать товары из Breeze (выбранные категории)')
def action_sync_selected(modeladmin, request, queryset):
    ids = list(queryset.values_list('id', flat=True))
    _run_sync(ids)
    messages.success(request, f'Синхронизация запущена для {len(ids)} категорий.')


@admin.action(description='✔ Включить синхронизацию')
def action_enable_sync(modeladmin, request, queryset):
    queryset.update(sync_enabled=True)


@admin.action(description='✖ Выключить синхронизацию')
def action_disable_sync(modeladmin, request, queryset):
    queryset.update(sync_enabled=False)


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ['title', 'parent', 'order', 'sync_badge', 'product_count']
    list_filter = ['sync_enabled', 'parent']
    search_fields = ['title']
    list_editable = ['sync_enabled'] if False else []  # used via actions only
    actions = [action_sync_selected, action_enable_sync, action_disable_sync]
    readonly_fields = ['slug']

    @admin.display(boolean=True, description='Синхр.')
    def sync_badge(self, obj):
        return obj.sync_enabled

    @admin.display(description='Товаров')
    def product_count(self, obj):
        n = obj.products.filter(is_active=True).count()
        return format_html('<b>{}</b>', n) if n else '—'


@admin.register(Brand)
class BrandAdmin(admin.ModelAdmin):
    list_display = ['title', 'featured_in_quiz', 'order', 'logo_url']
    list_editable = ['featured_in_quiz', 'order']
    list_filter = ['featured_in_quiz']
    prepopulated_fields = {'slug': ('title',)}
    search_fields = ['title']


class ProductImageInline(admin.TabularInline):
    model = ProductImage
    extra = 0


class ProductTechInline(admin.TabularInline):
    model = ProductTech
    extra = 0


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ['title', 'articul', 'nc_code', 'brand', 'category',
                    'price_wholesale', 'ric', 'is_active', 'has_rusklimat_guid']
    list_filter = ['brand', 'category', 'is_active']
    search_fields = ['title', 'articul', 'nc_code', 'rusklimat_guid']
    readonly_fields = ['slug', 'nc_code', 'created_at', 'updated_at']
    inlines = [ProductImageInline, ProductTechInline]
    list_per_page = 50

    @admin.display(boolean=True, description='Rusklimat')
    def has_rusklimat_guid(self, obj):
        return bool(obj.rusklimat_guid)


@admin.register(TechSpec)
class TechSpecAdmin(admin.ModelAdmin):
    list_display = ['title', 'unit', 'category', 'is_filter', 'order']
    list_filter = ['category', 'is_filter']
    search_fields = ['title']
