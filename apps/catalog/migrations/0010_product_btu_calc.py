from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('catalog', '0009_techspec_external_uuid'),
    ]

    operations = [
        migrations.AddField(
            model_name='product',
            name='btu_calc',
            field=models.IntegerField(
                blank=True, db_index=True, null=True,
                help_text='kBTU — пересчитывается командой compute_btu '
                          'из tech_values (мощность охлаждения + площадь).',
            ),
        ),
    ]
