# HANDOFF: Oasis B2B Portal — Передача проекта

**Дата создания архива:** 2026-05-01
**Прогресс:** 6/12 задач (50%)
**Ветка:** `develop` (запушена в GitHub)
**Репозиторий:** https://github.com/flycited2-dotcom/ClaudeCode_site_split

---

## 1. Что это за проект

B2B-портал для оптовой продажи климатической техники (кондиционеры) на домене **oasis.com.ru**. Бэкенд интегрирован с API поставщика **Бриз** (api.breez.ru). Только юридические лица регистрируются и получают доступ к оптовым ценам после одобрения менеджером.

---

## 2. Технологический стек

| Слой | Технология |
|---|---|
| Backend | Python 3.12, Django 5.2 |
| База данных | PostgreSQL 16 |
| Кэш + Очередь | Redis 7 |
| Очередь задач | Celery 5 + Celery Beat |
| Frontend | Django templates + Tailwind CSS 3 (CDN) + HTMX 1.9 |
| WSGI | Gunicorn |
| Web | Nginx (на VPS, не в контейнере) |
| Контейнеризация | Docker + Docker Compose |
| Экспорт | openpyxl (Excel), WeasyPrint (PDF) |

**Дизайн-тема:** «Современный серый» — фон `#F5F7FA`, акцент `#F97316` (оранжевый), шрифт Nunito Sans.

---

## 3. Учётные данные API Бриз

```
Login: flycited@gmail.com
Password: ea8d4b069a309d2e061c
Authorization Header: Basic Zmx5Y2l0ZWRAZ21haWwuY29tOmVhOGQ0YjA2OWEzMDlkMmUwNjFj
Base URL: https://api.breez.ru/v1/
```

Уже прописано в `.env.example` как placeholder, реальные значения должны быть в `.env` (не коммитится).

---

## 4. Документация проекта (читать обязательно)

| Файл | Что внутри |
|---|---|
| `docs/superpowers/specs/2026-04-30-oasis-b2b-portal-design.md` | Полная спецификация: модели, страницы, доступ, дизайн |
| `docs/superpowers/plans/2026-04-30-oasis-b2b-portal.md` | План на 12 задач с готовым кодом для каждой |
| `HANDOFF.md` | Этот файл |

---

## 5. Что СДЕЛАНО (задачи 1–6)

### ✅ Задача 1: Docker + структура Django-проекта
- `Dockerfile`, `docker-compose.yml` (5 сервисов: db, redis, web, celery, beat)
- `.env.example` с плейсхолдерами
- `requirements.txt` (14 пакетов)
- `oasis/settings/{base,local,production}.py`
- `oasis/celery.py`, `oasis/wsgi.py`, `manage.py`
- Скелет всех 6 приложений: `apps/{catalog,stock,accounts,orders,export,sync}/`

### ✅ Задача 2: Модели каталога (`apps/catalog/`)
- `Category` (древовидная, breez_id, slug, parent)
- `Brand` (breez_id, slug, logo_url)
- `Product` (nc_code, articul, цены price_wholesale + ric, описания, видео)
- `ProductImage` (галерея)
- `TechSpec` + `ProductTech` (тех. характеристики)
- Admin для всех моделей с inlines

### ✅ Задача 3: Stock + Accounts
- `apps/stock/models.py:Stock` — OneToOne к Product, quantity, warehouse, price_base
- `apps/accounts/models.py:CustomUser` — наследник AbstractUser:
  - Поля юрлица: company_name, inn, kpp, legal_address, phone, contact_person
  - Поля одобрения: is_approved, approved_at, approved_by, discount_percent
  - Метод `get_wholesale_price(price)` — возвращает Decimal с учётом скидки
- `apps/accounts/admin.py` — action `approve_users` отправляет email пользователю
- `apps/accounts/signals.py` — post_save уведомляет менеджера при регистрации

### ✅ Задача 4: Orders
- `Cart` (OneToOne user, properties total/count)
- `CartItem` (unique_together, subtotal через get_wholesale_price)
- `Order` (6 статусов: new/confirmed/in_progress/shipped/delivered/cancelled)
- `OrderItem` (snapshot полей price_at_order, ric_at_order)
- `apps/orders/context_processors.py:cart_count` — для всех шаблонов
- Admin с inlines для Cart и Order

