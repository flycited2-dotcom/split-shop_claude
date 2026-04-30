# Спецификация: B2B-портал Oasis — продажа климатической техники

**Дата:** 2026-04-30  
**Домен:** oasis.com.ru  
**Поставщик API:** Бриз (api.breez.ru)  
**Статус:** Утверждена

---

## 1. Цель и аудитория

B2B-портал для оптовых продаж кондиционеров и климатической техники. Целевая аудитория — юридические лица: дилеры, монтажные организации, корпоративные закупщики. Физические лица не регистрируются.

**Цели:**
- Автоматизировать работу с каталогом и остатками через API Бриз
- Дать дилерам самостоятельный доступ к оптовым ценам и оформлению заказов
- Снизить нагрузку на менеджеров за счёт личных кабинетов и экспорта прайсов

---

## 2. Технический стек

| Компонент | Технология |
|---|---|
| Backend | Python 3.12, Django 5.x |
| База данных | PostgreSQL 16 |
| Кэш | Redis 7 |
| Очередь задач | Celery + Redis broker |
| Frontend | Django templates + Tailwind CSS 3 + HTMX |
| WSGI | Gunicorn |
| Web-сервер | Nginx (уже установлен на VPS) |
| Контейнеризация | Docker + Docker Compose |
| SSL | Let's Encrypt (certbot) |
| Экспорт Excel | openpyxl |
| Экспорт PDF | WeasyPrint |

---

## 3. Дизайн-система («Современный серый»)

| Токен | Значение |
|---|---|
| Фон страницы | `#F5F7FA` |
| Белые карточки | `#FFFFFF` с `box-shadow: 0 1px 3px rgba(0,0,0,0.1)` |
| Акцентный цвет | `#F97316` (оранжевый) |
| Основной текст | `#111827` |
| Второстепенный текст | `#6B7280` |
| Шрифт | Nunito Sans (Google Fonts) |
| Hover-эффекты | `transition: all 0.2s ease` |
| Радиус карточек | `border-radius: 12px` |
| Сетка каталога | 4 колонки desktop / 2 планшет / 1 мобильный |

---

## 4. Структура приложений Django

```
oasis/
├── apps/
│   ├── catalog/       — Category, Brand, Product, ProductImage, TechSpec, ProductTech
│   ├── stock/         — Stock (остатки, цены, склад)
│   ├── accounts/      — CustomUser (юрлицо), профиль, одобрение
│   ├── orders/        — Cart, CartItem, Order, OrderItem
│   ├── export/        — генерация Excel и PDF прайсов
│   └── sync/          — Celery задачи синхронизации с API Бриз
├── templates/
├── static/
├── oasis/
│   ├── settings/
│   │   ├── base.py
│   │   ├── production.py
│   │   └── local.py
│   ├── urls.py
│   └── celery.py
├── docker-compose.yml
├── Dockerfile
├── nginx.conf
└── .env
```

---

## 5. Модели данных

### catalog

```python
Category(id, title, slug, parent_id, order, breez_id)
Brand(id, title, slug, logo_url, site_url, order, breez_id)
Product(
    id, nc_code, articul, category, brand, series, title,
    price_wholesale,   # из поля price API — только для одобренных
    ric,               # рекомендованная розничная цена — для всех
    ric_currency,
    description, booklet_url, manual_url,
    video_youtube, video_rutube,
    is_active, created_at, updated_at
)
ProductImage(id, product, url, order)
TechSpec(id, breez_id, title, unit, data_type, group, category, order, is_filter)
ProductTech(id, product, spec, value)
```

### stock

```python
Stock(
    id, product,
    quantity, warehouse,
    price_base, ric, ric_currency,
    updated_at
)
```

### accounts

```python
CustomUser(
    AbstractUser +
    company_name, inn, kpp, legal_address, phone,
    contact_person,
    is_approved,       # одобрён менеджером
    approved_at, approved_by,
    discount_percent   # индивидуальная скидка (по умолчанию 0)
)
```

### orders

```python
Cart(id, user, created_at, updated_at)
CartItem(id, cart, product, quantity)
Order(
    id, user, status, created_at, updated_at,
    delivery_address, comment, total,
    manager_note
)
OrderItem(id, order, product, quantity, price_at_order, ric_at_order)
```

**Статусы заказа:** `new → confirmed → in_progress → shipped → delivered → cancelled`

---

## 6. Логика доступа и цен

| Пользователь | РИЦ | Опт. цена | Корзина | Экспорт |
|---|---|---|---|---|
| Анонимный | ✅ | ❌ | ❌ | ❌ |
| Зарегистрирован, ожидает одобрения | ✅ | ❌ | ❌ | ❌ |
| Одобренный дилер | ✅ | ✅ | ✅ | ✅ |
| Менеджер/Админ | ✅ | ✅ | ✅ | ✅ |

