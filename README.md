# SplitHome

Розничный интернет-магазин кондиционеров и сплит-систем в Крыму
(Симферополь, Севастополь, Ялта, Евпатория, Феодосия, Керчь).
Автоматическая синхронизация каталога и остатков с тремя поставщиками
(Бриз, Rusklimat, Daichi), AI-подборщик за 6 шагов, форма «заказ в 1 клик»,
доставка и монтаж.

Production: <https://splithome.ru/>

## Стек

- Python 3.12, Django 5.2
- PostgreSQL, Redis (cache + Celery broker)
- Celery + django-celery-beat (расписание sync)
- htmx + Tailwind CSS (компилируемый из исходников, без CDN)
- nginx (TLS, статика), Hestia (mail server / DKIM)
- gunicorn, WeasyPrint (PDF-прайс), openpyxl (Excel-прайс)

## Структура приложений

```
apps/
├── accounts/      # CustomUser (физ/юр), регистрация, ЛК, signals
├── catalog/       # Product, Category, Brand, btu.py, фильтры, /availability/
├── stock/         # Stock (сводный) + WarehouseStock (per-warehouse)
├── orders/        # Cart, Order, checkout, история заказов
├── leads/         # QuickOrder, SelectionRequest, Quiz (AI-подбор)
├── sync/          # 3 поставщика: Breez (API), Rusklimat (REST), Daichi (B2B)
├── notifications/ # Telegram-уведомления через socat-proxy
└── export/        # Excel/PDF-прайс (для юрлиц)
```

## Быстрый старт

### Локально (Docker)

```bash
cp .env.example .env       # заполнить SECRET_KEY, DB_*, BREEZ_AUTH_HEADER, ...
docker compose build
docker compose up -d
docker compose exec web python manage.py migrate
docker compose exec web python manage.py createsuperuser
```

Откройте <http://localhost:8000/>.

### Локально (без Docker)

```bash
python -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
export DJANGO_SETTINGS_MODULE=splithome.settings.local
python manage.py migrate
python manage.py runserver
```

## Управление каталогом

| Команда | Назначение |
|---|---|
| `python manage.py sync_breez` | Полный sync каталога Бриза (товары + остатки) |
| `python manage.py sync_daichi` | Sync Daichi-каталога |
| `python manage.py sync_rusklimat_rest` | Sync Rusklimat через REST (JWT обновляется вручную раз в сутки до получения refresh-токена) |
| `python manage.py sync_breez_tech` | Характеристики (TechSpec) Бриза |
| `python manage.py sync_daichi_tech` | Характеристики Daichi |
| `python manage.py sync_rusklimat_rest --tech-only` | Характеристики Rusklimat |
| `python manage.py compute_btu` | Пересчитывает `Product.btu_calc` из tech_values (мощность охлаждения → площадь → артикул). Запускать после большой переcинхронизации |
| `python manage.py remap_categories` | Привязывает товары к мастер-категориям (бытовые/полупромышленные сплиты, мобильные и т.д.) |

Celery Beat ежечасно/каждые 4 часа дёргает sync Бриза и Daichi автоматически.
Rusklimat пока вручную (нужны API-credentials для JWT auto-refresh).

## Bizdev-ключевое

- **Скидка 15%** при регистрации физлица (`DISCOUNT_PERCENT_INDIVIDUAL` в settings).
  Применяется через `CustomUser.get_wholesale_price()` → `CartItem.subtotal` →
  `Order.total`.
- **Crimea-first** сортировка в каталоге: товары со складом «Симферополь»
  идут первыми, остальные «Под заказ из X» — следом.
- **AI-подборщик** (6 шагов): площадь → тип помещения → бюджет → инвертор →
  обогрев → цвет. На результате — round-robin 2+2+2 по поставщикам, 4-уровневая
  релаксация фильтров + спасательный 5-й уровень снятия BTU (когда `btu_calc=NULL`).
- **Подборки** (`apps/catalog/collections.py`) — срезы каталога со своим адресом
  и SEO-текстом: товар остаётся в своей категории и одновременно попадает в подборку
  (`Product.category` — ForeignKey, второй категории у товара быть не может).
  Первая — «Тепловые насосы» (`/catalog/heat-pumps/`): сплит-системы с обогревом
  до −20 °C и ниже плюс те, что поставщик сам назвал теплонасосом. Признак считается
  при синке в `Product.heating_min_temp` / `is_heat_pump` (`apps/catalog/heating.py`),
  разовый пересчёт для уже загруженных товаров — `python manage.py backfill_heating
  --apply`. Новая подборка = одна запись в `COLLECTIONS`, без миграций.

## Тесты

```bash
python manage.py test apps.catalog.tests apps.leads.tests apps.sync.tests apps.accounts.tests --verbosity=2
```

Стек — `django.test.TestCase` / `SimpleTestCase` + `unittest.mock`. Покрытие:
- `apps/catalog/btu.py` — все конвертации единиц, XIGMA/Ballu traps.
- `apps/leads/quiz_logic.py` — балансировка, 5 уровней релаксации.
- `apps/sync/warehouse_stock.py` — Crimea-detection, идемпотентность.
- `apps/sync/rusklimat_rest._sync_tech_specs` — v1/v2 форматы.
- `apps/sync/tasks._iter_leftoversnew` — 3 формата ответа Breez.
- View-тесты: quiz, catalog, /availability/, quick-order, dashboard.
- Регистрация: discount_percent при создании физлица.

## Деплой на прод

Боевой сайт — **212.116.115.150** (`/opt/oasis`); 213.109.202.45 только проксирует
на него и держит вторую копию приложения (её базу читает Telegram-бот отчётов).

На проде `docker-compose.yml` держит локальную правку (фиксированный IP контейнера
БД) — при обновлении ветки её нельзя затирать; бэкапы лежат рядом как
`docker-compose.yml.bak-*`.

`celery` и `beat` запускаются из образа `oasis-web` (`image:`, а не `build:`) — это
одно и то же приложение, отдельная сборка давала три почти одинаковых образа по
~3.5 ГБ. Собирать нужно только `web`.

```bash
ssh prod
cd /opt/oasis
git pull
docker compose build web            # Tailwind компилируется внутри образа
docker compose up -d web celery beat
docker compose exec web python manage.py migrate
docker compose exec web python manage.py collectstatic --no-input
# ВАЖНО: collectstatic пишет в docker-volume, а nginx раздаёт /static/ из
# ХОСТОВОЙ папки /opt/oasis/staticfiles — без копирования сайт продолжит
# отдавать старый CSS (2026-08-29 он отставал на два месяца).
docker compose cp web:/app/staticfiles/. /opt/oasis/staticfiles/
```

Статика отдаётся с `max-age=2592000` и без хэша в имени, поэтому в `base.html`
к CSS добавляется `?v={{ STATIC_VERSION }}` — метка берётся из mtime собранного
`tailwind.css` (`apps/catalog/context_processors.static_version`). Без неё
вернувшийся посетитель месяц видит старую вёрстку.

Подробности — `HANDOFF.md`.

## Полезные документы

- `HANDOFF.md` — детальная история проекта, текущий status, prod HEAD.
- `docs/superpowers/specs/` — спецификации фич.
- `docs/superpowers/plans/` — планы реализации.

## Контакты

Email: <flycited@gmail.com>. Поддержка клиентов: +7 978 579-29-95.
