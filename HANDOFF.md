# HANDOFF: SplitHome — Передача проекта

**Дата обновления:** 2026-05-24 (r-итерация — задеплоено и работает: квиз v2 + JWT auto-refresh + brand logos)
**Прогресс:** B2C-pivot + Quiz v2 (7 шагов, Wi-Fi, бренд с лого, «Назад») + Rusklimat JWT auto-refresh (cron 23:50 МСК) + brand logos из публичного Rusklimat API + TechSpec + per-warehouse + регистрация + welcome/pending email + cookie + LLM-SEO + mobile + правильный BTU + Бриз Крым + сортировка Крым-first + 4×4 grid + унифицированный badge + scroll-top + Tailwind compiled + 5 уровней релаксации + реальная скидка 15% + ЛК физлица + /availability/ + покрытие тестами
**Ветка:** `develop` (синхронизирована с прод-VPS)
**Репозиторий:** https://github.com/flycited2-dotcom/split-shop_claude
**Production HEAD на VPS:** `30c6284` (fix(quiz): _brand_logo_static проверяет и STATIC_ROOT) — **синхронизировано с develop**
**Production URL:** https://splithome.ru/ (Let's Encrypt SSL, expire 2026-08-14, авто-renewal через `certbot.timer`)

---

## Update 2026-05-24 (r-итерация) — квиз v2 + JWT auto-refresh

**r1. Квиз v2: Wi-Fi, бренд, кнопка «Назад», убрали «Цвет».** План `hashed-jumping-iverson.md` (6 шагов) был уже выполнен в q-итерации. Эта итерация — следующий слой. Теперь 7 шагов: площадь → тип → инвертор → **Wi-Fi** → обогрев → бюджет → **бренд** → результат. Бюджет перенесён ближе к финалу, после функциональных предпочтений. Шаг «Цвет» удалён из UI (поле `QuizResult.needs_black` сохранено для legacy записей).
- **Wi-Fi-фильтр** — гибрид: TechSpec по title icontains `wi-fi|вай-фай|беспровод|удал…управлен` + значение НЕ `нет/−/—/отсутств`, OR fallback на regex по `Product.description`/`title`. Включает кейс «возможность подключения Wi-Fi» (по словам владельца). Релаксация `wifi_relaxed`.
- **Бренд-фильтр** — manual select через новое поле `Brand.featured_in_quiz` (BooleanField) + сортировка по `order`. В админке `/admin/catalog/brand/` — list_editable для `featured_in_quiz` и `order`. Логотипы скачиваются в `static/images/brands/{slug}.{ext}` через `python manage.py download_brand_logos` (берёт `Brand.logo_url`, расширение из Content-Type). В шаблоне `<img>` если logo есть, иначе только название. Релаксация `brand_relaxed` (первой при пустоте — снимаем самый сильный сужающий фильтр).
- **Кнопка «Назад»** — `<button name="action" value="back" formnovalidate>` в каждом шаге кроме 1. View: `if request.POST.get('action') == 'back': render(prev_step, ...)` — POST hidden inputs автоматически восстанавливают предыдущие ответы.
- **Порядок релаксации** (от менее важного к более): `brand → wifi → budget → inverter → btu`.
- **Telegram-уведомление** при заявке: убрана строка про цвет, добавлены строки «Wi-Fi: да/нет» и «Бренд: …».
- Файлы: `apps/catalog/models.py:Brand` (+ migration 0011), `apps/catalog/admin.py`, `apps/catalog/management/commands/download_brand_logos.py` (новый), `apps/leads/models.py:QuizResult` (+ migration 0004 — `needs_wifi`, `wanted_brand` FK, переименован `needs_black` → «(legacy)»), `apps/leads/quiz_logic.py`, `apps/leads/views.py`, `apps/leads/admin.py`, `templates/leads/partials/_quiz_step.html`, `templates/leads/quiz.html`.
- Тесты: `apps/leads/tests/test_quiz_logic.py` — `WifiFilterTest` (4 кейса: TechSpec hit, явное Нет, description fallback, релаксация), `BrandFilterTest` (фильтр + brand_relaxed первой). `apps/leads/tests/test_views_quiz.py` — flow по 7 шагам, persist Wi-Fi и brand_id в QuizResult, кнопка «Назад» возвращает шаг N-1 без создания QuizResult.

**r2. JWT auto-refresh для Rusklimat REST.** Старая память утверждала, что auth-эндпоинт `POST b2b.rusklimat.com/api/v1/auth/jwt/` требует «отдельные API-credentials» — это было неверно. Спецификация владельца от 2026-05-24:
- Auth работает с обычными user-кредами при условии заголовка `User-Agent: catalog-ip` (без него 401 / «Invalid user/password»).
- Токен сбрасывается строго **в 00:00 МСК** (не +24ч от выпуска). Поэтому cron не «раз в сутки», а каждый день в **23:50 Europe/Moscow**.
- **Новый модуль `apps/sync/rusklimat_auth.py`** — `fetch_jwt()` (POST + cache.set), `get_jwt()` (cache → fetch → legacy fallback на статичный `RUSKLIMAT_JWT_TOKEN`), `invalidate_jwt()`. Кэш в Django cache (Redis), TTL 24ч (верхняя граница; реально сбрасывается cron-задачей). `threading.Lock` от race внутри процесса, между процессами безопасно (худший случай — два refresh параллельно, оба токена валидны).
- **RusklimatRestClient** теперь тянет JWT через `get_jwt()`, новый helper `_request(method, url, where, **kw)` на 401 делает invalidate → refresh → retry один раз. Если повторно 401 — бросает `RusklimatJWTExpired`. Все методы (`request_key`, `get_units`, `get_categories`, `get_properties`, `get_products`) перешли на `_request`. `partnerId` теперь из `settings.RUSKLIMAT_PARTNER_ID` (дефолт `e51a9046-...`), fallback на `JWT.payload.guid`.
- **Celery Beat** — задача `sync.refresh_rusklimat_jwt` в `apps/sync/tasks.py`, расписание в `splithome/settings/base.py`: `crontab(hour=23, minute=50)` (CELERY_TIMEZONE=`Europe/Moscow`).
- **Management command** `python manage.py refresh_rusklimat_jwt [--show]` — для первого запуска после деплоя (когда кэш пуст) и дебага.
- **Новые .env-переменные:** `RUSKLIMAT_LOGIN`, `RUSKLIMAT_PASSWORD`, `RUSKLIMAT_PARTNER_ID` (опционально, дефолт в settings). Статичный `RUSKLIMAT_JWT_TOKEN` оставлен как legacy fallback.
- Тесты `apps/sync/tests/test_rusklimat_auth.py` — `fetch_jwt` happy + 4xx + network + malformed; `get_jwt` cached / fetch-on-miss / legacy / no-creds; интеграционный 401→refresh→retry на `RusklimatRestClient.request_key`.

### Deploy-чеклист после `git pull`

```bash
# 1. В /opt/oasis/.env добавить:
#    RUSKLIMAT_LOGIN=<логин от b2b.rusklimat.com>
#    RUSKLIMAT_PASSWORD=<пароль>

# 2. Build + migrate + statics
docker compose build web
docker compose run --rm web python manage.py migrate
docker compose run --rm web python manage.py collectstatic --noinput
docker compose up -d

# 3. В admin /admin/catalog/brand/ — выставить featured_in_quiz=True
#    для 6 топ-брендов, расставить order (или сделать update через shell).

# 4. Скачать лого брендов:
docker compose exec web python manage.py download_brand_logos
docker compose exec web python manage.py collectstatic --noinput
# rsync статики на nginx host (см. server_deploy.md)

# 5. Первичное наполнение кэша JWT (без него первый sync_rusklimat_rest
#    дёрнет fetch_jwt сам, но лучше прогреть):
docker compose exec web python manage.py refresh_rusklimat_jwt --show

# 6. Перезапустить celery beat, чтобы подхватилось новое расписание:
docker compose restart celery-beat
# (или весь docker compose restart, если beat в общем контейнере)

# 7. Тесты:
docker compose exec web python manage.py test apps.leads.tests apps.sync.tests apps.catalog.tests
```

### Smoke-тест в браузере

1. https://splithome.ru/quiz/ — happy path: «до 25 м² (9 BTU)» → Квартира → Инвертор «Да» → Wi-Fi «Да» → Обогрев «Нет» → Бюджет «до 50k» → Daichi. Ожидаем 3–5 моделей с Wi-Fi, инвертором, под бюджет, бренд Daichi.
2. На шаге 5 кликнуть «← Назад» → шаг 4 с сохранённым Wi-Fi=Да.
3. Релаксация: выбрать бренд с одним товаром в нужной мощности + Wi-Fi=Да → плашка «Под бренд X не нашли — расширили поиск».
4. Заявка → Telegram: проверить строки «Wi-Fi: да» и «Бренд: …».
5. Около 23:50 МСК — `docker logs` должен показать `Rusklimat JWT refreshed (length=...)`.

### Что добавилось в процессе деплоя 24 мая

**r3. Brand logos из публичного Rusklimat API.**  
`b2b.rusklimat.com/api/v1/brands/?limit=200&page=N` — публичный endpoint (без авторизации), 357 брендов с лого на rkcdn.ru. Расширил `download_brand_logos`: опция `--from-rusklimat` подтягивает `Brand.logo_url` (точный + substring match, поймает `Mitsubishi` ↔ `MITSUBISHI ELECTRIC`), потом качает в `static/images/brands/{slug}.{ext}`. Skip для не-image Content-Type (часть URL отдаёт 404-страницу как text/html). Результат на проде: **66 логотипов скачано**, из топ-8 featured-AC брендов 6 с лого (Ballu, Royal Clima, Royal Thermo, Hisense, Funai, Midea, Dantex, Shuft), 2 без (Electrolux, Kentatsu — их нет в Rusklimat API). Через админку `/admin/catalog/brand/` для них можно загрузить лого вручную.