Оптовая цена с учётом скидки: `price_wholesale * (1 - discount_percent / 100)`

---

## 7. Страницы и URL-структура

| URL | Страница | Доступ |
|---|---|---|
| `/` | Главная | Все |
| `/catalog/` | Каталог с фильтрами | Все |
| `/catalog/<category-slug>/` | Каталог по категории | Все |
| `/product/<slug>/` | Карточка товара | Все |
| `/brands/` | Список брендов | Все |
| `/brands/<slug>/` | Товары бренда | Все |
| `/cart/` | Корзина | Одобренные |
| `/checkout/` | Оформление заказа | Одобренные |
| `/account/` | Личный кабинет | Авторизованные |
| `/account/orders/` | История заказов | Авторизованные |
| `/account/orders/<id>/` | Детали заказа | Авторизованные |
| `/export/price/excel/` | Скачать Excel прайс | Одобренные |
| `/export/price/pdf/` | Скачать PDF прайс | Одобренные |
| `/auth/register/` | Регистрация юрлица | Анонимные |
| `/auth/login/` | Вход | Анонимные |
| `/admin/` | Django Admin | Стафф |

---

## 8. Синхронизация с API Бриз

### Расписание Celery Beat

| Задача | Интервал | Эндпоинт |
|---|---|---|
| `sync_stock` | каждый час | `/leftoversnew/` |
| `sync_catalog` | каждые 4 часа | `/categories/`, `/brands/`, `/products/` |
| `sync_tech_specs` | каждые 24 часа | `/tech/?category=X` |

### Авторизация
```
Authorization: Basic Zmx5Y2l0ZWRAZ21haWwuY29tOmVhOGQ0YjA2OWEzMDlkMmUwNjFj
```

### Стратегия синхронизации
- При синхронизации — upsert по `nc_code` / `breez_id`
- Товары, которых нет в ответе API — помечаются `is_active=False`
- При первом запуске — полная загрузка всего каталога

### Кэш Redis

| Данные | TTL |
|---|---|
| Список товаров (постранично) | 30 мин |
| Карточка товара | 1 час |
| Остатки | 55 мин |
| Список брендов/категорий | 2 часа |

---

## 9. Экспорт прайс-листа

**Excel (openpyxl):**
- Колонки: Артикул, НС-код, Название, Бренд, Категория, Остаток, РИЦ, Опт. цена
- Один лист = весь каталог с текущими остатками
- Форматирование: шапка с цветом акцента, автоширина колонок

**PDF (WeasyPrint):**
- HTML-шаблон → PDF
- Логотип + дата + контакты в шапке
- Таблица товаров (артикул, название, цена, остаток)
- Постраничная разбивка

---

## 10. Уведомления по email

| Событие | Кому |
|---|---|
| Новая регистрация | Менеджеру |
| Пользователь одобрен | Пользователю |
| Новый заказ | Менеджеру + пользователю |
| Смена статуса заказа | Пользователю |

Транспорт: SMTP (настраивается через `.env`)

---

## 11. Docker Compose

```yaml
services:
  db:        PostgreSQL 16
  redis:     Redis 7-alpine
  web:       Django + Gunicorn, порт 8000
  celery:    Celery worker (4 воркера)
  beat:      Celery beat (планировщик)

Volumes:
  postgres_data, redis_data, static_files, media_files
```

**Nginx** (на хосте, не в контейнере):
- `oasis.com.ru` → `proxy_pass http://127.0.0.1:8000`
- `/static/` и `/media/` — прямая раздача
- HTTPS через Let's Encrypt

---

## 12. Переменные окружения (.env)

```
SECRET_KEY=
DEBUG=False
ALLOWED_HOSTS=oasis.com.ru

DB_NAME=oasis
DB_USER=oasis
DB_PASSWORD=
DB_HOST=db
DB_PORT=5432

REDIS_URL=redis://redis:6379/0

BREEZ_AUTH_HEADER=Basic Zmx5Y2l0ZWRAZ21haWwuY29tOmVhOGQ0YjA2OWEzMDlkMmUwNjFj
BREEZ_BASE_URL=https://api.breez.ru/v1/

EMAIL_HOST=
EMAIL_PORT=587
EMAIL_HOST_USER=
EMAIL_HOST_PASSWORD=
EMAIL_USE_TLS=True
DEFAULT_FROM_EMAIL=
MANAGER_EMAIL=
```

---

## 13. Критерии готовности

- [ ] Каталог синхронизируется с API Бриз автоматически
- [ ] Анонимный пользователь видит каталог и РИЦ
- [ ] Одобренный дилер видит опт. цены и может оформить заказ
- [ ] Экспорт Excel и PDF работает корректно
- [ ] Регистрация + одобрение менеджером через Django Admin
- [ ] Все страницы адаптивны (mobile-first)
- [ ] SSL включён, HTTP → HTTPS редирект
- [ ] Celery задачи выполняются по расписанию
