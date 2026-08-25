from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('leads', '0004_quizresult_wifi_brand')]

    operations = [
        migrations.CreateModel(
            name='ServiceRequest',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=150, verbose_name='Имя')),
                ('phone', models.CharField(max_length=30, verbose_name='Телефон')),
                ('locality', models.CharField(blank=True, max_length=150, verbose_name='Населённый пункт')),
                ('equipment_type', models.CharField(choices=[('air_conditioner', 'Кондиционер или сплит-система'), ('heat_pump', 'Тепловой насос'), ('ventilation', 'Вентиляция или рекуператор'), ('power', 'Стабилизатор или ИБП'), ('appliance', 'Бытовая техника'), ('other', 'Другое оборудование')], max_length=30, verbose_name='Тип оборудования')),
                ('service_type', models.CharField(choices=[('diagnostics', 'Диагностика'), ('maintenance', 'Профилактика и обслуживание'), ('repair', 'Ремонт'), ('commissioning', 'Пусконаладка и настройка'), ('consultation', 'Консультация специалиста')], max_length=30, verbose_name='Вид обращения')),
                ('equipment_model', models.CharField(blank=True, max_length=200, verbose_name='Марка и модель')),
                ('comment', models.TextField(blank=True, verbose_name='Описание задачи или неисправности')),
                ('preferred_time', models.CharField(blank=True, max_length=100, verbose_name='Удобное время для звонка')),
                ('privacy_accepted', models.BooleanField(default=False, verbose_name='Согласие на обработку данных')),
                ('utm_source', models.CharField(blank=True, max_length=100)),
                ('utm_medium', models.CharField(blank=True, max_length=100)),
                ('utm_campaign', models.CharField(blank=True, max_length=150)),
                ('utm_content', models.CharField(blank=True, max_length=150)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
            options={'verbose_name': 'Заявка на сервис', 'verbose_name_plural': 'Заявки на сервис', 'ordering': ['-created_at']},
        ),
    ]
