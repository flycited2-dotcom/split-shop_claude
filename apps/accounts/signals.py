from django.db.models.signals import post_save
from django.dispatch import receiver
from django.core.mail import send_mail
from django.conf import settings


@receiver(post_save, sender='accounts.CustomUser')
def notify_manager_on_registration(sender, instance, created, **kwargs):
    """Notify manager when a new user registers."""
    if created and getattr(settings, 'MANAGER_EMAIL', ''):
        send_mail(
            subject=f'Новая регистрация: {instance.company_name or instance.username}',
            message=(
                f'Компания: {instance.company_name}\n'
                f'ИНН: {instance.inn}\n'
                f'Email: {instance.email}\n'
                f'Телефон: {instance.phone}\n\n'
                f'Пользователь ожидает одобрения.'
            ),
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[settings.MANAGER_EMAIL],
            fail_silently=True,
        )
