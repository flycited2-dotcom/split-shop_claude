from django.db import models
from django.utils.text import slugify


class Category(models.Model):
    breez_id = models.IntegerField(unique=True)
    title = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255, unique=True)
    parent = models.ForeignKey('self', null=True, blank=True,
                               on_delete=models.SET_NULL, related_name='children')
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['order', 'title']
        verbose_name = 'Категория'
        verbose_name_plural = 'Категории'

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title, allow_unicode=True)
        super().save(*args, **kwargs)


class Brand(models.Model):
    breez_id = models.IntegerField(unique=True)
    title = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255, unique=True)
    logo_url = models.URLField(blank=True)
    site_url = models.URLField(blank=True)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['order', 'title']
        verbose_name = 'Бренд'
        verbose_name_plural = 'Бренды'

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title, allow_unicode=True)
        super().save(*args, **kwargs)


class Product(models.Model):
    nc_code = models.CharField(max_length=50, unique=True)
    articul = models.CharField(max_length=100, blank=True)
    category = models.ForeignKey(Category, null=True, blank=True,
                                 on_delete=models.SET_NULL, related_name='products')
    brand = models.ForeignKey(Brand, null=True, blank=True,
                              on_delete=models.SET_NULL, related_name='products')
    series = models.CharField(max_length=255, blank=True)
    title = models.CharField(max_length=500)
    slug = models.SlugField(max_length=500, unique=True)
    price_wholesale = models.DecimalField(max_digits=12, decimal_places=2,
                                          null=True, blank=True)
    ric = models.DecimalField(max_digits=12, decimal_places=2,
                              null=True, blank=True)
    ric_currency = models.CharField(max_length=10, default='RUB')
    description = models.TextField(blank=True)
    booklet_url = models.URLField(blank=True)
    manual_url = models.URLField(blank=True)
    video_youtube = models.URLField(blank=True)
    video_rutube = models.URLField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['title']
        verbose_name = 'Товар'
        verbose_name_plural = 'Товары'

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        if not self.slug:
            base = f"{self.brand}-{self.articul}" if self.articul else self.title
            self.slug = slugify(base, allow_unicode=True)
        super().save(*args, **kwargs)


class ProductImage(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE,
                                related_name='images')
    url = models.URLField()
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['order']

    def __str__(self):
        return f"Фото {self.product.title} #{self.order}"


class TechSpec(models.Model):
    breez_id = models.IntegerField(unique=True)
    title = models.CharField(max_length=255)
    unit = models.CharField(max_length=50, blank=True)
    data_type = models.CharField(max_length=50, blank=True)
    group = models.CharField(max_length=255, blank=True)
    category = models.ForeignKey(Category, null=True, blank=True,
                                 on_delete=models.SET_NULL, related_name='tech_specs')
    order = models.PositiveIntegerField(default=0)
    is_filter = models.BooleanField(default=False)

    class Meta:
        ordering = ['order']
        verbose_name = 'Характеристика'
        verbose_name_plural = 'Характеристики'

    def __str__(self):
        return self.title


class ProductTech(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE,
                                related_name='tech_values')
    spec = models.ForeignKey(TechSpec, on_delete=models.CASCADE)
    value = models.CharField(max_length=500)

    class Meta:
        unique_together = ('product', 'spec')

    def __str__(self):
        return f"{self.product.articul} — {self.spec.title}: {self.value}"
