"""Статьи из папки робота автовыкладки (ТЗ по SEO, приложение «/articles/»).

Робот кладёт опубликованные статьи в ARTICLES_DIR/published/<slug>.md, а
фактические даты выхода — в ARTICLES_DIR/state.json ({"dates": {slug: дата}}).
Сайт папку только ЧИТАЕТ. Формат файла — YAML-шапка между `---` и Markdown;
логика разбора повторяет articles.py из Proekt_stabilizator (parse_front,
md_to_html, split_faq), только без сборки HTML-страниц: их рисуют шаблоны.

Кэш: снимок папки (имена + mtime + размер файлов) сверяется не чаще раза в
CHECK_SECONDS; изменился — статьи перечитываются. Новый файл появляется на
сайте не позже чем через минуту, удалённый пропадает так же (ТЗ: ≤10 минут).
Битый файл пропускается с предупреждением в лог, а не роняет раздел.
"""
import datetime
import html
import json
import logging
import os
import re
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlsplit

from django.conf import settings

log = logging.getLogger(__name__)

CHECK_SECONDS = 60
SLUG_RE = re.compile(r'[a-z0-9]+(?:-[a-z0-9]+)*')
FAQ_TITLE_RE = re.compile(r'(?m)^##\s+Частые вопросы.*$')

MONTHS = ('января февраля марта апреля мая июня июля августа '
          'сентября октября ноября декабря').split()


class ArticleError(ValueError):
    pass


@dataclass
class Article:
    slug: str
    title: str
    description: str
    h1: str
    date: datetime.date
    category: str = ''
    cta: str = ''
    links: list = field(default_factory=list)
    read_time: int = 0
    body: str = ''          # Markdown без шапки
    image: str = ''

    @property
    def url(self):
        return f'/articles/{self.slug}/'

    @property
    def date_ru(self):
        return f'{self.date.day} {MONTHS[self.date.month - 1]} {self.date.year}'


# ------------------------------------------------------------------ разбор файла
def parse_front(text):
    """YAML-шапка: key: "строка" | key: строка | key: [..] | key: число.

    Плюс YAML-список в столбик (key:\\n  - a\\n  - b) — его тоже пишут.
    """
    text = text.lstrip('﻿')
    m = re.match(r'\s*---\s*\n(.*?)\n---\s*\n(.*)\Z', text, re.S)
    if not m:
        raise ArticleError('нет шапки между строками ---')
    meta, last_key = {}, None
    for line in m.group(1).splitlines():
        if not line.strip() or line.lstrip().startswith('#'):
            continue
        item = re.match(r'\s+-\s+(.*)$', line)
        if item and last_key is not None:
            if not isinstance(meta.get(last_key), list):
                meta[last_key] = []
            meta[last_key].append(_scalar(item.group(1).strip()))
            continue
        km = re.match(r'\s*([A-Za-z_][A-Za-z0-9_]*)\s*:\s*(.*)$', line)
        if not km:
            raise ArticleError(f'не понимаю строку шапки: {line[:60]}')
        last_key, v = km.group(1), km.group(2).strip()
        meta[last_key] = _value(v)
    return meta, m.group(2).strip() + '\n'


def _scalar(v):
    if len(v) >= 2 and v[0] == v[-1] and v[0] in '"\'':
        return v[1:-1]
    return v


def _value(v):
    if v.startswith('[') or v.startswith('"'):
        try:
            return json.loads(v)
        except ValueError:
            if v.startswith('['):
                return [_scalar(x.strip()) for x in v.strip('[]').split(',') if x.strip()]
            return v.strip('"')
    if v.startswith("'") and v.endswith("'") and len(v) >= 2:
        return v[1:-1]
    if re.fullmatch(r'\d+', v):
        return int(v)
    return v


def _date(value):
    try:
        return datetime.date.fromisoformat(str(value).strip()[:10])
    except ValueError:
        return None


def load_article(path, dates=None):
    path = Path(path)
    meta, body = parse_front(path.read_text(encoding='utf-8'))
    slug = str(meta.get('slug') or path.stem).strip()
    if not SLUG_RE.fullmatch(slug):
        raise ArticleError(f'slug «{slug}»: только латиница, цифры и дефисы')
    for key in ('title', 'h1'):
        if not str(meta.get(key, '')).strip():
            raise ArticleError(f'нет поля {key}')
    site = str(meta.get('site') or '').strip().lower()
    own = urlsplit(settings.SITE_URL).netloc.lower()
    if site and site not in (own, own.removeprefix('www.')):
        raise ArticleError(f'site={site}, а ожидается {own}')
    date = (_date((dates or {}).get(slug)) or _date(meta.get('date'))
            or datetime.date.fromtimestamp(path.stat().st_mtime))
    links = meta.get('links') or []
    if isinstance(links, str):
        links = [links]
    try:
        read_time = int(meta.get('read_time') or 0)
    except (TypeError, ValueError):
        read_time = 0
    if read_time <= 0:
        read_time = max(3, round(len(re.findall(r'\w+', body)) / 180))
    return Article(
        slug=slug,
        title=str(meta['title']).strip(),
        description=str(meta.get('description') or '').strip(),
        h1=str(meta['h1']).strip(),
        date=date,
        category=str(meta.get('category') or '').strip(),
        cta=str(meta.get('cta') or '').strip(),
        links=[str(x).strip() for x in links if str(x).strip()],
        read_time=read_time,
        body=body,
        image=str(meta.get('image') or '').strip(),
    )


