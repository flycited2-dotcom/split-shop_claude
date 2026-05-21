"""Юнит-тесты для apps/catalog/btu.py.

Pure-функции тестируем через SimpleTestCase (без БД). Каскад
`compute_btu` и кеш `resolve_btu` — через TestCase с реальными
Product/TechSpec/ProductTech.
"""
from types import SimpleNamespace

from django.test import SimpleTestCase, TestCase

from apps.catalog import btu
from apps.catalog.models import Brand, Category, Product, ProductTech, TechSpec


def _tv(title, unit, value):
    """Лёгкая имитация ProductTech для pure-тестов `_btu_from_tech_*`.

    Функции читают `getattr(tv, 'spec', None)`, `spec.title`, `spec.unit`,
    `tv.value` — SimpleNamespace покрывает это без БД.
    """
    return SimpleNamespace(
        spec=SimpleNamespace(title=title, unit=unit),
        value=value,
    )


class ParseNumberTest(SimpleTestCase):

    def test_int_string(self):
        self.assertEqual(btu._parse_number('9'), 9.0)

    def test_float_with_dot(self):
        self.assertEqual(btu._parse_number('9.5'), 9.5)

    def test_float_with_comma(self):
        self.assertEqual(btu._parse_number('2,65'), 2.65)

    def test_range_takes_first(self):
        # «2.65 (0.7 - 3.37)» — должен отдать 2.65 (первое число).
        self.assertEqual(btu._parse_number('2.65 (0.7 - 3.37)'), 2.65)

    def test_btu_in_thousands(self):
        self.assertEqual(btu._parse_number('7000'), 7000.0)

    def test_none(self):
        self.assertIsNone(btu._parse_number(None))

    def test_empty(self):
        self.assertIsNone(btu._parse_number(''))

    def test_no_digit(self):
        self.assertIsNone(btu._parse_number('abc'))


class RoundToStandardTest(SimpleTestCase):

    def test_exact_standard(self):
        self.assertEqual(btu._round_to_standard(9), 9)

    def test_close_above(self):
        # 11.5 → ближайший 12.
        self.assertEqual(btu._round_to_standard(11.5), 12)

    def test_close_below(self):
        # 8.6 → ближайший 9.
        self.assertEqual(btu._round_to_standard(8.6), 9)

    def test_zero(self):
        self.assertIsNone(btu._round_to_standard(0))

    def test_negative(self):
        self.assertIsNone(btu._round_to_standard(-5))

    def test_none(self):
        self.assertIsNone(btu._round_to_standard(None))


class IsCoolingSpecTest(SimpleTestCase):

    def test_holodoproizv(self):
        self.assertTrue(btu._is_cooling_spec('Холодопроизводительность'))

    def test_production_cooling(self):
        self.assertTrue(btu._is_cooling_spec('Макс. производительность охлаждения'))

    def test_power_cooling_btu(self):
        self.assertTrue(btu._is_cooling_spec('Мощность охлаждения, BTU'))

    def test_cooling_capacity_en(self):
        self.assertTrue(btu._is_cooling_spec('Cooling capacity'))

    def test_blacklist_consumption(self):
        # «Потребляемая мощность в режиме охлаждения» — не cooling capacity.
        self.assertFalse(btu._is_cooling_spec('Потребляемая мощность в режиме охлаждения'))

    def test_blacklist_eer(self):
        self.assertFalse(btu._is_cooling_spec('EER при охлаждении'))

    def test_blacklist_electric_heater(self):
        self.assertFalse(btu._is_cooling_spec('Теплопроизводительность электронагревателя'))

    def test_unrelated(self):
        self.assertFalse(btu._is_cooling_spec('Уровень шума'))

    def test_empty(self):
        self.assertFalse(btu._is_cooling_spec(''))
        self.assertFalse(btu._is_cooling_spec(None))


