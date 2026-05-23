Вот полный README файл с инструкцией по установке и запуску вашего приложения:

```markdown
# 🖼️ Dynamic Wallpaper Manager

Приложение для автоматической смены обоев рабочего стола Windows с загрузкой изображений из интернета.

## 📋 Требования

- **Операционная система**: Windows 10/11
- **Python**: версия 3.8 или выше
- **PostgreSQL**: версия 15, 16, 17 или 18
- **Интернет-соединение**: для загрузки изображений

## 🚀 Быстрый старт

### 1. Установка PostgreSQL

1. Скачайте установщик с официального сайта:
   ```
   https://www.postgresql.org/download/windows/
   ```

2. Запустите установку:
   - Выберите компоненты: **PostgreSQL Server** и **pgAdmin 4**
   - Задайте пароль для пользователя `postgres` (запомните его!)
   - Оставьте порт по умолчанию: `5432`
   - Выберите кодировку: `UTF8`

3. После установки запустите **pgAdmin 4**

### 2. Создание базы данных

В pgAdmin 4 выполните следующие шаги:

1. Подключитесь к серверу (пароль, который задали при установке)
2. Нажмите правой кнопкой на **Databases** → **Create** → **Database**
3. Введите имя базы: `wallpaper_db`
4. Нажмите **Save**

### 3. Создание таблиц

Откройте **Query Tool** (правой кнопкой на `wallpaper_db` → **Query Tool**) и выполните этот SQL:

```sql
-- Таблица изображений
CREATE TABLE wallpapers (
    id SERIAL PRIMARY KEY,
    image_data BYTEA NOT NULL,
    image_url TEXT NOT NULL,
    title TEXT,
    source TEXT,
    theme_category TEXT,
    width INTEGER,
    height INTEGER,
    file_size INTEGER,
    date_added TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_active BOOLEAN DEFAULT FALSE,
    times_used INTEGER DEFAULT 0,
    rating INTEGER DEFAULT 0
);

-- Таблица пользователей
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    username TEXT UNIQUE NOT NULL,
    password TEXT NOT NULL,
    theme_category TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_login TIMESTAMP
);

-- Таблица источников изображений
CREATE TABLE theme_sources (
    id SERIAL PRIMARY KEY,
    theme_name TEXT NOT NULL,
    source_name TEXT NOT NULL,
    api_url TEXT NOT NULL,
    search_query TEXT,
    is_enabled BOOLEAN DEFAULT TRUE,
    priority INTEGER DEFAULT 1
);

-- Добавление источников
INSERT INTO theme_sources (theme_name, source_name, api_url, is_enabled, priority) VALUES
('men', 'Lorem Picsum', 'https://picsum.photos/1920/1080', TRUE, 1),
('men', 'PlaceKitten', 'https://placekitten.com/1920/1080', TRUE, 2),
('women', 'Lorem Picsum', 'https://picsum.photos/1920/1080', TRUE, 1),
('women', 'PlaceKitten', 'https://placekitten.com/1920/1080', TRUE, 2),
('general', 'Lorem Picsum', 'https://picsum.photos/1920/1080', TRUE, 1),
('general', 'PlaceKitten', 'https://placekitten.com/1920/1080', TRUE, 2);

