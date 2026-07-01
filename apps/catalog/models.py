from django.db import models
from django.utils.text import slugify


class Category(models.Model):
    breez_id = models.IntegerField(unique=True, null=True, blank=True)
    title = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255, unique=True)
    parent = models.ForeignKey('self', null=True, blank=True,
                               on_delete=models.SET_NULL, related_name='children')
    order = models.PositiveIntegerField(default=0)
    sync_enabled = models.BooleanField(
        default=False,
        verbose_name='Синхронизировать',
        help_text='Импортировать товары этой категории из Breeze',
    )

    class Meta:
        ordering = ['order', 'title']
        verbose_name = 'Категория'
        verbose_name_plural = 'Категории'

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(self.title, allow_unicode=True) or f"cat-{self.breez_id}"
            self.slug = f"{base}-{self.breez_id}" if Category.objects.filter(slug=base).exists() else base
        super().save(*args, **kwargs)


class Brand(models.Model):
    breez_id = models.IntegerField(unique=True, null=True, blank=True)
    title = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255, unique=True)
    logo_url = models.URLField(max_length=500, blank=True)
    site_url = models.URLField(max_length=500, blank=True)
    order = models.PositiveIntegerField(default=0)
    featured_in_quiz = models.BooleanField(
        'Показывать в квизе',
        default=False,
        help_text='Выводить бренд на шаге выбора бренда в квиз-подборщике',
    )

    class Meta:
        ordering = ['order', 'title']
        verbose_name = 'Бренд'
        verbose_name_plural = 'Бренды'

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(self.title, allow_unicode=True) or f"brand-{self.breez_id}"
            self.slug = f"{base}-{self.breez_id}" if Brand.objects.filter(slug=base).exists() else base
        super().save(*args, **kwargs)


class Product(models.Model):
    KIND_SPLIT_SYSTEM = 'split_system'
    KIND_ACCESSORY = 'accessory'
    KIND_MULTI_SPLIT_BLOCK = 'multi_split_block'
    KIND_CHOICES = [
        (KIND_SPLIT_SYSTEM, 'Сплит-система'),
        (KIND_ACCESSORY, 'Аксессуар / не для розницы'),
        (KIND_MULTI_SPLIT_BLOCK, 'Компонент мульти-сплит'),
    ]

    nc_code = models.CharField(max_length=50, unique=True)
    articul = models.CharField(max_length=200, blank=True)
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
    booklet_url = models.URLField(max_length=500, blank=True)
    manual_url = models.URLField(max_length=500, blank=True)
    video_youtube = models.URLField(max_length=500, blank=True)
    video_rutube = models.URLField(max_length=500, blank=True)
    rusklimat_guid = models.CharField(max_length=36, blank=True, db_index=True)
    source = models.CharField(max_length=20, default='breeze', db_index=True)
    btu_calc = models.IntegerField(null=True, blank=True, db_index=True,
                                   help_text='kBTU — пересчитывается командой compute_btu '
                                             'из tech_values (мощность охлаждения + площадь).')
    kind = models.CharField(
        max_length=20, choices=KIND_CHOICES, default=KIND_SPLIT_SYSTEM, db_index=True,
        help_text='Считается один раз при синке по title через '
                  'apps.catalog.classify.classify_title — вместо regex-фильтра '
                  '(NON_RETAIL_Q/MULTI_SPLIT_BLOCK_Q), пересчитываемого на каждый '
                  'catalog-запрос.',
    )
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
            brand_part = slugify(self.brand.title, allow_unicode=True) if self.brand else ''
            if brand_part and self.articul:
                base = f"{brand_part}-{self.articul}-{self.nc_code}"
            else:
                base = f"{slugify(self.title, allow_unicode=True)}-{self.nc_code}"
            self.slug = base[:500] or f"product-{self.nc_code}"
        super().save(*args, **kwargs)


class ProductImage(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE,
                                related_name='images')
    url = models.URLField()
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['order']
        verbose_name = 'Изображение'
        verbose_name_plural = 'Изображения'

    def __str__(self):
        return f"Фото {self.product.title} #{self.order}"


class TechSpec(models.Model):
    breez_id = models.IntegerField(unique=True, null=True, blank=True)
    external_uuid = models.CharField(
        max_length=64, unique=True, null=True, blank=True, db_index=True,
        verbose_name='Внешний UUID (Rusklimat/Daichi)',
    )
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
        verbose_name = 'Характеристика товара'
        verbose_name_plural = 'Характеристики товара'

    def __str__(self):
        identifier = self.product.articul or self.product.nc_code
        return f"{identifier} — {self.spec.title}: {self.value}"
