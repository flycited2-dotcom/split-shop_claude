# План реализации B2B-портала Oasis

> **Для агентов:** ОБЯЗАТЕЛЬНЫЙ ПОДСКИЛЛ: используй superpowers:executing-plans для выполнения этого плана шаг за шагом.

**Цель:** Создать полноценный B2B-портал по продаже климатической техники на домене oasis.com.ru с интеграцией API Бриз.

**Архитектура:** Django 5 монолит с серверными шаблонами (Tailwind CSS + HTMX), PostgreSQL как основная БД, Redis для кэша и очереди Celery. Синхронизация каталога и остатков с api.breez.ru по расписанию.

**Стек:** Python 3.12, Django 5.2, PostgreSQL 16, Redis 7, Celery 5, Tailwind CSS 3, HTMX 1.9, Docker Compose, Gunicorn, Nginx, openpyxl, WeasyPrint.

---

## Карта файлов проекта

```
oasis/                          — корень Django-проекта
├── Dockerfile
├── docker-compose.yml
├── .env.example
├── requirements.txt
├── manage.py
├── oasis/
│   ├── settings/
│   │   ├── base.py             — общие настройки
│   │   ├── local.py            — для разработки
│   │   └── production.py       — для VPS
│   ├── urls.py                 — корневые URL
│   ├── celery.py               — конфигурация Celery
│   └── wsgi.py
├── apps/
│   ├── catalog/
│   │   ├── models.py           — Category, Brand, Product, ProductImage, TechSpec, ProductTech
│   │   ├── views.py            — каталог, карточка товара, бренды
│   │   ├── urls.py
│   │   ├── admin.py
│   │   └── filters.py         — django-filter для каталога
│   ├── stock/
│   │   ├── models.py           — Stock (остатки)
│   │   └── admin.py
│   ├── accounts/
│   │   ├── models.py           — CustomUser
│   │   ├── views.py            — регистрация, вход, ЛК
│   │   ├── urls.py
│   │   ├── forms.py
│   │   └── admin.py            — одобрение пользователей
│   ├── orders/
│   │   ├── models.py           — Cart, CartItem, Order, OrderItem
│   │   ├── views.py            — корзина (HTMX), оформление
│   │   ├── urls.py
│   │   ├── forms.py
│   │   └── admin.py
│   ├── export/
│   │   ├── views.py            — скачать Excel / PDF
│   │   ├── excel.py            — генерация Excel (openpyxl)
│   │   └── pdf.py              — генерация PDF (WeasyPrint)
│   └── sync/
│       ├── client.py           — HTTP-клиент к api.breez.ru
│       ├── tasks.py            — Celery задачи
│       └── management/commands/sync_all.py
├── templates/
│   ├── base.html
│   ├── home.html
│   ├── partials/
│   │   ├── header.html
│   │   ├── footer.html
│   │   └── product_card.html
│   ├── catalog/
│   │   ├── index.html
│   │   └── product_detail.html
│   ├── accounts/
│   │   ├── login.html
│   │   ├── register.html
│   │   ├── pending.html
│   │   └── dashboard.html
│   └── orders/
│       ├── cart.html
│       ├── checkout.html
│       ├── order_list.html
│       └── order_detail.html
└── static/
    ├── css/tailwind.css
    └── js/htmx.min.js
```

---

## ФАЗА 1: Фундамент проекта

---

### Задача 1: Docker + структура Django-проекта

**Файлы:**
- Создать: `requirements.txt`
- Создать: `Dockerfile`
- Создать: `docker-compose.yml`
- Создать: `.env.example`
- Создать: `oasis/settings/base.py`
- Создать: `oasis/settings/local.py`
- Создать: `oasis/settings/production.py`
- Создать: `oasis/celery.py`

- [ ] **Шаг 1: Создать requirements.txt**

```
Django==5.2
psycopg2-binary==2.9.9
redis==5.0.1
celery==5.3.6
django-redis==5.4.0
django-filter==24.1
Pillow==10.2.0
openpyxl==3.1.2
WeasyPrint==62.3
gunicorn==21.2.0
python-decouple==3.8
requests==2.31.0
django-htmx==1.17.3
```

- [ ] **Шаг 2: Создать Dockerfile**

```dockerfile
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update && apt-get install -y \
    libpango-1.0-0 libpangoft2-1.0-0 libffi-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
```

- [ ] **Шаг 3: Создать docker-compose.yml**

```yaml
version: "3.9"

services:
  db:
    image: postgres:16-alpine
    volumes:
      - postgres_data:/var/lib/postgresql/data
    env_file: .env
    environment:
      POSTGRES_DB: ${DB_NAME}
      POSTGRES_USER: ${DB_USER}
      POSTGRES_PASSWORD: ${DB_PASSWORD}

  redis:
    image: redis:7-alpine
    volumes:
      - redis_data:/data

  web:
    build: .
    command: gunicorn oasis.wsgi:application --bind 0.0.0.0:8000 --workers 4
    volumes:
      - static_files:/app/staticfiles
      - media_files:/app/media
    ports:
      - "8000:8000"
    env_file: .env
    depends_on:
      - db
      - redis

  celery:
    build: .
    command: celery -A oasis worker -l info -c 4
    env_file: .env
    depends_on:
      - db
      - redis

  beat:
    build: .
    command: celery -A oasis beat -l info --scheduler django_celery_beat.schedulers:DatabaseScheduler
    env_file: .env
    depends_on:
      - db
      - redis

volumes:
  postgres_data:
  redis_data:
  static_files:
  media_files:
```

- [ ] **Шаг 4: Создать .env.example**

```
SECRET_KEY=замените-на-случайную-строку
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1,oasis.com.ru

DB_NAME=oasis
DB_USER=oasis
DB_PASSWORD=сильный-пароль
DB_HOST=db
DB_PORT=5432

REDIS_URL=redis://redis:6379/0

BREEZ_AUTH_HEADER=Basic Zmx5Y2l0ZWRAZ21haWwuY29tOmVhOGQ0YjA2OWEzMDlkMmUwNjFj
BREEZ_BASE_URL=https://api.breez.ru/v1/

EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_HOST_USER=
EMAIL_HOST_PASSWORD=
EMAIL_USE_TLS=True
DEFAULT_FROM_EMAIL=noreply@oasis.com.ru
MANAGER_EMAIL=manager@oasis.com.ru
```

- [ ] **Шаг 5: Создать oasis/settings/base.py**

```python
from pathlib import Path
from decouple import config, Csv

BASE_DIR = Path(__file__).resolve().parent.parent.parent

SECRET_KEY = config('SECRET_KEY')
DEBUG = config('DEBUG', default=False, cast=bool)
ALLOWED_HOSTS = config('ALLOWED_HOSTS', cast=Csv())

DJANGO_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
]

THIRD_PARTY_APPS = [
    'django_htmx',
    'django_filter',
    'django_celery_beat',
]

LOCAL_APPS = [
    'apps.catalog',
    'apps.stock',
    'apps.accounts',
    'apps.orders',
    'apps.export',
    'apps.sync',
]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'django_htmx.middleware.HtmxMiddleware',
]

ROOT_URLCONF = 'oasis.urls'

TEMPLATES = [{
    'BACKEND': 'django.template.backends.django.DjangoTemplates',
    'DIRS': [BASE_DIR / 'templates'],
    'APP_DIRS': True,
    'OPTIONS': {
        'context_processors': [
            'django.template.context_processors.debug',
            'django.template.context_processors.request',
            'django.contrib.auth.context_processors.auth',
            'django.contrib.messages.context_processors.messages',
            'apps.orders.context_processors.cart_count',
        ],
    },
}]

WSGI_APPLICATION = 'oasis.wsgi.application'

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': config('DB_NAME'),
        'USER': config('DB_USER'),
        'PASSWORD': config('DB_PASSWORD'),
        'HOST': config('DB_HOST', default='localhost'),
        'PORT': config('DB_PORT', default='5432'),
    }
}

AUTH_USER_MODEL = 'accounts.CustomUser'
LOGIN_URL = '/auth/login/'
LOGIN_REDIRECT_URL = '/account/'
LOGOUT_REDIRECT_URL = '/'

CACHES = {
    'default': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': config('REDIS_URL'),
        'OPTIONS': {'CLIENT_CLASS': 'django_redis.client.DefaultClient'},
    }
}

CELERY_BROKER_URL = config('REDIS_URL')
CELERY_RESULT_BACKEND = config('REDIS_URL')
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_TIMEZONE = 'Europe/Moscow'

STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

LANGUAGE_CODE = 'ru-ru'
TIME_ZONE = 'Europe/Moscow'
USE_I18N = True
USE_TZ = True
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

BREEZ_AUTH_HEADER = config('BREEZ_AUTH_HEADER')
BREEZ_BASE_URL = config('BREEZ_BASE_URL', default='https://api.breez.ru/v1/')

EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = config('EMAIL_HOST', default='')
EMAIL_PORT = config('EMAIL_PORT', default=587, cast=int)
EMAIL_HOST_USER = config('EMAIL_HOST_USER', default='')
EMAIL_HOST_PASSWORD = config('EMAIL_HOST_PASSWORD', default='')
EMAIL_USE_TLS = config('EMAIL_USE_TLS', default=True, cast=bool)
DEFAULT_FROM_EMAIL = config('DEFAULT_FROM_EMAIL', default='noreply@oasis.com.ru')
MANAGER_EMAIL = config('MANAGER_EMAIL', default='')
```

- [ ] **Шаг 6: Создать oasis/settings/local.py**

```python
from .base import *

DEBUG = True
ALLOWED_HOSTS = ['*']
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
```

