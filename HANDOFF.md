# HANDOFF: SplitHome — Передача проекта

**Дата обновления:** 2026-05-20 (фикс BTU из tech_values + 500 на product_detail + Бриз Крым открыт)
**Прогресс:** B2C-pivot + Quiz + TechSpec у всех 3 поставщиков + per-warehouse + Rusklimat REST + регистрация физ/юр + cookie + LLM-SEO + mobile-адаптация + правильный BTU + Бриз Крым работает
**Ветка:** `develop` (запушена в GitHub, синхронизирована с VPS)
**Репозиторий:** https://github.com/flycited2-dotcom/split-shop_claude
**Production HEAD на VPS:** `b329bf9` (fix(btu): импорт resolve_btu в views.py)
**Production URL:** https://splithome.ru/ (Let's Encrypt SSL, expire 2026-08-14, авто-renewal через `certbot.timer`)

---

## Update 2026-05-20 — BTU из tech_values, 500 на product_detail, Бриз Крым открыт, Docker-зеркало

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
