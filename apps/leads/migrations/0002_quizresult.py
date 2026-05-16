from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('leads', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='QuizResult',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('area_sqm', models.PositiveIntegerField(verbose_name='Площадь, м²')),
                ('room_type', models.CharField(
                    choices=[('apartment', 'Квартира'), ('office', 'Офис'), ('shop', 'Магазин/HoReCa')],
                    max_length=20, verbose_name='Тип помещения',
                )),
                ('budget_max', models.PositiveIntegerField(blank=True, null=True, verbose_name='Бюджет до, ₽')),
                ('needs_inverter', models.BooleanField(default=False, verbose_name='Тихий/инвертор')),
                ('needs_heating', models.BooleanField(default=False, verbose_name='Нужен прогрев зимой')),
                ('recommended_btu', models.PositiveSmallIntegerField(blank=True, null=True, verbose_name='Подобранный BTU, тыс.')),
                ('recommended_product_ids', models.JSONField(blank=True, default=list, verbose_name='ID подобранных товаров')),
                ('contact_name', models.CharField(blank=True, max_length=150, verbose_name='Имя')),
                ('contact_phone', models.CharField(blank=True, max_length=30, verbose_name='Телефон')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
            options={
                'verbose_name': 'Прохождение квиза',
                'verbose_name_plural': 'Прохождения квиза',
                'ordering': ['-created_at'],
            },
        ),
    ]