- [ ] **Шаг 7: Создать oasis/settings/production.py**

```python
from .base import *

DEBUG = False
SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
```

- [ ] **Шаг 8: Создать oasis/celery.py**

```python
import os
from celery import Celery

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'oasis.settings.production')

app = Celery('oasis')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()
```

- [ ] **Шаг 9: Создать oasis/__init__.py**

```python
from .celery import app as celery_app
__all__ = ('celery_app',)
```

- [ ] **Шаг 10: Инициализировать Django-проект**

```bash
mkdir -p apps/catalog apps/stock apps/accounts apps/orders apps/export apps/sync
touch apps/__init__.py
for app in catalog stock accounts orders export sync; do
    touch apps/$app/__init__.py
done
cp .env.example .env
# Отредактировать .env под реальные данные
```

- [ ] **Шаг 11: Зафиксировать в git**

```bash
git init
echo "__pycache__/\n*.pyc\n.env\nstaticfiles/\nmedia/\n*.sqlite3" > .gitignore
git add .
git commit -m "feat: project foundation — Docker, Django settings, Celery"
```

---

### Задача 2: Модели каталога (catalog)

**Файлы:**
- Создать: `apps/catalog/models.py`
- Создать: `apps/catalog/admin.py`

- [ ] **Шаг 1: Написать модели**

```python
# apps/catalog/models.py
from django.db import models
from django.utils.text import slugify


class Category(models.Model):
    breez_id = models.IntegerField(unique=True)
    title = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255, unique=True)
    parent = models.ForeignKey('self', null=True, blank=True,
                               on_delete=models.SET_NULL, related_name='children')
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['order', 'title']
        verbose_name = 'Категория'
        verbose_name_plural = 'Категории'

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title, allow_unicode=True)
        super().save(*args, **kwargs)


class Brand(models.Model):
    breez_id = models.IntegerField(unique=True)
    title = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255, unique=True)
    logo_url = models.URLField(blank=True)
    site_url = models.URLField(blank=True)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['order', 'title']
        verbose_name = 'Бренд'
        verbose_name_plural = 'Бренды'

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title, allow_unicode=True)
        super().save(*args, **kwargs)


class Product(models.Model):
    nc_code = models.CharField(max_length=50, unique=True)
    articul = models.CharField(max_length=100, blank=True)
    category = models.ForeignKey(Category, null=True, blank=True,
                                 on_delete=models.SET_NULL, related_name='products')
    brand = models.ForeignKey(Brand, null=True, blank=True,
                              on_delete=models.SET_NULL, related_name='products')
    series = models.CharField(max_length=255, blank=True)
    title = models.CharField(max_length=500)
    slug = models.SlugField(max_length=500, unique=True)
    price_wholesale = models.DecimalField(max_digits=12, decimal_places=2,
                                          null=True, blank=True)
    ric = models.DecimalField(max_digits=12, decimal_places=2,
                              null=True, blank=True)
    ric_currency = models.CharField(max_length=10, default='RUB')
    description = models.TextField(blank=True)
    booklet_url = models.URLField(blank=True)
    manual_url = models.URLField(blank=True)
    video_youtube = models.URLField(blank=True)
    video_rutube = models.URLField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['title']
        verbose_name = 'Товар'
        verbose_name_plural = 'Товары'

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        if not self.slug:
            base = f"{self.brand}-{self.articul}" if self.articul else self.title
            self.slug = slugify(base, allow_unicode=True)
        super().save(*args, **kwargs)


class ProductImage(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE,
                                related_name='images')
    url = models.URLField()
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['order']

    def __str__(self):
        return f"Фото {self.product.title} #{self.order}"


class TechSpec(models.Model):
    breez_id = models.IntegerField(unique=True)
    title = models.CharField(max_length=255)
    unit = models.CharField(max_length=50, blank=True)
    data_type = models.CharField(max_length=50, blank=True)
    group = models.CharField(max_length=255, blank=True)
    category = models.ForeignKey(Category, null=True, blank=True,
                                 on_delete=models.SET_NULL, related_name='tech_specs')
    order = models.PositiveIntegerField(default=0)
    is_filter = models.BooleanField(default=False)

    class Meta:
        ordering = ['order']
        verbose_name = 'Характеристика'
        verbose_name_plural = 'Характеристики'

    def __str__(self):
        return self.title


class ProductTech(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE,
                                related_name='tech_values')
    spec = models.ForeignKey(TechSpec, on_delete=models.CASCADE)
    value = models.CharField(max_length=500)

    class Meta:
        unique_together = ('product', 'spec')

    def __str__(self):
        return f"{self.product.articul} — {self.spec.title}: {self.value}"
```

- [ ] **Шаг 2: Зарегистрировать в admin**

```python
# apps/catalog/admin.py
from django.contrib import admin
from .models import Category, Brand, Product, ProductImage, TechSpec, ProductTech


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ['title', 'parent', 'order']
    prepopulated_fields = {'slug': ('title',)}


@admin.register(Brand)
class BrandAdmin(admin.ModelAdmin):
    list_display = ['title', 'order']
    prepopulated_fields = {'slug': ('title',)}


class ProductImageInline(admin.TabularInline):
    model = ProductImage
    extra = 0


class ProductTechInline(admin.TabularInline):
    model = ProductTech
    extra = 0


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ['title', 'articul', 'nc_code', 'brand', 'category',
                    'price_wholesale', 'ric', 'is_active']
    list_filter = ['brand', 'category', 'is_active']
    search_fields = ['title', 'articul', 'nc_code']
    prepopulated_fields = {'slug': ('title',)}
    inlines = [ProductImageInline, ProductTechInline]


@admin.register(TechSpec)
class TechSpecAdmin(admin.ModelAdmin):
    list_display = ['title', 'unit', 'category', 'is_filter', 'order']
```

- [ ] **Шаг 3: Создать и применить миграцию**

```bash
docker compose run --rm web python manage.py makemigrations catalog
docker compose run --rm web python manage.py migrate
```

Ожидаемый вывод: `Applying catalog.0001_initial... OK`

- [ ] **Шаг 4: Зафиксировать**

```bash
git add apps/catalog/
git commit -m "feat: catalog models — Category, Brand, Product, TechSpec"
```

---

### Задача 3: Модель остатков (stock) и пользователей (accounts)

**Файлы:**
- Создать: `apps/stock/models.py`
- Создать: `apps/accounts/models.py`
- Создать: `apps/accounts/admin.py`

- [ ] **Шаг 1: Модель Stock**

```python
# apps/stock/models.py
from django.db import models
from apps.catalog.models import Product


class Stock(models.Model):
    product = models.OneToOneField(Product, on_delete=models.CASCADE,
                                   related_name='stock')
    quantity = models.PositiveIntegerField(default=0)
    warehouse = models.CharField(max_length=255, blank=True)
    price_base = models.DecimalField(max_digits=12, decimal_places=2,
                                     null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Остаток'
        verbose_name_plural = 'Остатки'

    def __str__(self):
        return f"{self.product.articul}: {self.quantity} шт."

    @property
    def in_stock(self):
        return self.quantity > 0
```

- [ ] **Шаг 2: Модель CustomUser**

```python
# apps/accounts/models.py
from django.contrib.auth.models import AbstractUser
from django.db import models


class CustomUser(AbstractUser):
    company_name = models.CharField('Название компании', max_length=255, blank=True)
    inn = models.CharField('ИНН', max_length=12, blank=True)
    kpp = models.CharField('КПП', max_length=9, blank=True)
    legal_address = models.TextField('Юридический адрес', blank=True)
    phone = models.CharField('Телефон', max_length=20, blank=True)
    contact_person = models.CharField('Контактное лицо', max_length=255, blank=True)
    is_approved = models.BooleanField('Одобрен', default=False)
    approved_at = models.DateTimeField(null=True, blank=True)
    approved_by = models.ForeignKey('self', null=True, blank=True,
                                    on_delete=models.SET_NULL,
                                    related_name='approved_users')
    discount_percent = models.DecimalField('Скидка %', max_digits=5,
                                           decimal_places=2, default=0)

    class Meta:
        verbose_name = 'Пользователь'
        verbose_name_plural = 'Пользователи'

    def __str__(self):
        return f"{self.company_name or self.username} ({self.email})"

    def get_wholesale_price(self, price):
        """Вернуть оптовую цену с учётом скидки пользователя."""
        if price is None:
            return None
        discount = self.discount_percent / 100
        return round(price * (1 - discount), 2)
```

- [ ] **Шаг 3: Admin для пользователей с кнопкой одобрения**

```python
# apps/accounts/admin.py
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.utils import timezone
from .models import CustomUser


@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    list_display = ['username', 'email', 'company_name', 'inn',
                    'is_approved', 'date_joined']
    list_filter = ['is_approved', 'is_staff']
    search_fields = ['username', 'email', 'company_name', 'inn']
    actions = ['approve_users']

    fieldsets = UserAdmin.fieldsets + (
        ('Реквизиты компании', {
            'fields': ('company_name', 'inn', 'kpp', 'legal_address',
                       'phone', 'contact_person')
        }),
        ('Статус дилера', {
            'fields': ('is_approved', 'approved_at', 'approved_by',
                       'discount_percent')
        }),
    )

    def approve_users(self, request, queryset):
        for user in queryset.filter(is_approved=False):
            user.is_approved = True
            user.approved_at = timezone.now()
            user.approved_by = request.user
            user.save()
            # Уведомление отправляется в сигнале
    approve_users.short_description = 'Одобрить выбранных пользователей'
```

- [ ] **Шаг 4: Миграции и применение**