**r4. Фикс `_brand_logo_static`.**  
В контейнере `BASE_DIR/static/` содержит только исходники из git (пустая папка `images/brands/`), после collectstatic файлы лежат в `STATIC_ROOT` (docker volume). View искал только в `static/` и не передавал `logo_static` в шаблон. Теперь проверка в обоих местах.

**r5. JWT auto-refresh — критическая деталь формата логина.**  
Auth-эндпоинт `POST b2b.rusklimat.com/api/v1/auth/jwt/` с `User-Agent: catalog-ip` принимает **только 10 цифр без префикса**. Пример из официальной документации: `9651111111`. У нас в `.env` был `+79152757788` — отсюда «Invalid user/password». Поменял на `9152757788` — auth заработал, `refresh_rusklimat_jwt` выдаёт свежий токен. Cron в 23:50 МСК настроен через `django_celery_beat.PeriodicTask` (на проде используется `DatabaseScheduler`, settings.CELERY_BEAT_SCHEDULE не подхватывается автоматически).

**Featured brands в БД (вечером 24 мая, после получения брендбуков от владельца):**
1. Ballu ✓ лого (rkcdn.ru)
2. Electrolux ✗ нет лого ни в API, ни локально — рендерится как текст
3. Royal Clima ✓ лого (breez.ru SVG)
4. Hisense ✓ лого (breez.ru SVG)
5. Funai ✓ лого (breez.ru SVG)
6. Midea ✓ лого (PNG, локально из брендбука)
7. Daichi ✓ лого (SVG, локально из брендбука Daichi 2021)
8. Kentatsu ✓ лого (SVG, локально из брендбука)

Файлы хранятся в `static/images/brands/` (закоммичены в репо). View `_brand_logo_static` ищет файл в `BASE_DIR/static/` ИЛИ `STATIC_ROOT` — оба пути работают.

**r6. Breeze API для лого** — `api.breez.ru/v1/brands/` (Basic Auth через `BREEZ_AUTH_HEADER`). Опция `--from-breeze` в `download_brand_logos`. Breeze отдаёт 53 бренда — преимущественно собственные торговые марки (Zilon, etc.). Полезен в комбинации с `--from-rusklimat` для разных источников.

### Свежие коммиты (24 мая r-итерация)

```
492963b fix(catalog): объединить полупромышленные категории + убрать аксессуары
03aeb3e feat(catalog): по умолчанию показываем только то, что в Крыму (home/catalog/similar)
4f632ff feat: модальный success для лидов + кнопка «Поделиться» в карточке товара
93c29ea fix(leads): /selection/ — форма пропадает после отправки + quick-order модалка auto-close
42523d3 docs(handoff): финал r-итерации — все 7 featured-брендов с лого
f1697ce feat(catalog): локальные лого Daichi/Daikin/Kentatsu/Midea/Axioma + опция --from-breeze
ef8d840 docs(handoff): полное состояние после деплоя r-итерации
30c6284 fix(quiz): _brand_logo_static проверяет и STATIC_ROOT, не только BASE_DIR/static
7e64ed0 fix(catalog): fuzzy match для брендов из rusklimat API
1ce91ac fix(catalog): download_brand_logos пропускает не-image Content-Type
b5337b8 feat(catalog): download_brand_logos --from-rusklimat — авто-подтяжка logo_url
662fd03 fix(sync): fallback на статичный RUSKLIMAT_JWT_TOKEN при ошибке fetch_jwt
adc744a docs(handoff): запись о r-итерации (квиз v2 + JWT auto-refresh)
8d97a25 feat(sync): auto-refresh Rusklimat JWT (User-Agent catalog-ip, cron 23:50 МСК)
4a7d9fa feat(quiz): Wi-Fi и бренд как шаги, кнопка «Назад», удалить шаг «Цвет»
```

### Финальный smoke-test на проде (24 мая, 15:35 МСК)

Полный flow квиза через curl с CSRF:
```
POST /leads/quiz-step/  step=7 → result
  area_sqm=25, room_type=apartment, inverter=yes, wifi=yes,
  heating=no, budget=50000, brand=56 (Ballu)
→ HTTP 200, 5085 bytes
→ 3 товара Ballu (BSTI-09HN8 34590₽, BSTI-12HN8 42490₽, BSOI-12HN8 41490₽)
→ alt 12k BTU (secondary, граница 25 м²), релаксаций нет
→ QuizResult: area=25, wifi=True, brand=Ballu, btu=9
```

JWT auto-refresh:
```
$ manage.py refresh_rusklimat_jwt --show
JWT обновлён (длина 232 символа)
$ manage.py sync_rusklimat_rest --max-pages 1
Rusklimat REST sync: updated=326, stocks=326, specs=115  (без 401)
```

---

## Update 2026-05-21 (q-итерация) — стабильность сайта + покрытие тестами + B2C-фичи

**q1. Hotfix quiz_picker.** На проде AI-подбор после 6 шагов отдавал «не нашлось моделей» + форму контактов, что воспринималось как «выкинуло на регистрацию». Корень: `recommend_products` возвращал пусто, потому что у активных товаров `Product.btu_calc=NULL` после большой переcинхронизации (никто не запустил `compute_btu`). Добавил 5-й уровень релаксации `btu_relaxed`: после снятия цвет→бюджет→инвертор снимаем сам BTU-фильтр и показываем доступные модели с пометкой «точную мощность подтвердит менеджер». Параллельно `logger.warning` в `quiz_step` пишет в `docker logs` диагностический след пустого результата. Файлы: `apps/leads/quiz_logic.py`, `apps/leads/views.py`, `templates/leads/partials/_quiz_step.html`. Прод-фикс параллельно: `docker compose exec web python manage.py compute_btu`.

**q2. Hotfix каталог-flicker.** При быстром browser-back из `product_detail.html` в каталог страница оставалась голой (без стилей). Виновник — `<script src="https://cdn.tailwindcss.com">` в `base.html`: runtime JIT не успевал применить классы при bfcache-нагрузке. Перешли на скомпилированный CSS:
- `tailwind.config.js` (новый) — переносит бренд-цвета `accent/teal/ink/surface`, шрифт Onest, `rounded-card` из inline-конфига. Content сканирует `templates/**/*.html`, `apps/**/templates/**/*.html` и `apps/**/*.py` (там тоже Tailwind-классы в filters/views).
- `static/css/tailwind-src.css` — `@tailwind base/components/utilities`.
- `Dockerfile` — качает Tailwind standalone v3.4.17 (без Node), компилирует в `static/css/tailwind.css`, удаляет binary.
- `base.html` — `<script cdn>` + inline-config → `<link static 'css/tailwind.css'>`.
- `production.py` — `STATICFILES_STORAGE = 'ManifestStaticFilesStorage'` (хешированные имена, cache-bust после deploy).
- `.gitignore` — `static/css/tailwind.css` (output, генерится в build).

Deploy: `docker compose build --no-cache web && docker compose up -d web && docker compose exec web python manage.py collectstatic --no-input`.

**q3. Unit-тесты 5 модулей.** Закрыли исходный пункт TODO 2026-05-20. Стек как в существующем `apps/sync/tests/test_client.py` (`django.test.TestCase` + `unittest.mock`, без новых зависимостей). Покрыто:
- `apps/catalog/btu.py` — все 4 конвертации (kBTU/BTU/kW/W), приоритет единиц, blacklists, **XIGMA TXE27-trap** (27 в артикуле — площадь, не BTU), **Ballu Eclipse-40-trap** (40 — серия), каскад `compute_btu` → `resolve_btu` (кеш) → `refresh_btu_calc`.
- `apps/leads/quiz_logic.py` — `btu_candidates` с border tolerance, `_balance_by_source` round-robin 2+2+2 / перекос / dedup / truncation, `recommend_products` все 5 уровней релаксации (включая новый `btu_relaxed`), `commercial`→exclude_mobile, исключение мульти-блоков.
- `apps/sync/warehouse_stock.py` — `_parse_qty` (`>50`→50, мусор→0), `_normalize_warehouse_name` (Симферополь, опечатка Симфирополь), `_CRIMEA_RE` (Бриз Крым / Ялта), `write_warehouse_stocks` (Крым priority, fallback, идемпотентность, replace-стратегия).
- `apps/sync/rusklimat_rest._sync_tech_specs` — v1/v2 форматы, TechSpec cache hit/miss, replace-strategy, dedup по `spec.pk`. **Mock-адрес** `apps.catalog.btu.refresh_btu_calc` (импорт inside функции).
- `apps/sync/tasks._iter_leftoversnew` — все 3 формата (dict / list-of-single / flat), `setdefault('nc')`, edge cases.

**q4. View-тесты.** Защита HTTP-эндпоинтов:
- `apps/leads/tests/test_views_quiz.py` — GET /quiz/, POST /leads/quiz-step/ промежуточный и финальный (с/без товаров), /leads/quiz-lead/ (200 / 404 / 400).
- `apps/catalog/tests/test_views_catalog.py` — GET /catalog/ + фильтры + HX-Request фрагмент + /product/<slug>/ + /availability/.
- `apps/leads/tests/test_views_orders.py` — POST /leads/quick-order/ с/без product_id, invalid form, GET → 405.
- `apps/accounts/tests/test_views_dashboard.py` — физлицо/юрлицо ветки, `/pending/` для неодобренных юрлиц.
- `apps/accounts/tests/test_registration.py` — discount_percent ставится при регистрации физлица, override_settings, `get_wholesale_price` реально считает 1000 → 850.

Все мокают `send_telegram` (patch на `apps.leads.views.send_telegram` / `apps.orders.views.send_telegram`).

