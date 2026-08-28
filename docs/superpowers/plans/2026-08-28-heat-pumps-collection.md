# Подборка «Тепловые насосы» — план реализации

> **Для агентов:** ОБЯЗАТЕЛЬНЫЙ СУБ-НАВЫК: используйте superpowers:subagent-driven-development
> (рекомендуется) или superpowers:executing-plans для выполнения плана задача за задачей.
> Шаги размечены чекбоксами (`- [ ]`).

**Цель:** дать сайту раздел «Тепловые насосы», который наполняется из уже имеющегося
каталога — сплит-системами с обогревом до −20 °C и ниже — плюс паспортными теплонасосами
Русклимата под заказ.

**Архитектура:** товар остаётся в своей категории (`Product.category` — ForeignKey,
второй категории у товара быть не может), а подборка — это правило отбора поверх каталога
со своим адресом и SEO-текстом. Признак низкотемпературного обогрева вычисляется один раз
при синке в поле `Product.heating_min_temp`, а не парсится из строк характеристик на каждый
запрос — по образцу `Product.kind` (см. `apps/catalog/classify.py`).

**Стек:** Django 5, django-filter, PostgreSQL, Tailwind (скомпилированный), htmx.
Тесты — `django.test.TestCase` / `SimpleTestCase` + `unittest.mock`, без pytest.

**Спецификация:** `docs/superpowers/specs/2026-08-28-heat-pumps-collection-design.md`

**Ветка:** `feature/heat-pumps-collection` (уже создана от `develop`, в ней лежит спека).

## Глобальные ограничения

- Порог подборки — **−20 °C и ниже** (`heating_min_temp <= -20`). Внутри вкладки фасета
  сужает до −25 и −30. Значения порога брать из констант, не из литералов по коду.
- Тесты запускаются командой из README:
  `python manage.py test apps.catalog.tests apps.leads.tests apps.sync.tests apps.accounts.tests --verbosity=2`.
  Для одного модуля: `python manage.py test apps.catalog.tests.test_heating --verbosity=2`.
  Нужна поднятая БД (`docker compose up -d db`), иначе тесты не стартуют.
- Парсеры и правила отбора — чистые функции без БД и сети, тестируются напрямую.
  Это принятый в проекте стиль (`classify.py`, `btu.py`, `warehouse_stock.py`).
- Комментарии и docstring — по-русски, с объяснением **почему**, а не что: так написан
  весь проект.
- Никаких правок логики `kind`, `btu_calc`, квиза и главной страницы — вне этого этапа.
- Коммит после каждой задачи, сообщения по-русски, префиксы `feat:` / `test:` / `docs:`.

---

## Структура файлов

**Создаются:**

| Файл | Ответственность |
|---|---|
| `apps/catalog/heating.py` | Парсер температуры обогрева и заполнение двух полей товара |
| `apps/catalog/collections.py` | Реестр подборок: slug, тексты, правило отбора |
| `apps/catalog/management/commands/backfill_heating.py` | Разовый пересчёт полей у существующих товаров |
| `apps/catalog/tests/test_heating.py` | Тесты парсера (без БД) и заполнения полей (с БД) |
| `apps/catalog/tests/test_collections.py` | Тесты правила подборки и страницы |
| `templates/catalog/collection.html` | Страница подборки: свой h1 и SEO-текст поверх листинга |

**Изменяются:**

| Файл | Что меняется |
|---|---|
| `apps/catalog/models.py` | Поля `heating_min_temp`, `is_heat_pump` на `Product` |
| `apps/catalog/urls.py` | Маршрут `/catalog/<slug>/` |
| `apps/catalog/views.py` | View подборки; вынос общего `base_qs` из `catalog()` |
| `apps/catalog/filters.py` | Фасета `heating` (−20 / −25 / −30) |
| `apps/catalog/facets.py` | Подсчёт значений фасеты `heating` |
| `apps/catalog/sitemaps.py` | Подборки в карту сайта |
| `templates/catalog/partials/_filters.html` | Блок фасеты «Работает на обогрев до» |
| `templates/catalog/index.html` | Пункт «Подборки» в сайдбаре |
| `templates/partials/header.html` | Ссылка на подборку в шапке |
| `apps/sync/breeze_tech.py` | Вызов заполнения полей после записи характеристик |
| `apps/sync/rusklimat_rest.py` | Тот же вызов + пропуск теплонасосов в синк + `is_heat_pump` |
| `apps/sync/daichi_catalog.py` | Тот же вызов после `_sync_tech_specs` |

---

## Задача 1: Парсер минимальной температуры обогрева

**Файлы:**
- Создать: `apps/catalog/heating.py`
- Создать: `apps/catalog/tests/test_heating.py`

**Интерфейсы:**
- Отдаёт: `HEATING_SPEC_TITLES: tuple[str, ...]`, `HEAT_PUMP_SPEC_TITLE: str`,
  `HEAT_PUMP_THRESHOLD: int = -20`, `parse_min_heating_temp(value: str) -> int | None`.

Три поставщика присылают одно и то же под разными названиями и в разных форматах —
Бриз `-20 ~ +24`, Daichi `-25~30`, Русклимат `-15`. Парсер берёт первое отрицательное
число: это и есть нижняя граница работы на обогрев.

- [ ] **Шаг 1: Написать падающий тест**

Создать `apps/catalog/tests/test_heating.py`:

```python
"""Тесты парсера минимальной температуры обогрева.

SimpleTestCase — БД не нужна: parse_min_heating_temp чистая функция.
Кейсы взяты из реальных значений прода (разведка 2026-08-28): Бриз отдаёт
диапазон «-20 ~ +24», Daichi «-25~30» без пробелов, Rusklimat одно число.
"""
from django.test import SimpleTestCase

from apps.catalog.heating import parse_min_heating_temp


class ParseMinHeatingTempTest(SimpleTestCase):

    def test_breez_range(self):
        self.assertEqual(parse_min_heating_temp('-20 ~ +24'), -20)

    def test_daichi_range_without_spaces(self):
        self.assertEqual(parse_min_heating_temp('-25~30'), -25)

    def test_rusklimat_single_number(self):
        self.assertEqual(parse_min_heating_temp('-15'), -15)

    def test_unicode_minus(self):
        # Rusklimat местами присылает юникодный минус U+2212
        self.assertEqual(parse_min_heating_temp('−20 ~ +24'), -20)

    def test_en_dash_separator(self):
        self.assertEqual(parse_min_heating_temp('-30 – +24'), -30)

    def test_positive_only_range_is_none(self):
        # «+17 ~ +30» — машина на обогрев в минус не работает, в подборку не идёт
        self.assertIsNone(parse_min_heating_temp('+17 ~ +30'))

    def test_empty_is_none(self):
        self.assertIsNone(parse_min_heating_temp(''))

    def test_none_is_none(self):
        self.assertIsNone(parse_min_heating_temp(None))

    def test_garbage_is_none(self):
        self.assertIsNone(parse_min_heating_temp('нет данных'))

    def test_degree_suffix(self):
        self.assertEqual(parse_min_heating_temp('-22 °C'), -22)
```

- [ ] **Шаг 2: Запустить тест, убедиться что падает**

Выполнить: `python manage.py test apps.catalog.tests.test_heating --verbosity=2`
Ожидается: `ModuleNotFoundError: No module named 'apps.catalog.heating'`

- [ ] **Шаг 3: Написать минимальную реализацию**

Создать `apps/catalog/heating.py`:

