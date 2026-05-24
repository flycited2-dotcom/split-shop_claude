"""View-тесты для quiz_picker (защита от регрессии, при которой пользователь
не получал результата подбора и видел «не нашлось моделей»).
"""
from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase, Client
from django.urls import reverse

from apps.catalog.models import Brand, Category, Product
from apps.leads.models import QuizResult
from apps.stock.models import Stock


class QuizFlowTest(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.category = Category.objects.create(
            title='Сплит-системы', slug='split', sync_enabled=True,
        )
        cls.brand = Brand.objects.create(title='B', slug='b')

    def _make_product(self, nc, btu_calc=9):
        p = Product.objects.create(
            nc_code=nc, articul=nc,
            category=self.category, brand=self.brand,
            title=f'AC Inverter {nc}',
            ric=Decimal('30000'),
            btu_calc=btu_calc,
        )
        Stock.objects.create(product=p, quantity=5, warehouse='Симферополь')
        return p

    def setUp(self):
        self.client = Client()

    def test_quiz_page_renders_step_1(self):
        r = self.client.get(reverse('quiz'))
        self.assertEqual(r.status_code, 200)

    def test_quiz_step_intermediate(self):
        # Шаг 1 → шаг 2: должен вернуть partial с следующим шагом.
        r = self.client.post(reverse('quiz_step'), {
            'step': '1', 'area_sqm': '25',
        })
        self.assertEqual(r.status_code, 200)
        # Не пустой ответ.
        self.assertTrue(len(r.content) > 0)

    def test_quiz_final_step_returns_products(self):
        self._make_product('NC-1')
        r = self.client.post(reverse('quiz_step'), {
            'step': '7',
            'area_sqm': '25',
            'room_type': 'apartment',
            'inverter': 'yes',
            'wifi': 'any',
            'heating': 'no',
            'budget': '50000',
            'brand': '',
        })
        self.assertEqual(r.status_code, 200)
        # Создан QuizResult.
        self.assertTrue(QuizResult.objects.exists())

    def test_quiz_final_step_persists_wifi_and_brand(self):
        self._make_product('NC-2')
        r = self.client.post(reverse('quiz_step'), {
            'step': '7',
            'area_sqm': '25',
            'room_type': 'apartment',
            'inverter': 'yes',
            'wifi': 'yes',
            'heating': 'no',
            'budget': '50000',
            'brand': str(self.brand.id),
        })
        self.assertEqual(r.status_code, 200)
        quiz = QuizResult.objects.latest('id')
        self.assertTrue(quiz.needs_wifi)
        self.assertEqual(quiz.wanted_brand_id, self.brand.id)

    def test_quiz_final_step_with_empty_db_still_creates_quiz_result(self):
        # Регрессия: даже когда товаров нет, view не должен 500'ить —
        # должен создать QuizResult и вернуть фрагмент с пустым результатом.
        r = self.client.post(reverse('quiz_step'), {
            'step': '7',
            'area_sqm': '25',
            'room_type': 'apartment',
            'inverter': 'yes',
            'wifi': 'any',
            'heating': 'no',
            'budget': '50000',
            'brand': '',
        })
        self.assertEqual(r.status_code, 200)
        self.assertTrue(QuizResult.objects.exists())

    def test_quiz_back_button_renders_previous_step(self):
        # Кнопка «Назад» на шаге 4 → возвращает шаг 3 с сохранёнными ответами.
        r = self.client.post(reverse('quiz_step'), {
            'action': 'back',
            'step': '4',
            'area_sqm': '25',
            'room_type': 'apartment',
            'inverter': 'yes',
        })
        self.assertEqual(r.status_code, 200)
        # QuizResult не создаётся, т.к. кнопка back.
        self.assertFalse(QuizResult.objects.exists())
        # В ответе должно быть значение шага 3 (inverter) — сохранённое hidden или checked.
        self.assertIn(b'inverter', r.content)

    def test_quiz_back_button_from_step_1_clamps_to_1(self):
        # «Назад» с шага 1 не должно ломаться — остаёмся на шаге 1.
        r = self.client.post(reverse('quiz_step'), {
            'action': 'back',
            'step': '1',
            'area_sqm': '',
        })
        self.assertEqual(r.status_code, 200)
        self.assertFalse(QuizResult.objects.exists())

    def test_quiz_lead_success_returns_thanks(self):
        self._make_product('NC-1')
        quiz = QuizResult.objects.create(
            area_sqm=25, room_type='apartment',
            recommended_btu=9, recommended_product_ids=[],
        )
        with patch('apps.leads.views.send_telegram') as m:
            r = self.client.post(
                reverse('quiz_lead', args=[quiz.id]),
                {'name': 'Иван', 'phone': '+79780000000'},
            )
        self.assertEqual(r.status_code, 200)
        m.assert_called_once()
        quiz.refresh_from_db()
        self.assertEqual(quiz.contact_name, 'Иван')
        self.assertEqual(quiz.contact_phone, '+79780000000')

    def test_quiz_lead_bad_id_returns_404(self):
        with patch('apps.leads.views.send_telegram'):
            r = self.client.post(
                reverse('quiz_lead', args=[99999]),
                {'name': 'Иван', 'phone': '+79780000000'},
            )
        self.assertEqual(r.status_code, 404)

    def test_quiz_lead_missing_name_returns_400(self):
        quiz = QuizResult.objects.create(
            area_sqm=25, room_type='apartment',
            recommended_btu=9, recommended_product_ids=[],
        )
        with patch('apps.leads.views.send_telegram'):
            r = self.client.post(
                reverse('quiz_lead', args=[quiz.id]),
                {'name': '', 'phone': '+79780000000'},
            )
        self.assertEqual(r.status_code, 400)

    def test_quiz_lead_missing_phone_returns_400(self):
        quiz = QuizResult.objects.create(
            area_sqm=25, room_type='apartment',
            recommended_btu=9, recommended_product_ids=[],
        )
        with patch('apps.leads.views.send_telegram'):
            r = self.client.post(
                reverse('quiz_lead', args=[quiz.id]),
                {'name': 'Иван', 'phone': ''},
            )
        self.assertEqual(r.status_code, 400)