**q5. Скидка 15% — реальная механика.** Плашка «Скидка до 15% при регистрации» висела по сайту, но `User.discount_percent` никогда не инициализировался — оставался 0. Инфраструктура (поле, `get_wholesale_price`, `CartItem.subtotal`) уже была.
- `settings.DISCOUNT_PERCENT_INDIVIDUAL=15` (override через `.env` для маркетинговых акций).
- `IndividualRegistrationForm.save()` ставит `discount_percent`.
- `accounts/migrations/0003_set_individual_discount.py` — data migration: для всех `account_type='individual'` с `discount_percent=0` ставит значение из settings. Юрлица и уже-настроенные не трогаются.
- `templates/orders/checkout.html` — строка «Применена ваша скидка −15%» если `user.discount_percent > 0`.
- `apps/orders/views.py` — email/Telegram уведомления заказа упоминают процент.

Deploy требует `python manage.py migrate accounts`.

**q6. ЛК физлица.** Dashboard был заточен под юрлица (карточки Компания/ИНН + кнопки экспорта оптового прайса). После B2C-пивота физлица — основная аудитория, видели чужие поля. `templates/accounts/dashboard.html` теперь ветвится по `user.account_type`:
- Физлицо: Email / Телефон+мессенджер / Скидка с пометкой «Применяется автоматически в корзине». Без кнопок прайса.
- Юрлицо: как раньше (Компания/ИНН/Скидка + Excel/PDF прайс).

**q7. /availability/.** Публичная страница «что прямо сейчас в наличии на крымском складе». View `apps/catalog/views.availability` фильтрует `WarehouseStock` по `warehouse__iexact='Симферополь'` (по умолчанию, можно переопределить `?warehouse=Москва`), `quantity > 0`, активным товарам, `category.sync_enabled=True`, исключая мульти-блоки. Шаблон с таблицей + пустым состоянием. SEO meta_description. URL-имя `availability`.

**q8. README.md.** Onboarding-документ: стек, структура apps, команды `manage.py`, тесты, deploy. Не дублирует HANDOFF.md — он отвечает на «как запустить», HANDOFF на «что мы делали и почему».

### Свежие коммиты (21 мая q-итерация)
```
4f44d23 docs: добавлен README.md — onboarding-документ проекта
4d4245d feat(catalog): публичная страница /availability/ — что прямо сейчас в Крыму
d130b58 feat(account): ЛК физлица — email/телефон/скидка вместо ИНН/компании
0ed596b feat(discount): применение скидки 15% при регистрации физлица
a4ccb89 test(views): HTTP-тесты quiz / catalog / quick-order через Django Client
87177fd test: unit-тесты для btu / quiz_logic / warehouse_stock / rusklimat / leftovers
4c8ed23 fix(ui): Tailwind CDN → compiled static/css/tailwind.css
3997414 fix(quiz): спасательная релаксация BTU + логирование пустого подбора
```

### Что осталось из TODO

- **Rusklimat JWT auto-refresh** — внешний блокер (нужны API-credentials).
- **Compare** (сравнение товаров) — большая UX-фича, требует обсуждения.
- **Кастомная админка** — большая фича, требует обсуждения сценариев.
- **Прод-deploy q-итерации** — `git pull && docker compose build --no-cache web && docker compose up -d web && docker compose exec web python manage.py migrate && docker compose exec web python manage.py collectstatic --no-input && docker compose exec web python manage.py compute_btu`.

---

## Update 2026-05-21 (вечер) — cleanup устаревшего Rusklimat scraping

**O1. Удалены legacy-файлы.** Старый scraping `b2b.rusklimat.com` давно заменён REST-клиентом `internet-partner.rusklimat.com` (см. `memory/rusklimat_rest.md`), но мёртвый код висел в репо и в Celery Beat. Снёс:
- `apps/sync/rusklimat_scraper.py` — login + BeautifulSoup парсинг HTML-каталога.
- `apps/sync/rusklimat_catalog.py` — CSV-импорт прайса.
- `apps/sync/rusklimat_stock.py` — YML-парсер остатков.
- `apps/sync/rusklimat_client.py` — клиент `remains.b2b-one.rusklimat.com` (резервный, тоже legacy).
- `apps/sync/management/commands/sync_rusklimat.py`, `remap_rusklimat_categories.py`.

**O2. Helpers вынесены.** `_resolve_master_category`, `_make_unique_slug`, `_CATEGORY_RULES` использовались `apps/sync/management/commands/remap_categories.py` (актуальная объединённая команда). Заинлайнил их прямо в `remap_categories.py` — теперь файл self-contained, не тянет legacy.

**O3. Celery Beat schedule почищен.** `splithome/settings/base.py:CELERY_BEAT_SCHEDULE` — убраны `sync-rusklimat-stock-hourly` (`sync.sync_rusklimat_stock`) и `sync-rusklimat-catalog-daily` (`sync.sync_rusklimat_catalog`). Новый REST-sync пока **не на расписании** — JWT-токен надо обновлять руками раз в сутки, авто-refresh нужно ждать API-credentials от Rusklimat. До тех пор владелец запускает `python manage.py sync_rusklimat_rest` руками.

**O4. Settings + .env подчищены.** Убраны `RUSKLIMAT_LOGIN`, `RUSKLIMAT_PASSWORD`, `RUSKLIMAT_AC_CATALOG_URL` — нужны были только scraper'у. Оставлены `RUSKLIMAT_JWT_TOKEN`, `RUSKLIMAT_CONTRACTOR_GUID` — используются новым REST-клиентом.

**O5. Celery tasks почищены.** `apps/sync/tasks.py` — удалены три legacy-task: `build_rusklimat_mapping` (rusklimat_guid теперь пишется при REST-sync), `sync_rusklimat_catalog`, `sync_rusklimat_stock`. Импорт `RusklimatClient` тоже снят.

### Свежие коммиты (21 мая вечер)
```
(будет добавлен после коммита)
```

---

## Update 2026-05-21 — email-уведомления при регистрации

**N1. Welcome / pending email пользователю.** До этой итерации `apps/accounts/signals.py` уведомлял только менеджера (email + Telegram), пользователь молча оказывался либо на главной (физик), либо на `/pending/` (юр). Расширил signal: добавил `_notify_user(user)` с веткой по `instance.account_type`:

- **Физлицо (`individual`)**: subject «Добро пожаловать в SplitHome», тело со скидкой 15%, ссылкой на каталог и номером поддержки.
- **Юрлицо (`company`)**: subject «Заявка на регистрацию получена — SplitHome», тело «менеджер откроет доступ в течение 1 рабочего дня».

Менеджерская часть (`_notify_manager`) вынесена в отдельную private-функцию без функциональных изменений — email + Telegram продолжают приходить на каждую регистрацию (физ и юр одинаково, по запросу владельца). Receiver переименован `notify_manager_on_registration` → `notify_on_registration`.

Константа `SUPPORT_PHONE = '+7 978 579-29-95'` — подставляется в welcome-тело физлицам.

**Smoke на проде:** регистрация физлица `flycited@gmail.com` (id=3) и юрлица `flycited+company@gmail.com` (id=4, ИНН 7706739445, ООО Тест) через форму в `manage.py shell`. Оба письма доставлены в Gmail-inbox, менеджер получил уведомления — подтверждено владельцем.

**Файлы изменены:** только `apps/accounts/signals.py` (+59 −11). Миграции не нужны.

**Что не трогали:**
- `apps/accounts/admin.py:approve_users` — email при одобрении дилера уже шлётся, оставили.
- `apps/accounts/forms.py`, `views.py` — никаких изменений, signal обрабатывает всё.
- SMTP-настройки уже работали (DKIM/SPF настроены в Hestia, см. `memory/mail_server.md`).

### Свежие коммиты (21 мая)
```
9e714ba feat(accounts): welcome email физлицу + pending email юрлицу при регистрации
```

### Открытые задачи (см. `memory/todo_2026_05_20.md`)
- **Rusklimat auto-refresh JWT** — нужны API-credentials.
- **SplitHub.ru как 4-й поставщик** — API-credentials.
- **Rusklimat btu_calc 85%** — 405 товаров без power/area в tech_values.
- **Скидка 15%** — реальной механики нет.
- **Удалить устаревший Rusklimat scraping**.
- План квиза `hashed-jumping-iverson` ждёт владельца.

---

## Update 2026-05-20 (ночь) — M-полировка: product_detail / scroll-top / favicon revert

**M1. product_detail badge — унификация с каталогом.** Жалоба: на странице товара стояло «В Крыму: N шт.» с зелёным фоном, а в каталоге «На складе» — рассинхрон формулировок. Поправил `templates/catalog/product_detail.html:91-101`: объединил blue+amber в один синий «Под заказ», зелёный «На складе» только при `Stock.warehouse='Симферополь' AND in_stock`. Теперь два состояния: **«На складе: N шт.»** (зелёный) или **«Под заказ[: N шт.]»** (синий) — везде одинаково.

**M2. Global scroll-top на любых HTMX swap каталога.** Жалоба: после клика «Вперёд» на пагинации страница оставалась в той же позиции. Inline `hx-on::after-swap` (добавил в прошлой итерации) не сработал. Заменил на глобальный listener в `templates/base.html:46`:
```js
document.addEventListener('htmx:afterSwap', function(e) {
  if (e.target && e.target.id === 'catalog-results') {
    window.scrollTo({top: 0, behavior: 'smooth'});
  }
});
```
Сработает на пагинации, сортировке и любых фильтрах. Inline hx-on убран как избыточный.

**M3. Favicon — две итерации отклонены, откат к swirl.png.**
- Попытка #1: `favicon splithome.jpg` с текстом «splithome.ru» — отклонена (текст не читается в 16×16).
- Попытка #2: `favvicon2.jpg` (дом+кондиционер без текста) — отклонена.
- Откат к исходному `static/img/swirl.png` (стеклянная спираль) — принят. Пересобрал полный набор в `static/img/favicon/`.
- Header/footer лого автоматически обновился (он ссылается на `favicon-192.png`).

