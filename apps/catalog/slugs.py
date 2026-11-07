"""Латинские адреса товаров.

Коды Бриза и Русклимата пишутся кириллицей («НС-1181388»), и раньше они
попадали в slug как есть: /product/electrolux-ewh-80-citadel-НС-1181388/.
Аудит 06.11.2026: 12 786 из 14 595 адресов sitemap были с кириллицей —
в выдаче и в ссылках они превращаются в нечитаемый percent-encoding.

to_latin() переводит в латиницу ТОЛЬКО не-ASCII символы, а латинскую часть
не трогает. Поэтому:
- адреса, которые и так были латинскими, не меняются (лишних 301 нет);
- функция идемпотентна: to_latin(to_latin(x)) == to_latin(x);
- старый кириллический адрес однозначно переводится в новый — карточка
  товара отдаёт 301, не храня таблицу соответствий.
"""
import re
import unicodedata

_TR = {
    'а': 'a', 'б': 'b', 'в': 'v', 'г': 'g', 'д': 'd', 'е': 'e', 'ё': 'e',
    'ж': 'zh', 'з': 'z', 'и': 'i', 'й': 'y', 'к': 'k', 'л': 'l', 'м': 'm',
    'н': 'n', 'о': 'o', 'п': 'p', 'р': 'r', 'с': 's', 'т': 't', 'у': 'u',
    'ф': 'f', 'х': 'h', 'ц': 'ts', 'ч': 'ch', 'ш': 'sh', 'щ': 'sch',
    'ъ': '', 'ы': 'y', 'ь': '', 'э': 'e', 'ю': 'yu', 'я': 'ya',
    'і': 'i', 'ї': 'yi', 'є': 'ye', 'ґ': 'g',
}


def to_latin(value):
    """Slug → латиница. ASCII-строка возвращается без изменений."""
    value = value or ''
    if value.isascii():
        return value
    out = []
    for ch in value:
        if ch.isascii():
            out.append(ch)
            continue
        low = ch.lower()
        if low in _TR:
            out.append(_TR[low])
            continue
        # ü → u, ² → 2 и т.п.; что не раскладывается в ASCII — разделитель
        ascii_ = unicodedata.normalize('NFKD', ch).encode('ascii', 'ignore').decode()
        out.append(ascii_.lower() if ascii_ else '-')
    s = ''.join(out)
    s = re.sub(r'[^A-Za-z0-9_-]+', '-', s)
    s = re.sub(r'-{2,}', '-', s).strip('-')
    return s
