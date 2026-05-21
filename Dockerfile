# Пинуем bookworm (Debian 12) — у trixie (свежий) репозитории нестабильны.
FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Меняем зеркало Debian на mirror.yandex.ru — deb.debian.org → Fastly CDN
# (199.232.x.x) недоступен с нашего VPS из контейнера (firewall блокирует :80).
RUN sed -i 's|http://deb.debian.org|http://mirror.yandex.ru|g; s|http://security.debian.org|http://mirror.yandex.ru|g' /etc/apt/sources.list.d/debian.sources 2>/dev/null \
 || sed -i 's|http://deb.debian.org|http://mirror.yandex.ru|g; s|http://security.debian.org|http://mirror.yandex.ru|g' /etc/apt/sources.list \
 && apt-get update && apt-get install -y \
    libpango-1.0-0 libpangoft2-1.0-0 libffi-dev curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Скачиваем Tailwind CSS standalone CLI (без Node.js) и компилируем стили.
# Закрепляем v3.4.17 — последний стабильный v3 с inline-конфигом, в котором
# уже описаны бренд-цвета (accent/teal/ink/surface) и rounded-card.
# Заменяет <script src="cdn.tailwindcss.com"> — CDN-вариант ломался при быстром
# browser-back из карточки товара (runtime JIT не успевал применить классы).
RUN curl -sSL -o /usr/local/bin/tailwindcss \
        https://github.com/tailwindlabs/tailwindcss/releases/download/v3.4.17/tailwindcss-linux-x64 \
 && chmod +x /usr/local/bin/tailwindcss \
 && tailwindcss \
        -c /app/tailwind.config.js \
        -i /app/static/css/tailwind-src.css \
        -o /app/static/css/tailwind.css \
        --minify \
 && rm /usr/local/bin/tailwindcss
