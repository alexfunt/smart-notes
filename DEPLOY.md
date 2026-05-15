# Smart Notes — деплой на VPS

Полный гайд: backend (FastAPI) + Telegram-бот + Postgres + frontend (Vite/React) под одним доменом через Caddy с автоматическим HTTPS.

Архитектура:

```
                       Internet
                          │
                       :80,:443
                          ▼
                    ┌─────────┐
                    │  Caddy  │  ← Let's Encrypt
                    └────┬────┘
                  /api/*  │  static
                  ┌───────┴────────┐
                  ▼                ▼
            ┌──────────┐   /srv (frontend dist)
            │ backend  │ ──┐
            │ (FastAPI)│   │  internal network
            └──────────┘   │
                  │        │
                  ▼        │
            ┌──────────┐   │
            │ postgres │ ◀─┤
            └──────────┘   │
                           ▼
                      ┌──────────┐
                      │   bot    │ → Telegram (long-polling)
                      └──────────┘
```

---

## 0. Требования

- VPS с Ubuntu 22.04/24.04, ≥1GB RAM, открыты порты 80/443
- Доменное имя (бесплатный сабдомен на DuckDNS подойдёт)
- Токен Telegram бота от @BotFather

---

## 1. Регистрация сабдомена на DuckDNS

1. Зайди на https://www.duckdns.org через GitHub/Google.
2. Создай поддомен, например `smart-notes` → получится `smart-notes.duckdns.org`.
3. В поле `current ip` укажи **публичный IPv4 твоего VPS** и нажми **update ip**.
4. Скопируй токен — пригодится для авто-обновления IP (если адрес динамический).

---

## 2. Подготовка VPS

SSH на сервер:

```bash
ssh root@<IP>
```

### Минимальная установка

```bash
apt update && apt upgrade -y
apt install -y curl git ufw

# Docker
curl -fsSL https://get.docker.com | sh

# Файрвол: только SSH + HTTP + HTTPS
ufw allow OpenSSH
ufw allow 80
ufw allow 443
ufw --force enable
```

### Несколько вещей для безопасности

```bash
# Создай не-root пользователя (по желанию, но рекомендую)
adduser deploy && usermod -aG docker deploy && usermod -aG sudo deploy
# С этого момента работай под deploy: su - deploy
```

---

## 3. Клонируем код

```bash
cd ~
git clone https://github.com/<your-username>/smart-notes.git
git clone https://github.com/<your-username>/smart-notes-frontend.git
# Папки должны быть рядом — docker-compose.prod.yml ссылается на ../smart-notes-frontend.
```

---

## 4. Готовим переменные окружения

```bash
cd ~/smart-notes
cp .env.prod.example .env
nano .env
```

Заполни обязательное:

```bash
PUBLIC_DOMAIN=smart-notes.duckdns.org
ACME_EMAIL=you@example.com               # для Let's Encrypt уведомлений
POSTGRES_PASSWORD=$(openssl rand -hex 24) # длинный случайный
TELEGRAM_BOT_TOKEN=123456:ABC-DEF...      # от @BotFather
WEB_APP_URL=https://smart-notes.duckdns.org
CORS_ORIGINS=https://smart-notes.duckdns.org
```

`DATABASE_URL` в `.env` можно оставить как есть — внутри docker-compose он перетирается на правильный путь к контейнеру `postgres`.

---

## 5. Запуск

```bash
cd ~/smart-notes
docker compose -f docker-compose.prod.yml up -d --build
```

Что произойдёт:
1. Соберётся Docker-образ backend.
2. Соберётся Docker-образ frontend (multi-stage: node → alpine с готовым dist).
3. Стартанёт Postgres → backend (с автомиграцией alembic) → bot → Caddy.
4. Caddy получит сертификат Let's Encrypt **автоматически** (нужно чтобы `PUBLIC_DOMAIN` уже резолвился в IP сервера, см. шаг 1).

Проверь статус:

