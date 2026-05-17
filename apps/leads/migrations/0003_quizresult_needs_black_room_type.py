from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('leads', '0002_quizresult'),
    ]

    operations = [
        migrations.AddField(
            model_name='quizresult',
            name='needs_black',
            field=models.BooleanField(default=False, verbose_name='Чёрный цвет'),
        ),
        migrations.AlterField(
            model_name='quizresult',
            name='room_type',
            field=models.CharField(
                choices=[
                    ('apartment', 'Квартира'),
                    ('house', 'Дом'),
                    ('office', 'Офис'),
                    ('commercial', 'Коммерция'),
                    ('shop', 'Магазин/HoReCa'),
                ],
                max_length=20,
                verbose_name='Тип помещения',
            ),
        ),
    ]