```bash
docker compose run --rm web python manage.py makemigrations accounts stock
docker compose run --rm web python manage.py migrate
```

- [ ] **Шаг 5: Зафиксировать**

```bash
git add apps/stock/ apps/accounts/
git commit -m "feat: Stock and CustomUser models with approval flow"
```

---

### Задача 4: Модели заказов (orders)

**Файлы:**
- Создать: `apps/orders/models.py`
- Создать: `apps/orders/context_processors.py`
- Создать: `apps/orders/admin.py`

- [ ] **Шаг 1: Модели Cart и Order**

```python
# apps/orders/models.py
from django.db import models
from django.conf import settings
from apps.catalog.models import Product


class Cart(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL,
                                on_delete=models.CASCADE, related_name='cart')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Корзина'
        verbose_name_plural = 'Корзины'

    def __str__(self):
        return f"Корзина {self.user}"

    @property
    def total(self):
        return sum(item.subtotal for item in self.items.all())

    @property
    def count(self):
        return self.items.aggregate(
            total=models.Sum('quantity'))['total'] or 0


class CartItem(models.Model):
    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1)

    class Meta:
        unique_together = ('cart', 'product')

    def __str__(self):
        return f"{self.product.articul} x{self.quantity}"

    @property
    def subtotal(self):
        price = self.cart.user.get_wholesale_price(self.product.price_wholesale)
        return (price or 0) * self.quantity


class Order(models.Model):
    STATUS_CHOICES = [
        ('new', 'Новый'),
        ('confirmed', 'Подтверждён'),
        ('in_progress', 'В обработке'),
        ('shipped', 'Отправлен'),
        ('delivered', 'Доставлен'),
        ('cancelled', 'Отменён'),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL,
                             on_delete=models.PROTECT, related_name='orders')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='new')
    delivery_address = models.TextField('Адрес доставки')
    comment = models.TextField('Комментарий', blank=True)
    total = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    manager_note = models.TextField('Заметка менеджера', blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Заказ'
        verbose_name_plural = 'Заказы'

    def __str__(self):
        return f"Заказ #{self.pk} — {self.user.company_name}"


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.PROTECT)
    quantity = models.PositiveIntegerField()
    price_at_order = models.DecimalField(max_digits=12, decimal_places=2)
    ric_at_order = models.DecimalField(max_digits=12, decimal_places=2,
                                       null=True, blank=True)

    def __str__(self):
        return f"{self.product.articul} x{self.quantity}"

    @property
    def subtotal(self):
        return self.price_at_order * self.quantity
```

- [ ] **Шаг 2: Контекст-процессор для счётчика корзины**

```python
# apps/orders/context_processors.py
def cart_count(request):
    if request.user.is_authenticated and request.user.is_approved:
        try:
            return {'cart_count': request.user.cart.count}
        except Exception:
            return {'cart_count': 0}
    return {'cart_count': 0}
```

- [ ] **Шаг 3: Миграции**

```bash
docker compose run --rm web python manage.py makemigrations orders
docker compose run --rm web python manage.py migrate
```

- [ ] **Шаг 4: Зафиксировать**

```bash
git add apps/orders/
git commit -m "feat: Cart, Order models with status flow"
```

---

## ФАЗА 2: Интеграция с API Бриз

---

### Задача 5: HTTP-клиент к API Бриз

**Файлы:**
- Создать: `apps/sync/client.py`

- [ ] **Шаг 1: Написать тест клиента**

```python
# apps/sync/tests/test_client.py
from unittest.mock import patch, Mock
from django.test import TestCase
from apps.sync.client import BreezClient


class BreezClientTest(TestCase):
    def setUp(self):
        self.client = BreezClient()

    @patch('apps.sync.client.requests.get')
    def test_get_categories_returns_list(self, mock_get):
        mock_get.return_value = Mock(
            status_code=200,
            json=lambda: [{'id': 1, 'title': 'Кондиционеры', 'chpu': 'konditsionery'}]
        )
        result = self.client.get_categories()
        self.assertIsInstance(result, list)
        self.assertEqual(result[0]['title'], 'Кондиционеры')

    @patch('apps.sync.client.requests.get')
    def test_returns_empty_list_on_error(self, mock_get):
        mock_get.return_value = Mock(
            status_code=200,
            json=lambda: {'error': 'Нет данных'}
        )
        result = self.client.get_categories()
        self.assertEqual(result, [])
```

- [ ] **Шаг 2: Запустить тест — убедиться в падении**

```bash
docker compose run --rm web python manage.py test apps.sync.tests.test_client -v 2
```

Ожидаемый вывод: `ImportError: cannot import name 'BreezClient'`

- [ ] **Шаг 3: Реализовать клиент**

```python
# apps/sync/client.py
import logging
import requests
from django.conf import settings

logger = logging.getLogger(__name__)


class BreezClient:
    def __init__(self):
        self.base_url = settings.BREEZ_BASE_URL
        self.headers = {
            'Authorization': settings.BREEZ_AUTH_HEADER,
            'Accept': 'application/json',
        }
        self.timeout = 60

    def _get(self, endpoint, params=None):
        url = f"{self.base_url}{endpoint}"
        try:
            resp = requests.get(url, headers=self.headers,
                                params=params, timeout=self.timeout)
            resp.raise_for_status()
            data = resp.json()
            if isinstance(data, dict) and 'error' in data:
                logger.warning("Breez API error for %s: %s", endpoint, data['error'])
                return []
            return data if isinstance(data, list) else []
        except Exception as exc:
            logger.error("Breez API request failed for %s: %s", endpoint, exc)
            return []

    def get_categories(self):
        return self._get('categories/')

    def get_brands(self):
        return self._get('brands/')

    def get_products(self):
        return self._get('products/')

    def get_tech_for_category(self, category_id):
        return self._get('tech/', params={'category': category_id})

    def get_tech_for_product(self, product_id):
        return self._get('tech/', params={'id': product_id})

    def get_stock(self):
        return self._get('leftoversnew/')

    def get_stock_by_nc(self, nc_code):
        return self._get('leftovers/', params={'nc': nc_code})
```

- [ ] **Шаг 4: Запустить тест — убедиться в успехе**

```bash
docker compose run --rm web python manage.py test apps.sync.tests.test_client -v 2
```

Ожидаемый вывод: `OK (2 tests)`

- [ ] **Шаг 5: Зафиксировать**

```bash
git add apps/sync/
git commit -m "feat: BreezClient — HTTP client for api.breez.ru"
```

---

### Задача 6: Celery-задачи синхронизации

**Файлы:**
- Создать: `apps/sync/tasks.py`
- Создать: `apps/sync/management/commands/sync_all.py`

- [ ] **Шаг 1: Написать задачи Celery**

```python
# apps/sync/tasks.py
import logging
from celery import shared_task
from django.utils.text import slugify
from apps.sync.client import BreezClient
from apps.catalog.models import Category, Brand, Product, ProductImage, TechSpec, ProductTech
from apps.stock.models import Stock

logger = logging.getLogger(__name__)
client = BreezClient()


@shared_task(name='sync.sync_categories')
def sync_categories():
    data = client.get_categories()
    created = updated = 0
    for item in data:
        slug = slugify(item.get('chpu') or item.get('title', ''), allow_unicode=True)
        obj, is_new = Category.objects.update_or_create(
            breez_id=item['id'],
            defaults={
                'title': item.get('title', ''),
                'slug': slug or f"cat-{item['id']}",
                'order': item.get('order', 0),
            }
        )
        if is_new:
            created += 1
        else:
            updated += 1
    # Установить родителей вторым проходом
    for item in data:
        parent_id = item.get('level')
        if parent_id:
            try:
                parent = Category.objects.get(breez_id=parent_id)
                Category.objects.filter(breez_id=item['id']).update(parent=parent)
            except Category.DoesNotExist:
                pass
    logger.info("Categories sync: %d created, %d updated", created, updated)
    return {'created': created, 'updated': updated}


@shared_task(name='sync.sync_brands')
def sync_brands():
    data = client.get_brands()
    created = updated = 0
    for item in data:
        slug = slugify(item.get('chpu') or item.get('title', ''), allow_unicode=True)
        _, is_new = Brand.objects.update_or_create(
            breez_id=item['id'],
            defaults={
                'title': item.get('title', ''),
                'slug': slug or f"brand-{item['id']}",
                'logo_url': item.get('image', ''),
                'site_url': item.get('url', ''),
                'order': item.get('order', 0),
            }
        )
        if is_new:
            created += 1
        else:
            updated += 1
    logger.info("Brands sync: %d created, %d updated", created, updated)
    return {'created': created, 'updated': updated}


@shared_task(name='sync.sync_products')
def sync_products():
    data = client.get_products()
    nc_codes = set()
    created = updated = 0

    for item in data:
        nc = item.get('nc')
        if not nc:
            continue
        nc_codes.add(nc)

        category = None
        if item.get('category_id'):
            category = Category.objects.filter(breez_id=item['category_id']).first()

        brand = None
        if item.get('brand'):
            brand = Brand.objects.filter(title=item['brand']).first()

        title = item.get('title', '')
        articul = item.get('articul', '')
        base_slug = slugify(f"{articul}-{nc}", allow_unicode=True) or f"product-{nc}"

        obj, is_new = Product.objects.update_or_create(
            nc_code=nc,
            defaults={
                'articul': articul,
                'category': category,
                'brand': brand,
                'series': item.get('series', ''),
                'title': title,
                'slug': base_slug,
                'price_wholesale': item.get('price') or None,
                'ric': item.get('ric') or None,
                'ric_currency': item.get('ric_currency', 'RUB'),
                'description': item.get('description', ''),
                'booklet_url': item.get('booklet', ''),
                'manual_url': item.get('manual', ''),
                'video_youtube': item.get('video_youtube', ''),
                'video_rutube': item.get('video_rutube', ''),
                'is_active': True,
            }
        )
        if is_new:
            created += 1
        else:
            updated += 1

        # Синхронизировать изображения
        images = item.get('images', [])
        if images:
            obj.images.all().delete()
            ProductImage.objects.bulk_create([
                ProductImage(product=obj, url=url, order=i)
                for i, url in enumerate(images)
            ])

    # Деактивировать товары, которых больше нет в API
    deactivated = Product.objects.exclude(nc_code__in=nc_codes).update(is_active=False)
    logger.info("Products: %d created, %d updated, %d deactivated", created, updated, deactivated)
    return {'created': created, 'updated': updated, 'deactivated': deactivated}


@shared_task(name='sync.sync_stock')
def sync_stock():
    data = client.get_stock()
    updated = 0
    for item in data:
        nc = item.get('nc') or item.get('nc_code')
        if not nc:
            continue
        product = Product.objects.filter(nc_code=nc).first()
        if not product:
            continue
        Stock.objects.update_or_create(
            product=product,
            defaults={
                'quantity': item.get('quantity', 0),
                'warehouse': item.get('warehouse', ''),
                'price_base': item.get('price') or None,
            }
        )
        updated += 1
    logger.info("Stock sync: %d records updated", updated)
    return {'updated': updated}


@shared_task(name='sync.sync_catalog')
def sync_catalog():
    sync_categories()
    sync_brands()
    sync_products()
    logger.info("Full catalog sync complete")
```

