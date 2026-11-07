"""Раздел /articles/ читает файлы робота из ARTICLES_DIR (ТЗ по SEO)."""
import json
import shutil
import tempfile
from pathlib import Path

from django.test import Client, TestCase, override_settings

from apps.articles import loader
from apps.catalog.models import Category

ARTICLE = """---
site: splithome.ru
slug: kak-vybrat-konditsioner
title: "Как выбрать кондиционер для квартиры в Крыму"
description: "Разбираем мощность, инвертор и шум: как выбрать сплит-систему для квартиры в Крыму и не переплатить."
h1: "Как выбрать кондиционер для квартиры"
date: 2026-11-01
category: Сплит-системы
main_query: как выбрать кондиционер
queries: ["выбор кондиционера", "кондиционер для квартиры"]
links: ["/catalog/", "/quiz/", "/installation/"]
cta: "Подберём модель под вашу комнату и установим за день."
read_time: 7
---
Вводный абзац со **жирным** и [ссылкой на подбор](/quiz/).

[[ФОТО: кондиционер на стене | Кондиционер в комнате]]

## Мощность

Смотрите [вторую статью](article:vtoraya-statya) и [несуществующую](article:net-takoy).

| Площадь | BTU |
|---|---|
| 20 м² | 7 |

## Инвертор

- пункт один
- пункт два

## Шум

1. первый
2. второй

## Монтаж

Плохая [ссылка](javascript:alert(1)).

## Частые вопросы

### Какой мощности нужен кондиционер?

На 20 м² хватит 7 000 BTU.

### Нужен ли инвертор?

Да, если кондиционер работает каждый день.
"""

SECOND = (ARTICLE.replace('slug: kak-vybrat-konditsioner', 'slug: vtoraya-statya')
          .replace('h1: "Как выбрать кондиционер для квартиры"', 'h1: "Вторая статья"'))


@override_settings(SITE_URL='https://splithome.ru', ALLOWED_HOSTS=['*'])
class ArticlesTest(TestCase):

    def setUp(self):
        self.root = Path(tempfile.mkdtemp())
        (self.root / 'published').mkdir()
        self.override = override_settings(ARTICLES_DIR=str(self.root))
        self.override.enable()
        loader.reset_cache()
        self.client = Client()

    def tearDown(self):
        self.override.disable()
        loader.reset_cache()
        shutil.rmtree(self.root, ignore_errors=True)

    def _put(self, name, text):
        (self.root / 'published' / name).write_text(text, encoding='utf-8')
        loader.reset_cache()

    def test_empty_list_is_noindex(self):
        r = self.client.get('/articles/', secure=True)
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'noindex, follow')

    def test_missing_dir_is_not_500(self):
        with override_settings(ARTICLES_DIR=str(self.root / 'nope')):
            loader.reset_cache()
            self.assertEqual(self.client.get('/articles/', secure=True).status_code, 200)
            self.assertEqual(self.client.get('/articles/x-y/', secure=True).status_code, 404)

    def test_article_page(self):
        self._put('a.md', ARTICLE)
        (self.root / 'state.json').write_text(
            json.dumps({'dates': {'kak-vybrat-konditsioner': '2026-11-05'}}), encoding='utf-8')
        loader.reset_cache()
        r = self.client.get('/articles/kak-vybrat-konditsioner/', secure=True)
        self.assertEqual(r.status_code, 200)
        body = r.content.decode()
        self.assertIn('<title>Как выбрать кондиционер для квартиры в Крыму</title>', body)
        self.assertIn('<link rel="canonical" href="https://splithome.ru/articles/kak-vybrat-konditsioner/">', body)
        self.assertIn('content="index, follow"', body)
        self.assertIn('5 ноября 2026', body)               # дата из state.json
        self.assertIn('7 мин чтения', body)
        self.assertIn('Содержание', body)                  # 4+ H2 → оглавление
        self.assertNotIn('ФОТО', body)
        self.assertNotIn('href="javascript:', body)
        self.assertIn('несуществующую', body)              # article: без статьи → текст
        self.assertNotIn('/articles/net-takoy/', body)
        self.assertIn('<details>', body)
        self.assertIn('"FAQPage"', body)
        self.assertIn('"Article"', body)
        self.assertIn('"BreadcrumbList"', body)
        self.assertIn('"datePublished": "2026-11-05"', body)
        self.assertIn('Подберём модель под вашу комнату', body)
        self.assertIn('href="/installation/"', body)

    def test_cross_link_and_read_more(self):
        self._put('a.md', ARTICLE)
        self._put('b.md', SECOND)
        body = self.client.get('/articles/kak-vybrat-konditsioner/', secure=True).content.decode()
        self.assertIn('href="/articles/vtoraya-statya/"', body)
        self.assertIn('Читайте также', body)

    def test_list_sitemap_and_removal(self):
        self._put('a.md', ARTICLE)
        r = self.client.get('/articles/', secure=True)
        self.assertContains(r, 'Как выбрать кондиционер для квартиры')
        self.assertNotContains(r, 'noindex')
        sm = self.client.get('/articles/sitemap.xml', secure=True).content.decode()
        self.assertIn('<loc>https://splithome.ru/articles/kak-vybrat-konditsioner/</loc>', sm)
        self.assertIn('<lastmod>2026-11-01</lastmod>', sm)
        main = self.client.get('/sitemap.xml', secure=True).content.decode()
        self.assertIn('/articles/kak-vybrat-konditsioner/', main)
        (self.root / 'published' / 'a.md').unlink()
        loader.reset_cache()
        self.assertEqual(self.client.get('/articles/kak-vybrat-konditsioner/', secure=True).status_code, 404)

    def test_unknown_slug_and_bad_page(self):
        self._put('a.md', ARTICLE)
        self.assertEqual(self.client.get('/articles/net-takoy/', secure=True).status_code, 404)
        self.assertEqual(self.client.get('/articles/?page=5', secure=True).status_code, 404)
        self.assertEqual(self.client.get('/articles/?page=abc', secure=True).status_code, 404)

    def test_pagination_canonical(self):
        for i in range(25):
            self._put(f'{i}.md', ARTICLE.replace('slug: kak-vybrat-konditsioner', f'slug: statya-{i}'))
        r = self.client.get('/articles/?page=2', secure=True)
        self.assertContains(r, '<link rel="canonical" href="https://splithome.ru/articles/?page=2">', html=False)

    def test_broken_file_skipped(self):
        self._put('a.md', ARTICLE)
        self._put('bad.md', 'без шапки')
        self.assertEqual(len(loader.get_articles()), 1)

    def test_related_articles(self):
        self._put('a.md', ARTICLE)
        self.assertEqual([a.slug for a in loader.related_articles('/catalog/')], ['kak-vybrat-konditsioner'])
        self.assertEqual(len(loader.related_articles('/product/x/', 'Сплит-системы')), 1)
        self.assertEqual(loader.related_articles('/product/x/', 'Мобильные'), [])

    def test_useful_articles_on_catalog(self):
        Category.objects.create(title='Сплит-системы', slug='split', sync_enabled=True)
        self._put('a.md', ARTICLE)
        self.assertContains(self.client.get('/catalog/', secure=True), 'Полезные статьи')

    def test_footer_link(self):
        self.assertContains(self.client.get('/contacts/', secure=True), 'href="/articles/"')