```python
"""Признак «тепловой насос» у товара — считается один раз при синке.

Тепловой насос воздух-воздух — это маркетинговый ярлык на инверторной сплит-системе
с низкотемпературным обогревом, а не отдельный тип оборудования. Поставщики его почти
не проставляют (характеристика «Тепловой насос» приходит у 796 товаров Бриза, значение
«да» — у 5), зато диапазон работы на обогрев отдают все трое — под разными названиями
и в разных форматах.

Значения хранятся строками, поэтому разбирать их регуляркой на каждый запрос каталога —
полный скан таблицы. Вместо этого результат пишется в Product.heating_min_temp при синке,
как это сделано для Product.kind (см. classify.py).
"""
import re

# Названия характеристики у трёх поставщиков (разведка прода 2026-08-28).
# При смене названия у поставщика товары тихо выпадут из подборки — следить
# по счётчику в команде backfill_heating.
HEATING_SPEC_TITLES = (
    'Рабочие температурные границы наружного воздуха (нагрев)',   # Бриз
    'Диапазон рабочих температур, нагрев, °C',                     # Daichi
    'Мин. рабочая температура воздуха для внешнего блока',         # Rusklimat
)

# Характеристика Бриза с прямым ответом «да»/«нет».
HEAT_PUMP_SPEC_TITLE = 'Тепловой насос'

# Порог подборки: машина, которая греет до -20 и ниже, продаётся как тепловой насос.
HEAT_PUMP_THRESHOLD = -20

# Пороги фасеты внутри подборки.
HEATING_THRESHOLDS = (-20, -25, -30)

# Минус: ASCII, юникодный U+2212. Тире-разделители диапазона не должны
# съедаться как знак числа, поэтому ищем минус, приклеенный к цифрам.
_MINUS = r'[-−]'
_NEG_RE = re.compile(rf'{_MINUS}\s?(\d+)')


def parse_min_heating_temp(value):
    """'-20 ~ +24' / '-25~30' / '-15' / '−20 ~ +24' -> -20 / -25 / -15.

    Возвращает первое отрицательное число строки — нижнюю границу работы
    на обогрев. None, если отрицательных чисел нет (машина греет только
    в плюс) или строка пустая/мусорная. Ничего не бросает.
    """
    if not value:
        return None
    match = _NEG_RE.search(str(value))
    if not match:
        return None
    try:
        return -int(match.group(1))
    except (TypeError, ValueError):
        return None
```

- [ ] **Шаг 4: Запустить тест, убедиться что проходит**

Выполнить: `python manage.py test apps.catalog.tests.test_heating --verbosity=2`
Ожидается: `OK`, 10 тестов.

- [ ] **Шаг 5: Коммит**

```bash
git add apps/catalog/heating.py apps/catalog/tests/test_heating.py
git commit -m "feat(catalog): парсер минимальной температуры обогрева

Три поставщика отдают диапазон работы на обогрев под разными названиями
и в разных форматах. Чистая функция, тесты без БД."
```

---

## Задача 2: Поля товара и их заполнение

**Файлы:**
- Изменить: `apps/catalog/models.py` (класс `Product`, после поля `kind`)
- Изменить: `apps/catalog/heating.py` (добавить две функции)
- Изменить: `apps/catalog/tests/test_heating.py` (добавить класс тестов с БД)
- Создать: миграция `apps/catalog/migrations/00XX_product_heating_fields.py` (генерируется)

**Интерфейсы:**
- Потребляет из задачи 1: `HEATING_SPEC_TITLES`, `HEAT_PUMP_SPEC_TITLE`,
  `parse_min_heating_temp`.
- Отдаёт: `Product.heating_min_temp`, `Product.is_heat_pump`,
  `min_heating_temp_for(product) -> int | None`,
  `apply_heating_fields(product, declared: bool = False) -> bool`.

Характеристики во всех трёх синках пишутся **после** создания товара, поэтому заполнение
полей — отдельный вызов после записи `ProductTech`, а не часть `update_or_create`.

- [ ] **Шаг 1: Добавить поля в модель**

В `apps/catalog/models.py`, в классе `Product` сразу после поля `kind`:

```python
    heating_min_temp = models.SmallIntegerField(
        null=True, blank=True, db_index=True,
        verbose_name='Мин. температура обогрева, °C',
        help_text='Нижняя граница работы на обогрев. Считается при синке из '
                  'tech_values (у трёх поставщиков три разных названия '
                  'характеристики) — см. apps.catalog.heating. Не парсится '
                  'строкой на каждый запрос, иначе full scan на каждый '
                  'заход в каталог.',
    )
    is_heat_pump = models.BooleanField(
        default=False, db_index=True,
        verbose_name='Тепловой насос (по данным поставщика)',
        help_text='Поставщик сам назвал товар тепловым насосом: категория '
                  'Rusklimat «Тепловые насосы...» или характеристика Бриза '
                  '«Тепловой насос: да». Товары с этим флагом попадают в '
                  'подборку независимо от heating_min_temp.',
    )
```

- [ ] **Шаг 2: Сгенерировать и применить миграцию**

```bash
python manage.py makemigrations catalog
python manage.py migrate
```
Ожидается: создана миграция с `AddField` для двух полей.

- [ ] **Шаг 3: Написать падающий тест заполнения**

Дописать в `apps/catalog/tests/test_heating.py`:

```python
from django.test import TestCase

from apps.catalog.heating import apply_heating_fields, min_heating_temp_for
from apps.catalog.models import Brand, Category, Product, ProductTech, TechSpec


class ApplyHeatingFieldsTest(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.category = Category.objects.create(
            title='Сплит-системы', slug='split-heating', sync_enabled=True,
        )
        cls.brand = Brand.objects.create(title='FUNAI', slug='funai-heating')

    def _product(self, nc):
        return Product.objects.create(
            nc_code=nc, articul=nc, category=self.category, brand=self.brand,
            title=f'AC {nc}', slug=f'ac-{nc}',
        )

    def _tech(self, product, spec_title, value):
        spec, _ = TechSpec.objects.get_or_create(title=spec_title)
        ProductTech.objects.create(product=product, spec=spec, value=value)

    def test_breez_spec_fills_field(self):
        p = self._product('NC-B1')
        self._tech(p, 'Рабочие температурные границы наружного воздуха (нагрев)', '-20 ~ +24')
        self.assertTrue(apply_heating_fields(p))
        p.refresh_from_db()
        self.assertEqual(p.heating_min_temp, -20)

    def test_daichi_spec_fills_field(self):
        p = self._product('NC-D1')
        self._tech(p, 'Диапазон рабочих температур, нагрев, °C', '-25~30')
        apply_heating_fields(p)
        p.refresh_from_db()
        self.assertEqual(p.heating_min_temp, -25)

    def test_rusklimat_spec_fills_field(self):
        p = self._product('NC-R1')
        self._tech(p, 'Мин. рабочая температура воздуха для внешнего блока', '-15')
        apply_heating_fields(p)
        p.refresh_from_db()
        self.assertEqual(p.heating_min_temp, -15)

    def test_two_specs_take_the_coldest(self):
        # У товара могут оказаться характеристики от двух источников —
        # берём минимальную (более холодную) границу.
        p = self._product('NC-M1')
        self._tech(p, 'Рабочие температурные границы наружного воздуха (нагрев)', '-15 ~ +24')
        self._tech(p, 'Диапазон рабочих температур, нагрев, °C', '-25~30')
        self.assertEqual(min_heating_temp_for(p), -25)

    def test_no_specs_leaves_none(self):
        p = self._product('NC-N1')
        apply_heating_fields(p)
        p.refresh_from_db()
        self.assertIsNone(p.heating_min_temp)
        self.assertFalse(p.is_heat_pump)

    def test_breez_declared_flag(self):
        p = self._product('NC-F1')
        self._tech(p, 'Тепловой насос', 'да')
        apply_heating_fields(p)
        p.refresh_from_db()
        self.assertTrue(p.is_heat_pump)

    def test_breez_declared_no_does_not_set_flag(self):
        p = self._product('NC-F2')
        self._tech(p, 'Тепловой насос', 'нет')
        apply_heating_fields(p)
        p.refresh_from_db()
        self.assertFalse(p.is_heat_pump)

    def test_declared_argument_sets_flag(self):
        # Rusklimat объявляет теплонасос названием категории, не характеристикой
        p = self._product('NC-F3')
        apply_heating_fields(p, declared=True)
        p.refresh_from_db()
        self.assertTrue(p.is_heat_pump)

    def test_returns_false_when_nothing_changed(self):
        p = self._product('NC-S1')
        self._tech(p, 'Мин. рабочая температура воздуха для внешнего блока', '-15')
        apply_heating_fields(p)
        # второй вызов ничего не меняет — лишнего UPDATE быть не должно
        self.assertFalse(apply_heating_fields(p))
```

