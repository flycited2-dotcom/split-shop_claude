from django import forms
from django.contrib.auth.forms import UserCreationForm
from .models import CustomUser


class RegistrationForm(UserCreationForm):
    email = forms.EmailField(required=True, label='Email')
    company_name = forms.CharField(max_length=255, label='Название компании')
    inn = forms.CharField(max_length=12, label='ИНН')
    kpp = forms.CharField(max_length=9, required=False, label='КПП')
    legal_address = forms.CharField(widget=forms.Textarea(attrs={'rows': 2}),
                                    label='Юридический адрес')
    phone = forms.CharField(max_length=20, label='Телефон')
    contact_person = forms.CharField(max_length=255, label='Контактное лицо')

    class Meta:
        model = CustomUser
        fields = ('username', 'email', 'password1', 'password2',
                  'company_name', 'inn', 'kpp', 'legal_address',
                  'phone', 'contact_person')
