from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('catalog', '0010_product_btu_calc'),
    ]

    operations = [
        migrations.AddField(
            model_name='brand',
            name='featured_in_quiz',
            field=models.BooleanField(
                default=False,
                help_text='Выводить бренд на шаге выбора бренда в квиз-подборщике',
                verbose_name='Показывать в квизе',
            ),
        ),
    ]