# ------------------------------------------------------------------ Markdown → HTML
_SAFE_HREF = re.compile(r'(/|#|https?://|tel:|mailto:)')


def _e(s):
    return html.escape(str(s), quote=True)


def _inline(s, link):
    s = html.escape(s, quote=False)
    s = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', s)
    s = re.sub(r'(?<![\w*])\*(?!\s)(.+?)(?<!\s)\*(?![\w*])', r'<em>\1</em>', s)
    s = re.sub(r'`([^`]+)`', r'<code>\1</code>', s)
    return re.sub(r'\[([^\]]+)\]\(([^)\s]+)\)',
                  lambda m: link(m.group(1), html.unescape(m.group(2))), s)


def heading_id(text):
    from apps.catalog.slugs import to_latin
    t = to_latin(re.sub(r'<[^>]+>', '', text).lower())
    return re.sub(r'[^a-z0-9]+', '-', t.lower()).strip('-')[:60] or 'r'


def md_to_html(body, link):
    body = re.sub(r'\[\[ФОТО:.*?\]\]', '', body, flags=re.S)
    lines, out, i = body.splitlines(), [], 0
    para = []
    used_ids = set()

    def flush():
        if para:
            out.append('<p>' + _inline(' '.join(para), link) + '</p>')
            para.clear()

    while i < len(lines):
        ln = lines[i].rstrip()
        if not ln.strip():
            flush()
            i += 1
            continue
        m = re.match(r'(#{2,4})\s+(.*)', ln)
        if m:
            flush()
            lv = len(m.group(1))
            text = m.group(2).strip()
            hid, n = heading_id(text), 1
            while hid in used_ids:
                n += 1
                hid = f'{heading_id(text)}-{n}'
            used_ids.add(hid)
            out.append(f'<h{lv} id="{hid}">{_inline(text, link)}</h{lv}>')
            i += 1
            continue
        if ln.lstrip().startswith('|'):
            flush()
            rows = []
            while i < len(lines) and lines[i].lstrip().startswith('|'):
                rows.append([c.strip() for c in lines[i].strip().strip('|').split('|')])
                i += 1
            rows = [r for r in rows if not all(re.fullmatch(r':?-{2,}:?', c) for c in r if c)]
            if rows:
                t = '<thead><tr>' + ''.join(f'<th>{_inline(c, link)}</th>' for c in rows[0]) + '</tr></thead><tbody>'
                t += ''.join('<tr>' + ''.join(f'<td>{_inline(c, link)}</td>' for c in r) + '</tr>'
                             for r in rows[1:])
                out.append(f'<div class="article-table"><table>{t}</tbody></table></div>')
            continue
        if re.match(r'\s*([-*•]|\d+[.)])\s+', ln):
            flush()
            ordered = bool(re.match(r'\s*\d+[.)]', ln))
            items = []
            while i < len(lines) and re.match(r'\s*([-*•]|\d+[.)])\s+', lines[i]):
                items.append('<li>' + _inline(re.sub(r'^\s*([-*•]|\d+[.)])\s+', '', lines[i]), link) + '</li>')
                i += 1
            tag = 'ol' if ordered else 'ul'
            out.append(f'<{tag}>' + ''.join(items) + f'</{tag}>')
            continue
        if ln.startswith('> '):
            flush()
            out.append('<p class="article-note">' + _inline(ln[2:], link) + '</p>')
            i += 1
            continue
        para.append(ln.strip())
        i += 1
    flush()
    return '\n'.join(out)


def split_faq(body):
    """Отделяет блок «## Частые вопросы» → (текст без него, [(вопрос, ответ_md)])."""
    m = FAQ_TITLE_RE.search(body)
    if not m:
        return body, []
    rest = body[m.end():]
    nxt = re.search(r'(?m)^##\s+', rest)
    faq_md, tail = (rest[:nxt.start()], rest[nxt.start():]) if nxt else (rest, '')
    items = []
    for q, a in re.findall(r'(?ms)^###\s+(.+?)\s*$\n(.*?)(?=^###\s|\Z)', faq_md):
        if a.strip():
            items.append((q.strip(), a.strip()))
    return body[:m.start()] + tail, items