- [ ] **Шаг 4: Запустить тест, убедиться что падает**

Выполнить: `python manage.py test apps.catalog.tests.test_heating --verbosity=2`
Ожидается: `ImportError: cannot import name 'apply_heating_fields'`

- [ ] **Шаг 5: Реализовать функции**

Дописать в `apps/catalog/heating.py`:

```python
def min_heating_temp_for(product):
    """Минимальная (самая холодная) граница обогрева среди характеристик товара.

    У товара может быть две записи от разных источников — берём наименьшую.
    None, если ни одна характеристика не распозналась.
    """
    values = (
        product.tech_values
        .filter(spec__title__in=HEATING_SPEC_TITLES)
        .values_list('value', flat=True)
    )
    temps = [t for t in (parse_min_heating_temp(v) for v in values) if t is not None]
    return min(temps) if temps else None


def _declared_by_spec(product):
    """True, если у товара характеристика «Тепловой насос» со значением «да»."""
    values = (
        product.tech_values
        .filter(spec__title=HEAT_PUMP_SPEC_TITLE)
        .values_list('value', flat=True)
    )
    return any(str(v).strip().lower() in ('да', 'yes', 'true') for v in values)


def apply_heating_fields(product, declared=False):
    """Проставляет heating_min_temp и is_heat_pump товару. True, если что-то изменилось.

    `declared` — поставщик объявил товар тепловым насосом вне характеристик
    (у Rusklimat это название категории). Вызывается синками ПОСЛЕ записи
    ProductTech: характеристики пишутся отдельным шагом после создания товара.
    """
    temp = min_heating_temp_for(product)
    is_pump = bool(declared) or _declared_by_spec(product)

    changed = (product.heating_min_temp != temp) or (product.is_heat_pump != is_pump)
    if changed:
        product.heating_min_temp = temp
        product.is_heat_pump = is_pump
        product.save(update_fields=['heating_min_temp', 'is_heat_pump'])
    return changed
```

- [ ] **Шаг 6: Запустить тест, убедиться что проходит**

Выполнить: `python manage.py test apps.catalog.tests.test_heating --verbosity=2`
Ожидается: `OK`, 19 тестов.

- [ ] **Шаг 7: Коммит**

```bash
git add apps/catalog/models.py apps/catalog/migrations/ apps/catalog/heating.py apps/catalog/tests/test_heating.py
git commit -m "feat(catalog): поля heating_min_temp и is_heat_pump

Считаются при синке после записи характеристик, как Product.kind.
Из двух характеристик берётся более холодная граница."
```

---

## Задача 3: Команда пересчёта для существующих товаров

**Файлы:**
- Создать: `apps/catalog/management/commands/backfill_heating.py`
- Изменить: `apps/catalog/tests/test_heating.py` (добавить класс тестов команды)

**Интерфейсы:**
- Потребляет из задачи 2: `apply_heating_fields`.
- Отдаёт: команду `python manage.py backfill_heating [--apply]`.

В базе ~4500 активных товаров, температура распознаётся у 2128 — их нужно проставить
разово. Устройство команды копирует `backfill_product_kind`: dry-run по умолчанию,
запись только по `--apply`.

- [ ] **Шаг 1: Написать падающий тест**

Дописать в `apps/catalog/tests/test_heating.py`:

```python
from io import StringIO

from django.core.management import call_command


class BackfillHeatingCommandTest(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.category = Category.objects.create(
            title='Сплит-системы', slug='split-backfill', sync_enabled=True,
        )

    def _product_with_temp(self, nc, value):
        p = Product.objects.create(
            nc_code=nc, articul=nc, category=self.category,
            title=f'AC {nc}', slug=f'ac-{nc}',
        )
        spec, _ = TechSpec.objects.get_or_create(
            title='Рабочие температурные границы наружного воздуха (нагрев)',
        )
        ProductTech.objects.create(product=p, spec=spec, value=value)
        return p

    def test_dry_run_does_not_write(self):
        p = self._product_with_temp('NC-DR', '-25 ~ +24')
        out = StringIO()
        call_command('backfill_heating', stdout=out)
        p.refresh_from_db()
        self.assertIsNone(p.heating_min_temp)
        self.assertIn('Dry-run', out.getvalue())

    def test_apply_writes_fields(self):
        p = self._product_with_temp('NC-AP', '-25 ~ +24')
        out = StringIO()
        call_command('backfill_heating', '--apply', stdout=out)
        p.refresh_from_db()
        self.assertEqual(p.heating_min_temp, -25)

    def test_summary_counts_by_threshold(self):
        self._product_with_temp('NC-T20', '-20 ~ +24')
        self._product_with_temp('NC-T25', '-25 ~ +24')
        self._product_with_temp('NC-T15', '-15 ~ +24')
        out = StringIO()
        call_command('backfill_heating', '--apply', stdout=out)
        text = out.getvalue()
        self.assertIn('до -20', text)
        self.assertIn('до -25', text)
```

- [ ] **Шаг 2: Запустить тест, убедиться что падает**

Выполнить: `python manage.py test apps.catalog.tests.test_heating.BackfillHeatingCommandTest --verbosity=2`
Ожидается: `CommandError: Unknown command: 'backfill_heating'`

- [ ] **Шаг 3: Реализовать команду**

Создать `apps/catalog/management/commands/backfill_heating.py`:

```python
from django.core.management.base import BaseCommand

from apps.catalog.heating import (
    HEATING_THRESHOLDS, apply_heating_fields, min_heating_temp_for,
)
from apps.catalog.models import Product


class Command(BaseCommand):
    help = (
        'Проставляет Product.heating_min_temp и is_heat_pump существующим товарам '
        'из уже синканных характеристик. Разово, после добавления полей; дальше '
        'их держат в актуальном состоянии сами синки. Dry-run по умолчанию — '
        'печатает сводку, ничего не пишет.'
    )

    def add_arguments(self, parser):
        parser.add_argument('--apply', action='store_true',
                            help='Записать изменения в БД. Без флага — только dry-run.')

    def handle(self, *args, **options):
        apply_changes = options['apply']

        total = with_temp = changed = 0
        by_threshold = {t: 0 for t in HEATING_THRESHOLDS}

        queryset = Product.objects.prefetch_related('tech_values__spec')
        for product in queryset.iterator(chunk_size=500):
            total += 1
            temp = min_heating_temp_for(product)
            if temp is not None:
                with_temp += 1
                for threshold in HEATING_THRESHOLDS:
                    if temp <= threshold:
                        by_threshold[threshold] += 1
            if apply_changes and apply_heating_fields(product):
                changed += 1

        self.stdout.write(f'Всего товаров: {total}')
        self.stdout.write(f'С распознанной температурой обогрева: {with_temp}')
        for threshold in HEATING_THRESHOLDS:
            self.stdout.write(f'  → до {threshold} °C и ниже: {by_threshold[threshold]}')

        if not apply_changes:
            self.stdout.write(self.style.WARNING(
                '\nDry-run mode. Запустите с --apply, чтобы записать изменения.'
            ))
            return

        self.stdout.write(self.style.SUCCESS(f'\nПрименено. Обновлено товаров: {changed}.'))
```

