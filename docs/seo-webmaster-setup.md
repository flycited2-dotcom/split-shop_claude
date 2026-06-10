# Регистрация splithome.ru в панелях вебмастеров

Файлы на сайте (`robots.txt`, `sitemap.xml`, `llms.txt`, Schema.org) — это
только «приглашение». Чтобы сайт реально попал в выдачу, нужно **добавить и
подтвердить** домен в панелях вебмастеров и **отправить им sitemap**. Это
запускает индексацию.

Три движка покрывают всех (браузеры используют именно их):

| Движок | Кого покрывает |
|--------|----------------|
| **Google** | Chrome, Firefox, Samsung Internet (по умолчанию) |
| **Yandex** | Яндекс.Браузер, выдача Яндекса |
| **Bing** | Edge, **Yahoo**, DuckDuckGo (работают на индексе Bing) |

## Способ подтверждения

В проекте уже встроена верификация **мета-тегом**: добавляете токен в `.env`,
перезапускаете контейнер — тег появляется в `<head>` на всех страницах.

```env
GOOGLE_SITE_VERIFICATION=<токен из Google>
YANDEX_VERIFICATION=<токен из Yandex>
BING_SITE_VERIFICATION=<токен из Bing>
```

После правки `.env`:

```bash
cd /opt/oasis
docker compose up -d --force-recreate web
# проверить, что тег появился:
curl -s https://splithome.ru/ | grep -E 'site-verification|yandex-verification|msvalidate'
```

---

## 1. Google Search Console

1. Откройте <https://search.google.com/search-console> (войдите в Google-аккаунт).
2. **Добавить ресурс** → выберите тип **«Ресурс с префиксом URL»** →
   введите `https://splithome.ru`.
3. В списке способов подтверждения выберите **«Тег HTML»**. Google покажет
   строку вида `<meta name="google-site-verification" content="XXXXXXXX">`.
4. Скопируйте **только значение** `content` (`XXXXXXXX`) в
   `GOOGLE_SITE_VERIFICATION` в `.env`, перезапустите контейнер (см. выше).
5. Вернитесь в Search Console и нажмите **«Подтвердить»**.
6. После подтверждения: меню **Sitemaps** → добавьте `sitemap.xml` → **Отправить**.

## 2. Yandex Вебмастер

1. Откройте <https://webmaster.yandex.ru> (войдите в Яндекс-аккаунт).
2. **Добавить сайт** → введите `https://splithome.ru`.
3. Вкладка подтверждения → способ **«Мета-тег»**. Скопируйте значение
   `content` из показанного тега `<meta name="yandex-verification" ...>` в
   `YANDEX_VERIFICATION`, перезапустите контейнер.
4. Нажмите **«Проверить»**.
5. После подтверждения: раздел **Индексирование → Файлы Sitemap** → добавьте
   `https://splithome.ru/sitemap.xml`.
6. Полезно сразу: **Индексирование → Переобход страниц** для главной.

## 3. Bing Webmaster Tools

1. Откройте <https://www.bing.com/webmasters> (вход через Microsoft/Google).
2. Проще всего — **импорт из Google Search Console** (кнопка предлагается
   сразу). Тогда домен и sitemap подтянутся автоматически, шаги ниже не нужны.
3. Если вручную: **Add site** → `https://splithome.ru` → способ **«HTML Meta
   Tag»**. Значение `content` из `<meta name="msvalidate.01" ...>` → в
   `BING_SITE_VERIFICATION`, перезапуск контейнера → **Verify**.
4. **Sitemaps** → Submit → `https://splithome.ru/sitemap.xml`.

---

## Проверка результата

- **Сразу:** в каждой панели статус домена должен стать «подтверждён», sitemap —
  «обработан/в обработке».
- **1–3 дня:** в отчётах появятся первые проиндексированные страницы.
- **1–4 недели:** сайт начнёт стабильно показываться по запросам бренда и
  товаров. Полная индексация каталога — до нескольких недель.

## Что уже отдаёт сайт (проверочные ссылки)

- <https://splithome.ru/robots.txt> — правила + ссылка на sitemap, LLM-краулеры разрешены
- <https://splithome.ru/sitemap.xml> — карта сайта (товары, категории, страницы)
- <https://splithome.ru/llms.txt> — описание для ИИ-поисковиков (ChatGPT, Perplexity, Claude и др.)
- Schema.org: `HVACBusiness` на всех страницах + `Product`/`Offer` на карточках
  товара. Проверить: <https://search.google.com/test/rich-results>
