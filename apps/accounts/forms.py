from decimal import Decimal

from django import forms
from django.conf import settings
from django.contrib.auth.forms import UserCreationForm
from django.core.exceptions import ValidationError

from .models import CustomUser


_CONSENT_TEXT = (
    'Согласен на обработку персональных данных согласно '
    'политике конфиденциальности'
)


class _BaseRegForm(UserCreationForm):
    """Общая часть: согласие на обработку ПД (обязательно по 152-ФЗ)."""

    data_consent = forms.BooleanField(
        required=True, label=_CONSENT_TEXT,
        error_messages={'required': 'Без согласия зарегистрировать нельзя'},
    )


class IndividualRegistrationForm(_BaseRegForm):
    """Регистрация физического лица — минимальная (email + phone + опц. мессенджер)."""

    email = forms.EmailField(required=True, label='Email')
    phone = forms.CharField(max_length=20, label='Телефон', required=True)
    messenger = forms.CharField(
        max_length=100, required=False, label='Telegram / Max (опционально)',
        help_text='Если оставите — менеджер свяжется через мессенджер быстрее',
    )

    class Meta:
        model = CustomUser
        fields = ('email', 'password1', 'password2', 'phone', 'messenger')

    def clean_email(self):
        email = self.cleaned_data['email'].lower().strip()
        if CustomUser.objects.filter(email__iexact=email).exists():
            raise ValidationError('Email уже зарегистрирован')
        return email

    def save(self, commit=True):
        user = super().save(commit=False)
        # username = email (физлицу отдельный логин не нужен).
        user.username = self.cleaned_data['email']
        user.email = self.cleaned_data['email']
        user.phone = self.cleaned_data['phone']
        user.messenger = self.cleaned_data.get('messenger', '')
        user.account_type = 'individual'
        # Физлицо не ждёт одобрения — открываем доступ сразу.
        user.is_approved = True
        # Применяем обещанную в плашках «Скидка до 15% при регистрации».
        # CartItem.subtotal → user.get_wholesale_price() автоматически применит
        # этот процент в корзине и в Order.total.
        user.discount_percent = Decimal(str(settings.DISCOUNT_PERCENT_INDIVIDUAL))
        if commit:
            user.save()
        return user


class CompanyRegistrationForm(_BaseRegForm):
    """Регистрация юрлица — для получения оптового прайс-листа.
    После регистрации требуется одобрение менеджером."""

    # Контакт (для связи с лицом, заполняющим)
    email = forms.EmailField(required=True, label='Email компании')
    contact_person = forms.CharField(
        max_length=255, label='Контактное лицо (ФИО)', required=True,
    )
    phone = forms.CharField(max_length=20, label='Телефон контактного лица', required=True)

    # Реквизиты компании
    company_name = forms.CharField(max_length=255, label='Название компании', required=True)
    inn = forms.CharField(
        max_length=12, label='ИНН', required=True,
        help_text='10 или 12 цифр',
    )
    kpp = forms.CharField(
        max_length=9, required=False, label='КПП',
        help_text='Необязательно для ИП',
    )
    legal_address = forms.CharField(
        widget=forms.Textarea(attrs={'rows': 2}),
        label='Юридический адрес', required=True,
    )

    class Meta:
        model = CustomUser
        fields = (
            'email', 'password1', 'password2',
            'contact_person', 'phone',
            'company_name', 'inn', 'kpp', 'legal_address',
        )

    def clean_email(self):
        email = self.cleaned_data['email'].lower().strip()
        if CustomUser.objects.filter(email__iexact=email).exists():
            raise ValidationError('Email уже зарегистрирован')
        return email

    def clean_inn(self):
        inn = (self.cleaned_data['inn'] or '').strip()
        if not inn.isdigit():
            raise ValidationError('ИНН должен содержать только цифры')
        if len(inn) not in (10, 12):
            raise ValidationError('ИНН — 10 цифр (юрлицо) или 12 (ИП)')
        return inn

    def save(self, commit=True):
        user = super().save(commit=False)
        # Логин = email (юрлицу отдельный логин не нужен).
        user.username = self.cleaned_data['email']
        user.email = self.cleaned_data['email']
        user.account_type = 'company'
        user.is_approved = False  # менеджер проверит ИНН и одобрит
        if commit:
            user.save()
        return user


# Обратная совместимость — пусть импорты `RegistrationForm` не ломаются.
RegistrationForm = CompanyRegistrationForm