- [ ] **Шаг 4: Запустить тесты, убедиться что проходят**

Выполнить: `python manage.py test apps.catalog.tests.test_heating --verbosity=2`
Ожидается: `OK`, 22 теста.

- [ ] **Шаг 5: Коммит**

```bash
git add apps/catalog/management/commands/backfill_heating.py apps/catalog/tests/test_heating.py
git commit -m "feat(catalog): команда backfill_heating

Разовый пересчёт полей обогрева по образцу backfill_product_kind:
dry-run по умолчанию, сводка по порогам -20/-25/-30."
```

---

## Задача 4: Синки заполняют поля и впускают теплонасосы Русклимата

**Файлы:**
- Изменить: `apps/sync/breeze_tech.py:116-125` (после `bulk_create` в `_sync_product_tech`)
- Изменить: `apps/sync/daichi_catalog.py:449` (после `_sync_tech_specs`)
- Изменить: `apps/sync/rusklimat_rest.py:55-58` (regex), `184-197` (категории), `455-465` (вызов)
- Изменить: `apps/sync/tests/test_rusklimat_rest.py` (тесты regex и имени категории)

**Интерфейсы:**
- Потребляет из задачи 2: `apply_heating_fields(product, declared=False)`.
- Отдаёт: `_find_ac_categories(client) -> tuple[set[str], dict[str, str]]` — теперь
  возвращает и множество id, и карту `{category_id: name}`; вызывающий код в
  `sync_rusklimat_rest` распаковывает пару.

Категория «Тепловые насосы воздух-воздух» (22 товара) сейчас не проходит `_AC_CATEGORY_RE`
и в синк не попадает. После правки товары приезжают, раскладываются в бытовые сплиты
(это и есть сплит-системы) и получают `is_heat_pump=True`.

- [ ] **Шаг 1: Написать падающий тест regex и карты категорий**

Дописать в `apps/sync/tests/test_rusklimat_rest.py`:

```python
from unittest.mock import Mock

from apps.sync.rusklimat_rest import (
    _AC_CATEGORY_RE, _AC_EXCLUDE_RE, _find_ac_categories, _is_heat_pump_category,
)


class HeatPumpCategoryTest(SimpleTestCase):

    def test_heat_pump_category_passes_filter(self):
        name = 'Тепловые насосы воздух-воздух'
        self.assertTrue(_AC_CATEGORY_RE.search(name))
        self.assertFalse(_AC_EXCLUDE_RE.search(name))

    def test_heat_pump_air_water_passes_filter(self):
        self.assertTrue(_AC_CATEGORY_RE.search('Тепловые насосы воздух-вода. Моноблоки'))

    def test_heat_pump_accessories_still_excluded(self):
        # Аксессуары к теплонасосам в розницу не нужны
        self.assertTrue(_AC_EXCLUDE_RE.search('Аксессуары для тепловых насосов'))

    def test_is_heat_pump_category_by_name(self):
        self.assertTrue(_is_heat_pump_category('Тепловые насосы воздух-воздух'))
        self.assertFalse(_is_heat_pump_category('Бытовые кондиционеры'))

    def test_find_ac_categories_returns_ids_and_names(self):
        client = Mock()
        client.get_categories.return_value = [
            {'id': 'uuid-1', 'name': 'Бытовые кондиционеры'},
            {'id': 'uuid-2', 'name': 'Тепловые насосы воздух-воздух'},
            {'id': 'uuid-3', 'name': 'Шланги садовые'},
        ]
        ids, names = _find_ac_categories(client)
        self.assertEqual(ids, {'uuid-1', 'uuid-2'})
        self.assertEqual(names['uuid-2'], 'Тепловые насосы воздух-воздух')
        self.assertNotIn('uuid-3', ids)
```

Если в файле ещё нет импорта `SimpleTestCase`, добавить `from django.test import SimpleTestCase`.

- [ ] **Шаг 2: Запустить тест, убедиться что падает**

Выполнить: `python manage.py test apps.sync.tests.test_rusklimat_rest --verbosity=2`
Ожидается: `ImportError: cannot import name '_is_heat_pump_category'`

- [ ] **Шаг 3: Правка regex и карты категорий Русклимата**

В `apps/sync/rusklimat_rest.py` заменить блок с `_AC_CATEGORY_RE` (строки 54-63):

```python
# Соответствие master-категорий Rusklimat (по regex по name).
# «Тепловые насосы» добавлены 2026-08-28: воздух-воздух — это те же сплит-системы,
# продаются как тепловой насос (22 позиции, все под заказ). См.
# docs/superpowers/specs/2026-08-28-heat-pumps-collection-design.md
_AC_CATEGORY_RE = re.compile(
    r'кондицион|сплит.?систем|мульти.?сплит|мобильн\w*\s+кондицион|'
    r'теплов\w*\s+насос',
    re.IGNORECASE,
)
# Исключаем категории-аксессуары / запчасти / комплектующие.
_AC_EXCLUDE_RE = re.compile(
    r'аксессуар|запчаст|комплектующ|расходн|чехл|абажур|пульт|фильтр',
    re.IGNORECASE,
)
# Категория, которой поставщик сам объявил товар тепловым насосом.
_HEAT_PUMP_CATEGORY_RE = re.compile(r'теплов\w*\s+насос', re.IGNORECASE)


def _is_heat_pump_category(name):
    """True, если Rusklimat назвал категорию тепловыми насосами."""
    return bool(_HEAT_PUMP_CATEGORY_RE.search(name or ''))
```

Заменить `_find_ac_categories` (строки ~184-197):

```python
def _find_ac_categories(client):
    """(ids, names) категорий Rusklimat с AC-товарами.

    Возвращает и карту {id: name} — она нужна, чтобы при записи товара понять,
    объявил ли поставщик его тепловым насосом (в самом товаре есть только
    categoryId, названия там нет).
    """
    cats = client.get_categories()
    ids = set()
    names = {}
    for cat in cats:
        name = (cat.get('name') or '').strip()
        names[cat['id']] = name
        if _AC_EXCLUDE_RE.search(name):
            continue
        if _AC_CATEGORY_RE.search(name):
            ids.add(cat['id'])
    logger.info('Rusklimat REST: %d AC-категорий из %d', len(ids), len(cats))
    return ids, names
```

- [ ] **Шаг 4: Запустить тест, убедиться что проходит**

Выполнить: `python manage.py test apps.sync.tests.test_rusklimat_rest --verbosity=2`
Ожидается: `OK`

- [ ] **Шаг 5: Подключить вызов в синке Русклимата**

В `sync_rusklimat_rest` заменить строку `ac_ids = _find_ac_categories(client)` на:

```python
    ac_ids, category_names = _find_ac_categories(client)
```

Добавить импорт вверху файла рядом с `from apps.catalog.classify import classify_title`:

```python
from apps.catalog.heating import apply_heating_fields
```

В теле цикла, сразу после блока записи характеристик (после `specs_synced += 1`),
добавить:

```python
                # Поля обогрева — после ProductTech: характеристики пишутся
                # отдельным шагом, до него считать нечего.
                apply_heating_fields(
                    product,
                    declared=_is_heat_pump_category(
                        category_names.get(p.get('categoryId', ''), '')
                    ),
                )
```

- [ ] **Шаг 6: Подключить вызов в синке Daichi**

В `apps/sync/daichi_catalog.py` добавить импорт:

```python
from apps.catalog.heating import apply_heating_fields
```

После блока `tech_count = _sync_tech_specs(product, pp, category, tech_cache)`
и его `if tech_count: specs_synced += 1` добавить:

```python
                apply_heating_fields(product)
```

- [ ] **Шаг 7: Подключить вызов в синке характеристик Бриза**

