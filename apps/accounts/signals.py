from django.db.models.signals import post_save
from django.dispatch import receiver
from django.core.mail import send_mail
from django.conf import settings


@receiver(post_save, sender='accounts.CustomUser')
def notify_manager_on_registration(sender, instance, created, **kwargs):
    """Notify manager when a new user registers."""
    if not created:
        return
    manager_email = getattr(settings, 'MANAGER_EMAIL', '')
    if manager_email:
        send_mail(
            subject=f'Новая регистрация: {instance.company_name or instance.username}',
            message=(
                f'Компания: {instance.company_name}\n'
                f'ИНН: {instance.inn}\n'
                f'Email: {instance.email}\n'
                f'Телефон: {instance.phone}\n\n'
                f'Пользователь ожидает одобрения в Django Admin.'
            ),
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[manager_email],
            fail_silently=True,
        )
    from apps.notifications.telegram import send_telegram
    tg_text = (
        f'🔔 <b>Новая регистрация</b>\n'
        f'👤 {instance.company_name or instance.username}\n'
        f'📞 {instance.phone or "—"}\n'
        f'🆔 ИНН: {instance.inn or "—"}\n'
        f'✉️ {instance.email}\n'
        f'🔗 /admin/accounts/customuser/{instance.pk}/change/'
    )
    send_telegram(tg_text)
