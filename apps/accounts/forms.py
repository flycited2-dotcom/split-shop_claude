from django import forms
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
        if commit:
            user.save()
        return user


class CompanyRegistrationForm(_BaseRegForm):
    """Регистрация юрлица — для получения оптового прайс-листа.
    После регистрации требуется одобрение менеджером."""

    email = forms.EmailField(required=True, label='Email')
    company_name = forms.CharField(max_length=255, label='Название компании')
    inn = forms.CharField(max_length=12, label='ИНН')
    kpp = forms.CharField(max_length=9, required=False, label='КПП')
    legal_address = forms.CharField(
        widget=forms.Textarea(attrs={'rows': 2}), label='Юридический адрес',
    )
    phone = forms.CharField(max_length=20, label='Телефон')
    contact_person = forms.CharField(max_length=255, label='Контактное лицо')

    class Meta:
        model = CustomUser
        fields = (
            'username', 'email', 'password1', 'password2',
            'company_name', 'inn', 'kpp', 'legal_address',
            'phone', 'contact_person',
        )

    def save(self, commit=True):
        user = super().save(commit=False)
        user.account_type = 'company'
        user.is_approved = False  # менеджер проверит ИНН и одобрит
        if commit:
            user.save()
        return user


# Обратная совместимость — пусть импорты `RegistrationForm` не ломаются.
RegistrationForm = CompanyRegistrationForm