-- Создание индексов
CREATE INDEX idx_wallpapers_theme ON wallpapers(theme_category);
CREATE INDEX idx_users_name ON users(username);
```

### 4. Установка Python и зависимостей

1. **Установите Python** (если не установлен):
   ```
   https://www.python.org/downloads/
   ```
   ⚠️ **Важно**: При установке отметьте галочку "Add Python to PATH"

2. **Установите необходимые библиотеки**:

   Откройте **Командную строку (cmd)** или **PowerShell** и выполните:

   ```bash
   pip install psycopg2-binary requests pillow
   ```

   Или установите все сразу:

   ```bash
   pip install psycopg2-binary requests pillow
   ```

### 5. Настройка приложения

1. Скачайте файл `wallpaper_app.py`

2. Откройте его в любом текстовом редакторе

3. Найдите и измените настройки подключения к БД (в начале файла):

   ```python
   DB_CONFIG = {
       'host': 'localhost',
       'port': 5432,
       'database': 'wallpaper_db',
       'user': 'postgres',
       'password': 'ВАШ_ПАРОЛЬ'  # Пароль, который задали при установке PostgreSQL
   }
   ```

### 6. Запуск приложения

1. **Способ 1: Через командную строку**
   ```bash
   python wallpaper_app.py
   ```

2. **Способ 2: Двойным щелчком**
   - Просто дважды кликните по файлу `wallpaper_app.py`

3. **Способ 3: Создать ярлык**
   - Создайте ярлык и укажите: `python "путь_к_файлу\wallpaper_app.py"`

## 📖 Использование приложения

### Регистрация

1. При первом запуске заполните форму регистрации
2. Введите **логин** и **пароль**
3. Нажмите **"Зарегистрироваться"**

### Вход в систему

1. Введите логин и пароль
2. Нажмите **"Войти"**

### Выбор темы

Выберите одну из тем:

| Тема | Описание | Цвет |
|------|----------|------|
| 🎮 **Мужская** | Авто, спорт, технологии | Синий |
| 💐 **Женская** | Мода, цветы, искусство | Красный |
| 🌍 **Смешанная** | Разнообразные изображения | Зеленый |

### Настройка

Перед запуском настройте параметры:

- **Интервал смены** (10-300 секунд)
- **Количество для предзагрузки** (1-20 изображений)
- **Режим работы** (Интернет + БД или только БД)

### Управление

В окне управления доступны кнопки:

| Кнопка | Действие |
|--------|----------|
| ▶️ Запустить | Возобновить смену обоев |
| ⏹️ Остановить | Приостановить смену |
| 🔄 Интервал | Изменить время смены |
| 📊 Статистика | Показать статистику БД |
| 🗄️ База данных | Просмотр содержимого |
| 🎨 Сменить тему | Выбрать другую тему |
| ❌ Выйти | Завершить работу |

## 🐛 Устранение неполадок

### 1. Ошибка подключения к PostgreSQL

```
connection to server at "127.0.0.1", port 5432 failed
```

**Решение:**
- Запустите службу PostgreSQL: `Win + R` → `services.msc` → найдите `postgresql-x64-...` → нажмите "Запустить"
- Проверьте пароль в `DB_CONFIG`
- Убедитесь, что база `wallpaper_db` создана

### 2. Ошибка "psycopg2 not found"

```
ModuleNotFoundError: No module named 'psycopg2'
```

**Решение:**
```bash
pip install psycopg2-binary
```

### 3. Ошибка "PIL not found"

```
ModuleNotFoundError: No module named 'PIL'
```

**Решение:**
```bash
pip install Pillow
```

### 4. Ошибка "requests not found"

```
ModuleNotFoundError: No module named 'requests'
```

**Решение:**
```bash
pip install requests
```

### 5. Обои не устанавливаются

**Решение:**
- Запустите программу от имени администратора
- Проверьте, что папка `downloaded_wallpapers` существует и доступна для записи

### 6. Не загружаются изображения из интернета

**Решение:**
- Проверьте интернет-соединение
- Проверьте работу источников: откройте в браузере `https://picsum.photos/1920/1080`
- Временно отключите антивирус/фаервол

## 📁 Структура проекта

```
project/
├── wallpaper_app.py          # Главный файл приложения
├── downloaded_wallpapers/    # Папка для временных файлов (создается автоматически)
└── requirements.txt          # Файл с зависимостями (опционально)
```

## 📦 Зависимости

Создайте файл `requirements.txt`:

```txt
psycopg2-binary>=2.9.0
requests>=2.31.0
Pillow>=10.0.0
```

Установка всех зависимостей одной командой:

```bash
pip install -r requirements.txt
```

## ⚙️ Технические детали

### Источники изображений

Приложение использует бесплатные API для загрузки изображений:

- **Lorem Picsum** - реальные фотографии высокого качества
- **PlaceKitten** - изображения котят (юмор)
- **Dummy Image** - цветные заглушки с текстом

### Формат изображений

- Размер: 1920×1080 (Full HD) и выше
- Формат: JPEG
- Качество: 85-90%

### Хранение в БД

- Изображения хранятся в поле `BYTEA` (бинарные данные)
- Средний размер одного изображения: ~200-500 KB

## 🎯 Возможности

- ✅ Автоматическая смена обоев
- ✅ Загрузка из интернета
- ✅ Сохранение в базу данных
- ✅ Предзагрузка изображений
- ✅ Статистика использования
- ✅ Система пользователей
- ✅ Настраиваемый интервал
- ✅ Тематические коллекции
- ✅ Резервные изображения (при отключении интернета)

## 📞 Поддержка

При возникновении проблем:

1. Проверьте лог событий в окне управления
2. Посмотрите вывод в консоли (черное окно)
3. Проверьте, что PostgreSQL запущен
4. Убедитесь, что база данных `wallpaper_db` создана

## 📝 Лицензия

Свободное использование для личных целей.

---

**Приятного использования!** 🖼️✨
```

Сохраните этот текст как `README.md` в папке с вашим проектом.