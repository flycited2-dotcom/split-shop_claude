from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('catalog', '0004_category_sync_enabled'),
    ]

    operations = [
        migrations.AlterField(
            model_name='brand',
            name='breez_id',
            field=models.IntegerField(blank=True, null=True, unique=True),
        ),
        migrations.AlterField(
            model_name='category',
            name='breez_id',
            field=models.IntegerField(blank=True, null=True, unique=True),
        ),
    ]