В `apps/sync/breeze_tech.py` добавить импорт:

```python
from apps.catalog.heating import apply_heating_fields
```

В `_sync_product_tech`, сразу после `ProductTech.objects.bulk_create(to_create)`:

```python
    # Характеристики Бриза приезжают отдельной командой sync_breez_tech,
    # поэтому поля обогрева обновляем здесь, а не в sync_products.
    apply_heating_fields(product)
```

- [ ] **Шаг 8: Прогнать все тесты синков**

Выполнить: `python manage.py test apps.sync.tests apps.catalog.tests --verbosity=2`
Ожидается: `OK`, регрессий нет.

- [ ] **Шаг 9: Коммит**

```bash
git add apps/sync/rusklimat_rest.py apps/sync/daichi_catalog.py apps/sync/breeze_tech.py apps/sync/tests/test_rusklimat_rest.py
git commit -m "feat(sync): поля обогрева при синке + теплонасосы Rusklimat

_AC_CATEGORY_RE впускает «Тепловые насосы воздух-воздух» (+23 позиции
под заказ), _find_ac_categories отдаёт карту имён — по ней ставится
is_heat_pump. apply_heating_fields вызывается после записи ProductTech
во всех трёх синках."
```

---

## Задача 5: Реестр подборок

**Файлы:**
- Создать: `apps/catalog/collections.py`
- Создать: `apps/catalog/tests/test_collections.py`

**Интерфейсы:**
- Потребляет из задачи 1: `HEAT_PUMP_THRESHOLD`.
- Отдаёт: `Collection` (dataclass: `slug`, `title`, `h1`, `seo_text`, `rule`),
  `COLLECTIONS: dict[str, Collection]`, `get_collection(slug) -> Collection | None`.

- [ ] **Шаг 1: Написать падающий тест**

Создать `apps/catalog/tests/test_collections.py`:

```python
"""Тесты правила отбора подборки «Тепловые насосы».

Товар остаётся в своей категории — подборка это срез поверх каталога,
поэтому проверяем именно queryset-правило, а не принадлежность категории.
"""
from django.test import TestCase

from apps.catalog.collections import COLLECTIONS, get_collection
from apps.catalog.models import Brand, Category, Product


class HeatPumpCollectionRuleTest(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.category = Category.objects.create(
            title='Бытовые сплит-системы', slug='split-coll', sync_enabled=True,
        )
        cls.brand = Brand.objects.create(title='FUNAI', slug='funai-coll')

    def _product(self, nc, temp=None, declared=False, kind=Product.KIND_SPLIT_SYSTEM):
        return Product.objects.create(
            nc_code=nc, articul=nc, category=self.category, brand=self.brand,
            title=f'AC {nc}', slug=f'ac-{nc}',
            heating_min_temp=temp, is_heat_pump=declared, kind=kind,
        )

    def _selected(self):
        rule = COLLECTIONS['heat-pumps'].rule
        return set(Product.objects.filter(rule).values_list('nc_code', flat=True))

    def test_minus_20_included(self):
        self._product('NC-20', temp=-20)
        self.assertIn('NC-20', self._selected())

    def test_minus_25_included(self):
        self._product('NC-25', temp=-25)
        self.assertIn('NC-25', self._selected())

    def test_minus_15_excluded(self):
        self._product('NC-15', temp=-15)
        self.assertNotIn('NC-15', self._selected())

    def test_no_temp_excluded(self):
        self._product('NC-NONE')
        self.assertNotIn('NC-NONE', self._selected())

    def test_declared_included_without_temp(self):
        self._product('NC-DECL', declared=True)
        self.assertIn('NC-DECL', self._selected())

    def test_accessory_excluded_even_if_cold(self):
        self._product('NC-ACC', temp=-30, kind=Product.KIND_ACCESSORY)
        self.assertNotIn('NC-ACC', self._selected())

    def test_multi_split_block_excluded(self):
        self._product('NC-MULTI', temp=-25, kind=Product.KIND_MULTI_SPLIT_BLOCK)
        self.assertNotIn('NC-MULTI', self._selected())

    def test_get_collection_unknown_slug(self):
        self.assertIsNone(get_collection('no-such-collection'))

    def test_get_collection_known_slug(self):
        self.assertEqual(get_collection('heat-pumps').slug, 'heat-pumps')
```

- [ ] **Шаг 2: Запустить тест, убедиться что падает**

Выполнить: `python manage.py test apps.catalog.tests.test_collections --verbosity=2`
Ожидается: `ModuleNotFoundError: No module named 'apps.catalog.collections'`

- [ ] **Шаг 3: Реализовать реестр**

Создать `apps/catalog/collections.py`:

```python
"""Подборки — срезы каталога со своим адресом, заголовком и SEO-текстом.

Зачем не категория дерева: Product.category — ForeignKey, товар лежит ровно
в одной категории. Инверторная сплит-система с обогревом до -20 должна остаться
в «Бытовых сплит-системах» (иначе покупатель обычного настенного FUNAI KAGAMI
её там не найдёт) и одновременно попадать в «Тепловые насосы».

Реестр держится в коде, а не в БД: сейчас подборка одна, админка для правил
отбора — преждевременное усложнение. Следующая подборка («Инверторные»,
«С Wi-Fi») — это одна запись в COLLECTIONS, без миграций.
"""
from dataclasses import dataclass

from django.db.models import Q

from .heating import HEAT_PUMP_THRESHOLD
from .models import Product


@dataclass(frozen=True)
class Collection:
    slug: str
    title: str          # для меню и хлебных крошек
    h1: str             # заголовок страницы
    seo_text: str       # текст под листингом
    rule: Q             # правило отбора поверх базового queryset каталога


HEAT_PUMPS_SEO_TEXT = (
    'Тепловой насос воздух-воздух — это инверторная сплит-система, которая '
    'работает на обогрев при уличной температуре до −20 °C и ниже. В крымскую '
    'зиму такая машина закрывает отопление квартиры или дома целиком: на каждый '
    'киловатт электричества она отдаёт три-четыре киловатта тепла, то есть '
    'обходится в три-четыре раза дешевле электрокотла или обогревателя. '
    'В подборку попадают только модели с подтверждённым в характеристиках '
    'диапазоном работы на обогрев — фильтром слева можно сузить выбор до '
    'машин, которые греют до −25 и −30 °C.'
)

COLLECTIONS = {
    'heat-pumps': Collection(
        slug='heat-pumps',
        title='Тепловые насосы',
        h1='Тепловые насосы воздух-воздух в Крыму',
        seo_text=HEAT_PUMPS_SEO_TEXT,
        # Сплит-система И (поставщик объявил теплонасосом ИЛИ греет до -20 и ниже)
        rule=Q(kind=Product.KIND_SPLIT_SYSTEM) & (
            Q(is_heat_pump=True) | Q(heating_min_temp__lte=HEAT_PUMP_THRESHOLD)
        ),
    ),
}


def get_collection(slug):
    """Collection по slug или None — вызывающий отдаёт 404."""
    return COLLECTIONS.get(slug)
```

- [ ] **Шаг 4: Запустить тест, убедиться что проходит**

Выполнить: `python manage.py test apps.catalog.tests.test_collections --verbosity=2`
Ожидается: `OK`, 9 тестов.

- [ ] **Шаг 5: Коммит**

```bash
git add apps/catalog/collections.py apps/catalog/tests/test_collections.py
git commit -m "feat(catalog): реестр подборок и правило «Тепловые насосы»

Подборка — срез поверх каталога, товар остаётся в своей категории.
Правило: сплит-система И (объявлен теплонасосом ИЛИ греет до -20)."
```

---

## Задача 6: Страница подборки