- [ ] **Шаг 2: Команда для ручного запуска**

```python
# apps/sync/management/__init__.py (пустой)
# apps/sync/management/commands/__init__.py (пустой)

# apps/sync/management/commands/sync_all.py
from django.core.management.base import BaseCommand
from apps.sync.tasks import sync_catalog, sync_stock


class Command(BaseCommand):
    help = 'Полная синхронизация с API Бриз'

    def handle(self, *args, **options):
        self.stdout.write('Синхронизация каталога...')
        result = sync_catalog()
        self.stdout.write(self.style.SUCCESS(f'Каталог: {result}'))

        self.stdout.write('Синхронизация остатков...')
        result = sync_stock()
        self.stdout.write(self.style.SUCCESS(f'Остатки: {result}'))
```

- [ ] **Шаг 3: Добавить расписание Celery Beat в настройки**

Добавить в `oasis/settings/base.py`:

```python
from celery.schedules import crontab

CELERY_BEAT_SCHEDULE = {
    'sync-stock-hourly': {
        'task': 'sync.sync_stock',
        'schedule': crontab(minute=5),  # каждый час в 5 минут
    },
    'sync-catalog-4h': {
        'task': 'sync.sync_catalog',
        'schedule': crontab(minute=0, hour='*/4'),
    },
}
```

- [ ] **Шаг 4: Первый запуск синхронизации**

```bash
docker compose run --rm web python manage.py sync_all
```

Ожидаемый вывод: `Каталог: {...}  Остатки: {...}`

- [ ] **Шаг 5: Зафиксировать**

```bash
git add apps/sync/
git commit -m "feat: Celery sync tasks for catalog and stock from Breez API"
```

---

## ФАЗА 3: Фронтенд — базовые шаблоны

---

### Задача 7: Base-шаблон, Tailwind CSS, HTMX

**Файлы:**
- Создать: `templates/base.html`
- Создать: `templates/partials/header.html`
- Создать: `templates/partials/footer.html`
- Создать: `static/css/main.css`

- [ ] **Шаг 1: Создать base.html**

```html
<!-- templates/base.html -->
<!DOCTYPE html>
<html lang="ru">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{% block title %}Oasis — климатическая техника{% endblock %}</title>
  <script src="https://cdn.tailwindcss.com"></script>
  <script>
    tailwind.config = {
      theme: {
        extend: {
          colors: { accent: '#F97316' },
          fontFamily: { sans: ['Nunito Sans', 'sans-serif'] },
          borderRadius: { card: '12px' }
        }
      }
    }
  </script>
  <link href="https://fonts.googleapis.com/css2?family=Nunito+Sans:wght@400;600;700;800&display=swap" rel="stylesheet">
  <script src="https://unpkg.com/htmx.org@1.9.10"></script>
  <style>
    body { background-color: #F5F7FA; font-family: 'Nunito Sans', sans-serif; }
    .card { background: white; border-radius: 12px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }
    .btn-accent { background: #F97316; color: white; transition: all .2s; }
    .btn-accent:hover { background: #ea6c0a; }
  </style>
  {% block extra_head %}{% endblock %}
</head>
<body class="text-gray-900 min-h-screen flex flex-col">
  {% include 'partials/header.html' %}
  <main class="flex-1 max-w-7xl mx-auto w-full px-4 py-8">
    {% if messages %}
      {% for message in messages %}
        <div class="mb-4 p-4 rounded-card
          {% if message.tags == 'error' %}bg-red-100 text-red-700
          {% elif message.tags == 'success' %}bg-green-100 text-green-700
          {% else %}bg-blue-100 text-blue-700{% endif %}">
          {{ message }}
        </div>
      {% endfor %}
    {% endif %}
    {% block content %}{% endblock %}
  </main>
  {% include 'partials/footer.html' %}
</body>
</html>
```

- [ ] **Шаг 2: Создать header.html**

```html
<!-- templates/partials/header.html -->
<header class="bg-white shadow-sm sticky top-0 z-50">
  <div class="max-w-7xl mx-auto px-4 py-3 flex items-center justify-between">
    <a href="/" class="text-2xl font-extrabold text-accent">OASIS</a>
    <nav class="hidden md:flex items-center gap-6 text-sm font-semibold text-gray-600">
      <a href="/catalog/" class="hover:text-accent transition">Каталог</a>
      <a href="/brands/" class="hover:text-accent transition">Бренды</a>
    </nav>
    <div class="flex items-center gap-4">
      {% if user.is_authenticated %}
        {% if user.is_approved %}
          <a href="/cart/" class="relative hover:text-accent transition">
            🛒
            {% if cart_count > 0 %}
              <span class="absolute -top-2 -right-2 bg-accent text-white text-xs
                           rounded-full w-5 h-5 flex items-center justify-center">
                {{ cart_count }}
              </span>
            {% endif %}
          </a>
        {% endif %}
        <a href="/account/" class="text-sm font-semibold hover:text-accent">
          {{ user.company_name|default:user.username }}
        </a>
        <form method="post" action="/auth/logout/">
          {% csrf_token %}
          <button class="text-sm text-gray-400 hover:text-red-500">Выйти</button>
        </form>
      {% else %}
        <a href="/auth/login/" class="text-sm font-semibold hover:text-accent">Войти</a>
        <a href="/auth/register/"
           class="btn-accent px-4 py-2 rounded-lg text-sm font-semibold">
          Регистрация
        </a>
      {% endif %}
    </div>
  </div>
</header>
```

- [ ] **Шаг 3: Создать footer.html**

```html
<!-- templates/partials/footer.html -->
<footer class="bg-white border-t mt-12 py-8">
  <div class="max-w-7xl mx-auto px-4 text-center text-sm text-gray-500">
    <p class="font-bold text-gray-700 mb-1">OASIS — климатическая техника</p>
    <p>oasis.com.ru &nbsp;|&nbsp; B2B портал для дилеров</p>
  </div>
</footer>
```

- [ ] **Шаг 4: Создать корневые URL**

```python
# oasis/urls.py
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static


urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('apps.catalog.urls')),
    path('auth/', include('apps.accounts.urls')),
    path('account/', include('apps.accounts.urls_account')),
    path('cart/', include('apps.orders.urls')),
    path('export/', include('apps.export.urls')),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
```

- [ ] **Шаг 5: Зафиксировать**

```bash
git add templates/ oasis/urls.py
git commit -m "feat: base template, header, footer — Tailwind + HTMX"
```

---

### Задача 8: Главная страница и каталог

**Файлы:**
- Создать: `templates/home.html`
- Создать: `templates/catalog/index.html`
- Создать: `templates/partials/product_card.html`
- Создать: `templates/catalog/product_detail.html`
- Создать: `apps/catalog/views.py`
- Создать: `apps/catalog/urls.py`
- Создать: `apps/catalog/filters.py`

- [ ] **Шаг 1: Фильтр каталога**

```python
# apps/catalog/filters.py
import django_filters
from .models import Product, Brand, Category


class ProductFilter(django_filters.FilterSet):
    brand = django_filters.ModelChoiceFilter(queryset=Brand.objects.all(),
                                             label='Бренд')
    category = django_filters.ModelChoiceFilter(queryset=Category.objects.all(),
                                                label='Категория')
    in_stock = django_filters.BooleanFilter(method='filter_in_stock',
                                            label='Только в наличии')
    q = django_filters.CharFilter(field_name='title', lookup_expr='icontains',
                                  label='Поиск')

    class Meta:
        model = Product
        fields = ['brand', 'category', 'in_stock', 'q']

    def filter_in_stock(self, queryset, name, value):
        if value:
            return queryset.filter(stock__quantity__gt=0)
        return queryset
```

- [ ] **Шаг 2: Views каталога**