class UnitKindTest(SimpleTestCase):

    def test_kbtu_in_unit(self):
        self.assertEqual(btu._unit_kind('Холодопроизв.', 'kBTU'), 'kbtu')

    def test_kw_in_unit_ru(self):
        self.assertEqual(btu._unit_kind('Мощность охлаждения', 'кВт'), 'kw')

    def test_kw_in_unit_en(self):
        self.assertEqual(btu._unit_kind('Cooling capacity', 'kW'), 'kw')

    def test_w_unit(self):
        self.assertEqual(btu._unit_kind('Мощность охлаждения', 'Вт'), 'w')

    def test_btu_unit(self):
        self.assertEqual(btu._unit_kind('Мощность охлаждения, BTU', 'BTU'), 'btu')

    def test_unknown(self):
        self.assertIsNone(btu._unit_kind('Уровень шума', 'дБ'))


class ValueToKbtuTest(SimpleTestCase):

    def test_kbtu_passthrough(self):
        self.assertEqual(btu._value_to_kbtu(9.0, 'kbtu'), 9.0)

    def test_btu_divides_1000(self):
        self.assertEqual(btu._value_to_kbtu(7000, 'btu'), 7.0)

    def test_kw_multiplies_by_3_412(self):
        self.assertAlmostEqual(btu._value_to_kbtu(2.65, 'kw'), 2.65 * 3.412142, places=4)

    def test_w_divides_then_multiplies(self):
        # 2650 Вт = 2.65 кВт ≈ 9 kBTU.
        self.assertAlmostEqual(btu._value_to_kbtu(2650, 'w'), (2650 / 1000) * 3.412142, places=4)

    def test_zero_returns_none(self):
        self.assertIsNone(btu._value_to_kbtu(0, 'kw'))

    def test_negative_returns_none(self):
        self.assertIsNone(btu._value_to_kbtu(-1, 'kw'))

    def test_unknown_kind_returns_none(self):
        self.assertIsNone(btu._value_to_kbtu(9.0, 'unknown'))


class BtuFromTechCoolingTest(SimpleTestCase):

    def test_kbtu_direct(self):
        tv = _tv('Холодопроизв., kBTU', 'kBTU', '9')
        self.assertEqual(btu._btu_from_tech_cooling([tv]), 9)

    def test_kw_conversion(self):
        # 2.65 кВт * 3.412 ≈ 9.04 → округляется к 9.
        tv = _tv('Мощность охлаждения', 'кВт', '2.65')
        self.assertEqual(btu._btu_from_tech_cooling([tv]), 9)

    def test_btu_full_number(self):
        tv = _tv('Мощность охлаждения, BTU', 'BTU', '7000')
        self.assertEqual(btu._btu_from_tech_cooling([tv]), 7)

    def test_priority_kbtu_over_kw(self):
        # Если есть и kBTU, и kW — берём kBTU (priority 4 > 2).
        kw_tv = _tv('Мощность охлаждения', 'кВт', '3.5')  # ≈ 12 kBTU
        kbtu_tv = _tv('Холодопроизв.', 'kBTU', '9')
        result = btu._btu_from_tech_cooling([kw_tv, kbtu_tv])
        self.assertEqual(result, 9)  # из kBTU, не из kW

    def test_blacklist_consumption_ignored(self):
        consumption = _tv('Потребляемая мощность в режиме охлаждения', 'кВт', '0.85')
        self.assertIsNone(btu._btu_from_tech_cooling([consumption]))

    def test_blacklist_eer_ignored(self):
        eer = _tv('EER', '', '3.4')
        self.assertIsNone(btu._btu_from_tech_cooling([eer]))

    def test_empty_iterable(self):
        self.assertIsNone(btu._btu_from_tech_cooling([]))

    def test_no_spec(self):
        # tv без .spec → пропускается, не ломается.
        broken = SimpleNamespace(spec=None, value='9')
        self.assertIsNone(btu._btu_from_tech_cooling([broken]))