**Файлы:**
- Изменить: `apps/catalog/views.py` (вынести `_catalog_base_qs`, добавить `collection`)
- Изменить: `apps/catalog/urls.py`
- Создать: `templates/catalog/collection.html`
- Изменить: `apps/catalog/sitemaps.py`
- Изменить: `apps/catalog/tests/test_collections.py` (добавить view-тесты)

**Интерфейсы:**
- Потребляет из задачи 5: `get_collection`, `COLLECTIONS`.
- Отдаёт: url-имя `collection` с параметром `slug`; функцию
  `_catalog_base_qs(request) -> QuerySet`, которую использует и `catalog()`.

`catalog()` сейчас строит `base_qs` внутри себя. Выносим построение в функцию, чтобы
подборка использовала ровно ту же выборку (Крым-first, `with_order`, `select_related`)
и не разъезжалась с каталогом при будущих правках.

- [ ] **Шаг 1: Написать падающий view-тест**

Дописать в `apps/catalog/tests/test_collections.py`:

```python
from django.test import Client
from django.urls import reverse

from apps.stock.models import Stock


class CollectionViewTest(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.category = Category.objects.create(
            title='Бытовые сплит-системы', slug='split-view', sync_enabled=True,
        )
        cls.brand = Brand.objects.create(title='Hisense', slug='hisense-view')

    def _product(self, nc, temp, qty=3, warehouse='Симферополь'):
        p = Product.objects.create(
            nc_code=nc, articul=nc, category=self.category, brand=self.brand,
            title=f'Инверторная сплит-система {nc}', slug=f'ac-{nc}',
            heating_min_temp=temp,
        )
        Stock.objects.create(product=p, quantity=qty, warehouse=warehouse)
        return p

    def setUp(self):
        self.client = Client()

    def test_page_returns_200(self):
        self._product('NC-V20', -20)
        r = self.client.get(reverse('collection', args=['heat-pumps']))
        self.assertEqual(r.status_code, 200)

    def test_unknown_slug_404(self):
        r = self.client.get('/catalog/no-such-collection/')
        self.assertEqual(r.status_code, 404)

    def test_only_matching_products_listed(self):
        self._product('NC-V20', -20)
        self._product('NC-V15', -15)
        r = self.client.get(reverse('collection', args=['heat-pumps']))
        self.assertContains(r, 'NC-V20')
        self.assertNotContains(r, 'NC-V15')

    def test_h1_and_seo_text_rendered(self):
        self._product('NC-V25', -25)
        r = self.client.get(reverse('collection', args=['heat-pumps']))
        self.assertContains(r, 'Тепловые насосы воздух-воздух в Крыму')
        self.assertContains(r, 'воздух-воздух — это инверторная сплит-система')

    def test_under_order_hidden_by_default(self):
        # Товар без крымского остатка виден только по ?with_order=1 —
        # то же правило, что в каталоге
        self._product('NC-ORDER', -25, qty=4, warehouse='Шерризон')
        r = self.client.get(reverse('collection', args=['heat-pumps']))
        self.assertNotContains(r, 'NC-ORDER')
        r2 = self.client.get(reverse('collection', args=['heat-pumps']), {'with_order': '1'})
        self.assertContains(r2, 'NC-ORDER')
```

- [ ] **Шаг 2: Запустить тест, убедиться что падает**

Выполнить: `python manage.py test apps.catalog.tests.test_collections.CollectionViewTest --verbosity=2`
Ожидается: `NoReverseMatch: Reverse for 'collection' not found`

- [ ] **Шаг 3: Вынести построение базового queryset**

В `apps/catalog/views.py` добавить функцию перед `def catalog(request)`:

```python
def _catalog_base_qs(request):
    """Базовая выборка каталога: активные розничные товары включённых категорий.

    Вынесена из catalog(), чтобы страница подборки (collection) использовала ровно
    ту же выборку — Крым-first, ?with_order, prefetch — и не разъезжалась с каталогом.

    Stock.warehouse='Симферополь' выставляется в write_warehouse_stocks ТОЛЬКО когда
    qty в Крыму > 0. Если в Крыму 0 — там warehouse=крупнейший из Шерризон/Ростов/
    Краснодар (fallback «под заказ»). Поэтому первый ключ — наличие Крыма, а не сам
    Stock.quantity.
    """
    base_qs = (
        Product.objects.filter(is_active=True, category__sync_enabled=True,
                               kind=Product.KIND_SPLIT_SYSTEM)
        .annotate(
            is_crimea=Case(
                When(stock__warehouse='Симферополь', then=Value(1)),
                default=Value(0),
                output_field=IntegerField(),
            )
        )
        .select_related('brand', 'category', 'stock')
        .prefetch_related('images', 'tech_values__spec')
    )
    # Правило владельца (2026-05-24): по умолчанию показываем только то, что
    # физически лежит на крымском складе. ?with_order=1 расширяет до «под заказ».
    if not request.GET.get('with_order'):
        base_qs = base_qs.filter(stock__warehouse='Симферополь',
                                 stock__quantity__gt=0)
    return base_qs
```

В `catalog()` заменить блок построения `base_qs` (от `base_qs = (` до конца блока
`if not request.GET.get('with_order'):`) на:

```python
    base_qs = _catalog_base_qs(request)
```

- [ ] **Шаг 4: Добавить view подборки**

В `apps/catalog/views.py` после `catalog()` добавить:

```python
def collection(request, slug):
    """Страница подборки — срез каталога со своим h1 и SEO-текстом.

    Использует тот же base_qs, фильтры и шаблон листинга, что каталог: подборка
    отличается только правилом отбора и текстами. См. apps/catalog/collections.py.
    """
    from .collections import get_collection

    coll = get_collection(slug)
    if coll is None:
        raise Http404('Подборка не найдена')

    base_qs = _catalog_base_qs(request).filter(coll.rule)

    f = ProductFilter(request.GET, queryset=base_qs)
    filtered_qs = f.qs
    tech_qs = apply_tech_filters(request.GET, filtered_qs)

    ordering_key = request.GET.get('ordering', '')
    ordering_map = {
        'price': F('ric').asc(nulls_last=True),
        '-price': F('ric').desc(nulls_last=True),
        '-created': F('created_at').desc(),
        'title': F('title').asc(),
    }
    if ordering_key in ordering_map:
        ordered_qs = tech_qs.order_by(ordering_map[ordering_key])
    else:
        ordered_qs = tech_qs.order_by(
            F('is_crimea').desc(),
            F('stock__quantity').desc(nulls_last=True),
            'title',
        )

    paginator = Paginator(ordered_qs, 16)
    page = paginator.get_page(request.GET.get('page'))

    categories = (
        Category.objects
        .filter(sync_enabled=True)
        .annotate(product_count=Count('products', filter=Q(products__is_active=True)))
        .filter(product_count__gt=0)
        .order_by('order', 'title')
    )

    context = {
        'filter': f,
        'page_obj': page,
        'categories': categories,
        'collection': coll,
        'show_price': request.user.is_authenticated and request.user.is_approved,
        'current_ordering': ordering_key,
        'facets': compute_facets(request.GET, base_qs),
        'tech_facets': compute_tech_facets(request.GET, None, filtered_qs),
    }

    template = (
        'catalog/partials/_catalog_content.html'
        if request.headers.get('HX-Request') == 'true'
        else 'catalog/collection.html'
    )
    return render(request, template, context)
```

Добавить в импорты вверху `views.py`: `from django.http import Http404`.

- [ ] **Шаг 5: Добавить маршрут**

В `apps/catalog/urls.py` — новый маршрут **после** `catalog/`, чтобы `/catalog/`
не перехватывался:

```python
    path('catalog/<slug:slug>/', views.collection, name='collection'),
```

- [ ] **Шаг 6: Создать шаблон страницы**

Создать `templates/catalog/collection.html`:

