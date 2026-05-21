"""View-тесты личного кабинета физлица и юрлица."""
from decimal import Decimal

from django.test import TestCase, Client
from django.urls import reverse

from apps.accounts.models import CustomUser


class DashboardIndividualTest(TestCase):

    def setUp(self):
        self.client = Client()
        self.user = CustomUser.objects.create_user(
            username='ivan@example.com',
            email='ivan@example.com',
            password='SuperSecret123!',
            account_type='individual',
            is_approved=True,
            phone='+79780000000',
            messenger='@ivan_tg',
            discount_percent=Decimal('15'),
        )

    def test_unauthenticated_redirects_to_login(self):
        r = self.client.get(reverse('account_dashboard'))
        # login_required → редирект.
        self.assertEqual(r.status_code, 302)

    def test_individual_sees_email_and_phone(self):
        self.client.force_login(self.user)
        r = self.client.get(reverse('account_dashboard'))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'ivan@example.com')
        self.assertContains(r, '+79780000000')

    def test_individual_sees_discount(self):
        self.client.force_login(self.user)
        r = self.client.get(reverse('account_dashboard'))
        self.assertContains(r, '15%')
        self.assertContains(r, 'Применяется автоматически')

    def test_individual_does_not_see_price_export_buttons(self):
        # Экспорт прайса — только для юрлиц (оптовая работа).
        self.client.force_login(self.user)
        r = self.client.get(reverse('account_dashboard'))
        self.assertNotContains(r, 'Скачать прайс Excel')
        self.assertNotContains(r, 'Скачать прайс PDF')

    def test_individual_zero_discount_shows_inactive(self):
        self.user.discount_percent = Decimal('0')
        self.user.save()
        self.client.force_login(self.user)
        r = self.client.get(reverse('account_dashboard'))
        self.assertContains(r, 'Не активна')


class DashboardCompanyTest(TestCase):

    def setUp(self):
        self.client = Client()
        self.user = CustomUser.objects.create_user(
            username='company@example.com',
            email='company@example.com',
            password='SuperSecret123!',
            account_type='company',
            is_approved=True,  # симулируем уже-одобренное юрлицо
            company_name='ООО Тест',
            inn='7707083893',
            discount_percent=Decimal('10'),
        )

    def test_company_sees_inn_and_name(self):
        self.client.force_login(self.user)
        r = self.client.get(reverse('account_dashboard'))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'ООО Тест')
        self.assertContains(r, '7707083893')

    def test_company_sees_price_export(self):
        self.client.force_login(self.user)
        r = self.client.get(reverse('account_dashboard'))
        self.assertContains(r, 'Скачать прайс Excel')
        self.assertContains(r, 'Скачать прайс PDF')


class DashboardPendingTest(TestCase):

    def test_pending_user_redirects(self):
        # Юрлицо до одобрения → /pending/.
        user = CustomUser.objects.create_user(
            username='pending@example.com',
            email='pending@example.com',
            password='SuperSecret123!',
            account_type='company',
            is_approved=False,
        )
        self.client.force_login(user)
        r = self.client.get(reverse('account_dashboard'))
        self.assertRedirects(r, reverse('pending'), fetch_redirect_response=False)