```python
# apps/catalog/views.py
from django.shortcuts import render, get_object_or_404
from django.core.paginator import Paginator
from django.views.decorators.cache import cache_page
from .models import Product, Category, Brand
from .filters import ProductFilter


def home(request):
    brands = Brand.objects.all()[:12]
    featured = Product.objects.filter(
        is_active=True, stock__quantity__gt=0
    ).select_related('brand', 'stock')[:8]
    return render(request, 'home.html', {'brands': brands, 'featured': featured})


def catalog(request):
    qs = Product.objects.filter(is_active=True).select_related(
        'brand', 'category', 'stock'
    ).prefetch_related('images')
    f = ProductFilter(request.GET, queryset=qs)
    paginator = Paginator(f.qs, 24)
    page = paginator.get_page(request.GET.get('page'))
    categories = Category.objects.filter(parent=None).prefetch_related('children')
    return render(request, 'catalog/index.html', {
        'filter': f,
        'page_obj': page,
        'categories': categories,
    })


def product_detail(request, slug):
    product = get_object_or_404(
        Product.objects.select_related('brand', 'category', 'stock')
                       .prefetch_related('images', 'tech_values__spec'),
        slug=slug, is_active=True
    )
    show_price = request.user.is_authenticated and request.user.is_approved
    return render(request, 'catalog/product_detail.html', {
        'product': product,
        'show_price': show_price,
    })


def brands_list(request):
    brands = Brand.objects.all()
    return render(request, 'catalog/brands.html', {'brands': brands})
```

- [ ] **Шаг 3: URL каталога**

```python
# apps/catalog/urls.py
from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('catalog/', views.catalog, name='catalog'),
    path('product/<slug:slug>/', views.product_detail, name='product_detail'),
    path('brands/', views.brands_list, name='brands'),
]
```

- [ ] **Шаг 4: Шаблон карточки товара**

```html
<!-- templates/partials/product_card.html -->
<div class="card p-4 flex flex-col hover:shadow-md transition">
  {% with img=product.images.first %}
    <a href="{% url 'product_detail' product.slug %}">
      <img src="{{ img.url|default:'/static/img/no-photo.png' }}"
           alt="{{ product.title }}"
           class="w-full h-40 object-contain mb-3">
    </a>
  {% endwith %}
  <p class="text-xs text-gray-400 mb-1">{{ product.brand }}</p>
  <a href="{% url 'product_detail' product.slug %}"
     class="font-semibold text-sm text-gray-800 hover:text-accent line-clamp-2 mb-2">
    {{ product.title }}
  </a>
  {% if product.stock.in_stock %}
    <span class="text-xs text-green-600 font-semibold mb-2">В наличии</span>
  {% else %}
    <span class="text-xs text-gray-400 mb-2">Нет в наличии</span>
  {% endif %}
  <div class="mt-auto">
    {% if product.ric %}
      <p class="text-xs text-gray-400">РИЦ: {{ product.ric|floatformat:0 }} ₽</p>
    {% endif %}
    {% if show_price and product.price_wholesale %}
      <p class="text-lg font-bold text-accent">
        {{ product.price_wholesale|floatformat:0 }} ₽
      </p>
    {% elif not show_price %}
      <p class="text-sm text-gray-400 italic">Цена — после регистрации</p>
    {% endif %}
  </div>
</div>
```

- [ ] **Шаг 5: Шаблон каталога**

```html
<!-- templates/catalog/index.html -->
{% extends 'base.html' %}
{% block title %}Каталог климатической техники — Oasis{% endblock %}
{% block content %}
<div class="flex gap-6">
  <!-- Фильтры -->
  <aside class="w-64 shrink-0">
    <div class="card p-5">
      <h2 class="font-bold text-lg mb-4">Фильтры</h2>
      <form method="get">
        <div class="mb-4">
          <label class="block text-sm font-semibold mb-1">Поиск</label>
          {{ filter.form.q }}
        </div>
        <div class="mb-4">
          <label class="block text-sm font-semibold mb-1">Бренд</label>
          {{ filter.form.brand }}
        </div>
        <div class="mb-4">
          <label class="block text-sm font-semibold mb-1">Категория</label>
          {{ filter.form.category }}
        </div>
        <div class="mb-4 flex items-center gap-2">
          {{ filter.form.in_stock }}
          <label class="text-sm">Только в наличии</label>
        </div>
        <button type="submit" class="btn-accent w-full py-2 rounded-lg font-semibold">
          Применить
        </button>
        <a href="/catalog/" class="block text-center text-sm text-gray-400 mt-2">
          Сбросить
        </a>
      </form>
    </div>
  </aside>
  <!-- Товары -->
  <div class="flex-1">
    <p class="text-sm text-gray-400 mb-4">
      Найдено: {{ page_obj.paginator.count }} товаров
    </p>
    <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
      {% for product in page_obj %}
        {% include 'partials/product_card.html' with show_price=show_price %}
      {% empty %}
        <p class="col-span-4 text-gray-400 text-center py-12">Товары не найдены</p>
      {% endfor %}
    </div>
    <!-- Пагинация -->
    {% if page_obj.has_other_pages %}
      <div class="flex justify-center gap-2 mt-8">
        {% if page_obj.has_previous %}
          <a href="?page={{ page_obj.previous_page_number }}"
             class="px-4 py-2 card text-sm hover:text-accent">← Назад</a>
        {% endif %}
        <span class="px-4 py-2 bg-accent text-white rounded-card text-sm">
          {{ page_obj.number }} / {{ page_obj.paginator.num_pages }}
        </span>
        {% if page_obj.has_next %}
          <a href="?page={{ page_obj.next_page_number }}"
             class="px-4 py-2 card text-sm hover:text-accent">Вперёд →</a>
        {% endif %}
      </div>
    {% endif %}
  </div>
</div>
{% endblock %}
```

- [ ] **Шаг 6: Шаблон карточки товара (детальная)**

```html
<!-- templates/catalog/product_detail.html -->
{% extends 'base.html' %}
{% block title %}{{ product.title }} — Oasis{% endblock %}
{% block content %}
<div class="grid grid-cols-1 md:grid-cols-2 gap-8">
  <!-- Галерея -->
  <div class="card p-4">
    {% with images=product.images.all %}
      {% if images %}
        <img id="main-img" src="{{ images.0.url }}"
             alt="{{ product.title }}" class="w-full h-80 object-contain mb-4">
        <div class="flex gap-2 flex-wrap">
          {% for img in images %}
            <img src="{{ img.url }}" alt=""
                 class="w-16 h-16 object-contain cursor-pointer border-2 rounded
                        hover:border-accent"
                 onclick="document.getElementById('main-img').src='{{ img.url }}'">
          {% endfor %}
        </div>
      {% else %}
        <div class="h-80 flex items-center justify-center text-gray-300 text-4xl">
          📦
        </div>
      {% endif %}
    {% endwith %}
  </div>
  <!-- Информация -->
  <div>
    <p class="text-sm text-gray-400 mb-1">{{ product.brand }} / {{ product.category }}</p>
    <h1 class="text-2xl font-bold mb-2">{{ product.title }}</h1>
    <p class="text-sm text-gray-400 mb-4">Арт: {{ product.articul }} | НС: {{ product.nc_code }}</p>
    <!-- Наличие -->
    {% if product.stock.in_stock %}
      <div class="inline-block bg-green-100 text-green-700 px-3 py-1 rounded-full text-sm font-semibold mb-4">
        В наличии: {{ product.stock.quantity }} шт.
      </div>
    {% else %}
      <div class="inline-block bg-gray-100 text-gray-500 px-3 py-1 rounded-full text-sm mb-4">
        Нет в наличии
      </div>
    {% endif %}
    <!-- Цены -->
    {% if product.ric %}
      <p class="text-sm text-gray-500">РИЦ: {{ product.ric|floatformat:0 }} {{ product.ric_currency }}</p>
    {% endif %}
    {% if show_price %}
      {% if product.price_wholesale %}
        <p class="text-3xl font-extrabold text-accent mt-1 mb-4">
          {{ product.price_wholesale|floatformat:0 }} ₽
        </p>
        {% if product.stock.in_stock %}
          <form hx-post="/cart/add/" hx-target="#cart-msg" hx-swap="innerHTML"
                class="flex gap-3 items-center">
            {% csrf_token %}
            <input type="hidden" name="product_id" value="{{ product.pk }}">
            <input type="number" name="quantity" value="1" min="1"
                   class="w-20 border rounded-lg px-3 py-2 text-center">
            <button class="btn-accent px-6 py-2 rounded-lg font-semibold">
              В корзину
            </button>
          </form>
          <div id="cart-msg" class="mt-2 text-sm text-green-600"></div>
        {% endif %}
      {% endif %}
    {% else %}
      <div class="card p-4 bg-orange-50 mt-2">
        <p class="text-sm text-gray-600">
          <a href="/auth/register/" class="text-accent font-semibold">Зарегистрируйтесь</a>
          как дилер, чтобы увидеть оптовые цены и оформить заказ.
        </p>
      </div>
    {% endif %}
    <!-- Документы -->
    <div class="flex gap-3 mt-4">
      {% if product.booklet_url %}
        <a href="{{ product.booklet_url }}" target="_blank"
           class="text-sm text-accent hover:underline">📄 Буклет</a>
      {% endif %}
      {% if product.manual_url %}
        <a href="{{ product.manual_url }}" target="_blank"
           class="text-sm text-accent hover:underline">📋 Инструкция</a>
      {% endif %}
    </div>
  </div>
</div>
<!-- Технические характеристики -->
{% if product.tech_values.exists %}
  <div class="card p-6 mt-8">
    <h2 class="text-xl font-bold mb-4">Технические характеристики</h2>
    <div class="grid grid-cols-1 md:grid-cols-2 gap-2">
      {% for tv in product.tech_values.all %}
        <div class="flex justify-between py-2 border-b border-gray-100">
          <span class="text-sm text-gray-600">{{ tv.spec.title }}</span>
          <span class="text-sm font-semibold">{{ tv.value }} {{ tv.spec.unit }}</span>
        </div>
      {% endfor %}
    </div>
  </div>
{% endif %}
{% endblock %}
```

