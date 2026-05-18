from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('catalog', '0007_ensure_master_categories'),
    ]

    operations = [
        migrations.AlterField(
            model_name='techspec',
            name='breez_id',
            field=models.IntegerField(blank=True, null=True, unique=True),
        ),
    ]