**Гочи Docker build.** Дважды попадался: новый favicon.ico в репо был размером 17336, а на проде через nginx отдавался размером 16225 (старая версия). Корень — Docker layer cache: `COPY . .` не пересобирается при изменении бинарных файлов одинакового размера/mtime. Решение: `docker compose build --no-cache web` при замене бинарных asset'ов. Записал в `memory/feedback_docker_cache.md`.

### Свежие коммиты (ночь 20 мая)
```
c044c96 revert(brand): favicon ← swirl.png (стеклянная спираль)
754be8e fix(ux): новый favicon (без текста), product_detail badge, global scroll-top
2c129b0 docs(handoff): Update 2026-05-20 вечер — L-итерация
e4eb9d0 feat(brand): новый favicon splithome — ico + png + apple-touch + og-image
871a270 feat(btu): refresh_btu_calc хук после каждого _sync_tech_specs
9f3dcfc feat(btu): Product.btu_calc + три точки контроля (мощность/площадь/артикул)
fe9f9cf feat(catalog): badge «На складе», 4×4 = 16 карточек, фильтр Крым only
910e2b6 fix(catalog): первичный ключ сортировки — реальное наличие в Крыму
```

### Открытые задачи (см. `memory/todo_2026_05_20.md`)
- **Rusklimat auto-refresh JWT** — нужны API-credentials.
- **SplitHub.ru как 4-й поставщик** — API-credentials.
- **Rusklimat btu_calc 85%** — у 405 товаров нет мощности/площади в tech_values.
- **Скидка 15%** — реальной механики нет.
- **Удалить устаревший Rusklimat scraping**.
- План квиза `hashed-jumping-iverson` ждёт владельца.

---

## Update 2026-05-20 (вечер) — L-итерация: badge / sort / grid / BTU / favicon

**L1. Badge «В Крыму» → «На складе»** — `templates/partials/product_card.html`. Зелёный badge только при `Stock.warehouse='Симферополь' AND in_stock`. Всё остальное (Бриз Шерризон/Ростов, Rusklimat Краснодар/Киржач через fallback в `write_warehouse_stocks`) — синий «Под заказ».

**L2. Фильтр «Только в наличии» = только Крым.** `filter_in_stock` в `apps/catalog/filters.py` теперь добавляет `Q(stock__warehouse='Симферополь', stock__quantity__gt=0)`. Раньше просто `quantity__gt=0` ловил fallback-варианты.

**L3. Pagination scroll-to-top.** `hx-on::after-swap="window.scrollTo({top:0, behavior:'smooth'})"` на ссылках «Назад/Вперёд» в `templates/catalog/partials/_results.html`.

**L4. Сетка 4×4 = 16 карточек.** `Paginator(qs, 16)` (было 24). На xl-экранах ровно 4 ряда по 4 карточки.

**L5. Новый favicon SplitHome.** Сгенерировал из исходника владельца (`favicon splithome.jpg`) полный набор: `favicon.ico` (multi-size 16/32/48/64), `favicon-{16,32,48,96,192,512}.png`, `apple-touch-icon.png` (180×180), `og-image.jpg` (1200×630). Все в `static/img/favicon/`. Подключено в `templates/base.html` (4 `<link rel="icon">` + apple-touch + og-image), `header.html`/`footer.html` (логотип через `favicon-192.png`), `home.html` JSON-LD `LocalBusiness.image` через `favicon-512.png`. Старый `swirl.png` больше не используется.

**Деплой favicon — нюанс**: nginx раздаёт `/static/` из `/opt/oasis/staticfiles/` (host-путь), а `collectstatic` пишет в docker volume `/var/lib/docker/volumes/oasis_static_files/_data/`. Нужно после `collectstatic` делать `rsync -a /var/lib/docker/volumes/oasis_static_files/_data/ /opt/oasis/staticfiles/`. См. `memory/server_deploy.md`.

**L6. BTU из tech_values — переработан полностью.** Новое поле `Product.btu_calc` (IntegerField, db_index) хранит вычисленный BTU. `resolve_btu` теперь имеет 3 точки контроля:
1. TechSpec холодопроизводительность: kBTU > BTU > кВт > Вт (с конвертацией: 1 kW = 3.412 kBTU, 1 Вт = 0.003412 kBTU).
2. TechSpec рекомендуемая площадь (`Эффективен для помещ`, `Для помещения площад`) → ближайший BTU из `BTU_TO_AREA`.
3. `extract_btu(articul)` — последний fallback.

Проблема жалобы: артикул `Ballu BPAC-14` → 14 BTU из артикула, но реально это маркетинговый индекс — реальная мощность 7 kBTU (по площади 18 м² и кВт=2). Аналогично XIGMA TXE27 (27 м², НЕ 27 BTU). Теперь `btu_calc` для них корректные 7 и 9 соответственно.

Bootstrap всех 4439 активных товаров — `python manage.py compute_btu`. Покрытие: breeze 99%, daichi 100%, rusklimat 85%. Хук `refresh_btu_calc(product)` подключён после каждого `_sync_tech_specs` в `apps/sync/{breeze_tech,daichi_catalog,rusklimat_rest}.py` — при будущих sync новые товары сразу получат btu_calc.

Фильтр каталога `_btu_q` (filters.py) и квиза (`apps/leads/quiz_logic.py`) переключены с `articul__iregex` на `Q(btu_calc__in=values)`. Это решает проблему «болу 40 ≠ 40 000 BTU» о которой говорил владелец.

### Сортировка каталога (доделано в этой же итерации, K2)
`catalog()` default ordering — `annotate(is_crimea=Case(When(stock__warehouse='Симферополь', then=1), default=0))` + `order_by(F('is_crimea').desc(), F('stock__quantity').desc(nulls_last=True), 'title')`. Топ-страница — все 16 карточек с зелёным «На складе».

### Свежие коммиты (вечер 20 мая)
```
e4eb9d0 feat(brand): новый favicon splithome — ico + png + apple-touch + og-image
871a270 feat(btu): refresh_btu_calc хук после каждого _sync_tech_specs
9f3dcfc feat(btu): Product.btu_calc + три точки контроля (мощность/площадь/артикул)
fe9f9cf feat(catalog): badge «На складе», 4×4 = 16 карточек, фильтр Крым only, scroll top
910e2b6 fix(catalog): первичный ключ сортировки — реальное наличие в Крыму
21efd0b feat(catalog): двухуровневая сортировка — Крым → любой склад → title
9a27a0b feat(prod): LOGGING StreamHandler для 500 traceback в docker logs
b329bf9 fix(btu): импорт resolve_btu в views.py (фикс 500 на product_detail)
```

### Открытые задачи (см. `memory/todo_2026_05_20.md`)
- **Rusklimat auto-refresh JWT** — нужны API-credentials.
- **SplitHub.ru как 4-й поставщик** — API-credentials.
- **Rusklimat btu_calc 85%** — у 405 товаров нет ни мощности, ни площади.
- **Скидка 15%** — реальной механики нет.
- **Удалить устаревший Rusklimat scraping** и `static/img/swirl.png`.
- План квиза `hashed-jumping-iverson` ждёт владельца.

---

## Update 2026-05-20 (день) — BTU из tech_values, 500 на product_detail, Бриз Крым открыт, Docker-зеркало

**J4. BTU приоритетно из tech_values.** Изначально жалоба пользователя: на карточке XIGMA `XGI-TXE27RHA` в quick-facts показывалось «27 000 BTU» (из артикула), а в табе характеристик «Холодопроизводительность (kBTU) = 9» (из API Бриза) — рассинхрон. Корень: XIGMA маркирует артикул цифрой ПЛОЩАДИ помещения (м²), а не BTU. Старый `extract_btu(articul)` ловил `27` и трактовал как BTU.

- Новая функция `apps/catalog/btu.py:resolve_btu(product)` — приоритет:
  1. `product.tech_values.all()` — берёт первую запись TechSpec, у которой `title` содержит «холодопроизв» / «мощность охлажд» / «cooling capacity» **и** unit/title содержит `kbtu`/`btu` (исключая `квт`/`kw`).
  2. Парсит value (`9`, `9.5`, `2.65 (0.7 - 3.37)`), округляет до ближайшего из `BTU_TO_AREA`.
  3. Fallback на `extract_btu(articul)` — для товаров без tech_values.
- `apps/catalog/views.py:product_detail`, `apps/catalog/templatetags/catalog_extras.py:btu_for` — переключены на `resolve_btu`.
- В каждый queryset, отдающий товар в шаблон, добавлен `prefetch_related('tech_values__spec')` (предотвращает N+1).

**Фикс 500 на product_detail (b329bf9).** После выкатки `resolve_btu` каждая страница `/product/.../` отдавала 500. В docker logs и nginx error.log — пусто. Корень: в `views.py` я вызвал `resolve_btu(product)`, но забыл импорт. `NameError` проглатывался Django потому что в `splithome/settings/production.py` нет `LOGGING`-конфига. См. `memory/debugging_prod_500.md` — методика поимки traceback через `manage.py shell` + `Client(HTTP_X_FORWARDED_PROTO="https")`.

**Бриз Крым — доступ к API открыт.** После запроса через форму «Отправить запрос» на api.breez.ru Бриз расширил права ключа `flycited@gmail.com` на склад «Бриз Крым». Текущий sync_stock: `"Бриз Крым": {"total": 1890, "nonzero": 286}`. UI и WarehouseStock автоматически подтянули. См. `memory/breez_warehouse_diagnosis.md`.

**Docker-билд — переключён на mirror.yandex.ru.** При сборке web-контейнера `apt-get update` падал: Fastly CDN (199.232.x.x для `deb.debian.org`) недоступен с нашего VPS (firewall блокирует :80 наружу). `Dockerfile` теперь делает `sed -i 's|http://deb.debian.org|http://mirror.yandex.ru|g'` по `sources.list.d/debian.sources` или `sources.list` перед `apt-get install`. Параллельно пин на `python:3.12-slim-bookworm` (Debian 12 stable — у trixie репозитории нестабильны).