- [ ] **Шаг 7: Запустить dev-сервер и проверить каталог**

```bash
docker compose run --rm web python manage.py sync_all
docker compose up
```

Открыть http://localhost:8000 — должен отображаться каталог с товарами.

- [ ] **Шаг 8: Зафиксировать**

```bash
git add templates/ apps/catalog/
git commit -m "feat: catalog views, filters, product detail template"
```

---

## ФАЗА 4: Аутентификация и личный кабинет

---

### Задача 9: Регистрация и вход

**Файлы:**
- Создать: `apps/accounts/forms.py`
- Создать: `apps/accounts/views.py`
- Создать: `apps/accounts/urls.py`
- Создать: `apps/accounts/signals.py`
- Создать: `templates/accounts/login.html`
- Создать: `templates/accounts/register.html`
- Создать: `templates/accounts/pending.html`
- Создать: `templates/accounts/dashboard.html`

- [ ] **Шаг 1: Форма регистрации**

```python
# apps/accounts/forms.py
from django import forms
from django.contrib.auth.forms import UserCreationForm
from .models import CustomUser


class RegistrationForm(UserCreationForm):
    email = forms.EmailField(required=True, label='Email')
    company_name = forms.CharField(max_length=255, label='Название компании')
    inn = forms.CharField(max_length=12, label='ИНН')
    kpp = forms.CharField(max_length=9, required=False, label='КПП')
    legal_address = forms.CharField(widget=forms.Textarea(attrs={'rows': 2}),
                                    label='Юридический адрес')
    phone = forms.CharField(max_length=20, label='Телефон')
    contact_person = forms.CharField(max_length=255, label='Контактное лицо')

    class Meta:
        model = CustomUser
        fields = ('username', 'email', 'password1', 'password2',
                  'company_name', 'inn', 'kpp', 'legal_address',
                  'phone', 'contact_person')
```

- [ ] **Шаг 2: Views аккаунтов**

```python
# apps/accounts/views.py
from django.shortcuts import render, redirect
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .forms import RegistrationForm


def register(request):
    if request.method == 'POST':
        form = RegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            messages.success(request,
                'Регистрация прошла успешно. Ожидайте одобрения менеджера.')
            return redirect('pending')
    else:
        form = RegistrationForm()
    return render(request, 'accounts/register.html', {'form': form})


def login_view(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)
        if user:
            login(request, user)
            return redirect('account_dashboard')
        messages.error(request, 'Неверный логин или пароль')
    return render(request, 'accounts/login.html')


def logout_view(request):
    logout(request)
    return redirect('home')


def pending(request):
    return render(request, 'accounts/pending.html')


@login_required
def dashboard(request):
    if not request.user.is_approved:
        return redirect('pending')
    orders = request.user.orders.all()[:10]
    return render(request, 'accounts/dashboard.html', {'orders': orders})
```

- [ ] **Шаг 3: URLs аккаунтов**

```python
# apps/accounts/urls.py
from django.urls import path
from . import views

urlpatterns = [
    path('register/', views.register, name='register'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('pending/', views.pending, name='pending'),
]

# apps/accounts/urls_account.py
from django.urls import path
from . import views

urlpatterns = [
    path('', views.dashboard, name='account_dashboard'),
]
```

- [ ] **Шаг 4: Сигнал — email менеджеру при регистрации**

```python
# apps/accounts/signals.py
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.core.mail import send_mail
from django.conf import settings
from .models import CustomUser


@receiver(post_save, sender=CustomUser)
def notify_on_registration(sender, instance, created, **kwargs):
    if created and settings.MANAGER_EMAIL:
        send_mail(
            subject=f'Новая регистрация: {instance.company_name}',
            message=(f'Пользователь {instance.company_name} (ИНН: {instance.inn}) '
                     f'зарегистрировался и ожидает одобрения.\n'
                     f'Email: {instance.email}'),
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[settings.MANAGER_EMAIL],
            fail_silently=True,
        )

    if not created and instance.is_approved:
        send_mail(
            subject='Ваш аккаунт одобрен — Oasis',
            message=(f'Здравствуйте, {instance.company_name}!\n\n'
                     f'Ваш аккаунт одобрен. Теперь вы можете видеть оптовые '
                     f'цены и оформлять заказы на oasis.com.ru'),
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[instance.email],
            fail_silently=True,
        )


# Подключить в apps/accounts/apps.py
```

```python
# apps/accounts/apps.py
from django.apps import AppConfig


class AccountsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.accounts'

    def ready(self):
        import apps.accounts.signals  # noqa
```

- [ ] **Шаг 5: Шаблоны аккаунтов**

```html
<!-- templates/accounts/register.html -->
{% extends 'base.html' %}
{% block title %}Регистрация дилера — Oasis{% endblock %}
{% block content %}
<div class="max-w-2xl mx-auto">
  <div class="card p-8">
    <h1 class="text-2xl font-bold mb-6">Регистрация дилера</h1>
    <p class="text-sm text-gray-500 mb-6">
      Только для юридических лиц. После регистрации менеджер проверит данные
      и откроет доступ к оптовым ценам.
    </p>
    <form method="post" class="space-y-4">
      {% csrf_token %}
      {% for field in form %}
        <div>
          <label class="block text-sm font-semibold mb-1">{{ field.label }}</label>
          {{ field }}
          {% if field.errors %}
            <p class="text-red-500 text-xs mt-1">{{ field.errors.0 }}</p>
          {% endif %}
        </div>
      {% endfor %}
      <button type="submit" class="btn-accent w-full py-3 rounded-lg font-bold mt-4">
        Отправить заявку
      </button>
    </form>
    <p class="text-center text-sm text-gray-400 mt-4">
      Уже есть аккаунт? <a href="/auth/login/" class="text-accent">Войти</a>
    </p>
  </div>
</div>
{% endblock %}
```

```html
<!-- templates/accounts/login.html -->
{% extends 'base.html' %}
{% block title %}Вход — Oasis{% endblock %}
{% block content %}
<div class="max-w-sm mx-auto">
  <div class="card p-8">
    <h1 class="text-2xl font-bold mb-6">Вход</h1>
    <form method="post" class="space-y-4">
      {% csrf_token %}
      <div>
        <label class="block text-sm font-semibold mb-1">Логин</label>
        <input type="text" name="username" required
               class="w-full border rounded-lg px-3 py-2">
      </div>
      <div>
        <label class="block text-sm font-semibold mb-1">Пароль</label>
        <input type="password" name="password" required
               class="w-full border rounded-lg px-3 py-2">
      </div>
      <button type="submit" class="btn-accent w-full py-3 rounded-lg font-bold">
        Войти
      </button>
    </form>
    <p class="text-center text-sm text-gray-400 mt-4">
      Нет аккаунта? <a href="/auth/register/" class="text-accent">Регистрация</a>
    </p>
  </div>
</div>
{% endblock %}
```

```html
<!-- templates/accounts/dashboard.html -->
{% extends 'base.html' %}
{% block title %}Личный кабинет — Oasis{% endblock %}
{% block content %}
<h1 class="text-2xl font-bold mb-6">Личный кабинет</h1>
<div class="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
  <div class="card p-6">
    <p class="text-sm text-gray-400 mb-1">Компания</p>
    <p class="font-bold">{{ user.company_name }}</p>
  </div>
  <div class="card p-6">
    <p class="text-sm text-gray-400 mb-1">ИНН</p>
    <p class="font-bold">{{ user.inn }}</p>
  </div>
  <div class="card p-6">
    <p class="text-sm text-gray-400 mb-1">Скидка</p>
    <p class="font-bold text-accent">{{ user.discount_percent }}%</p>
  </div>
</div>
<div class="flex gap-4 mb-6">
  <a href="/export/price/excel/" class="btn-accent px-6 py-2 rounded-lg font-semibold">
    📊 Скачать прайс Excel
  </a>
  <a href="/export/price/pdf/" class="btn-accent px-6 py-2 rounded-lg font-semibold">
    📄 Скачать прайс PDF
  </a>
</div>
<h2 class="text-xl font-bold mb-4">Мои заказы</h2>
{% if orders %}
  <div class="card overflow-hidden">
    <table class="w-full text-sm">
      <thead class="bg-gray-50">
        <tr>
          <th class="px-4 py-3 text-left">№</th>
          <th class="px-4 py-3 text-left">Дата</th>
          <th class="px-4 py-3 text-left">Статус</th>
          <th class="px-4 py-3 text-right">Сумма</th>
          <th class="px-4 py-3"></th>
        </tr>
      </thead>
      <tbody>
        {% for order in orders %}
          <tr class="border-t hover:bg-gray-50">
            <td class="px-4 py-3">#{{ order.pk }}</td>
            <td class="px-4 py-3">{{ order.created_at|date:"d.m.Y" }}</td>
            <td class="px-4 py-3">{{ order.get_status_display }}</td>
            <td class="px-4 py-3 text-right font-bold">{{ order.total|floatformat:0 }} ₽</td>
            <td class="px-4 py-3">
              <a href="/account/orders/{{ order.pk }}/" class="text-accent hover:underline">
                Детали
              </a>
            </td>
          </tr>
        {% endfor %}
      </tbody>
    </table>
  </div>
{% else %}
  <p class="text-gray-400">Заказов пока нет.</p>
{% endif %}
{% endblock %}
```

