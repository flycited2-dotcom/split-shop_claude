from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('catalog', '0005_nullable_breez_id'),
    ]

    operations = [
        migrations.AddField(
            model_name='product',
            name='source',
            field=models.CharField(db_index=True, default='breeze', max_length=20),
        ),
    ]
