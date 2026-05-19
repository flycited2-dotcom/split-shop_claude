from django.contrib.auth.models import AbstractUser
from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator


class CustomUser(AbstractUser):
    ACCOUNT_TYPE_CHOICES = [
        ('individual', 'Физическое лицо'),
        ('company', 'Юридическое лицо'),
    ]
    account_type = models.CharField(
        'Тип аккаунта', max_length=20, choices=ACCOUNT_TYPE_CHOICES,
        default='individual',
    )
    company_name = models.CharField('Название компании', max_length=255, blank=True)
    inn = models.CharField('ИНН', max_length=12, blank=True)
    kpp = models.CharField('КПП', max_length=9, blank=True)
    legal_address = models.TextField('Юридический адрес', blank=True)
    phone = models.CharField('Телефон', max_length=20, blank=True)
    contact_person = models.CharField('Контактное лицо', max_length=255, blank=True)
    messenger = models.CharField(
        'Мессенджер', max_length=100, blank=True,
        help_text='Telegram или Max — для связи',
    )
    is_approved = models.BooleanField('Одобрен', default=False)
    approved_at = models.DateTimeField(null=True, blank=True)
    approved_by = models.ForeignKey(
        'self', null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='approved_users'
    )
    discount_percent = models.DecimalField(
        'Скидка %', max_digits=5, decimal_places=2, default=0,
        validators=[MinValueValidator(0), MaxValueValidator(100)]
    )

    class Meta:
        verbose_name = 'Пользователь'
        verbose_name_plural = 'Пользователи'

    def __str__(self):
        return f"{self.company_name or self.username} ({self.email})"

    def get_wholesale_price(self, price):
        """Return wholesale price after applying user discount."""
        if price is None:
            return None
        from decimal import Decimal, ROUND_HALF_UP
        price = price if isinstance(price, Decimal) else Decimal(str(price))
        factor = (Decimal('100') - self.discount_percent) / Decimal('100')
        return (price * factor).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
