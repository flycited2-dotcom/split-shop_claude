from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('catalog', '0008_nullable_techspec_breez_id'),
    ]

    operations = [
        migrations.AddField(
            model_name='techspec',
            name='external_uuid',
            field=models.CharField(
                blank=True, db_index=True, max_length=64, null=True, unique=True,
                verbose_name='Внешний UUID (Rusklimat/Daichi)',
            ),
        ),
    ]