- [ ] **Шаг 6: Зафиксировать**

```bash
git add apps/accounts/ templates/accounts/
git commit -m "feat: registration, login, dashboard, approval notifications"
```

---

## ФАЗА 5: Корзина и заказы

---

### Задача 10: Корзина с HTMX

**Файлы:**
- Создать: `apps/orders/views.py`
- Создать: `apps/orders/urls.py`
- Создать: `templates/orders/cart.html`
- Создать: `templates/orders/checkout.html`

- [ ] **Шаг 1: Views корзины**

```python
# apps/orders/views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.http import HttpResponse
from django.contrib import messages
from django.core.mail import send_mail
from django.conf import settings
from .models import Cart, CartItem, Order, OrderItem
from .forms import CheckoutForm
from apps.catalog.models import Product


def _require_approved(request):
    return request.user.is_authenticated and request.user.is_approved


@login_required
def cart_view(request):
    if not request.user.is_approved:
        return redirect('pending')
    cart, _ = Cart.objects.get_or_create(user=request.user)
    return render(request, 'orders/cart.html', {'cart': cart})


@require_POST
@login_required
def cart_add(request):
    if not request.user.is_approved:
        return HttpResponse('Доступ закрыт', status=403)
    product_id = request.POST.get('product_id')
    quantity = int(request.POST.get('quantity', 1))
    product = get_object_or_404(Product, pk=product_id, is_active=True)
    cart, _ = Cart.objects.get_or_create(user=request.user)
    item, created = CartItem.objects.get_or_create(cart=cart, product=product)
    if not created:
        item.quantity += quantity
    else:
        item.quantity = quantity
    item.save()
    if request.htmx:
        return HttpResponse(
            f'<span class="text-green-600 font-semibold">✓ Добавлено в корзину</span>'
        )
    return redirect('cart')


@require_POST
@login_required
def cart_remove(request, item_id):
    item = get_object_or_404(CartItem, pk=item_id, cart__user=request.user)
    item.delete()
    cart = request.user.cart
    if request.htmx:
        return render(request, 'orders/partials/cart_table.html', {'cart': cart})
    return redirect('cart')


@require_POST
@login_required
def cart_update(request, item_id):
    item = get_object_or_404(CartItem, pk=item_id, cart__user=request.user)
    quantity = int(request.POST.get('quantity', 1))
    if quantity > 0:
        item.quantity = quantity
        item.save()
    else:
        item.delete()
    cart = request.user.cart
    if request.htmx:
        return render(request, 'orders/partials/cart_table.html', {'cart': cart})
    return redirect('cart')


@login_required
def checkout(request):
    if not request.user.is_approved:
        return redirect('pending')
    cart = get_object_or_404(Cart, user=request.user)
    if not cart.items.exists():
        return redirect('cart')
    if request.method == 'POST':
        form = CheckoutForm(request.POST)
        if form.is_valid():
            order = Order.objects.create(
                user=request.user,
                delivery_address=form.cleaned_data['delivery_address'],
                comment=form.cleaned_data.get('comment', ''),
                total=cart.total,
                status='new',
            )
            for item in cart.items.select_related('product'):
                OrderItem.objects.create(
                    order=order,
                    product=item.product,
                    quantity=item.quantity,
                    price_at_order=request.user.get_wholesale_price(
                        item.product.price_wholesale) or 0,
                    ric_at_order=item.product.ric,
                )
            cart.items.all().delete()
            # Уведомление менеджеру
            if settings.MANAGER_EMAIL:
                send_mail(
                    subject=f'Новый заказ #{order.pk} — {request.user.company_name}',
                    message=f'Заказ #{order.pk} на сумму {order.total} ₽',
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[settings.MANAGER_EMAIL],
                    fail_silently=True,
                )
            messages.success(request, f'Заказ #{order.pk} успешно оформлен!')
            return redirect('order_detail', pk=order.pk)
    else:
        form = CheckoutForm(initial={'delivery_address': request.user.legal_address})
    return render(request, 'orders/checkout.html', {'cart': cart, 'form': form})


@login_required
def order_list(request):
    orders = request.user.orders.all()
    return render(request, 'orders/order_list.html', {'orders': orders})


@login_required
def order_detail(request, pk):
    order = get_object_or_404(Order, pk=pk, user=request.user)
    return render(request, 'orders/order_detail.html', {'order': order})
```

- [ ] **Шаг 2: Форма оформления заказа**

```python
# apps/orders/forms.py
from django import forms


class CheckoutForm(forms.Form):
    delivery_address = forms.CharField(
        label='Адрес доставки',
        widget=forms.Textarea(attrs={'rows': 3})
    )
    comment = forms.CharField(
        label='Комментарий к заказу',
        widget=forms.Textarea(attrs={'rows': 2}),
        required=False
    )
```

- [ ] **Шаг 3: URLs заказов**

```python
# apps/orders/urls.py
from django.urls import path
from . import views

urlpatterns = [
    path('', views.cart_view, name='cart'),
    path('add/', views.cart_add, name='cart_add'),
    path('remove/<int:item_id>/', views.cart_remove, name='cart_remove'),
    path('update/<int:item_id>/', views.cart_update, name='cart_update'),
    path('checkout/', views.checkout, name='checkout'),
]

# Добавить в apps/accounts/urls_account.py:
# path('orders/', views.order_list, name='order_list'),
# path('orders/<int:pk>/', views.order_detail, name='order_detail'),
```

- [ ] **Шаг 4: Шаблон корзины**

```html
<!-- templates/orders/cart.html -->
{% extends 'base.html' %}
{% block title %}Корзина — Oasis{% endblock %}
{% block content %}
<h1 class="text-2xl font-bold mb-6">Корзина</h1>
{% if cart.items.exists %}
  <div id="cart-content">
    {% include 'orders/partials/cart_table.html' %}
  </div>
  <div class="flex justify-end mt-6">
    <a href="/cart/checkout/"
       class="btn-accent px-8 py-3 rounded-lg font-bold text-lg">
      Оформить заказ →
    </a>
  </div>
{% else %}
  <div class="card p-12 text-center">
    <p class="text-gray-400 text-lg mb-4">Корзина пуста</p>
    <a href="/catalog/" class="btn-accent px-6 py-2 rounded-lg font-semibold">
      Перейти в каталог
    </a>
  </div>
{% endif %}
{% endblock %}
```

```html
<!-- templates/orders/partials/cart_table.html -->
<div class="card overflow-hidden">
  <table class="w-full text-sm">
    <thead class="bg-gray-50">
      <tr>
        <th class="px-4 py-3 text-left">Товар</th>
        <th class="px-4 py-3 text-center">Кол-во</th>
        <th class="px-4 py-3 text-right">Цена</th>
        <th class="px-4 py-3 text-right">Сумма</th>
        <th class="px-4 py-3"></th>
      </tr>
    </thead>
    <tbody>
      {% for item in cart.items.all %}
        <tr class="border-t" id="row-{{ item.pk }}">
          <td class="px-4 py-3">
            <a href="/product/{{ item.product.slug }}/"
               class="font-semibold hover:text-accent">
              {{ item.product.title }}
            </a>
            <p class="text-xs text-gray-400">{{ item.product.articul }}</p>
          </td>
          <td class="px-4 py-3 text-center">
            <form hx-post="/cart/update/{{ item.pk }}/"
                  hx-target="#cart-content" hx-swap="innerHTML">
              {% csrf_token %}
              <input type="number" name="quantity" value="{{ item.quantity }}"
                     min="1" onchange="this.form.requestSubmit()"
                     class="w-16 border rounded px-2 py-1 text-center">
            </form>
          </td>
          <td class="px-4 py-3 text-right">
            {{ item.product.price_wholesale|floatformat:0 }} ₽
          </td>
          <td class="px-4 py-3 text-right font-bold">
            {{ item.subtotal|floatformat:0 }} ₽
          </td>
          <td class="px-4 py-3 text-center">
            <form hx-post="/cart/remove/{{ item.pk }}/"
                  hx-target="#cart-content" hx-swap="innerHTML">
              {% csrf_token %}
              <button class="text-red-400 hover:text-red-600">✕</button>
            </form>
          </td>
        </tr>
      {% endfor %}
    </tbody>
    <tfoot class="bg-gray-50">
      <tr>
        <td colspan="3" class="px-4 py-3 font-bold">Итого:</td>
        <td class="px-4 py-3 text-right font-extrabold text-accent text-lg">
          {{ cart.total|floatformat:0 }} ₽
        </td>
        <td></td>
      </tr>
    </tfoot>
  </table>
</div>
```

- [ ] **Шаг 5: Зафиксировать**

```bash
git add apps/orders/ templates/orders/
git commit -m "feat: cart with HTMX, checkout, order creation"
```

---

## ФАЗА 6: Экспорт прайс-листа

---

### Задача 11: Excel и PDF экспорт

**Файлы:**
- Создать: `apps/export/excel.py`
- Создать: `apps/export/pdf.py`
- Создать: `apps/export/views.py`
- Создать: `apps/export/urls.py`
- Создать: `templates/export/price_pdf.html`

- [ ] **Шаг 1: Генератор Excel**