### ✅ Задача 5: BreezClient (`apps/sync/client.py`)
- Класс `BreezClient` с 7 методами:
  - `get_categories()`, `get_brands()`, `get_products()`
  - `get_tech_for_category(id)`, `get_tech_for_product(nc)`
  - `get_stock()`, `get_stock_by_nc(nc)`
- Корректная обработка 4 типов ошибок: Timeout, JSONDecodeError, HTTPError, RequestException
- 8 unit-тестов в `apps/sync/tests/test_client.py`

### ✅ Задача 6: Celery Sync Tasks (`apps/sync/tasks.py`)
- 5 задач: `sync_categories`, `sync_brands`, `sync_products`, `sync_stock`, `sync_catalog`
- `sync_products` обёрнут в `transaction.atomic()`, удаляет неактивные товары
- Парные изображения: на каждый sync товара — delete + bulk_create
- Management command: `python manage.py sync_all` с флагами `--catalog-only`, `--stock-only`
- Расписание Celery Beat в `oasis/settings/base.py`:
  - `sync.sync_stock` — каждый час в xx:05
  - `sync.sync_catalog` — каждые 4 часа

---

## 6. Что ОСТАЛОСЬ (задачи 7–12)

### ❌ Задача 7: Base-шаблон + URL-структура
**Файлы создать:**
- `templates/base.html` — каркас с Tailwind CDN, HTMX, Nunito Sans
- `templates/partials/header.html` — навигация, корзина, login
- `templates/partials/footer.html`
- `oasis/urls.py` — обновить, подключить URL всех приложений

Готовый код в плане → раздел «Задача 7».

### ❌ Задача 8: Главная + каталог + карточка товара
**Файлы создать:**
- `apps/catalog/views.py` — home, catalog, product_detail, brands_list
- `apps/catalog/urls.py`
- `apps/catalog/filters.py` — django-filter (бренд, категория, in_stock, поиск)
- `templates/home.html`
- `templates/catalog/index.html`
- `templates/catalog/product_detail.html`
- `templates/partials/product_card.html`

Готовый код в плане → раздел «Задача 8».

### ❌ Задача 9: Регистрация, вход, личный кабинет
**Файлы создать:**
- `apps/accounts/forms.py` — RegistrationForm с реквизитами юрлица
- `apps/accounts/views.py` — register, login_view, logout_view, pending, dashboard
- `apps/accounts/urls.py` (для /auth/) и `apps/accounts/urls_account.py` (для /account/)
- `templates/accounts/{login,register,pending,dashboard}.html`

Готовый код в плане → раздел «Задача 9».

### ❌ Задача 10: Корзина с HTMX + оформление заказа
**Файлы создать:**
- `apps/orders/views.py` — cart_view, cart_add, cart_remove, cart_update, checkout, order_list, order_detail
- `apps/orders/urls.py`
- `apps/orders/forms.py` — CheckoutForm
- `templates/orders/{cart,checkout,order_list,order_detail}.html`
- `templates/orders/partials/cart_table.html` — для HTMX swap

Готовый код в плане → раздел «Задача 10».

### ❌ Задача 11: Excel + PDF экспорт прайс-листа
**Файлы создать:**
- `apps/export/excel.py` — `generate_price_excel(user)` через openpyxl
- `apps/export/pdf.py` — `generate_price_pdf(user, request)` через WeasyPrint
- `apps/export/views.py` — export_excel, export_pdf
- `apps/export/urls.py`
- `templates/export/price_pdf.html`

Готовый код в плане → раздел «Задача 11».

### ❌ Задача 12: Nginx + SSL + деплой
**Файлы создать:**
- `nginx.conf` — конфиг с SSL и reverse proxy
- `deploy.sh` — bash-скрипт первого деплоя на VPS
- `.claude/launch.json` — для Claude Code preview

**Действия на VPS** (нужны учётные данные SSH от пользователя):
- Установить Docker
- `git clone` проекта в `/opt/oasis`
- Получить SSL через certbot для oasis.com.ru
- Запустить `./deploy.sh`
- Создать суперпользователя