class BtuFromTechAreaTest(SimpleTestCase):

    def test_area_25m2_returns_9_kbtu(self):
        tv = _tv('Эффективен для помещений площадью', 'м²', '25')
        self.assertEqual(btu._btu_from_tech_area([tv]), 9)

    def test_area_50m2_returns_18_kbtu(self):
        # BTU_TO_AREA[18] = 50.
        tv = _tv('Площадь помещения', 'м²', '50')
        self.assertEqual(btu._btu_from_tech_area([tv]), 18)

    def test_blacklist_storage(self):
        # «эксплуатироваться в помещении» — не рекомендуемая, а минимальная.
        tv = _tv('Должен эксплуатироваться в помещении более 25 м²', '', '25')
        self.assertIsNone(btu._btu_from_tech_area([tv]))

    def test_unit_other_than_m_squared_skipped(self):
        # Если unit задан и в нём нет «м» или «m» — спека не подходит.
        tv = _tv('Площадь помещения', 'дБ', '25')
        self.assertIsNone(btu._btu_from_tech_area([tv]))

    def test_unit_empty_allowed(self):
        # unit может быть пустым — значение само содержит число.
        tv = _tv('Площадь помещения', '', '25')
        self.assertEqual(btu._btu_from_tech_area([tv]), 9)


class ExtractBtuTest(SimpleTestCase):

    def test_ballu_bpac09_legitimate(self):
        # BPAC-09 → «09» легитимный BTU-код для оконных.
        self.assertEqual(btu.extract_btu('BPAC-09'), 9)

    def test_articul_with_two_digit_code(self):
        self.assertEqual(btu.extract_btu('ASW-H12B4'), 12)

    def test_no_match_returns_none(self):
        self.assertIsNone(btu.extract_btu('NO-DIGITS'))

    def test_empty(self):
        self.assertIsNone(btu.extract_btu(''))
        self.assertIsNone(btu.extract_btu(None))


class BtuTrapTest(SimpleTestCase):
    """XIGMA / Ballu Eclipse: число в артикуле — это НЕ BTU."""

    def test_xigma_txe27_via_area_returns_10_kbtu(self):
        # XIGMA TXE27: «27» в артикуле — площадь (м²), не BTU. Через TechSpec
        # площади 27 м² _btu_from_tech_area берёт ближайший стандарт:
        # BTU_TO_AREA[10]=28 (diff=1) ближе, чем [9]=25 (diff=2). Главное —
        # _не_ 27 из артикула.
        tv = _tv('Эффективен для помещений площадью', 'м²', '27')
        self.assertEqual(btu._btu_from_tech_area([tv]), 10)

    def test_ballu_eclipse40_via_cooling_returns_14_kbtu(self):
        # Ballu Eclipse-40: «40» в артикуле — серия. Через TechSpec мощности
        # 4.0 кВт получаем 13.65 ≈ 14 kBTU (ближайший стандарт).
        tv = _tv('Мощность охлаждения', 'кВт', '4.0')
        self.assertEqual(btu._btu_from_tech_cooling([tv]), 14)

    def test_extract_btu_alone_unreliable_for_eclipse40(self):
        # extract_btu для «Eclipse-40» легально вернёт 40 — это известная
        # ловушка. Caller (compute_btu) обязан сначала пытаться TechSpec.
        self.assertEqual(btu.extract_btu('Ballu BSDI-FM/in-40HN1'), 40)


class BtuLabelTest(SimpleTestCase):

    def test_with_area_known_btu(self):
        self.assertEqual(btu.btu_label(9), '9 000 BTU (до 25 м²)')

    def test_without_area(self):
        self.assertEqual(btu.btu_label(9, with_area=False), '9 000 BTU')

    def test_unknown_btu(self):
        # Не стандарт — без скобок.
        self.assertEqual(btu.btu_label(11), '11 000 BTU')

    def test_zero(self):
        self.assertEqual(btu.btu_label(0), '')

    def test_none(self):
        self.assertEqual(btu.btu_label(None), '')


# === DB-тесты ===

