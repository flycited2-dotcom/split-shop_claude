from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='customuser',
            name='account_type',
            field=models.CharField(
                choices=[('individual', 'Физическое лицо'), ('company', 'Юридическое лицо')],
                default='individual',
                max_length=20,
                verbose_name='Тип аккаунта',
            ),
        ),
        migrations.AddField(
            model_name='customuser',
            name='messenger',
            field=models.CharField(
                blank=True,
                help_text='Telegram или Max — для связи',
                max_length=100,
                verbose_name='Мессенджер',
            ),
        ),
    ]
