# BabyBot — Telegram-бот для отслеживания ухода за ребёнком

## Что умеет

- 😴 **Сон** — фиксировать засыпание и пробуждение с выбором времени (сейчас / N минут назад)
- 🌅 **Ночной опросник** — в 8:30 бот спрашивает о ночи через кнопки, рассчитывает ночной сон
- 🍼 **Кормление** — смесь (мл, быстрые кнопки) и грудь (таймер)
- ⚖️ **Вес** — ввод и динамический график
- 🎵 **Музыка** — добавить YouTube-ссылку, слушать без открытия YouTube
- 📊 **Статистика** — графики сна и кормлений за день/неделю/месяц
- 🌙 **Дайджест в 21:00** — автоматическая сводка за день
- 📅 **Напоминание о весе** — каждый понедельник в 9:00

---

## Быстрый старт

### 1. Получить токен бота

Написать @BotFather → `/newbot` → получить `BOT_TOKEN`

### 2. Узнать свой Telegram ID

Написать @userinfobot — он покажет ваш числовой ID

### 3. Настроить .env

```bash
cp .env.example .env
nano .env
```

Заполнить:
```
BOT_TOKEN=1234567890:AAaabbcc...
ALLOWED_USERS=123456789          # ваш telegram ID (через запятую для нескольких)
TZ=Asia/Almaty                   # или Europe/Moscow, Asia/Novosibirsk и т.д.
BABY_BIRTHDATE=2025-04-09        # дата рождения ребёнка
BABY_NAME=Арсений                # имя малыша
```

### 4. Запустить через Docker

```bash
docker compose up -d
```

Смотреть логи:
```bash
docker compose logs -f
```

---

## Деплой на Timeweb Cloud VPS

1. Создать VPS: Ubuntu 22.04, минимум 1 CPU / 1GB RAM (~200 ₽/мес)
2. Подключиться по SSH и установить Docker:
   ```bash
   curl -fsSL https://get.docker.com | sh
   ```
3. Склонировать бота:
   ```bash
   git clone <ваш репо> baby-bot && cd baby-bot
   ```
4. Настроить `.env` (шаг 3 выше)
5. Запустить:
   ```bash
   docker compose up -d
   ```

База данных хранится в `./data/baby.db` — не теряется при перезапуске контейнера.

### Бэкап базы

```bash
cp data/baby.db data/baby-$(date +%Y%m%d).db
```

---

## Структура проекта

```
baby-bot/
├── bot/
│   ├── main.py              # точка входа
│   ├── config.py            # настройки из .env
│   ├── models.py            # SQLite модели
│   ├── handlers/
│   │   ├── menu.py          # главное меню
│   │   ├── sleep.py         # трекер сна
│   │   ├── night_report.py  # утренний опросник
│   │   ├── feeding.py       # кормление
│   │   ├── weight.py        # вес
│   │   ├── music.py         # музыка
│   │   └── analytics.py     # статистика
│   ├── keyboards/
│   │   └── inline.py        # все клавиатуры
│   └── services/
│       ├── db.py            # session helper
│       ├── baby.py          # возраст, форматирование
│       └── scheduler.py     # APScheduler задачи
├── data/                    # база данных (volume)
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── .env.example
```