```html
{% extends 'catalog/index.html' %}

{% block title %}{{ collection.h1 }} — SplitHome{% endblock %}

{% block catalog_heading %}
  <h1 class="text-2xl lg:text-3xl font-bold text-gray-900 mb-2">{{ collection.h1 }}</h1>
{% endblock %}

{% block catalog_seo_text %}
  <section class="card p-5 mt-6 text-sm leading-relaxed text-gray-600">
    {{ collection.seo_text }}
  </section>
{% endblock %}
```

В `templates/catalog/index.html` добавить два пустых блока — **вне** flex-контейнера
колонок. Блоки нельзя класть внутрь `_results.html`: это `<main id="catalog-results">`,
цель htmx-подмены, её содержимое перезатирается при каждом изменении фильтра.

Было (строки 3-4 и хвост файла):

```html
{% block content %}
<div class="flex flex-col lg:flex-row gap-4 lg:gap-6">
```

Стало:

```html
{% block content %}
{% block catalog_heading %}{% endblock %}
<div class="flex flex-col lg:flex-row gap-4 lg:gap-6">
```

И в хвосте, после закрывающего `</div>` flex-контейнера, перед `<script>`:

```html
</div>

{% block catalog_seo_text %}{% endblock %}

<script>
```

Собственного `<h1>` в каталоге нет (только `<h2>Каталог</h2>` в сайдбаре) — обычный
каталог оставляет оба блока пустыми, заголовок появляется только на подборке.

- [ ] **Шаг 7: Добавить подборки в sitemap**

В `apps/catalog/sitemaps.py` добавить класс, затем зарегистрировать его в
`splithome/urls.py`: в импорт на строке 11 добавить `CollectionSitemap`, а в словарь
`sitemaps` (строка 13) — запись `'collections': CollectionSitemap`.

```python
class CollectionSitemap(Sitemap):
    changefreq = 'weekly'
    priority = 0.7

    def items(self):
        from .collections import COLLECTIONS
        return list(COLLECTIONS.values())

    def location(self, obj):
        return reverse('collection', args=[obj.slug])
```

- [ ] **Шаг 8: Запустить тесты**

Выполнить: `python manage.py test apps.catalog.tests --verbosity=2`
Ожидается: `OK` — и новые view-тесты, и старые `test_views_catalog`, `test_sitemap`.

- [ ] **Шаг 9: Коммит**

```bash
git add apps/catalog/views.py apps/catalog/urls.py apps/catalog/sitemaps.py templates/catalog/collection.html templates/catalog/index.html apps/catalog/tests/test_collections.py
git commit -m "feat(catalog): страница подборки /catalog/<slug>/

Общий base_qs вынесен из catalog(), подборка использует тот же листинг,
фильтры и правило «под заказ». Свой h1, SEO-текст, запись в sitemap."
```

---

## Задача 7: Фасета «Работает на обогрев до»

**Файлы:**
- Изменить: `apps/catalog/filters.py` (константы + фильтр `heating`)
- Изменить: `apps/catalog/facets.py` (подсчёт в `compute_facets`)
- Изменить: `templates/catalog/partials/_filters.html`
- Изменить: `apps/catalog/tests/test_filters.py`

**Интерфейсы:**
- Потребляет из задачи 1: `HEATING_THRESHOLDS`.
- Отдаёт: GET-параметр `?heating=-20` (повторяемый), `_heating_q(codes) -> Q`,
  ключ `heating` в словаре фасет.

- [ ] **Шаг 1: Написать падающий тест**

Дописать в `apps/catalog/tests/test_filters.py`:

```python
from apps.catalog.filters import ProductFilter, _heating_q


class HeatingFilterTest(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.category = Category.objects.create(
            title='Сплит-системы', slug='split-heatfilter', sync_enabled=True,
        )

    def _product(self, nc, temp):
        return Product.objects.create(
            nc_code=nc, articul=nc, category=self.category,
            title=f'AC {nc}', slug=f'ac-{nc}', heating_min_temp=temp,
        )

    def test_filter_minus_25_keeps_colder_only(self):
        self._product('NC-H20', -20)
        self._product('NC-H25', -25)
        self._product('NC-H30', -30)
        qs = Product.objects.filter(_heating_q(['-25']))
        self.assertEqual(
            set(qs.values_list('nc_code', flat=True)), {'NC-H25', 'NC-H30'},
        )

    def test_several_thresholds_take_the_warmest(self):
        # Выбраны -20 и -25 → показываем всё, что подходит хотя бы под один,
        # то есть от -20 и холоднее
        self._product('NC-M20', -20)
        self._product('NC-M15', -15)
        qs = Product.objects.filter(_heating_q(['-20', '-25']))
        self.assertEqual(set(qs.values_list('nc_code', flat=True)), {'NC-M20'})

    def test_empty_selection_no_filter(self):
        self.assertEqual(_heating_q([]), Q())

    def test_filterset_applies_heating(self):
        self._product('NC-F25', -25)
        self._product('NC-F15', -15)
        f = ProductFilter({'heating': ['-25']}, queryset=Product.objects.all())
        self.assertEqual(
            set(f.qs.values_list('nc_code', flat=True)), {'NC-F25'},
        )
```

Если в файле нет импортов `Q`, `Category`, `Product` — добавить.

- [ ] **Шаг 2: Запустить тест, убедиться что падает**

Выполнить: `python manage.py test apps.catalog.tests.test_filters.HeatingFilterTest --verbosity=2`
Ожидается: `ImportError: cannot import name '_heating_q'`

- [ ] **Шаг 3: Добавить фильтр**

В `apps/catalog/filters.py` рядом с другими константами:

```python
from .heating import HEATING_THRESHOLDS

# Фасета «Работает на обогрев до» — по Product.heating_min_temp (посчитан при
# синке, см. apps/catalog/heating.py). Значение чекбокса — сам порог.
HEATING_CHOICES = [(str(t), f'до {t} °C') for t in HEATING_THRESHOLDS]


def _heating_q(codes):
    """Фильтр по порогам обогрева. Несколько выбранных = самый тёплый из них
    (объединение множеств: -25 целиком входит в -20)."""
    thresholds = []
    for code in codes:
        try:
            thresholds.append(int(code))
        except (TypeError, ValueError):
            continue
    if not thresholds:
        return Q()
    return Q(heating_min_temp__lte=max(thresholds))
```

В классе `ProductFilter` добавить поле рядом с `inverter`:

```python
    heating = django_filters.MultipleChoiceFilter(
        choices=HEATING_CHOICES,
        method='filter_heating', label='Работает на обогрев до', conjoined=False,
    )
```

В `Meta.fields` добавить `'heating'`. И метод:

```python
    def filter_heating(self, queryset, name, value):
        q = _heating_q(value or [])
        return queryset.filter(q) if q else queryset
```

- [ ] **Шаг 4: Добавить подсчёт в фасеты**

В `apps/catalog/facets.py` в импорт из `.filters` добавить `HEATING_CHOICES, _heating_q`.
В `compute_facets` рядом с остальными:

```python
    selected_heating = set(get_data.getlist('heating'))
    qs_no_heating = _apply_filters_excluding(get_data, 'heating', base_qs)

    heating_facet = []
    for code, label in HEATING_CHOICES:
        n = qs_no_heating.filter(_heating_q([code])).count()
        if n == 0 and code not in selected_heating:
            continue
        heating_facet.append({
            'value':    code,
            'label':    label,
            'count':    n,
            'selected': code in selected_heating,
        })
```

И добавить `'heating': heating_facet` в возвращаемый словарь.

- [ ] **Шаг 5: Добавить блок в шаблон**

В `templates/catalog/partials/_filters.html` после блока «Площадь помещения»
(перед «Тип управления»):

