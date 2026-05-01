from decimal import Decimal

from django.db import models
from django.conf import settings
from apps.catalog.models import Product


class Cart(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='cart'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Корзина'
        verbose_name_plural = 'Корзины'

    def __str__(self):
        return f"Корзина {self.user}"

    @property
    def total(self):
        return sum(
            (item.subtotal for item in self.items.select_related('product', 'cart__user')),
            Decimal('0')
        )

    @property
    def count(self):
        result = self.items.aggregate(total=models.Sum('quantity'))
        return result['total'] or 0


class CartItem(models.Model):
    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1)

    class Meta:
        unique_together = ('cart', 'product')
        verbose_name = 'Позиция корзины'
        verbose_name_plural = 'Позиции корзины'

    def __str__(self):
        return f"{self.product.articul or self.product.nc_code} x{self.quantity}"

    @property
    def subtotal(self):
        price = self.cart.user.get_wholesale_price(self.product.price_wholesale)
        return (price if price is not None else Decimal('0')) * self.quantity


class Order(models.Model):
    STATUS_NEW = 'new'
    STATUS_CONFIRMED = 'confirmed'
    STATUS_IN_PROGRESS = 'in_progress'
    STATUS_SHIPPED = 'shipped'
    STATUS_DELIVERED = 'delivered'
    STATUS_CANCELLED = 'cancelled'

    STATUS_CHOICES = [
        (STATUS_NEW, 'Новый'),
        (STATUS_CONFIRMED, 'Подтверждён'),
        (STATUS_IN_PROGRESS, 'В обработке'),
        (STATUS_SHIPPED, 'Отправлен'),
        (STATUS_DELIVERED, 'Доставлен'),
        (STATUS_CANCELLED, 'Отменён'),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='orders'
    )
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default=STATUS_NEW
    )
    delivery_address = models.TextField('Адрес доставки')
    comment = models.TextField('Комментарий', blank=True)
    total = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    manager_note = models.TextField('Заметка менеджера', blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Заказ'
        verbose_name_plural = 'Заказы'

    def __str__(self):
        return f"Заказ #{self.pk} — {self.user}"


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.PROTECT)
    quantity = models.PositiveIntegerField()
    price_at_order = models.DecimalField(max_digits=12, decimal_places=2)
    ric_at_order = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True
    )

    class Meta:
        verbose_name = 'Позиция заказа'
        verbose_name_plural = 'Позиции заказа'

    def __str__(self):
        identifier = self.product.articul or self.product.nc_code
        return f"{identifier} x{self.quantity}"

    @property
    def subtotal(self):
        return self.price_at_order * self.quantity