### Свежие коммиты (20 мая)
```
b329bf9 fix(btu): импорт resolve_btu в views.py (фикс 500 на product_detail)
61e342f fix(docker): зеркало Debian → mirror.yandex.ru (Fastly CDN недоступен с VPS)
5fdc67d fix(docker): пин python:3.12-slim-bookworm (Debian 12)
018e738 fix(btu): BTU из tech_values «Холодопроизводительность» вместо артикула
d429b14 feat(sync): Daichi Business partner API integration
```

### Открытые задачи (см. `memory/todo_2026_05_20.md`)
- **`LOGGING` в production.py** — добавить StreamHandler ERROR, чтобы 500 на проде логировались.
- **Rusklimat auto-refresh JWT** — нужны отдельные API-credentials.
- **SplitHub.ru как 4-й поставщик** — нужны API-credentials.
- **Скидка 15%** — реальной механики нет, только плашка.
- **Удалить устаревший Rusklimat scraping** — заменён REST-клиентом.
- **План `~/.claude/plans/hashed-jumping-iverson.md`** (квиз → цвет/площадь-пилюли/relaxed-list) — ждёт владельца.

---

## Update 2026-05-19 — регистрация, cookie, LLM-SEO, мобильная адаптация, Бриз-диагноз

**I3. Регистрация физлицо/юрлицо** — `/auth/register/` с двумя табами. По умолчанию «Физлицо» (email + телефон + опц. Telegram/Max + согласие на ПД). Авто-логин после регистрации. Юрлицо — отдельная стилизованная форма (`fieldset` + `legend`: Контактное лицо / Реквизиты / Пароль), валидация ИНН (10 или 12 цифр), `inputmode=numeric`. После регистрации юрлица — pending до одобрения менеджером. См. `memory/registration_forms.md`. Файлы: `apps/accounts/forms.py`, `templates/accounts/register.html`, миграция `accounts/0002_account_type_messenger`.

**I4. Cookie banner + Privacy** — banner внизу страницы при первом визите (флаг в localStorage, кнопки «Принять» / «Только необходимые»). Страница `/privacy/` со стандартным текстом 152-ФЗ (собираемые данные, цели, права пользователя). Файлы: `templates/base.html`, `templates/pages/privacy.html`, URL `/privacy/` в `splithome/urls.py`.

**I5. LLM-SEO** — `/llms.txt` по стандарту llmstxt.org (описание, география, бренды, BTU-таблица). `/robots.txt` теперь явно разрешает GPTBot, ChatGPT-User, PerplexityBot, ClaudeBot, anthropic-ai, Google-Extended, CCBot. Schema.org JSON-LD: `LocalBusiness` на главной (адрес Симферополь, areaServed Крым, opening hours), `Product+Offer` на карточках (priceCurrency=RUB, availability=InStock|PreOrder).

**I6. Кликабельные labels в фильтре** — «Только в наличии» обёрнут в `<label>`, клик по тексту переключает чекбокс.

**Бриз Крым — окончательный диагноз** — API `/v1/leftoversnew/` возвращает qty=0 на «Бриз Крым» у всех 4667 товаров. На B2B-портале для того же аккаунта остатки есть (NC-1761129 — 8+282 шт). Реверс-инжиниринг SPA + Keycloak показал: scraping `b2b.breez.ru` невозможен (Keycloak realm `breez` блокирует `password`/`implicit`/`code_no_secret`). Перепарсили `sync_stock` по новой инструкции Бриза (robust парсер `_iter_leftoversnew` поддерживает оба формата JSON, диагностика по складам в логах). Sync пишет правильные данные — просто API отдаёт ноль. Действие — запросить расширение прав API-ключа у Бриза. См. `memory/breez_warehouse_diagnosis.md`. Fallback в `apps/sync/warehouse_stock.py`: если в Крыму 0, но есть на Шерризон/Ростов — `Stock.quantity = сумма`, badge синий «Под заказ: N шт.», ссылается на блок остатков по складам в карточке.

**J1. Стилизованная форма юрлица** — переписал unstyled `{{ field }}` Django-render на ручной HTML с теми же классами что у физлица (border-ink/15 + focus:border-accent), placeholder'ами («ООО Ромашка», «7706739445», «119180, г. Москва...»), help-текстами под полями, красными звёздочками * у required. Бэкенд: `clean_inn()` валидирует длину 10/12 цифр, username=email при сохранении.

**J2. Мобильная адаптация** — header получил burger-кнопку (`md:hidden`) с drawer-меню. Каталог `/catalog/` — на `< lg` sidebar скрыт (`hidden lg:block`), сверху кнопка «Категории и фильтры» (`toggleCatalogSidebar()`). Раньше сайдбар `w-64` оккупировал 256px на мобиле — фатальный баг. См. `memory/mobile_responsive.md`. Файлы: `templates/partials/header.html`, `templates/catalog/index.html`.

### Свежие коммиты (19 мая)
```
df68e95 feat(mobile): burger menu в header + collapsible sidebar каталога
b28b150 feat(sync): Breez sync_stock — robust парсер + диагностика складов
913bb44 fix(register): стилизованная форма юрлица + ИНН-валидация
4222439 fix(home): Хиты сезона только сплит-системы (без аксессуаров/осушителей)
805b6e7 feat(stock): «Под заказ из X: N шт.» вместо «Под заказ» при остатке на не-крымских складах
2484420 fix(stock): обработка quantity='>50' от Бриза
d325e1d feat(ux): I3 регистрация + I4 cookie + I5 LLM-SEO + I6 labels
```

### Открытые задачи
- **Бриз Крым** — запросить у Бриза расширение API-ключа на склад Крым.
- **Rusklimat auto-refresh JWT** — нужны отдельные API-credentials от Rusklimat.
- **SplitHub.ru как 4-й поставщик** — нужны API-credentials.
- **Скидка 15%** — пока только маркетинговая плашка, реальной механики нет.
- **Удалить устаревший Rusklimat scraping** (`apps/sync/rusklimat_scraper.py`, `rusklimat_catalog.py`).

---

## Update 2026-05-18 (вечер) — TechSpec у всех 3 поставщиков + per-warehouse остатки + Rusklimat REST

**TechSpec sync — закрыли «таб всегда disabled».** TechSpec total **612**, ProductTech **144 793**, у каждого активного товара трёх поставщиков теперь есть полный набор технических характеристик. На карточке таб «Технические характеристики» открывается с реальными данными.

- **Бриз (245 TechSpec, 1137 товаров):** новый модуль `apps/sync/breeze_tech.py`. Endpoint `GET /v1/tech/?id={breez_id}` — характеристики по **внутреннему id** Бриза, не nc_code. Mapping `nc_code → breez_id` берётся из `/v1/products/` full dump. ~1137 HTTP-запросов, rate-limit 0.15с, прогон ~5 минут. Команда: `python manage.py sync_breez_tech`.
- **Daichi (92 TechSpec, 495 товаров):** расширен `apps/sync/daichi_catalog.py`. `/productparams/get/` отдаёт ATTR_* поля — `_sync_tech_specs(product, pp_data, category, tech_cache)` парсит в TechSpec (по title, без unique-ключа) и ProductTech. Дедупликация через `filter().first()` — наследие старых sync без unique.
- **Rusklimat (275 TechSpec, 899 товаров):** в `apps/sync/rusklimat_rest.py:_sync_tech_specs`. `properties` dict у товара v2 API = `{prop_uuid: {value, unit_uuid}}`. TechSpec.external_uuid = prop_uuid. Загружаем `/properties` (2161 свойство) и `/units` (156 единиц) один раз — кэш.

Миграции: `catalog/0008` (`TechSpec.breez_id` теперь null=True), `catalog/0009` (новое поле `TechSpec.external_uuid`).

**Rusklimat REST API — заменил сломанный scraper.** Старый scraping `b2b.rusklimat.com` получал HTTP 403 на login с VPS (IP-block). Перешли на REST API на отдельном домене `internet-partner.rusklimat.com` (с VPS отвечает нормально).

- **Swagger:** `https://internet-partner.rusklimat.com/swagger/v1/swagger.json` — OpenAPI 3.0 со всеми 5 endpoints.
- **Endpoints:** `GET /api/v1/InternetPartner/{partnerId}/requestKey` (~60s сессия), `GET .../categories/{key}`, `GET .../properties/{key}`, `GET .../units`, `POST /api/v{1|2|3}/.../{partnerId}/products/{key}` (v2 — с unit_uuid).
- **JWT в .env** как `RUSKLIMAT_JWT_TOKEN` — срок жизни ~сутки. **partnerId извлекается прямо из JWT-payload** (поле `guid`), а не из `.env` — иначе 403 «PartnerId не соответствует JWT». В `.env` остался старый GUID `7d42c370-...`, а JWT под `e51a9046-...` — расхождение разрешается автоматически.
- **Auto-refresh JWT не работает.** `POST https://b2b.rusklimat.com/api/v1/auth/jwt/` существует, но с user-кредами (`+79152757788/319820`) отдаёт `Invalid user/password`. Нужны отдельные API-credentials — запросить у Rusklimat. Пока обновляем JWT вручную через `/personal/internet_partner/catalog_api/` под логином.

Файлы: `apps/sync/rusklimat_rest.py` (клиент + sync), `apps/sync/management/commands/sync_rusklimat_rest.py`. Старые `rusklimat_scraper.py`, `rusklimat_catalog.py` — устарели, можно удалять.

Команда: `python manage.py sync_rusklimat_rest [--max-pages N]`. Полный прогон ~25 секунд (3 страницы × 500 товаров после фильтрации AC-категорий).

