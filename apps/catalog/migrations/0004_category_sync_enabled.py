import re
from django.db import migrations, models


_AC_RE = re.compile(
    r'сплит|split|кондиционер|мультисплит|инвертор|полупромышленн|мобильн|он.офф',
    re.I | re.UNICODE,
)


def enable_ac_categories(apps, schema_editor):
    """Set sync_enabled=True for AC/split-system categories."""
    Category = apps.get_model('catalog', 'Category')
    for cat in Category.objects.select_related('parent'):
        is_ac = bool(_AC_RE.search(cat.title))
        if not is_ac and cat.parent:
            is_ac = bool(_AC_RE.search(cat.parent.title))
        if is_ac:
            cat.sync_enabled = True
            cat.save(update_fields=['sync_enabled'])


class Migration(migrations.Migration):

    dependencies = [
        ('catalog', '0003_product_rusklimat_guid'),
    ]

    operations = [
        migrations.AddField(
            model_name='category',
            name='sync_enabled',
            field=models.BooleanField(
                default=False,
                verbose_name='Синхронизировать',
                help_text='Импортировать товары этой категории из Breeze',
            ),
        ),
        migrations.RunPython(enable_ac_categories, migrations.RunPython.noop),
    ]