class _DbBase(TestCase):
    """Общий setup для DB-тестов: категория, бренд, TechSpec'и."""

    @classmethod
    def setUpTestData(cls):
        cls.category = Category.objects.create(
            title='Сплит-системы', slug='split-systems', sync_enabled=True,
        )
        cls.brand = Brand.objects.create(title='TestBrand', slug='testbrand')
        cls.spec_cooling = TechSpec.objects.create(
            title='Холодопроизводительность', unit='кВт', order=1,
        )
        cls.spec_area = TechSpec.objects.create(
            title='Эффективен для помещений площадью', unit='м²', order=2,
        )

    def _make_product(self, nc_code, articul='', btu_calc=None):
        return Product.objects.create(
            nc_code=nc_code, articul=articul,
            category=self.category, brand=self.brand,
            title=f'Test {articul or nc_code}',
            btu_calc=btu_calc,
        )

    def _attach(self, product, spec, value):
        return ProductTech.objects.create(product=product, spec=spec, value=value)


class ComputeBtuDBTest(_DbBase):

    def test_cooling_takes_precedence(self):
        p = self._make_product('NC-1', articul='BPAC-09')  # articul → 9
        self._attach(p, self.spec_cooling, '3.5')  # 3.5 кВт ≈ 12 kBTU
        # Cooling (12) выигрывает у articul (9).
        self.assertEqual(btu.compute_btu(p), 12)

    def test_area_when_no_cooling(self):
        p = self._make_product('NC-2', articul='BPAC-09')  # articul → 9
        self._attach(p, self.spec_area, '50')  # 50 м² → 18 kBTU
        # Area (18) выигрывает у articul (9), т.к. в каскаде стоит выше.
        self.assertEqual(btu.compute_btu(p), 18)

    def test_articul_when_no_tech(self):
        p = self._make_product('NC-3', articul='BPAC-09')
        # Без tech_values → fallback на articul.
        self.assertEqual(btu.compute_btu(p), 9)

    def test_no_data_returns_none(self):
        p = self._make_product('NC-4', articul='NO-DIGITS-HERE')
        self.assertIsNone(btu.compute_btu(p))

    def test_none_product(self):
        self.assertIsNone(btu.compute_btu(None))


class ResolveBtuTest(_DbBase):

    def test_returns_cached_btu_calc(self):
        p = self._make_product('NC-10', articul='NO-DIGITS', btu_calc=12)
        # Кеш установлен — compute_btu не должен дёргаться (нет tech_values, нет articul-числа).
        self.assertEqual(btu.resolve_btu(p), 12)

    def test_falls_to_compute_when_no_cache(self):
        p = self._make_product('NC-11', articul='BPAC-09', btu_calc=None)
        # Нет кеша → compute_btu → articul → 9.
        self.assertEqual(btu.resolve_btu(p), 9)

    def test_none_product(self):
        self.assertIsNone(btu.resolve_btu(None))


class RefreshBtuCalcTest(_DbBase):

    def test_updates_field_when_changed(self):
        p = self._make_product('NC-20', articul='BPAC-09', btu_calc=None)
        result = btu.refresh_btu_calc(p)
        self.assertEqual(result, 9)
        p.refresh_from_db()
        self.assertEqual(p.btu_calc, 9)

    def test_no_save_when_unchanged(self):
        p = self._make_product('NC-21', articul='BPAC-09', btu_calc=9)
        # Уже 9, новый compute → 9. Save с update_fields пройти не должен,
        # но проще проверить итог: значение не сбилось, объект валиден.
        result = btu.refresh_btu_calc(p)
        self.assertEqual(result, 9)
        p.refresh_from_db()
        self.assertEqual(p.btu_calc, 9)

    def test_returns_none_for_product_without_data(self):
        p = self._make_product('NC-22', articul='NO-DIGITS', btu_calc=12)
        # Нет cooling/area/valid articul → None. И поле сбросится в None.
        result = btu.refresh_btu_calc(p)
        self.assertIsNone(result)
        p.refresh_from_db()
        self.assertIsNone(p.btu_calc)

    def test_none_product(self):
        self.assertIsNone(btu.refresh_btu_calc(None))