**Per-warehouse остатки — все 3 поставщика.** Новая модель `apps.stock.WarehouseStock(product, warehouse, quantity)` + миграция `stock/0002`. Один товар может иметь записи по нескольким складам.

Helper `apps/sync/warehouse_stock.write_warehouse_stocks(product, pairs)`:
- Replace-strategy: удаляет старые `WarehouseStock` товара, пишет новые.
- Нормализация имени склада (`_normalize_warehouse_name`): «симферополь склад» (Rusklimat) / «Симферопль» (опечатка Daichi) / любой `симфер*` → канонический **«Симферополь»**.
- Параллельно обновляет сводный `Stock`: `quantity = qty в Крыму`, `warehouse = 'Симферополь'`. Если в Крыму 0 — Stock.quantity=0 («Под заказ»).

Подключено в трёх sync-функциях:
- `apps/sync/rusklimat_rest.py:_sync_stock` — `remains.warehouses` → pairs.
- `apps/sync/daichi_catalog.py:sync_catalog` — `STORE.NAME` + `STORE_AMOUNT` (1 склад).
- `apps/sync/tasks.py:sync_stock` (Бриз) — `stocks[]` из `/leftoversnew/`.

Текущие склады в БД (на 2026-05-18):

| Склад | Поставщик | Σ остаток |
|---|---|---:|
| ррц Краснодар | Rusklimat | 52 581 |
| фрц Киржач | Rusklimat | 30 819 |
| **Симферополь** | Rusklimat + Daichi | **2 911** |
| ФРЦ Бриз Шерризон-Норд WMS | Бриз | 2 573 |
| РРЦ Бриз Ростов LV | Бриз | 144 |
| Бриз Крым | Бриз | 0 (API всегда возвращает 0) |

В Крыму сейчас 579 моделей доступно (147 в наличии прямо сейчас: 76 Rusklimat + 71 Daichi + 0 Бриз).

**UI карточки товара:** badge «В Крыму: N шт.» (зелёный, Stock.quantity>0) или «Под заказ» (амбер). Раскрывающийся `<details>`-блок «Остатки по складам (N)» — список всех `WarehouseStock`.

**Известная проблема Бриз Крым.** `/v1/leftoversnew/` отдаёт «Бриз Крым» с qty=0 для всех 4667 товаров. У владельца на B2B-портале Бриза есть видимые остатки в Крыму — значит, либо это резерв «под заказ» не в API, либо другой endpoint. Нужно уточнить у Бриза.

### Свежие коммиты (вечер 2026-05-18)
```
c47101c fix(stock): нормализуем имя склада «Симферопль/симферополь склад» → «Симферополь»
a516600 fix(stock): расширил Crimea-regex — ловит «Симферопль» (опечатка Daichi)
9354641 fix(sync): Daichi TechSpec dedup + Rusklimat title-filter аксессуаров
c7ee092 feat(stock): per-warehouse breakdown — все 3 поставщика + UI
8ddba55 feat(sync): Rusklimat — Crimea-only stock + TechSpec + skip БЕЗ МАРКИ
489793f fix(sync): Rusklimat REST — exclude аксессуаров + safe partial sync
14d7582 fix(sync): Rusklimat partnerId извлекаем из JWT, не из .env
5bdb504 feat(sync): Rusklimat REST API client + полный sync каталога
2d6e558 feat(sync): Breez tech sync — структурированные характеристики из /v1/tech/?id=
7d9114e fix(catalog): clean_description filter в tech-таблице
f808104 feat(sync): Daichi TechSpec — пишем ATTR_* в структурированные характеристики
```

### Открытые задачи (на потом)
- **Бриз Крым:** уточнить у поставщика как получать актуальные остатки крымского склада через API.
- **Rusklimat auto-refresh JWT:** запросить у поставщика отдельные API-credentials (user phone+password не подходят).
- **Удалить устаревший Rusklimat scraping:** `rusklimat_scraper.py`, `rusklimat_catalog.py`, `rusklimat_stock.py`, команды `sync_rusklimat` / `remap_rusklimat_categories`.
- **SplitHub.ru как 4-й поставщик** (бренды Бирюса, Тайкон, MDV) — нужны API-credentials.
- Логика скидки 15% при регистрации — пока только маркетинговая плашка.

---

## Update 2026-05-18 — B2C-pivot + большой UX overhaul

Владелец принял решение перевести SplitHome в **чисто розничную модель** (оптовые/дилерские продажи будут на отдельном сайте). За одну сессию закрыто 15 задач из обратной связи:

**B2C-pivot.** Дилерская оптовая цена убрана со всех страниц — везде показывается `Product.ric` (РРЦ). `show_price` логика выпилена из карточки товара, листинга и hero на главной. Для гостей показывается CTA «Скидка до 15% — при регистрации» (только маркетинг, реальной механики скидки ещё нет — см. todo_2026_05_18.md).

**Каталог-карточки (`/catalog/`).** Перевёрстан `templates/partials/product_card.html`: бренд контрастно, новая строка «9 000 BTU (до 25 м²)» через `apps/catalog/btu.py` + template-tag `{% btu_for product %}`, цена крупно всем, плашка «Скидка 15%» под ценой для гостей.

**Карточка товара (`/product/.../`).** Полная переверстка `templates/catalog/product_detail.html`:
- Quick-facts получили окантовку `border-ink/10` (раньше были плоские).
- Описание и Технические характеристики переделаны в **табы** (vanilla JS). Если `tech_values` пустой — таб «Характеристики» disabled с tooltip.
- Кнопка «**Поделиться**» рядом с «Купить в 1 клик»: dropdown с Email / Copy / Telegram / **MAX**.
- Secondary-кнопки «Подобрать другую / Заказать монтаж / Инструкция» — единый стиль `btn-outline`, без эмодзи.
- Похожие модели рендерятся через тот же product_card.html.
- HTML-эскейпы в описаниях Бриз/Rusklimat очищаются через template-фильтр `clean_description` (`apps/catalog/templatetags/catalog_extras.py`).

**Quiz (`/quiz/`).** 6-шаговый wizard (подробнее в memory `quiz_picker.md`):
- Шаг 1 — пилюли с площадью и BTU в скобках.
- Шаг 2 — 4 типа помещения (квартира / дом / офис / коммерция). При `commercial` подбор исключает «мобильные».
- Шаг 3 — 5 опций бюджета (30/40/50/70k/любой).
- Шаги 4-6 (инвертор, обогрев, цвет) теперь имеют третью кнопку **«Не знаю»** → соответствующий фильтр не применяется.
- Результат: **балансировка 2+2+2 по поставщикам** (`_balance_by_source` в `apps/leads/quiz_logic.py`). Round-robin по breeze/rusklimat/daichi, итого 6 моделей. При нехватке от одного — добиваем другими.
- Fallback при пустой выдаче: цвет → бюджет → инвертор (в порядке возрастания критичности). Возвращается `relaxed=[...]`, в шаблоне показывается плашка «По вашим параметрам не нашли — показываем…».

**Daichi (3-й поставщик).** Расширен `apps/sync/daichi_catalog.py`:
- Новый формат title: `{Brand} {Articul} {Series}` (раньше было generic «Бытовой кондиционер» из `ATTR_RUS_NAME_AX` — путало в листинге).
- Фотографии (`PHOTOES`) загружаются через `/productparams/get/` — у 100% Daichi-товаров теперь есть фото.
- Описание синтезируется из ATTR_* (`_build_description`) — мощность охлаждения, шум внутр/наружн, хладагент, цвет, габариты, вес, страна, срок эксплуатации. У 100% Daichi-товаров есть содержательное описание.

**Главная.** В hero-блоке «Премьера 2026» (`templates/home.html`) фото товара увеличено (max-h-32 → 64), блок занимает 3 строки grid (row-span-3), цена ric вместо price_wholesale.

**Мульти-блоки исключены** (`MULTI_SPLIT_BLOCK_Q` в `apps/catalog/filters.py`) из catalog view, home featured, sitemap и quiz. Внутренние/наружные блоки мульти-сплит-систем — компоненты, не самостоятельные кондиционеры, ≈40% активных AC.

### Открытые гэпы (см. `memory/todo_2026_05_18.md`)
- **TechSpec / ProductTech = 0 / 2474** у всех 3 поставщиков. Таб «Характеристики» поэтому всегда disabled. Daichi-данные доступны (ATTR_* в API), нужно дотюнить sync. У Бриза и Rusklimat — характеристики есть на сайтах поставщиков, в sync не парсятся.
- Rusklimat — 22% активных товаров без описания и фото (sync ломается на части товаров).
- Реальная механика скидки 15% при регистрации НЕ реализована — только маркетинговая плашка.

### Свежие коммиты
```
cf98375 feat(sync): Daichi title = Brand + Articul + Series
aa692b4 feat(ui): B2C-ориентация — РРЦ всем, информативные карточки, табы, поделиться
e9fb21d fix(catalog): двойной unescape + расширенный BTU regex
7488e6b fix(catalog): чистим escaped HTML из описаний Бриз/Rusklimat
b27853d feat(catalog): полная карточка + автоописание Daichi из ATTR_*
4ae619c feat(sync): загрузка фото Daichi через /productparams/get/
7024892 fix(catalog): исключить мульти-блоки из каталога, главной и sitemap
461dade fix(quiz): исключить мульти-блоки из подбора
8a6360a feat(quiz): подбор по цвету + relaxed-фолбэки, шаг 6, пилюли BTU
d429b14 feat(sync): Daichi Business partner API integration
```

---

---

## 1. Что это за проект

**SplitHome** — сайт продажи и монтажа сплит-систем по Крыму. Изначально стартовал как B2B-портал «Oasis» под оптовых клиентов (юрлица, скидки после одобрения менеджером), затем переименовался в «СплитХаб» (кириллицей), 2026-05-16 финально переведён на «SplitHome» (латиницей). С 2026-05-12 ведётся полная переверстка под B2C-розницу по дизайн-прототипу `flycited2-dotcom/SplitHub_roznica`. B2B-функционал (регистрация юрлиц, корзина с оптовыми ценами, личный кабинет) сохранён и продолжает работать.