```bash
docker compose -f docker-compose.prod.yml ps
docker compose -f docker-compose.prod.yml logs -f backend
docker compose -f docker-compose.prod.yml logs -f bot
docker compose -f docker-compose.prod.yml logs -f caddy
```

Проверь снаружи:

```bash
curl -sf https://smart-notes.duckdns.org/health
# {"status":"ok","service":"smart-notes-backend"}
```

Открой `https://smart-notes.duckdns.org/` в браузере — должна загрузиться SPA.

---

## 6. Включаем нативную WebApp-кнопку в @BotFather

1. Открой бота в Telegram, набери `/start` → должна появиться **обычная** клавиатура (1-тап-вариант) с кнопкой «🌐 Открыть приложение» (т.к. URL https).
2. Хочешь, чтобы у бота **снизу был "Open App"** (постоянная Menu Button):
   - В @BotFather: `/mybots` → выбери бота → **Bot Settings** → **Menu Button** → **Configure menu button**
   - URL: `https://smart-notes.duckdns.org`
   - Текст: `Open App`

---

## 7. Обновление кода

```bash
cd ~/smart-notes && git pull
cd ~/smart-notes-frontend && git pull
cd ~/smart-notes
docker compose -f docker-compose.prod.yml up -d --build
```

`--build` пересоберёт изменённые образы. Caddy не трогает сертификат при обновлении — он лежит в `caddy_data` volume и переживает рестарт.

Если меняешь **только** frontend:

```bash
cd ~/smart-notes-frontend && git pull
cd ~/smart-notes
docker compose -f docker-compose.prod.yml up -d --build frontend-build
docker compose -f docker-compose.prod.yml restart caddy
```

---

## 8. Бэкап БД

```bash
# Дамп
docker compose -f docker-compose.prod.yml exec -T postgres \
  pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB" \
  | gzip > ~/backups/smartnotes-$(date +%F).sql.gz

# Восстановление
gunzip -c ~/backups/smartnotes-YYYY-MM-DD.sql.gz \
  | docker compose -f docker-compose.prod.yml exec -T postgres \
    psql -U "$POSTGRES_USER" -d "$POSTGRES_DB"
```

Можно прицепить в cron:

```bash
crontab -e
# каждый день в 03:00
0 3 * * * /usr/bin/docker compose -f /home/deploy/smart-notes/docker-compose.prod.yml exec -T postgres pg_dump -U smartnotes smart_notes | gzip > /home/deploy/backups/snotes-$(date +\%F).sql.gz
```

---

## 9. Авто-обновление DuckDNS (если IP меняется)

Если у VPS статический IP — можно пропустить. Иначе:

```bash
mkdir -p ~/duckdns && cd ~/duckdns
cat > duck.sh <<'EOF'
#!/bin/sh
echo url="https://www.duckdns.org/update?domains=smart-notes&token=YOUR_DUCKDNS_TOKEN&ip=" | curl -k -o ~/duckdns/duck.log -K -
EOF
chmod 700 duck.sh
crontab -e
# каждые 5 минут
*/5 * * * * /home/deploy/duckdns/duck.sh >/dev/null 2>&1
```

---

## 10. Часто встречающиеся проблемы

| Симптом | Причина | Решение |
|---|---|---|
| Caddy не получает сертификат | Домен ещё не резолвится в IP или порт 80 занят | `dig smart-notes.duckdns.org`, проверь firewall |
| Bot молчит | Старый процесс крутится локально и съел polling | `docker compose logs bot`, останови локальный |
| `BUTTON_URL_INVALID` | `WEB_APP_URL` ещё http — рестартуй бота после правки .env | `docker compose restart bot` |
| Фронт 404 на роутах | Caddyfile должен иметь `try_files {path} /index.html` (уже есть) | проверь Caddyfile в репо |
| CORS в браузере | Фронт обращается на /api/, а Caddy не проксирует | `docker compose logs caddy`, проверь Caddyfile |
| 500 при создании заметки | Миграции не накатились | `docker compose exec backend alembic upgrade head` |