Готовый код в плане → раздел «Задача 12».

---

## 7. Как продолжать работу (Subagent-Driven Development)

Пользователь выбрал режим **Subagent (быстрее)**. Workflow:

1. **Контроллер (главный Claude)** читает следующую задачу из плана
2. Отправляет **Implementer subagent** с полным текстом задачи
3. После завершения → **Spec Reviewer** проверяет соответствие плану
4. Затем → **Code Quality Reviewer** (через `superpowers:code-reviewer`)
5. Если есть issues → **Fix subagent** исправляет
6. Только после ✅ обоих ревью — следующая задача

**Полезные подскиллы:**
- `superpowers:subagent-driven-development` — основной воркфлоу
- `superpowers:executing-plans` — альтернатива для in-session
- `superpowers:test-driven-development` — для написания тестов

**Команда для запуска ревью качества:**
```
Task tool (superpowers:code-reviewer):
  WHAT_WAS_IMPLEMENTED: ...
  PLAN_OR_REQUIREMENTS: Task N from docs/superpowers/plans/...
  BASE_SHA: <commit-before-task>
  HEAD_SHA: <commit-after-task>
```

---

## 8. История коммитов (на момент архивации)

```
fbb8846  fix: sync tasks — dead imports, atomic, image edge, stock counts
9f69077  feat: Celery sync tasks + sync_all management command
90d4dde  fix: JSONDecodeError exception ordering
541a83d  feat: BreezClient HTTP client with 7 tests
621c38e  fix: orders Decimal types, N+1, CartItemInline
a1c980c  feat: Cart, Order models
1707f5c  fix: Decimal arithmetic, validators
eeaa907  feat: Stock and CustomUser models
840e83e  fix: catalog slug collision, None-brand bug
e91bd9f  feat: catalog models
9f5ff1b  fix: security and config issues
0a52656  feat: project foundation
fcd1bb3  docs: project spec and implementation plan
```

---

## 9. Известные ограничения / TODO

1. **Docker не запускался локально** — все коммиты только из исходного кода. Первый запуск + миграции произойдёт на VPS.
2. **API ключ публичен** — пользователь явно сказал использовать текущий ключ. При публичном репо его лучше ротировать.
3. **Тесты только для BreezClient** — для Celery-задач и моделей тестов пока нет (можно добавить).
4. **Нет CI/CD** — деплой ручной через `deploy.sh`.

---

## 10. Решения, требующие подтверждения от пользователя

При продолжении работы могут понадобиться:
- **Доступ SSH к VPS** для деплоя (Задача 12)
- **Email SMTP** для уведомлений (заполнить в .env)
- **Настоящий SECRET_KEY** для production (сгенерировать на VPS)
- **Логотип компании** для PDF-прайса (Задача 11)

---

## 11. Команды для быстрого старта (после распаковки архива)

```bash
# 1. Распаковать в нужное место
unzip oasis-b2b-portal-2026-05-01.zip
cd oasis-b2b-portal

# 2. Создать .env из примера
cp .env.example .env
# Отредактировать .env (заполнить реальные значения, особенно SECRET_KEY)

# 3. Поднять Docker (требует Docker Desktop / Docker Engine)
docker compose build
docker compose up -d db redis
docker compose run --rm web python manage.py migrate
docker compose run --rm web python manage.py createsuperuser

# 4. Первая синхронизация с API Бриз
docker compose run --rm web python manage.py sync_all

# 5. Запустить всё
docker compose up

# 6. Открыть http://localhost:8000
```

---

## 12. Контакты / контекст пользователя

- Язык общения: **русский**
- Пользователь предпочитает **прямой стиль**, без воды
- Уже выбран дизайн (Вариант 2 — современный серый с оранжевым акцентом)
- Использует **Subagent-Driven Development** workflow
- Проект разрабатывается с нуля — никакого legacy кода
- Domain `oasis.com.ru` — будет настроен SSL через Let's Encrypt

---

**Удачи следующей модели! 🚀 Все ответы на «как сделать X» уже есть в плане.**