**Домен:** `splithome.ru` (плюс `www.splithome.ru`).
**География:** весь Крым — Симферополь, Севастополь, Ялта, Евпатория, Феодосия, Керчь.
**Поставщики (два источника товара):**
- **Бриз** (api.breez.ru) — основной API, JSON.
- **Rusklimat** (b2b.rusklimat.com) — CSV-импорт каталога + персональный YML-прайс с остатками + web-scraping AC-каталога.

Под одним мастер-деревом категорий сводятся товары обоих поставщиков (миграция `ensure_master_categories`, синк управляется флагом `sync_enabled` на категорию).

---

## 2. Технологический стек

| Слой | Технология |
|---|---|
| Backend | Python 3.12, Django 5.2 |
| База данных | PostgreSQL 16 |
| Кэш + брокер | Redis 7 |
| Очередь задач | Celery 5 + django-celery-beat ≥2.8 |
| Frontend | Django templates + Tailwind CSS 3 (CDN) + HTMX 1.9 (`django-htmx`) |
| HTML-парсинг | BeautifulSoup 4 (для scraping Rusklimat) |
| WSGI | Gunicorn (2 workers — сервер 961MB RAM) |
| Web | Nginx (на VPS, не в контейнере) |
| Контейнеризация | Docker + Docker Compose |
| Экспорт | openpyxl (Excel), WeasyPrint (PDF) |

**Дизайн-система SplitHome (steps 1-2 завершены, далее по плану переверстки):**
- Палитра: primary `#2E7CF6`, accent `#1FC8C5`, ink `#0E1A2B`, surface `#F4F8FC`.
- Шрифт Onest 400–800. Радиусы 8/12/18/24/32.
- Логотип — вихрь `assets/swirl.png` из архива макета.
- Главная розницы — bento-grid (коммит `bb6318a`).
- Эталон — JSX-макеты из `flycited2-dotcom/SplitHub_roznica`. README макета прямо говорит: визуальная спецификация, не код для копирования.

---

## 3. Учётные данные и секреты

**Реальные значения хранятся только в `/opt/oasis/.env` на VPS** и в `.env` локально. В этом файле — только структура и плейсхолдеры. Текущие живые значения см. в memory `telegram_notifications.md`, `server_deploy.md` и в боевом `.env`.

### Бриз API
```
BREEZ_AUTH_HEADER=Basic <base64(login:password)>
BREEZ_BASE_URL=https://api.breez.ru/v1/
```
Login: `flycited@gmail.com`. **Ключ был залит в репо в исходном handoff — ротировать при следующем деплое.**

### Rusklimat
```
RUSKLIMAT_LOGIN=
RUSKLIMAT_PASSWORD=
RUSKLIMAT_AC_CATALOG_URL=https://b2b.rusklimat.com/catalog/1162450-konditsionery-bytovye/
RUSKLIMAT_JWT_TOKEN=
RUSKLIMAT_CONTRACTOR_GUID=e51a9046-47ff-4d7e-977d-7dba40c0a979
```
Первичный путь — scraping b2b.rusklimat.com. JWT-токен — резервный через API b2b-one.

### Telegram (уведомления менеджера)
```
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=
```
Чат групповой (отрицательный ID). Живой токен и ID — в memory `telegram_notifications.md`.

### Email (SMTP)
```
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_HOST_USER=
EMAIL_HOST_PASSWORD=
DEFAULT_FROM_EMAIL=noreply@splithome.ru
MANAGER_EMAIL=zakaz@splithome.ru
```

Полный шаблон — `.env.example` в корне.

---

## 4. Документация проекта

| Файл | Что внутри |
|---|---|
| `docs/superpowers/specs/2026-04-30-oasis-b2b-portal-design.md` | Исходная спецификация B2B-портала (модели, страницы, доступ) |
| `docs/superpowers/plans/2026-04-30-oasis-b2b-portal.md` | Исходный план на 12 задач с готовым кодом |
| `HANDOFF.md` | Этот файл |
| `CLAUDE.md` (если присутствует) | Инструкции уровня проекта |

Memory-папка (`~/.claude/projects/.../memory/`) содержит актуальный контекст по ребренду, фильтрам, деплою, leads, Telegram — читать обязательно перед началом работы.

---

## 5. Реализованная архитектура

Django-пакет: `splithome/` (после ребренда; в репозитории сервера всё ещё `/opt/oasis/`, см. раздел 9).

### apps/catalog
- Модели: `Category` (древовидная, мастер-узлы + breez_id + rusklimat_id), `Brand`, `Product` (nc_code, articul, цены `price_wholesale` + `ric`, описание, видео, `source` для разделения Бриз/Rusklimat), `ProductImage`, `TechSpec` + `ProductTech`.
- `views.py`: home, catalog (с HTMX partial response), product_detail, brands_list.
- `filters.py` (django-filter) + `facets.py` (мульти-селект с подсчётом результатов).
- BTU-фильтр по артикулу (regex `(^|[^0-9])07([^0-9]|$)`), инвертор/неинвертор по названию, чёрный цвет, диапазон цен, фильтр по бренду.
- Management commands: `cleanup_brands`, `sync_all`, `remap_categories`.
- Шаблоны: `home.html` (bento-grid розницы), `catalog/index.html`, `catalog/product_detail.html` с модалом «Купить в 1 клик», `partials/product_card.html`.

### apps/stock
- `Stock` (OneToOne к Product, quantity, warehouse, price_base).

### apps/accounts
- `CustomUser` (AbstractUser + company_name, inn, kpp, legal_address, phone, contact_person, is_approved, approved_at, approved_by, discount_percent, `get_wholesale_price(price)`).
- Admin action `approve_users` шлёт email.
- Signals: post_save → Telegram при регистрации.
- `views.py`: register, login_view, logout_view, pending, dashboard.
- `urls.py` (`/auth/`) + `urls_account.py` (`/account/`).
- Шаблоны `accounts/{login,register,pending,dashboard}.html`.

### apps/orders
- `Cart` (OneToOne user) + `CartItem` (unique_together, subtotal через `get_wholesale_price`).
- `Order` (6 статусов) + `OrderItem` (snapshot `price_at_order`, `ric_at_order`).
- `context_processors.cart_count` — для всех шаблонов.
- HTMX-корзина (`partials/cart_table.html`), checkout, order_list, order_detail.
- При оформлении заказа — уведомление в Telegram.

### apps/export
- `excel.py` (`generate_price_excel(user)` через openpyxl).
- `pdf.py` (`generate_price_pdf(user, request)` через WeasyPrint).
- Endpoint `export_excel`, `export_pdf`.
- Шаблон `templates/export/price_pdf.html`.

### apps/sync
- `BreezClient` — 7 методов, обработка Timeout/JSONDecodeError/HTTPError/RequestException. 8 unit-тестов в `tests/test_client.py`.
- Celery tasks: `sync_categories`, `sync_brands`, `sync_products`, `sync_stock`, `sync_catalog`; для Rusklimat — CSV-импорт, YML-стоки, scraping остатков.
- Управление синком per category через `sync_enabled` (admin).
- Расписание Celery Beat: stock каждый час, catalog каждые 4 часа, Rusklimat daily.

### apps/leads (новое, не было в исходном плане)
- Модели: `QuickOrder` (имя/телефон/продукт/комментарий), `SelectionRequest` (имя/телефон/город/площадь/тип помещения/бюджет/нужен ли монтаж/срок/комментарий), `InstallationRequest` (имя/телефон/адрес/тип техники/этаж/тип стены/нужна ли штроба).
- Endpoints: `POST /leads/quick-order/`, `POST /leads/selection/`, `POST /leads/installation/` (все HTMX), `GET /selection/`, `GET /installation/`.
- Все три формы шлют уведомление в Telegram.

### apps/notifications (новое)
- `telegram.py:send_telegram(text: str) -> bool` — единая точка отправки.
- Вызывается из orders/views.py, accounts/signals.py, leads/views.py.

### templates/pages
- Статические страницы: `about`, `contacts`, `delivery`, `payment`, `warranty` — обработаны TemplateView в `splithome/urls.py`.

### Deploy-артефакты
- `nginx.conf` — SSL для splithome.ru.
- `deploy.sh` — bash-скрипт первого деплоя.
- `.claude/launch.json` — для Claude Code preview.
- `docker-compose.yml` — 5 сервисов (db, redis, web, celery, beat).

---

## 6. Что осталось / open items

### Срочное на завтра (после деплоя 2026-05-16)
1. **HTTPS для splithome.ru** — отдельного vhost на 443 нет, certbot не выпускался. Сайт сейчас только по HTTP. Команда: `certbot --nginx -d splithome.ru -d www.splithome.ru`. Затем обновить nginx-конфиг `/etc/nginx/conf.d/oasis_main.conf` либо создать новый `splithome.conf` с listen 443 ssl.
2. **Дроп stash после убеждения, что прод стабилен.** На сервере висит `git stash` с локальными правками от прежних base64-загрузок (`stash@{0}: On develop: pre-deploy-2026-05-16 server-side edits`, 40 файлов, 782+/456-). После пары дней эксплуатации без регрессов: `ssh root@213.109.202.45 'cd /opt/oasis && git stash drop'`.
3. **Бэкап-папки на VPS** — `templates.bak.1778621726/`, `static.bak.1778621726/`, `backups/`. После убеждения в стабильности можно удалить.

