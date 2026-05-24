from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('catalog', '0011_brand_featured_in_quiz'),
        ('leads', '0003_quizresult_needs_black_room_type'),
    ]

    operations = [
        migrations.AddField(
            model_name='quizresult',
            name='needs_wifi',
            field=models.BooleanField(default=False, verbose_name='Wi-Fi управление'),
        ),
        migrations.AddField(
            model_name='quizresult',
            name='wanted_brand',
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='quiz_results',
                to='catalog.brand',
                verbose_name='Предпочитаемый бренд',
            ),
        ),
        migrations.AlterField(
            model_name='quizresult',
            name='needs_black',
            field=models.BooleanField(default=False, verbose_name='Чёрный цвет (legacy)'),
        ),
    ]
