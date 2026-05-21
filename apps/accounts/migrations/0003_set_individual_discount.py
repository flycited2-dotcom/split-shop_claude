"""Data migration: установить discount_percent для уже зарегистрированных
физлиц, у которых поле осталось 0. Реализует обещание плашек «Скидка до 15%
при регистрации» для пользователей, зарегистрированных до фикса.

Не трогаем тех, у кого discount_percent уже > 0 — менеджер мог установить
персональную скидку вручную.
"""
from decimal import Decimal

from django.conf import settings
from django.db import migrations


def set_default_discount_for_individuals(apps, schema_editor):
    CustomUser = apps.get_model('accounts', 'CustomUser')
    percent = Decimal(str(getattr(settings, 'DISCOUNT_PERCENT_INDIVIDUAL', 15)))
    CustomUser.objects.filter(
        account_type='individual',
        discount_percent=0,
    ).update(discount_percent=percent)


def noop_reverse(apps, schema_editor):
    # Откат не сбрасывает discount_percent в 0, чтобы не потерять персональные
    # настройки менеджера, накопившиеся после применения миграции.
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0002_account_type_messenger'),
    ]

    operations = [
        migrations.RunPython(set_default_discount_for_individuals, noop_reverse),
    ]
