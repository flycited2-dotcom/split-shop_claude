"""Тесты регистрации физ./юр.лиц с фокусом на инициализацию discount_percent.

Регрессия 2026-05-21: плашка «Скидка до 15% при регистрации» висела по сайту,
но IndividualRegistrationForm.save() не устанавливал discount_percent — поле
оставалось 0, и при оформлении заказа скидка не применялась.
"""
from decimal import Decimal

from django.test import TestCase, override_settings

from apps.accounts.forms import CompanyRegistrationForm, IndividualRegistrationForm
from apps.accounts.models import CustomUser


def _individual_payload(**overrides):
    base = {
        'email': 'ivan@example.com',
        'phone': '+79780000000',
        'messenger': '',
        'password1': 'SuperSecret123!',
        'password2': 'SuperSecret123!',
        'data_consent': True,
    }
    base.update(overrides)
    return base


def _company_payload(**overrides):
    base = {
        'email': 'company@example.com',
        'contact_person': 'Иван Иванов',
        'phone': '+79780000001',
        'company_name': 'ООО Тест',
        'inn': '7707083893',
        'kpp': '',
        'legal_address': 'г. Москва',
        'password1': 'SuperSecret123!',
        'password2': 'SuperSecret123!',
        'data_consent': True,
    }
    base.update(overrides)
    return base


class IndividualRegistrationTest(TestCase):

    def test_form_is_valid(self):
        form = IndividualRegistrationForm(data=_individual_payload())
        self.assertTrue(form.is_valid(), msg=form.errors)

    def test_save_sets_discount_percent_15(self):
        form = IndividualRegistrationForm(data=_individual_payload())
        self.assertTrue(form.is_valid(), msg=form.errors)
        user = form.save()
        # 15 — из DISCOUNT_PERCENT_INDIVIDUAL (default).
        self.assertEqual(user.discount_percent, Decimal('15'))

    @override_settings(DISCOUNT_PERCENT_INDIVIDUAL=20)
    def test_save_respects_settings_override(self):
        form = IndividualRegistrationForm(data=_individual_payload())
        self.assertTrue(form.is_valid(), msg=form.errors)
        user = form.save()
        self.assertEqual(user.discount_percent, Decimal('20'))

    def test_save_marks_account_individual(self):
        form = IndividualRegistrationForm(data=_individual_payload())
        self.assertTrue(form.is_valid())
        user = form.save()
        self.assertEqual(user.account_type, 'individual')
        self.assertTrue(user.is_approved)

    def test_discount_actually_applied_in_get_wholesale_price(self):
        # Конечная цель: get_wholesale_price даёт цену со скидкой.
        form = IndividualRegistrationForm(data=_individual_payload())
        self.assertTrue(form.is_valid())
        user = form.save()
        # 1000 ₽ * (1 - 15/100) = 850 ₽.
        self.assertEqual(user.get_wholesale_price(Decimal('1000')), Decimal('850.00'))

    def test_no_consent_invalid(self):
        form = IndividualRegistrationForm(data=_individual_payload(data_consent=False))
        self.assertFalse(form.is_valid())

    def test_duplicate_email_invalid(self):
        CustomUser.objects.create_user(
            username='existing', email='ivan@example.com', password='x',
        )
        form = IndividualRegistrationForm(data=_individual_payload())
        self.assertFalse(form.is_valid())

    # --- Защита от спам-ботов (2026-06-09) ---

    def test_honeypot_filled_rejected(self):
        # Бот заполнил скрытое поле website → регистрация невалидна.
        form = IndividualRegistrationForm(data=_individual_payload(website='http://spam'))
        self.assertFalse(form.is_valid())
        self.assertIn('website', form.errors)

    def test_foreign_phone_rejected(self):
        # Все боты в волне использовали номера +1 — должны отсекаться.
        form = IndividualRegistrationForm(data=_individual_payload(phone='+1-826-851-7512'))
        self.assertFalse(form.is_valid())
        self.assertIn('phone', form.errors)

    def test_phone_with_leading_8_normalized(self):
        form = IndividualRegistrationForm(data=_individual_payload(phone='8 (978) 000-00-00'))
        self.assertTrue(form.is_valid(), msg=form.errors)
        user = form.save()
        self.assertEqual(user.phone, '+79780000000')


class CompanyRegistrationTest(TestCase):

    def test_save_no_default_discount(self):
        # Юрлицо получает скидку только после approval — менеджер выставляет
        # вручную в admin. По умолчанию discount_percent остаётся 0.
        form = CompanyRegistrationForm(data=_company_payload())
        self.assertTrue(form.is_valid(), msg=form.errors)
        user = form.save()
        self.assertEqual(user.discount_percent, Decimal('0'))
        self.assertEqual(user.account_type, 'company')
        self.assertFalse(user.is_approved)

    def test_invalid_inn_short(self):
        form = CompanyRegistrationForm(data=_company_payload(inn='123'))
        self.assertFalse(form.is_valid())

    def test_invalid_inn_letters(self):
        form = CompanyRegistrationForm(data=_company_payload(inn='abcdefghij'))
        self.assertFalse(form.is_valid())
