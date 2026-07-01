from io import StringIO

from django.core.management import call_command
from django.test import TestCase

from apps.catalog.models import Brand, Category, Product


class BackfillProductKindTest(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.category = Category.objects.create(title='Сплит-системы', slug='split')
        cls.brand = Brand.objects.create(title='Ballu', slug='ballu')

    def _make(self, nc, title, kind=Product.KIND_SPLIT_SYSTEM):
        return Product.objects.create(
            nc_code=nc, articul=nc, category=self.category, brand=self.brand,
            title=title, kind=kind,
        )

    def test_dry_run_does_not_change_db(self):
        p = self._make('NC-1', 'Экран для вентиляционной решётки Ballu Квадра 600')
        out = StringIO()
        call_command('backfill_product_kind', stdout=out)
        p.refresh_from_db()
        self.assertEqual(p.kind, Product.KIND_SPLIT_SYSTEM)  # unchanged без --apply
        self.assertIn('Dry-run', out.getvalue())

    def test_apply_reclassifies_accessory(self):
        p = self._make('NC-1', 'Экран для вентиляционной решётки Ballu Квадра 600')
        call_command('backfill_product_kind', '--apply', stdout=StringIO())
        p.refresh_from_db()
        self.assertEqual(p.kind, Product.KIND_ACCESSORY)

    def test_apply_reclassifies_multi_split(self):
        p = self._make('NC-1', 'Мульти-блок внутренний 9')
        call_command('backfill_product_kind', '--apply', stdout=StringIO())
        p.refresh_from_db()
        self.assertEqual(p.kind, Product.KIND_MULTI_SPLIT_BLOCK)

    def test_apply_leaves_correctly_classified_untouched(self):
        p = self._make('NC-1', 'AC Standard 9', kind=Product.KIND_SPLIT_SYSTEM)
        call_command('backfill_product_kind', '--apply', stdout=StringIO())
        p.refresh_from_db()
        self.assertEqual(p.kind, Product.KIND_SPLIT_SYSTEM)

    def test_summary_counts_reported(self):
        self._make('NC-1', 'AC Standard 9')
        self._make('NC-2', 'Экран для вентиляционной решётки Ballu Квадра 600')
        out = StringIO()
        call_command('backfill_product_kind', stdout=out)
        text = out.getvalue()
        self.assertIn('Всего товаров: 2', text)
        self.assertIn('Изменится kind у: 1', text)
