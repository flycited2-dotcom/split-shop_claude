from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('catalog', '0009_techspec_external_uuid'),
        ('stock', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='WarehouseStock',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('warehouse', models.CharField(max_length=255)),
                ('quantity', models.PositiveIntegerField(default=0)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('product', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='warehouse_stocks',
                    to='catalog.product',
                )),
            ],
            options={
                'verbose_name': 'Остаток по складу',
                'verbose_name_plural': 'Остатки по складам',
                'ordering': ['-quantity', 'warehouse'],
                'unique_together': {('product', 'warehouse')},
            },
        ),
    ]
