from django.contrib import admin
from .models import Category, Brand, Product, ProductImage, TechSpec, ProductTech


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ['title', 'parent', 'order']
    prepopulated_fields = {'slug': ('title',)}
    list_filter = ['parent']
    search_fields = ['title']


@admin.register(Brand)
class BrandAdmin(admin.ModelAdmin):
    list_display = ['title', 'order']
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
                    'price_wholesale', 'ric', 'is_active']
    list_filter = ['brand', 'category', 'is_active']
    search_fields = ['title', 'articul', 'nc_code']
    prepopulated_fields = {'slug': ('title',)}
    inlines = [ProductImageInline, ProductTechInline]
    list_per_page = 50


@admin.register(TechSpec)
class TechSpecAdmin(admin.ModelAdmin):
    list_display = ['title', 'unit', 'category', 'is_filter', 'order']
    list_filter = ['category', 'is_filter']
    search_fields = ['title']
