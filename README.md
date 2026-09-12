# avito-parser 🚀

> **Надёжный, быстрый и модульный парсер Авито** с автоматическим решением Proof-of-Work (PoW) челленджей, ротацией прокси, адаптивным контроллером задержек и поддержкой современного React SSR/Redux состояния (`__staticRouterHydrationData`).

---

## ⚡ Особенности

- **🛡️ Автоматический обход PoW (Proof-of-Work):** Самостоятельно перехватывает и решает криптографический SHA-256 челлендж Авито за <0.1 секунды без внешних сервисов капчи.
- **📦 Полный сбор данных:**
  - Точная цена и валюта
  - Полное описание без обрезки и HTML-мусора
  - Все характеристики (процессор, ядра, память, SSD, видеокарта, экран и т.д.)
  - Данные продавца (имя, рейтинг, количество отзывов, статус компании)
  - Адрес и город
  - Список фотографий в максимальном разрешении
- **🔄 Пул и ротация прокси:** Поддержка HTTP/HTTPS/SOCKS4/SOCKS5 (с удалённым DNS `socks5h`), авторизацией и автоматическим отключением сбойных адресов.
- **⏱️ Умный Rate Limiter:** Адаптивные задержки со случайным джиттером и экспоненциальным backoff при получении 429/439 кодов.
- **💾 Множество форматов экспорта:** Консольная таблица, JSON, JSONL, CSV, база данных SQLite.
- **🛠️ Два режима работы:** Как CLI-утилита в терминале и как Python-библиотека.

---

## 📥 Установка

```bash
git clone https://github.com/gemeguardian/avito-parser.git
cd avito-parser
pip install -r requirements.txt
pip install -e .
```

---

## 💻 Использование через CLI

### 1. Парсинг одного или нескольких объявлений

```bash
avito-parser item "https://www.avito.ru/nizhniy_novgorod/noutbuki/honor_magicbook_14_nmh-wfq9hn_16512gb_8388969237"
```

Экспорт в JSON, CSV или SQLite:
```bash
avito-parser item "URL1" "URL2" --json items.json --csv items.csv --sqlite items.db
```

Использование SOCKS5 / HTTP прокси:
```bash
avito-parser item "URL" --proxy "socks5h://user:password@host:port"
```

### 2. Пакетная обработка списка ссылок из файла

```bash
avito-parser batch urls.txt --proxy-file proxies.txt --json output.json --sqlite database.db
```

### 3. Поиск по каталогу

```bash
avito-parser search "ThinkBook 16GB" --location "nizhniy_novgorod" --page 1
```

### 4. Тестирование обхода PoW защиты

```bash
avito-parser test-pow --proxy "socks5h://user:password@host:port"
```

---

## 🐍 Использование как Python библиотеки

### Парсинг отдельного объявления

```python
from avito_parser import AvitoParser

# Инициализация с настройкой задержек и прокси
parser = AvitoParser(
    proxies="socks5h://user:password@host:port",  # опционально
    min_delay=2.0,
    max_delay=4.0
)

url = "https://www.avito.ru/nizhniy_novgorod/noutbuki/honor_magicbook_14_nmh-wfq9hn_16512gb_8388969237"
item = parser.get_item(url)

if item:
    print(f"Название: {item.title}")
    print(f"Цена: {item.formatted_price}")
    print(f"Продавец: {item.seller.name} (★ {item.seller.rating})")
    print(f"Характеристики: {item.params}")
    print(f"Описание:\n{item.description}")
```

### Пакетный сбор с пулом прокси и сохранением

```python
from avito_parser import AvitoParser, ProxyManager, ItemExporter

urls = [
    "https://www.avito.ru/.../url1",
    "https://www.avito.ru/.../url2",
]

# Пул прокси с ротацией
proxy_manager = ProxyManager([
    "socks5h://user:pass@proxy1:2002",
    "socks5h://user:pass@proxy2:2002",
], max_fails=2, randomize=True)

with AvitoParser(proxies=proxy_manager, min_delay=2.0, max_delay=4.0) as parser:
    items = parser.get_items(urls)

    # Вывод сводной таблицы
    ItemExporter.print_summary(items)

    # Сохранение в JSON, CSV и SQLite
    ItemExporter.to_json(items, "results.json")
    ItemExporter.to_csv(items, "results.csv")
    ItemExporter.to_sqlite(items, "results.db")
```

---

## 🧩 Архитектура проекта

```
avito-parser/
├── avito_parser/
│   ├── __init__.py         # Экспорт основных сущностей
│   ├── client.py           # Высокоуровневый клиент AvitoParser
│   ├── pow.py              # Автономный Proof-of-Work солвер
│   ├── parser.py           # Парсер Hydration (Redux) + Schema.org + Meta
│   ├── models.py           # Dataclass структуры данных (AvitoItem, SellerInfo)
│   ├── proxy.py            # ProxyManager, ротация, нормализация протоколов
│   ├── rate_limiter.py     # Адаптивный контроллер задержек и backoff
│   ├── exporter.py         # Экспорт в JSON, CSV, SQLite, Terminal Table
│   └── cli.py              # Аргументы командной строки
├── examples/               # Практические примеры использования
├── tests/                  # Модульные и интеграционные тесты
├── requirements.txt        # Зависимости
├── setup.py                # Установка пакета
└── README.md               # Документация
```

---

## ⏱️ Профили задержек и лимиты Авито

На основе реверс-инжиниринга фаервола Авито библиотека реализует 4 профиля:

| Профиль | Задержка (интервал) | Jitter | Назначение |
|---|---|---|---|
| `balanced` *(default)* | **2.5 – 4.5 сек** | ±0.3с | Оптимальный баланс для обычного использования |
| `stealth` | **3.5 – 6.5 сек** | ±0.5с | Максимальная маскировка под человека на одном мобильном/домашнем IP |
| `datacenter` | **4.5 – 8.5 сек** | ±0.7с | Для серверных/датацентровых подсетей с частым триггером PoW |
| `fast_rotating` | **0.8 – 1.8 сек** | ±0.2с | Только для больших пулов ротируемых резидентских прокси |

### Механика антифрода Авито:
- **Burst-порог:** Более 2–3 запросов в секунду с одного IP приводят к `429: проблема с IP`.
- **Token TTL (420 сек):** При успешном решении PoW сервер выдает `unblock_ttl: 420` (7 минут). Библиотека отслеживает этот таймер и превентивно обновляет сессию, не допуская внезапного разрыва в середине парсинга.
- **Экспоненциальный откат (Backoff):** При получении `429` интервал временно увеличивается в 1.8–2.2 раза, спасая IP от долгосрочного пермабана.

```bash
# Использование профиля через CLI:
avito-parser item "URL" --profile stealth
avito-parser batch urls.txt --profile fast_rotating --proxy-file proxies.txt
```

---

## 💡 Рекомендации по обходу блокировок

1. **Тип IP:** Авито строго фильтрует датацентровые подсети (Hetzner, OVH, DigitalOcean и т.д.). Для непрерывного парсинга используйте **резидентские** или **мобильные** российские прокси.
2. **Тайминги:** Безопасный интервал между запросами с одного IP — **2.5–5 секунд** (профиль `balanced` или `stealth`).
3. **PoW Solver:** Модуль `AvitoPoWSolver` решает челленджи автоматически, но при появлении ручной капчи (Geo/Behavioral) рекомендуется смена прокси через `ProxyManager`.

---

## 📄 Лицензия

MIT License. Создано в исследовательских целях.