```html
    <!-- Работает на обогрев до -->
    {% if facets.heating %}
    <div class="mb-4">
      <p class="text-xs font-semibold text-gray-500 mb-2 uppercase tracking-wide">Работает на обогрев до</p>
      <div class="space-y-1">
        {% for item in facets.heating %}
          <label class="flex items-center justify-between text-sm cursor-pointer
                        {% if item.count == 0 and not item.selected %}opacity-40{% endif %}">
            <span class="flex items-center gap-2">
              <input type="checkbox" name="heating" value="{{ item.value }}"
                     {% if item.selected %}checked{% endif %}
                     {% if item.count == 0 and not item.selected %}disabled{% endif %}
                     class="w-4 h-4 accent-orange-500">
              <span>{{ item.label }}</span>
            </span>
            <span class="text-xs text-gray-400">{{ item.count }}</span>
          </label>
        {% endfor %}
      </div>
    </div>
    {% endif %}
```

- [ ] **Шаг 6: Запустить тесты**

Выполнить: `python manage.py test apps.catalog.tests --verbosity=2`
Ожидается: `OK`, включая `test_dynamic_filters` и `test_views_catalog` без регрессий.

- [ ] **Шаг 7: Коммит**

```bash
git add apps/catalog/filters.py apps/catalog/facets.py templates/catalog/partials/_filters.html apps/catalog/tests/test_filters.py
git commit -m "feat(catalog): фасета «Работает на обогрев до»

Пороги -20/-25/-30 по Product.heating_min_temp, со счётчиками.
Доступна и в каталоге, и внутри подборки."
```

---

## Задача 8: Навигация и выкатка

**Файлы:**
- Изменить: `templates/catalog/index.html` (блок «Подборки» в сайдбаре)
- Изменить: `templates/partials/header.html` (ссылка в шапке)
- Изменить: `apps/catalog/views.py` (передать подборки в контекст обоих view)
- Изменить: `README.md` (раздел про подборки)

**Интерфейсы:**
- Потребляет из задачи 5: `COLLECTIONS`.
- Отдаёт: ключ `collections` в контексте `catalog()` и `collection()`.

- [ ] **Шаг 1: Передать реестр в контекст**

В `apps/catalog/views.py` в обоих view (`catalog` и `collection`) добавить в `context`:

```python
        'collections': list(COLLECTIONS.values()),
```

Импорт вверху файла: `from .collections import COLLECTIONS, get_collection`
(и убрать локальный импорт `get_collection` из тела `collection()`).

- [ ] **Шаг 2: Добавить блок в сайдбар**

В `templates/catalog/index.html` сразу после карточки со списком категорий:

```html
    <!-- Подборки — срезы каталога, не категории (товар остаётся в своей категории) -->
    {% if collections %}
    <div class="card p-5">
      <h2 class="font-bold text-base mb-3 text-gray-800">Подборки</h2>
      <div class="space-y-2">
        {% for coll in collections %}
          <a href="{% url 'collection' coll.slug %}"
             class="cat-btn {% if collection.slug == coll.slug %}is-active{% endif %}">
            <span>{{ coll.title }}</span>
          </a>
        {% endfor %}
      </div>
    </div>
    {% endif %}
```

- [ ] **Шаг 3: Добавить ссылку в шапку**

В `templates/partials/header.html` ссылку нужно добавить **в оба меню** — десктопное
и мобильное, у них разные классы.

Десктопное меню, после строки 13 (`<a href="/catalog/" class="nav-btn">Каталог</a>`):

```html
      <a href="/catalog/heat-pumps/" class="nav-btn">Тепловые насосы</a>
```

Мобильное меню, после строки 60 (`<a href="/catalog/" class="nav-btn justify-center">Каталог</a>`):

```html
      <a href="/catalog/heat-pumps/" class="nav-btn justify-center">Тепловые насосы</a>
```

Адрес зашит строкой, как у остальных пунктов этого меню (`/quiz/`, `/installation/`) —
`{% url %}` там не используется.

- [ ] **Шаг 4: Прогнать полный набор тестов**

Выполнить:
```bash
python manage.py test apps.catalog.tests apps.leads.tests apps.sync.tests apps.accounts.tests --verbosity=2
```
Ожидается: `OK`, регрессий нет.

- [ ] **Шаг 5: Дописать README**

В `README.md` после раздела «Bizdev-ключевое» добавить:

```markdown
- **Подборки** (`apps/catalog/collections.py`) — срезы каталога со своим адресом
  и SEO-текстом: товар остаётся в своей категории и одновременно попадает в подборку.
  Первая — «Тепловые насосы» (`/catalog/heat-pumps/`): сплит-системы с обогревом
  до −20 °C и ниже плюс паспортные теплонасосы Rusklimat. Признак считается при
  синке в `Product.heating_min_temp` (`apps/catalog/heating.py`), разовый пересчёт —
  `python manage.py backfill_heating --apply`.
```

- [ ] **Шаг 6: Коммит**

```bash
git add templates/catalog/index.html templates/partials/header.html apps/catalog/views.py README.md
git commit -m "feat(catalog): подборки в навигации + README

Блок «Подборки» в сайдбаре каталога и ссылка в шапке."
```

- [ ] **Шаг 7: Выкатка на прод**

```bash
ssh -i ~/.ssh/splithub_deploy root@213.109.202.45
cd /opt/oasis
git fetch origin && git checkout feature/heat-pumps-collection && git pull
docker compose exec web python manage.py migrate
docker compose exec web python manage.py backfill_heating          # сначала dry-run
docker compose exec web python manage.py backfill_heating --apply
docker compose restart web
```

- [ ] **Шаг 8: Проверка на проде**

```bash
curl -s -o /dev/null -w '%{http_code}\n' https://splithome.ru/catalog/heat-pumps/
curl -s 'https://splithome.ru/catalog/heat-pumps/' | grep -c 'product-card'
curl -s 'https://splithome.ru/catalog/heat-pumps/?with_order=1' | grep -c 'product-card'
curl -s -o /dev/null -w '%{http_code}\n' https://splithome.ru/sitemap.xml
```

Ожидается: 200 на странице подборки, порядка 16 карточек на первой странице (пагинация
по 16 при 42 позициях в наличии), больше карточек с `?with_order=1`, 200 на sitemap.
Итоговые числа сверить с разведкой: **42 позиции в наличии, 428 под заказ**
(цифры от 2026-08-28, после суточных синков могут слегка сдвинуться — важен порядок).

Проверить глазами: заголовок, SEO-текст под листингом, фасета «Работает на обогрев до»
со счётчиками, пункт «Подборки» в сайдбаре, ссылка в шапке на мобильном и десктопе.

---

## Порядок выполнения

Задачи 1 → 2 → 3 → 4 → 5 → 6 → 7 → 8 строго последовательно: каждая следующая
использует интерфейсы предыдущих. Задачи 4 и 5 независимы друг от друга — их можно
поменять местами, если удобнее.

## Проверка соответствия спецификации

| Требование спеки | Задача |
|---|---|
| Парсер трёх форматов, чистая функция | 1 |
| `heating_min_temp`, `is_heat_pump`, миграция | 2 |
| Заполнение из характеристик, «более холодная» из двух | 2 |
| Команда бэкфилла с dry-run | 3 |
| Заполнение при синке во всех трёх источниках | 4 |
| Regex Русклимата впускает теплонасосы, `is_heat_pump` по категории | 4 |
| Реестр подборок, правило `-20` + declared, `kind` отсекает аксессуары | 5 |
| Страница `/catalog/<slug>/`, свой h1 и SEO-текст, общий шаблон листинга | 6 |
| Показ «под заказ» по тому же правилу, что каталог | 6 |
| Подборки в sitemap | 6 |
| Фасета −20 / −25 / −30 | 7 |
| Пункт в дереве каталога и в шапке | 8 |
| Проверка чисел на проде (42 / 428) | 8 |