### Технический долг
1. **Тесты только для BreezClient** (`apps/sync/tests/test_client.py`). Нет тестов для Celery-задач Rusklimat, моделей catalog/orders/accounts, views leads/orders, утилиты `send_telegram`.
2. **Нет CI/CD** — деплой ручной через base64+SSH или `git pull` (см. memory `server_deploy.md`). Можно настроить webhook → автодеплой.
3. **API-ключ Бриз был залит в исходный handoff в репо** — ротировать при следующей возможности.
4. **Несоответствие путей: dir `/opt/oasis/` vs пакет `splithome/`** — директория на сервере сознательно не переименована (чтобы сохранить docker-volumes `oasis_postgres_data`, `oasis_static_files`, `oasis_media_files`, `oasis_redis_data`). Контейнеры теперь `oasis-web-1` / `oasis-celery-1` / `oasis-beat-1`, но команды внутри них — `gunicorn splithome.wsgi:application` и `celery -A splithome`. Не путать.
5. **Docker-volume для статики ≠ путь nginx** — после `collectstatic` нужен `rsync -a /var/lib/docker/volumes/oasis_static_files/_data/ /opt/oasis/staticfiles/` (nginx читает из второго).
6. **README.md** в репозитории отсутствует.

### Продуктовый бэклог (B2C-переверстка)
Идёт с 2026-05-12 по дизайн-прототипу `SplitHub_roznica`. Завершены steps 1-2 (design system + bento home). Дальше по плану 11 задач (см. TaskList #1–#11 в активной сессии):
- Quiz (AI-подборщик кондиционера) — новый экран, не было раньше.
- Compare (страница сравнения) — новый экран.
- Admin (кастомная панель) — новый экран.
- Адаптив «по здравому смыслу» (отдельных мобильных макетов нет).
- Verification — VPS-сервер, локального dev-сервера нет.

---

## 7. Расширения после исходного плана

Не предусмотрены в `docs/superpowers/plans/2026-04-30-oasis-b2b-portal.md`, но добавлены в ходе работы:

| Расширение | Коммиты | Суть |
|---|---|---|
| Rusklimat full catalog sync | `ee39d32`, `5d8ef5f`, `2adbc3c`, `f9b69f1` | CSV-импорт + YML-стоки + scraping |
| Master category tree | `05e7348`, `0ad51fa`, `64cf48a`, `c7fb25d` | Единое дерево для двух поставщиков |
| `sync_enabled` per category | `8be207a` | Admin-управление синком по категориям |
| Catalog filters + facets | `5fda5fb`, `b0fbbe3`, `1959c72`, `b2a9016`, `de4131e` | BTU/инвертор/чёрный + мульти-селект + HTMX-partial |
| Leads + Telegram | `0ca49e6`, `4a5ecc4` | QuickOrder/SelectionRequest/InstallationRequest + бот |
| Static pages + SEO | `5850e66` | about/contacts/delivery/payment/warranty + Yandex.Metrika |
| Catalog UI polish | `8216a51`, `85eaf86`, `1dff1f0` | Стилизация фильтров, дерево категорий, удаление Brands |
| Ребренд Oasis → СплитХаб | `9146c78`, `cdb7936` | Переименование пакета, домена, дизайн-системы |
| Розничная главная | `bb6318a` | Bento-grid layout |

---

## 8. Workflow

Пользователь предпочитает **Subagent-Driven Development**:

1. Контроллер (главный Claude) читает следующую задачу из плана / TaskList.
2. Отправляет **Implementer subagent** с полным контекстом.
3. После завершения → **Spec Reviewer** проверяет соответствие требованиям.
4. Затем → **Code Quality Reviewer** (`superpowers:code-reviewer`).
5. Если есть issues → **Fix subagent** правит.
6. Только после ✅ обоих ревью — следующая задача.

**Подскиллы:**
- `superpowers:subagent-driven-development` — основной воркфлоу.
- `superpowers:executing-plans` — альтернатива in-session.
- `superpowers:test-driven-development` — для написания тестов.
- `karpathy-guidelines` — базовый стиль (думать до кода, минимальные хирургические правки, цели с верификацией).

---

## 9. История коммитов (свежие → старые)

```
bb6318a  feat(home): bento grid layout for retail home page
cdb7936  chore: rename project oasis → splithome, domain splithome.ru
9146c78  feat(brand): rebrand Oasis → СплитХаб, design system (steps 1-2)
de4131e  feat(catalog): split catalog template, multi-select sidebar over HTMX
b2a9016  feat(catalog): faceted filter counts and HTMX partial response
1959c72  feat(catalog): multi-select filters with 11 BTU values
64cf48a  chore(migrations): ensure_master_categories data migration
85eaf86  feat(catalog): rename sidebar to "Каталог", drop "Все кондиционеры"
c7fb25d  feat(sync): generalize remap_categories for Breeze + Rusklimat
1dff1f0  chore(catalog): remove Brands page and header/footer links
12a381b  feat(catalog): cleanup_brands management command
5fda5fb  feat: BTU quick-filter, inverter/non-inverter and black color filters
b0fbbe3  fix: catalog shows AC products only, stock-first sorting, price range
4a5ecc4  feat: Telegram notifications, leads app, catalog cleanup
0ad51fa  fix: remap command creates master categories if missing
05e7348  feat: unified master category tree for all suppliers
2adbc3c  feat: sync Rusklimat stock from personalised YML price list
5d8ef5f  fix: prevent Breeze sync from deactivating Rusklimat products
ee39d32  feat: Rusklimat full catalog sync — CSV import, nullable breez_id
8be207a  feat: admin sync management per category + sync_enabled flag
f6d274d  fix: filter Breeze product sync to AC/split-system categories only
f9b69f1  feat: Rusklimat AC stock sync via b2b.rusklimat.com scraping
5850e66  Batch 2: static pages, SEO, Yandex.Metrika, catalog sorting
0ca49e6  Add Telegram notifications, leads app and quick order forms
8216a51  Improve catalog UI: styled filters, category tree, brand logos
…
dbb06ca  feat: Nginx config, deploy script, launch.json — production ready
4f0adcb  feat: Excel and PDF price list export
109fa0e  feat: cart with HTMX, checkout, order views and templates
a0d1ec8  feat: registration, login, dashboard, approval flow
f8825bf  feat: catalog views, filters, templates — home, catalog, product
4f92c80  feat: base template, header, footer — Tailwind + HTMX
758a578  docs: HANDOFF.md — project handoff guide for next Claude model
fbb8846  fix: sync tasks — dead imports, atomic, image edge, stock counts
…
0a52656  feat: project foundation
fcd1bb3  docs: project spec and implementation plan
```

Полный лог: `git log --oneline`.

---

## 10. Контакты сервера и деплой

**Сервер:** `213.109.202.45` (DNS `splithome.ru` уже указывает сюда A-записью, без IPv6).
**SSH:** root / пароль в memory `server_deploy.md`.
**Проект на сервере:** `/opt/oasis/` (имя директории сознательно не переименовано в `/opt/splithome/` — docker-volumes привязаны к префиксу `oasis_`, перенос потерял бы данные БД/media/статики).
**Production HEAD:** `fc406e9` (от 2026-05-16).
**Контейнеры:** `oasis-web-1` (gunicorn splithome.wsgi, 2 workers), `oasis-celery-1`, `oasis-beat-1`, `oasis-db-1` (postgres 16), `oasis-redis-1`.

**Процедура деплоя (актуальная, после 2026-05-16):**
1. Локально закоммитить и `git push origin develop`.
2. На сервере: `cd /opt/oasis && git stash push -u -m "pre-deploy" && git pull --ff-only origin develop` (или `git reset --hard origin/develop` если рабочая копия грязная).
3. `docker compose build` (web/celery/beat). Только `restart` НЕ применит изменения — код запечён в образ.
4. `docker compose run --rm web python manage.py migrate --noinput`.
5. `docker compose run --rm web python manage.py collectstatic --noinput`.
6. `docker compose up -d`.
7. `rsync -a /var/lib/docker/volumes/oasis_static_files/_data/ /opt/oasis/staticfiles/` — обязательно, nginx читает оттуда, не из volume.
8. Smoke: `curl -I --resolve splithome.ru:80:213.109.202.45 http://splithome.ru/` → ожидать HTTP 200.

**Старая база (если git pull недоступен):** SFTP не работает (`SSHException: EOF during negotiation`) — заливать файлы через base64 по SSH. Скрипт paramiko в memory `server_deploy.md`.

**Сосуществующие сервисы на VPS:** Apache (8443/8081/8084), Node `climat-simf.ru:3001`, CRM на 8090 (перехватывает прямой IP через `crm_ip_proxy.conf`). Не трогать.

---

## 11. Команды быстрого старта

```bash
# Локально (Docker Desktop / Docker Engine)
git clone https://github.com/flycited2-dotcom/split-shop_claude.git
cd split-shop_claude
cp .env.example .env
# заполнить .env (SECRET_KEY, BREEZ_*, RUSKLIMAT_*, TELEGRAM_*, EMAIL_*)

docker compose build
docker compose up -d db redis
docker compose run --rm web python manage.py migrate
docker compose run --rm web python manage.py createsuperuser

# Первая синхронизация
docker compose run --rm web python manage.py sync_all
# Опции: --catalog-only, --stock-only

# Запуск всех сервисов
docker compose up

# Открыть http://localhost:8000
```

---

## 12. Контекст пользователя

- Язык общения: **русский**.
- Стиль: **прямой, без воды**.
- Working style: `karpathy-guidelines` по умолчанию (думать до кода, хирургические правки, цели с верификацией).
- Workflow: **Subagent-Driven Development**.
- Локального dev-сервера нет — проверка результата на VPS.
- Домен `splithome.ru` (нужно подтвердить, что DNS направлен на 213.109.202.45 и выпущен SSL).
- Проект разрабатывается с нуля, без legacy.

---

**Следующему Claude:** перед началом работы прочитай весь `~/.claude/projects/.../memory/MEMORY.md` и связанные файлы. Они содержат живой контекст, которого нет в коде.
