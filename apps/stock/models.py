from django.db import models
from apps.catalog.models import Product


class Stock(models.Model):
    product = models.OneToOneField(Product, on_delete=models.CASCADE,
                                   related_name='stock')
    quantity = models.PositiveIntegerField(default=0)
    warehouse = models.CharField(max_length=255, blank=True)
    price_base = models.DecimalField(max_digits=12, decimal_places=2,
                                     null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Остаток'
        verbose_name_plural = 'Остатки'

    def __str__(self):
        return f"{self.product.articul or self.product.nc_code}: {self.quantity} шт."

    @property
    def in_stock(self):
        return self.quantity > 0
