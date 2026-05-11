import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('catalog', '0006_product_source'),
    ]

    operations = [
        migrations.CreateModel(
            name='QuickOrder',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=150, verbose_name='Имя')),
                ('phone', models.CharField(max_length=30, verbose_name='Телефон')),
                ('comment', models.TextField(blank=True, verbose_name='Комментарий')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('product', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    to='catalog.product',
                    verbose_name='Товар',
                )),
            ],
            options={
                'verbose_name': 'Заказ в 1 клик',
                'verbose_name_plural': 'Заказы в 1 клик',
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='SelectionRequest',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=150, verbose_name='Имя')),
                ('phone', models.CharField(max_length=30, verbose_name='Телефон')),
                ('city', models.CharField(blank=True, max_length=100, verbose_name='Город')),
                ('area_sqm', models.PositiveIntegerField(blank=True, null=True, verbose_name='Площадь, м²')),
                ('room_type', models.CharField(blank=True, max_length=100, verbose_name='Тип помещения')),
                ('budget', models.CharField(blank=True, max_length=100, verbose_name='Бюджет')),
                ('needs_installation', models.BooleanField(default=False, verbose_name='Нужен монтаж')),
                ('timeline', models.CharField(blank=True, max_length=100, verbose_name='Когда планируется покупка')),
                ('comment', models.TextField(blank=True, verbose_name='Комментарий')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
            options={
                'verbose_name': 'Заявка на подбор',
                'verbose_name_plural': 'Заявки на подбор',
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='InstallationRequest',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=150, verbose_name='Имя')),
                ('phone', models.CharField(max_length=30, verbose_name='Телефон')),
                ('address', models.TextField(verbose_name='Адрес объекта')),
                ('equipment_type', models.CharField(blank=True, max_length=150, verbose_name='Тип оборудования')),
                ('has_equipment', models.BooleanField(default=False, verbose_name='Кондиционер уже куплен')),
                ('floor', models.PositiveSmallIntegerField(blank=True, null=True, verbose_name='Этаж')),
                ('wall_type', models.CharField(blank=True, max_length=100, verbose_name='Тип стены')),
                ('needs_channel', models.BooleanField(default=False, verbose_name='Нужна закладка трассы')),
                ('comment', models.TextField(blank=True, verbose_name='Комментарий')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
            options={
                'verbose_name': 'Заявка на монтаж',
                'verbose_name_plural': 'Заявки на монтаж',
                'ordering': ['-created_at'],
            },
        ),
    ]
