from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('catalog', '0002_alter_brand_logo_url_alter_brand_site_url_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='product',
            name='rusklimat_guid',
            field=models.CharField(blank=True, db_index=True, max_length=36),
        ),
    ]