```python
# apps/export/excel.py
import io
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment
from apps.catalog.models import Product


def generate_price_excel(user):
    wb = Workbook()
    ws = wb.active
    ws.title = 'Прайс-лист Oasis'

    # Шапка
    headers = ['Артикул', 'НС-код', 'Название', 'Бренд', 'Категория',
               'Остаток', 'РИЦ', 'Опт. цена']
    header_fill = PatternFill(start_color='F97316', end_color='F97316', fill_type='solid')
    for col, h in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col, value=h)
        cell.font = Font(bold=True, color='FFFFFF')
        cell.fill = header_fill
        cell.alignment = Alignment(horizontal='center')

    products = Product.objects.filter(is_active=True).select_related(
        'brand', 'category', 'stock'
    ).order_by('brand__title', 'title')

    for row, p in enumerate(products, 2):
        stock_qty = p.stock.quantity if hasattr(p, 'stock') else 0
        wholesale = user.get_wholesale_price(p.price_wholesale) if p.price_wholesale else ''
        ws.append([
            p.articul, p.nc_code, p.title,
            str(p.brand) if p.brand else '',
            str(p.category) if p.category else '',
            stock_qty,
            float(p.ric) if p.ric else '',
            float(wholesale) if wholesale else '',
        ])

    # Ширина колонок
    col_widths = [15, 15, 50, 20, 25, 10, 15, 15]
    for i, width in enumerate(col_widths, 1):
        ws.column_dimensions[ws.cell(row=1, column=i).column_letter].width = width

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf
```

- [ ] **Шаг 2: Генератор PDF**

```python
# apps/export/pdf.py
import io
from django.template.loader import render_to_string
from weasyprint import HTML
from apps.catalog.models import Product


def generate_price_pdf(user, request):
    products = Product.objects.filter(is_active=True).select_related(
        'brand', 'category', 'stock'
    ).order_by('brand__title', 'title')

    items = []
    for p in products:
        stock_qty = p.stock.quantity if hasattr(p, 'stock') else 0
        wholesale = user.get_wholesale_price(p.price_wholesale) if p.price_wholesale else None
        items.append({
            'articul': p.articul,
            'title': p.title,
            'brand': str(p.brand) if p.brand else '',
            'stock': stock_qty,
            'ric': p.ric,
            'price': wholesale,
        })

    html_str = render_to_string('export/price_pdf.html', {
        'user': user, 'items': items
    })
    pdf_buf = io.BytesIO()
    HTML(string=html_str, base_url=request.build_absolute_uri('/')).write_pdf(pdf_buf)
    pdf_buf.seek(0)
    return pdf_buf
```

- [ ] **Шаг 3: Views и URLs экспорта**

```python
# apps/export/views.py
import datetime
from django.http import HttpResponse
from django.contrib.auth.decorators import login_required
from .excel import generate_price_excel
from .pdf import generate_price_pdf


def _require_approved(user):
    return user.is_authenticated and user.is_approved


@login_required
def export_excel(request):
    if not request.user.is_approved:
        return HttpResponse('Доступ закрыт', status=403)
    buf = generate_price_excel(request.user)
    date = datetime.date.today().strftime('%Y-%m-%d')
    response = HttpResponse(
        buf.getvalue(),
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = f'attachment; filename="oasis-price-{date}.xlsx"'
    return response


@login_required
def export_pdf(request):
    if not request.user.is_approved:
        return HttpResponse('Доступ закрыт', status=403)
    buf = generate_price_pdf(request.user, request)
    date = datetime.date.today().strftime('%Y-%m-%d')
    response = HttpResponse(buf.getvalue(), content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="oasis-price-{date}.pdf"'
    return response
```

```python
# apps/export/urls.py
from django.urls import path
from . import views

urlpatterns = [
    path('price/excel/', views.export_excel, name='export_excel'),
    path('price/pdf/', views.export_pdf, name='export_pdf'),
]
```

- [ ] **Шаг 4: PDF-шаблон**

```html
<!-- templates/export/price_pdf.html -->
<!DOCTYPE html>
<html lang="ru">
<head>
  <meta charset="UTF-8">
  <style>
    body { font-family: Arial, sans-serif; font-size: 10px; color: #111; }
    h1 { color: #F97316; font-size: 18px; margin-bottom: 4px; }
    .meta { color: #666; font-size: 9px; margin-bottom: 16px; }
    table { width: 100%; border-collapse: collapse; }
    th { background: #F97316; color: white; padding: 6px 8px; text-align: left; font-size: 9px; }
    td { padding: 5px 8px; border-bottom: 1px solid #eee; }
    tr:nth-child(even) { background: #F5F7FA; }
    .price { font-weight: bold; color: #F97316; }
  </style>
</head>
<body>
  <h1>OASIS — Прайс-лист</h1>
  <p class="meta">
    Для: {{ user.company_name }} | ИНН: {{ user.inn }} |
    Дата: {% now "d.m.Y" %} | oasis.com.ru
  </p>
  <table>
    <thead>
      <tr>
        <th>Артикул</th>
        <th>Название</th>
        <th>Бренд</th>
        <th>Остаток</th>
        <th>РИЦ</th>
        <th>Опт. цена</th>
      </tr>
    </thead>
    <tbody>
      {% for item in items %}
        <tr>
          <td>{{ item.articul }}</td>
          <td>{{ item.title }}</td>
          <td>{{ item.brand }}</td>
          <td>{{ item.stock }}</td>
          <td>{% if item.ric %}{{ item.ric }} ₽{% endif %}</td>
          <td class="price">{% if item.price %}{{ item.price }} ₽{% endif %}</td>
        </tr>
      {% endfor %}
    </tbody>
  </table>
</body>
</html>
```

- [ ] **Шаг 5: Зафиксировать**

```bash
git add apps/export/ templates/export/
git commit -m "feat: Excel and PDF price list export"
```

---

## ФАЗА 7: Деплой на VPS

---

### Задача 12: Nginx + SSL + production-деплой

**Файлы:**
- Создать: `nginx.conf`
- Создать: `deploy.sh`

- [ ] **Шаг 1: Создать nginx.conf**

```nginx
# nginx.conf
server {
    listen 80;
    server_name oasis.com.ru www.oasis.com.ru;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl;
    server_name oasis.com.ru www.oasis.com.ru;

    ssl_certificate /etc/letsencrypt/live/oasis.com.ru/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/oasis.com.ru/privkey.pem;

    client_max_body_size 20M;

    location /static/ {
        alias /opt/oasis/staticfiles/;
        expires 30d;
    }

    location /media/ {
        alias /opt/oasis/media/;
        expires 7d;
    }

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 120;
    }
}
```

- [ ] **Шаг 2: Создать deploy.sh**

```bash
#!/bin/bash
set -e

echo "=== Деплой Oasis B2B портала ==="

# Сборка и запуск контейнеров
docker compose pull
docker compose build

# Миграции
docker compose run --rm web python manage.py migrate --noinput

# Статика
docker compose run --rm web python manage.py collectstatic --noinput

# Перезапуск
docker compose up -d

# Первая синхронизация с Бриз API
docker compose run --rm web python manage.py sync_all

# Создать суперпользователя (если первый деплой)
echo "Создать суперпользователя? (y/n)"
read CREATE_SU
if [ "$CREATE_SU" = "y" ]; then
    docker compose run --rm web python manage.py createsuperuser
fi

echo "=== Деплой завершён. Сайт доступен на https://oasis.com.ru ==="
```

- [ ] **Шаг 3: Инструкция по первому деплою на VPS**

```bash
# На VPS (выполнять от root или sudo):

# 1. Установить Docker
curl -fsSL https://get.docker.com | sh

# 2. Скопировать проект
git clone <repo> /opt/oasis
cd /opt/oasis

# 3. Создать .env из примера и заполнить
cp .env.example .env
nano .env   # вставить реальные данные

# 4. Получить SSL-сертификат
apt install certbot python3-certbot-nginx -y
certbot certonly --standalone -d oasis.com.ru -d www.oasis.com.ru

# 5. Настроить Nginx
cp nginx.conf /etc/nginx/sites-available/oasis
ln -s /etc/nginx/sites-available/oasis /etc/nginx/sites-enabled/
nginx -t && systemctl reload nginx

# 6. Запустить деплой
chmod +x deploy.sh
./deploy.sh
```

- [ ] **Шаг 4: Проверить работу**

```bash
# Проверить статус контейнеров
docker compose ps

# Проверить логи
docker compose logs web --tail=50
docker compose logs celery --tail=20

# Проверить доступность сайта
curl -I https://oasis.com.ru
```

Ожидаемый вывод: `HTTP/2 200`

- [ ] **Шаг 5: Создать launch.json для разработки**

```bash
mkdir -p .claude
```

```json
// .claude/launch.json
{
  "version": "0.0.1",
  "configurations": [
    {
      "name": "Django dev server",
      "runtimeExecutable": "docker",
      "runtimeArgs": ["compose", "run", "--rm", "--service-ports", "web",
                      "python", "manage.py", "runserver", "0.0.0.0:8000"],
      "port": 8000
    },
    {
      "name": "Celery worker",
      "runtimeExecutable": "docker",
      "runtimeArgs": ["compose", "up", "celery"],
      "port": 0
    }
  ]
}
```

- [ ] **Шаг 6: Финальный коммит**

```bash
git add .
git commit -m "feat: Nginx config, deploy script, launch.json — production ready"
```

---

## Критерии завершения

- [ ] `docker compose up` запускается без ошибок
- [ ] `python manage.py sync_all` синхронизирует каталог и остатки
- [ ] Анонимный пользователь видит каталог и РИЦ
- [ ] Одобренный дилер видит опт. цены и может добавить в корзину
- [ ] Оформление заказа создаёт Order в БД и уведомляет менеджера
- [ ] Экспорт Excel и PDF скачивается корректно
- [ ] Регистрация уведомляет менеджера по email
- [ ] Сайт работает на https://oasis.com.ru с SSL
- [ ] Celery Beat выполняет синхронизацию по расписанию
