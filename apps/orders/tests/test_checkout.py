from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from apps.catalog.models import Product
from apps.orders.models import Cart, CartItem, Order


class CheckoutNotificationTest(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username='buyer', password='secret', is_approved=True,
        )
        self.product = Product.objects.create(
            nc_code='CHECKOUT-1', title='Test product',
            price_wholesale=Decimal('10000'), ric=Decimal('12000'),
        )
        self.cart = Cart.objects.create(user=self.user)
        CartItem.objects.create(cart=self.cart, product=self.product, quantity=2)
        self.client.force_login(self.user)

    @patch('apps.orders.views.enqueue_manager_notifications')
    def test_checkout_persists_and_queues_without_direct_provider_wait(self, enqueue):
        response = self.client.post(reverse('checkout'), {
            'delivery_address': 'Test address',
            'comment': 'Test comment',
        })

        self.assertEqual(response.status_code, 302)
        self.assertEqual(Order.objects.count(), 1)
        self.assertFalse(self.cart.items.exists())
        enqueue.assert_called_once()
        self.assertIn('telegram_text', enqueue.call_args.kwargs)
        self.assertIn('email_body', enqueue.call_args.kwargs)
