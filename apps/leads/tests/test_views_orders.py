"""View-тесты для quick_order_submit (smoke).

Мокируем send_telegram — чтобы тесты не дёргали внешний API. Проверяем
что заявка создаётся в БД и уведомление отправляется.
"""
from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase, Client
from django.urls import reverse

from apps.catalog.models import Brand, Category, Product
from apps.leads.models import QuickOrder


class QuickOrderSubmitTest(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.category = Category.objects.create(
            title='Сплит', slug='split', sync_enabled=True,
        )
        cls.brand = Brand.objects.create(title='B', slug='b')
        cls.product = Product.objects.create(
            nc_code='NC-1', articul='NC-1',
            category=cls.category, brand=cls.brand,
            title='Test AC',
        )

    def setUp(self):
        self.client = Client()

    def test_success_creates_order_and_sends_telegram(self):
        with patch('apps.leads.views.enqueue_manager_notifications') as m:
            r = self.client.post(reverse('quick_order_submit'), {
                'name': 'Иван',
                'phone': '+79780000000',
                'product_id': str(self.product.pk),
                'comment': 'Привезите завтра',
            })
        self.assertEqual(r.status_code, 200)
        m.assert_called_once()
        order = QuickOrder.objects.get()
        self.assertEqual(order.name, 'Иван')
        self.assertEqual(order.product, self.product)
        self.assertEqual(order.comment, 'Привезите завтра')

    def test_telegram_dynamic_values_are_html_escaped(self):
        self.product.title = 'AC <Pro> & Home'
        self.product.articul = 'A&B'
        self.product.save(update_fields=['title', 'articul'])
        with patch('apps.leads.views.enqueue_manager_notifications') as enqueue:
            self.client.post(reverse('quick_order_submit'), {
                'name': 'Иван <И>',
                'phone': '+7 & 900',
                'product_id': str(self.product.pk),
                'comment': 'Дом < 50 & офис',
            })

        text = enqueue.call_args.kwargs['telegram_text']
        self.assertIn('Иван &lt;И&gt;', text)
        self.assertIn('A&amp;B', text)
        self.assertIn('AC &lt;Pro&gt; &amp; Home', text)
        self.assertIn('Дом &lt; 50 &amp; офис', text)

    def test_success_without_product(self):
        with patch('apps.leads.views.enqueue_manager_notifications') as m:
            r = self.client.post(reverse('quick_order_submit'), {
                'name': 'Иван',
                'phone': '+79780000000',
            })
        self.assertEqual(r.status_code, 200)
        m.assert_called_once()
        order = QuickOrder.objects.get()
        self.assertIsNone(order.product)

    def test_invalid_form_no_order_created(self):
        with patch('apps.leads.views.enqueue_manager_notifications') as m:
            r = self.client.post(reverse('quick_order_submit'), {
                # Без name и phone — form invalid.
                'comment': 'test',
            })
        # View рендерит форму обратно (200), но Order не создан.
        self.assertEqual(r.status_code, 200)
        self.assertFalse(QuickOrder.objects.exists())
        m.assert_not_called()

    def test_invalid_product_id_ignored(self):
        # Несуществующий product_id не ломает создание заявки.
        with patch('apps.leads.views.enqueue_manager_notifications'):
            r = self.client.post(reverse('quick_order_submit'), {
                'name': 'Иван',
                'phone': '+79780000000',
                'product_id': 'not-a-number',
            })
        self.assertEqual(r.status_code, 200)
        order = QuickOrder.objects.get()
        self.assertIsNone(order.product)

    def test_get_not_allowed(self):
        # Декоратор @require_POST.
        r = self.client.get(reverse('quick_order_submit'))
        self.assertEqual(r.status_code, 405)