def make_linker(published, own_slug=''):
    """[текст](article:slug) → ссылка, если статья вышла, иначе просто текст."""
    def link(text, href):
        if href.startswith('article:'):
            s = href[len('article:'):].strip().strip('/')
            if s in published and s != own_slug:
                return f'<a href="/articles/{_e(s)}/">{text}</a>'
            return text
        if not _SAFE_HREF.match(href):
            return text  # javascript: и прочее — только текст
        if href.startswith('http'):
            return f'<a href="{_e(href)}" target="_blank" rel="noopener">{text}</a>'
        return f'<a href="{_e(href)}">{text}</a>'
    return link


def render_article(article, published):
    """→ dict(html, toc, faq) для шаблона.

    faq: [(вопрос_html, ответ_html, вопрос_текст, ответ_текст)] — текст для JSON-LD.
    """
    link = make_linker(published, article.slug)
    main_md, faq = split_faq(article.body)
    content = md_to_html(main_md, link)
    heads = re.findall(r'<h2 id="([^"]+)">(.*?)</h2>', content)
    toc = [(hid, re.sub(r'<[^>]+>', '', t)) for hid, t in heads] if len(heads) >= 4 else []
    faq_items = []
    for q, a in faq:
        answer_html = md_to_html(a, link)
        answer_text = re.sub(r'\s+', ' ', html.unescape(re.sub(r'<[^>]+>', ' ', answer_html))).strip()
        faq_items.append((_inline(q, link), answer_html, html.unescape(re.sub(r'<[^>]+>', '', _inline(q, link))),
                          answer_text))
    return {'html': content, 'toc': toc, 'faq': faq_items}


# ------------------------------------------------------------------ папка + кэш
_lock = threading.Lock()
_cache = {'dir': None, 'checked': 0.0, 'sig': None, 'articles': {}}


def _snapshot(root):
    pub = root / 'published'
    sig = []
    try:
        with os.scandir(pub) as it:
            for e in it:
                if e.name.endswith('.md') and not e.name.startswith(('.', '_')) and e.is_file():
                    st = e.stat()
                    sig.append((e.name, st.st_mtime_ns, st.st_size))
    except OSError:
        return None
    try:
        st = (root / 'state.json').stat()
        sig.append(('state.json', st.st_mtime_ns, st.st_size))
    except OSError:
        pass
    return tuple(sorted(sig))


def _read_dates(root):
    try:
        data = json.loads((root / 'state.json').read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return {}
    dates = data.get('dates') if isinstance(data, dict) else None
    return dates if isinstance(dates, dict) else {}


def _load_all(root):
    dates = _read_dates(root)
    arts = {}
    for f in sorted((root / 'published').glob('*.md')):
        if f.name.startswith(('.', '_')):
            continue
        try:
            a = load_article(f, dates)
        except (ArticleError, OSError, UnicodeDecodeError) as exc:
            log.warning('articles: пропускаю %s — %s', f.name, exc)
            continue
        if a.slug in arts:
            log.warning('articles: дубль slug %s в %s', a.slug, f.name)
            continue
        arts[a.slug] = a
    # новые сверху
    return dict(sorted(arts.items(), key=lambda kv: (kv[1].date, kv[0]), reverse=True))


def get_articles():
    """{slug: Article}, новые сверху. Нет папки — пустой dict."""
    root = Path(getattr(settings, 'ARTICLES_DIR', '') or '/nonexistent')
    now = time.monotonic()
    with _lock:
        if _cache['dir'] == str(root) and now - _cache['checked'] < CHECK_SECONDS:
            return _cache['articles']
        sig = _snapshot(root)
        if not (_cache['dir'] == str(root) and sig == _cache['sig']):
            _cache['articles'] = _load_all(root) if sig is not None else {}
            _cache['sig'] = sig
            _cache['dir'] = str(root)
        _cache['checked'] = now
        return _cache['articles']


def reset_cache():
    with _lock:
        _cache.update({'dir': None, 'checked': 0.0, 'sig': None, 'articles': {}})


def related_articles(path, category_title='', limit=3):
    """«Полезные статьи» для страницы магазина: в links статьи есть путь этой
    страницы, либо категория статьи совпадает с категорией товара/каталога."""
    try:
        arts = get_articles()
    except Exception:  # раздел статей не должен ронять каталог
        log.exception('articles: не удалось прочитать статьи')
        return []
    if not arts:
        return []
    cat = (category_title or '').strip().lower()
    by_link, by_cat = [], []
    for a in arts.values():
        if path in a.links:
            by_link.append(a)
        elif cat and a.category.lower() == cat:
            by_cat.append(a)
    return (by_link + by_cat)[:limit]
