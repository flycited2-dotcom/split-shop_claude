import logging

from django.db.models.signals import post_save
from django.dispatch import receiver
from django.core.mail import send_mail
from django.conf import settings
from apps.notifications.telegram import send_telegram

logger = logging.getLogger(__name__)

SUPPORT_PHONE = '+7 978 579-29-95'

WELCOME_INDIVIDUAL_SUBJECT = 'Добро пожаловать в SplitHome'
WELCOME_INDIVIDUAL_BODY = (
    'Здравствуйте!\n\n'
    'Спасибо за регистрацию на SplitHome.\n\n'
    'Теперь вам доступна скидка до 15% на сплит-системы и оформление '
    'заказа в один клик.\n'
    'Каталог: https://splithome.ru/catalog/\n\n'
    'Если возникнут вопросы — ответьте на это письмо или напишите '
    f'нам в Telegram/WhatsApp по номеру {SUPPORT_PHONE}.\n\n'
    '— Команда SplitHome'
)

PENDING_COMPANY_SUBJECT = 'Заявка на регистрацию получена — SplitHome'
PENDING_COMPANY_BODY = (
    'Здравствуйте, {company_name}!\n\n'
    'Мы получили вашу заявку на регистрацию в качестве дилера. '
    'Менеджер проверит реквизиты и откроет доступ к оптовым ценам '
    'в течение 1 рабочего дня.\n\n'
    'После одобрения вы получите отдельное письмо с подтверждением.\n\n'
    '— Команда SplitHome'
)


@receiver(post_save, sender='accounts.CustomUser')
def notify_on_registration(sender, instance, created, **kwargs):
    if not created:
        return
    _notify_user(instance)
    _notify_manager(instance)


def _notify_user(user):
    if not user.email:
        return
    if user.account_type == 'individual':
        subject = WELCOME_INDIVIDUAL_SUBJECT
        body = WELCOME_INDIVIDUAL_BODY
    else:
        subject = PENDING_COMPANY_SUBJECT
        body = PENDING_COMPANY_BODY.format(
            company_name=user.company_name or user.username
        )
    send_mail(
        subject=subject,
        message=body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[user.email],
        fail_silently=True,
    )


def _notify_manager(user):
    manager_email = getattr(settings, 'MANAGER_EMAIL', '')
    if manager_email:
        send_mail(
            subject=f'Новая регистрация: {user.company_name or user.username}',
            message=(
                f'Компания: {user.company_name}\n'
                f'ИНН: {user.inn}\n'
                f'Email: {user.email}\n'
                f'Телефон: {user.phone}\n\n'
                f'Пользователь ожидает одобрения в Django Admin.'
            ),
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[manager_email],
            fail_silently=True,
        )
    try:
        tg_text = (
            f'🔔 Новая регистрация\n'
            f'👤 {user.company_name or user.username}\n'
            f'📞 {user.phone or "—"}\n'
            f'🆔 ИНН: {user.inn or "—"}\n'
            f'✉️ /admin/accounts/customuser/{user.pk}/change/'
        )
        send_telegram(tg_text)
    except Exception as exc:
        logger.warning('Telegram registration notification failed: %s', exc)
