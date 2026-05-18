from django.db import models
from apps.catalog.models import Product


class Stock(models.Model):
    """Сводный остаток для совместимости с фильтрами/сортировкой каталога.

    `quantity` хранит остаток на «главном» складе (для Крыма — Симферополь;
    если его нет — сумма по всем). Детализация по складам в `WarehouseStock`.
    """
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


class WarehouseStock(models.Model):
    """Остаток по конкретному складу поставщика — для показа клиенту
    «честной» карты доступности («Симферополь 2 / Краснодар 35 / Киржач 200»)."""
    product = models.ForeignKey(Product, on_delete=models.CASCADE,
                                related_name='warehouse_stocks')
    warehouse = models.CharField(max_length=255)
    quantity = models.PositiveIntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('product', 'warehouse')
        ordering = ['-quantity', 'warehouse']
        verbose_name = 'Остаток по складу'
        verbose_name_plural = 'Остатки по складам'

    def __str__(self):
        return f'{self.product.articul or self.product.nc_code} @ {self.warehouse}: {self.quantity}'
