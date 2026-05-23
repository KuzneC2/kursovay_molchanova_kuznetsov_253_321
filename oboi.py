import subprocess
import sys
import os

try:
    import psycopg2
    from psycopg2.extras import RealDictCursor

    USE_POSTGRESQL = True
    print("✅ Используем PostgreSQL")
except ImportError:
    print("⚠️ psycopg2 не найден, устанавливаем...")
    subprocess.check_call([sys.executable, '-m', 'pip', 'install', 'psycopg2-binary'])
    import psycopg2
    from psycopg2.extras import RealDictCursor

    USE_POSTGRESQL = True
    print("✅ psycopg2 установлен, используем PostgreSQL")

import requests
import ctypes
import time
import threading
from datetime import datetime
from pathlib import Path
import random
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont
import tkinter as tk
from tkinter import messagebox, simpledialog, ttk
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

DB_CONFIG = {
    'host': 'localhost',
    'port': 5433,
    'database': 'wallpaper_db',
    'user': 'postgres',
    'password': '0908'
}


class DatabaseManager:

    def __init__(self):
        self.conn = None
        self.cursor = None
        self.connect()

    def connect(self):
        try:
            self.conn = psycopg2.connect(**DB_CONFIG)
            self.cursor = self.conn.cursor()
            print("✅ Подключено к PostgreSQL")
            return True
        except Exception as e:
            print(f"❌ Ошибка подключения к PostgreSQL: {e}")
            return False

    def execute(self, query, params=None, fetch_one=False, fetch_all=False):
        try:
            if not self.conn or self.conn.closed:
                self.connect()

            if params:
                self.cursor.execute(query, params)
            else:
                self.cursor.execute(query)

            if fetch_one:
                return self.cursor.fetchone()
            elif fetch_all:
                return self.cursor.fetchall()

            self.conn.commit()
            return True

        except Exception as e:
            if self.conn:
                self.conn.rollback()
            print(f"❌ Ошибка запроса: {e}")
            return None

    def close(self):
        """Закрытие соединения"""
        if self.cursor:
            self.cursor.close()
        if self.conn:
            self.conn.close()
            print("🔌 Соединение с PostgreSQL закрыто")


class DynamicWallpaperManager:
    def __init__(self, images_folder="downloaded_wallpapers"):
        self.program_dir = Path(__file__).parent.absolute()
        self.images_folder = self.program_dir / images_folder
        self.images_folder.mkdir(exist_ok=True)

        self.running = False
        self.current_theme = None
        self.current_user = None
        self.wallpaper_thread = None

        # Подключение к БД
        self.db = DatabaseManager()

        # Настройка сессии для загрузки
        self.session = self._create_session()

        # Инициализация БД
        self.init_database()

    def _create_session(self):
        """Создание сессии с повторными попытками"""
        session = requests.Session()
        retry_strategy = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[500, 502, 503, 504]
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        return session

    def init_database(self):
        """Инициализация базы данных"""
        # Создание таблиц
        queries = [
            """
            CREATE TABLE IF NOT EXISTS wallpapers (
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
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                username TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL,
                theme_category TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_login TIMESTAMP
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS theme_sources (
                id SERIAL PRIMARY KEY,
                theme_name TEXT NOT NULL,
                source_name TEXT NOT NULL,
                api_url TEXT NOT NULL,
                search_query TEXT,
                is_enabled BOOLEAN DEFAULT TRUE,
                priority INTEGER DEFAULT 1
            )
            """,
            """
            CREATE INDEX IF NOT EXISTS idx_wallpapers_theme ON wallpapers(theme_category)
            """,
            """
            CREATE INDEX IF NOT EXISTS idx_wallpapers_active ON wallpapers(is_active)
            """,
            """
            CREATE INDEX IF NOT EXISTS idx_users_name ON users(username)
            """
        ]

        for query in queries:
            self.db.execute(query)

        # Добавление начальных данных
        self.db.execute("SELECT COUNT(*) FROM theme_sources")
        count = self.db.cursor.fetchone()[0]

        if count == 0:
            sources = [
                ("men", "Lorem Picsum", "https://picsum.photos/1920/1080", "", True, 1),
                ("men", "PlaceKitten", "https://placekitten.com/1920/1080", "", True, 2),
                ("men", "Dummy Image", "https://dummyimage.com/1920x1080/2c3e50/ffffff", "", True, 3),
                ("women", "Lorem Picsum", "https://picsum.photos/1920/1080", "", True, 1),
                ("women", "PlaceKitten", "https://placekitten.com/1920/1080", "", True, 2),
                ("women", "Dummy Image", "https://dummyimage.com/1920x1080/e74c3c/ffffff", "", True, 3),
                ("general", "Lorem Picsum", "https://picsum.photos/1920/1080", "", True, 1),
                ("general", "PlaceKitten", "https://placekitten.com/1920/1080", "", True, 2),
                ("general", "Dummy Image", "https://dummyimage.com/1920x1080/27ae60/ffffff", "", True, 3),
            ]

            for s in sources:
                self.db.execute("""
                    INSERT INTO theme_sources (theme_name, source_name, api_url, search_query, is_enabled, priority)
                    VALUES (%s, %s, %s, %s, %s, %s)
                """, s)

            print("✅ Начальные данные добавлены")

    def get_images_from_web(self, theme, limit=5):
        """Получение изображений из интернета"""
        self.db.execute("""
            SELECT source_name, api_url, priority 
            FROM theme_sources 
            WHERE theme_name = %s AND is_enabled = TRUE 
            ORDER BY priority
        """, (theme,))

        sources = self.db.cursor.fetchall()
        images_data = []

        for source in sources:
            if len(images_data) >= limit:
                break

            source_name, api_url, priority = source

            # Формируем URL для разных источников
            if "picsum" in api_url.lower():
                random_id = random.randint(1, 200)
                url = f"https://picsum.photos/id/{random_id}/1920/1080"
            elif "placekitten" in api_url.lower():
                width = random.choice([1920, 2560, 3840])
                height = random.choice([1080, 1440, 2160])
                url = f"https://placekitten.com/{width}/{height}"
            elif "dummyimage" in api_url.lower():
                colors = {
                    "men": "2c3e50",
                    "women": "e74c3c",
                    "general": "27ae60"
                }
                color = colors.get(theme, "3498db")
                url = f"https://dummyimage.com/1920x1080/{color}/ffffff"
            else:
                url = api_url

            try:
                image_data, info = self.download_image(url, source_name)
                if image_data:
                    info['theme'] = theme
                    images_data.append((image_data, info))
                    print(f"✅ Загружено: {source_name}")
            except Exception as e:
                print(f"⚠️ Ошибка загрузки из {source_name}: {e}")
                continue

            time.sleep(0.5)

        # Если не удалось загрузить, создаем резервное
        if not images_data:
            image_data, info = self.create_fallback_image(theme)
            if image_data:
                images_data.append((image_data, info))

        return images_data

    def download_image(self, url, source_name):
        """Скачивание изображения"""
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }

            response = self.session.get(url, headers=headers, timeout=15)
            response.raise_for_status()

            image_data = response.content

            # Проверяем и конвертируем
            img = Image.open(BytesIO(image_data))
            width, height = img.size

            if img.mode != 'RGB':
                img = img.convert('RGB')
                img_bytes = BytesIO()
                img.save(img_bytes, format='JPEG', quality=85)
                image_data = img_bytes.getvalue()

            info = {
                "width": width,
                "height": height,
                "file_size": len(image_data),
                "url": url,
                "source": source_name
            }

            return image_data, info

        except Exception as e:
            return None, None

    def create_fallback_image(self, theme):
        """Создание резервного изображения"""
        try:
            theme_colors = {
                "men": ("#2980b9", "#1a5276", "МУЖСКАЯ ТЕМА\nАвто • Спорт • Технологии"),
                "women": ("#e74c3c", "#c0392b", "ЖЕНСКАЯ ТЕМА\nМода • Цветы • Искусство"),
                "general": ("#27ae60", "#1e8449", "СМЕШАННАЯ ТЕМА\nРазнообразные изображения")
            }

            color1, color2, text = theme_colors.get(theme, ("#3498db", "#2c3e50", "ДИНАМИЧЕСКИЕ ОБОИ"))

            img = Image.new('RGB', (1920, 1080))
            draw = ImageDraw.Draw(img)

            # Рисуем градиент
            for y in range(1080):
                ratio = y / 1080
                r = int(int(color1[1:3], 16) * (1 - ratio) + int(color2[1:3], 16) * ratio)
                g = int(int(color1[3:5], 16) * (1 - ratio) + int(color2[3:5], 16) * ratio)
                b = int(int(color1[5:7], 16) * (1 - ratio) + int(color2[5:7], 16) * ratio)
                draw.line([(0, y), (1920, y)], fill=(r, g, b))

            # Добавляем текст
            try:
                font = ImageFont.truetype("arial.ttf", 60)
                font_small = ImageFont.truetype("arial.ttf", 30)
            except:
                font = ImageFont.load_default()
                font_small = ImageFont.load_default()

            # Центрируем текст
            draw.text((960, 540), text, fill='white', font=font, anchor='mm')

            footer_text = "Dynamic Wallpaper Manager"
            draw.text((960, 1000), footer_text, fill='#bdc3c7', font=font_small, anchor='mm')

            img_bytes = BytesIO()
            img.save(img_bytes, format='JPEG', quality=90)
            image_data = img_bytes.getvalue()

            info = {
                "width": 1920,
                "height": 1080,
                "file_size": len(image_data),
                "url": "fallback_image",
                "source": "Built-in Generator"
            }

            return image_data, info
        except Exception as e:
            print(f"Ошибка создания изображения: {e}")
            return None, None

    def save_to_database(self, image_data, info, theme, title=None):
        """Сохранение изображения в БД"""
        try:
            if not title:
                title = f"{info['source']} - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"

            query = """
                INSERT INTO wallpapers 
                (image_data, image_url, title, source, theme_category, width, height, file_size, is_active)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
            """
            params = (psycopg2.Binary(image_data), info['url'], title[:100],
                      info['source'], theme, info['width'], info['height'],
                      info['file_size'], False)

            result = self.db.execute(query, params, fetch_one=True)

            if result:
                return result[0]
            return None

        except Exception as e:
            print(f"Ошибка сохранения: {e}")
            return None

    def get_random_from_database(self, theme):
        """Получение случайного изображения из БД"""
        try:
            # Сначала ищем по теме
            query = """
                SELECT id, image_data, title, source, theme_category, width, height
                FROM wallpapers
                WHERE theme_category = %s
                ORDER BY times_used ASC, RANDOM()
                LIMIT 1
            """
            result = self.db.execute(query, (theme,), fetch_one=True)

            if not result:
                # Если нет, ищем в general
                query = """
                    SELECT id, image_data, title, source, theme_category, width, height
                    FROM wallpapers
                    WHERE theme_category = 'general'
                    ORDER BY times_used ASC, RANDOM()
                    LIMIT 1
                """
                result = self.db.execute(query, fetch_one=True)

            if result:
                image_id, image_data, title, source, theme_category, width, height = result

                # Обновляем счетчик
                self.db.execute("""
                    UPDATE wallpapers 
                    SET times_used = times_used + 1, is_active = TRUE
                    WHERE id = %s
                """, (image_id,))

                # Деактивируем другие
                self.db.execute("""
                    UPDATE wallpapers 
                    SET is_active = FALSE
                    WHERE id != %s
                """, (image_id,))

                info = {
                    "id": image_id,
                    "title": title,
                    "source": source,
                    "width": width,
                    "height": height,
                    "theme": theme_category
                }

                return image_data, info

            return None, None

        except Exception as e:
            print(f"Ошибка получения из БД: {e}")
            return None, None

    def set_wallpaper_windows(self, image_data):
        """Установка обоев в Windows"""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]
            filepath = self.images_folder / f"wallpaper_{timestamp}.jpg"

            with open(filepath, "wb") as f:
                f.write(image_data)

            result = ctypes.windll.user32.SystemParametersInfoW(20, 0, str(filepath.absolute()), 0x01 | 0x02)
            return bool(result)
        except Exception as e:
            print(f"Ошибка установки обоев: {e}")
            return False

    def preload_images(self, theme, count=5):
        """Предзагрузка изображений"""
        images = self.get_images_from_web(theme, count)
        successful = 0

        for image_data, info in images:
            if image_data:
                self.save_to_database(image_data, info, theme)
                successful += 1

        return successful

    def start_cycle(self, theme, interval_seconds=30, use_web=True):
        """Запуск цикла смены обоев"""
        self.current_theme = theme
        self.running = True

        def cycle():
            cycle_count = 0

            while self.running:
                try:
                    cycle_count += 1

                    if use_web and cycle_count % 3 == 0:
                        # Загружаем новое из интернета
                        images = self.get_images_from_web(self.current_theme, 1)
                        if images:
                            image_data, info = images[0]
                            self.save_to_database(image_data, info, self.current_theme)
                            self.set_wallpaper_windows(image_data)
                            print(f"🖼️ Установлено новое изображение из интернета: {info['source']}")
                    else:
                        # Берем из БД
                        image_data, info = self.get_random_from_database(self.current_theme)

                        if not image_data:
                            # Если в БД пусто, загружаем
                            images = self.get_images_from_web(self.current_theme, 1)
                            if images:
                                image_data, info = images[0]
                                self.save_to_database(image_data, info, self.current_theme)

                        if image_data:
                            self.set_wallpaper_windows(image_data)
                            print(f"🖼️ Установлено изображение из БД: {info['title']}")

                    # Пауза
                    for i in range(interval_seconds):
                        if not self.running:
                            break
                        time.sleep(1)

                except Exception as e:
                    print(f"Ошибка в цикле: {e}")
                    time.sleep(5)

        self.wallpaper_thread = threading.Thread(target=cycle, daemon=True)
        self.wallpaper_thread.start()

    def stop_cycle(self):
        """Остановка цикла"""
        self.running = False
        if self.wallpaper_thread:
            self.wallpaper_thread.join(timeout=2)

    def register_user(self, username, password):
        """Регистрация пользователя"""
        try:
            self.db.execute(
                "INSERT INTO users (username, password) VALUES (%s, %s)",
                (username, password)
            )
            return True
        except Exception:
            return False

    def login_user(self, username, password):
        """Вход пользователя"""
        try:
            result = self.db.execute(
                "SELECT username FROM users WHERE username = %s AND password = %s",
                (username, password),
                fetch_one=True
            )

            if result:
                self.db.execute(
                    "UPDATE users SET last_login = CURRENT_TIMESTAMP WHERE username = %s",
                    (username,)
                )
                return result[0]
            return None
        except Exception:
            return None

    def get_statistics(self):
        """Получение статистики"""
        try:
            total = self.db.execute("SELECT COUNT(*) FROM wallpapers", fetch_one=True)
            avg = self.db.execute("SELECT AVG(file_size) FROM wallpapers", fetch_one=True)
            sources = self.db.execute(
                "SELECT source, COUNT(*) FROM wallpapers GROUP BY source",
                fetch_all=True
            )

            return {
                "total_images": total[0] if total else 0,
                "avg_file_size": avg[0] if avg and avg[0] else 0,
                "sources_distribution": sources or []
            }
        except Exception as e:
            print(f"Ошибка статистики: {e}")
            return {"total_images": 0, "avg_file_size": 0, "sources_distribution": []}


class WallpaperApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Динамические обои")
        self.root.geometry("500x600")
        self.root.configure(bg='#2c3e50')

        self.wallpaper_manager = DynamicWallpaperManager()
        self.current_user = None

        self.colors = {
            'bg': '#2c3e50',
            'fg': '#ecf0f1',
            'button_bg': '#3498db',
            'button_fg': 'white',
            'entry_bg': '#34495e',
            'entry_fg': '#ecf0f1'
        }

        self.show_registration()

    def clear_window(self):
        for widget in self.root.winfo_children():
            widget.destroy()

    def show_registration(self):
        self.clear_window()

        tk.Label(self.root, text="ДИНАМИЧЕСКИЕ ОБОИ",
                 font=("Arial", 18, "bold"),
                 bg=self.colors['bg'], fg=self.colors['fg']).pack(pady=20)

        tk.Label(self.root, text="Регистрация",
                 font=("Arial", 12),
                 bg=self.colors['bg'], fg=self.colors['fg']).pack(pady=5)

        frame = tk.Frame(self.root, bg=self.colors['bg'])
        frame.pack(pady=30)

        tk.Label(frame, text="Логин:", font=("Arial", 11),
                 bg=self.colors['bg'], fg=self.colors['fg']).grid(row=0, column=0, padx=10, pady=10)
        self.reg_login = tk.Entry(frame, width=25, font=("Arial", 11),
                                  bg=self.colors['entry_bg'], fg=self.colors['entry_fg'])
        self.reg_login.grid(row=0, column=1, padx=10, pady=10)

        tk.Label(frame, text="Пароль:", font=("Arial", 11),
                 bg=self.colors['bg'], fg=self.colors['fg']).grid(row=1, column=0, padx=10, pady=10)
        self.reg_password = tk.Entry(frame, width=25, font=("Arial", 11), show="*",
                                     bg=self.colors['entry_bg'], fg=self.colors['entry_fg'])
        self.reg_password.grid(row=1, column=1, padx=10, pady=10)

        tk.Button(self.root, text="Зарегистрироваться", command=self.register,
                  bg=self.colors['button_bg'], fg=self.colors['button_fg'],
                  font=("Arial", 10, "bold"), padx=20, pady=5).pack(pady=5)

        tk.Button(self.root, text="Уже есть аккаунт? Войти", command=self.show_login,
                  bg=self.colors['bg'], fg=self.colors['button_bg'],
                  font=("Arial", 10), relief='flat').pack(pady=5)

    def show_login(self):
        self.clear_window()

        tk.Label(self.root, text="ДИНАМИЧЕСКИЕ ОБОИ",
                 font=("Arial", 18, "bold"),
                 bg=self.colors['bg'], fg=self.colors['fg']).pack(pady=20)

        tk.Label(self.root, text="Вход в систему",
                 font=("Arial", 12),
                 bg=self.colors['bg'], fg=self.colors['fg']).pack(pady=5)

        frame = tk.Frame(self.root, bg=self.colors['bg'])
        frame.pack(pady=30)

        tk.Label(frame, text="Логин:", font=("Arial", 11),
                 bg=self.colors['bg'], fg=self.colors['fg']).grid(row=0, column=0, padx=10, pady=10)
        self.login_login = tk.Entry(frame, width=25, font=("Arial", 11),
                                    bg=self.colors['entry_bg'], fg=self.colors['entry_fg'])
        self.login_login.grid(row=0, column=1, padx=10, pady=10)

        tk.Label(frame, text="Пароль:", font=("Arial", 11),
                 bg=self.colors['bg'], fg=self.colors['fg']).grid(row=1, column=0, padx=10, pady=10)
        self.login_password = tk.Entry(frame, width=25, font=("Arial", 11), show="*",
                                       bg=self.colors['entry_bg'], fg=self.colors['entry_fg'])
        self.login_password.grid(row=1, column=1, padx=10, pady=10)

        tk.Button(self.root, text="Войти", command=self.login,
                  bg=self.colors['button_bg'], fg=self.colors['button_fg'],
                  font=("Arial", 10, "bold"), padx=20, pady=5).pack(pady=5)

        tk.Button(self.root, text="Нет аккаунта? Зарегистрироваться", command=self.show_registration,
                  bg=self.colors['bg'], fg=self.colors['button_bg'],
                  font=("Arial", 10), relief='flat').pack(pady=5)

    def register(self):
        login = self.reg_login.get().strip()
        password = self.reg_password.get().strip()

        if not login or not password:
            messagebox.showerror("Ошибка", "Логин и пароль не могут быть пустыми")
            return

        if self.wallpaper_manager.register_user(login, password):
            messagebox.showinfo("Успех", "Регистрация успешна!")
            self.show_login()
        else:
            messagebox.showerror("Ошибка", "Пользователь уже существует")

    def login(self):
        login = self.login_login.get().strip()
        password = self.login_password.get().strip()

        if not login or not password:
            messagebox.showerror("Ошибка", "Введите логин и пароль")
            return

        user = self.wallpaper_manager.login_user(login, password)

        if user:
            self.current_user = user
            messagebox.showinfo("Успех", f"Добро пожаловать, {self.current_user}!")
            self.show_theme_choice()
        else:
            messagebox.showerror("Ошибка", "Неверный логин или пароль")

    def show_theme_choice(self):
        self.clear_window()

        tk.Label(self.root, text=f"Добро пожаловать, {self.current_user}!",
                 font=("Arial", 16, "bold"),
                 bg=self.colors['bg'], fg=self.colors['fg']).pack(pady=20)

        tk.Label(self.root, text="Выберите тематику обоев",
                 font=("Arial", 12),
                 bg=self.colors['bg'], fg=self.colors['fg']).pack(pady=10)

        themes = [
            ("Темы для мужчин", "men", "#2980b9", "Авто • Спорт • Технологии"),
            ("Темы для женщин", "women", "#e74c3c", "Мода • Цветы • Искусство"),
            ("Смешанные темы", "general", "#27ae60", "Разнообразные изображения")
        ]

        for title, theme, color, desc in themes:
            btn = tk.Button(self.root, text=title,
                            command=lambda t=theme: self.start_wallpaper_with_theme(t),
                            bg=color, fg='white',
                            font=("Arial", 12, "bold"),
                            padx=40, pady=15, width=20)
            btn.pack(pady=10)

            tk.Label(self.root, text=desc,
                     font=("Arial", 9), bg=self.colors['bg'], fg='#bdc3c7').pack(pady=(0, 20))

    def start_wallpaper_with_theme(self, theme):
        theme_names = {"men": "мужские", "women": "женские", "general": "смешанные"}
        self.show_settings_window(theme, theme_names.get(theme, theme))

    def show_settings_window(self, theme, theme_name):
        settings_window = tk.Toplevel(self.root)
        settings_window.title(f"Настройки - {theme_name} тема")
        settings_window.geometry("500x600")
        settings_window.configure(bg=self.colors['bg'])

        tk.Label(settings_window, text=f"Настройка {theme_name} темы",
                 font=("Arial", 14, "bold"),
                 bg=self.colors['bg'], fg=self.colors['fg']).pack(pady=20)

        # Интервал
        frame1 = tk.Frame(settings_window, bg=self.colors['bg'])
        frame1.pack(pady=20, fill='x', padx=50)

        tk.Label(frame1, text="Интервал смены (секунд):",
                 bg=self.colors['bg'], fg=self.colors['fg']).pack(anchor='w')

        interval_var = tk.IntVar(value=30)
        scale = tk.Scale(frame1, from_=10, to=300, orient='horizontal',
                         variable=interval_var, bg=self.colors['bg'],
                         length=300, tickinterval=50)
        scale.pack(fill='x', pady=10)

        # Предзагрузка
        frame2 = tk.Frame(settings_window, bg=self.colors['bg'])
        frame2.pack(pady=20, fill='x', padx=50)

        tk.Label(frame2, text="Количество для предзагрузки:",
                 bg=self.colors['bg'], fg=self.colors['fg']).pack(anchor='w')

        preload_var = tk.IntVar(value=5)
        spinbox = tk.Spinbox(frame2, from_=1, to=20, width=10,
                             textvariable=preload_var)
        spinbox.pack(anchor='w', pady=5)

        # Режим
        use_web_var = tk.BooleanVar(value=True)
        check = tk.Checkbutton(settings_window, text="Загружать новые изображения из интернета",
                               variable=use_web_var, bg=self.colors['bg'],
                               fg=self.colors['fg'], selectcolor=self.colors['bg'])
        check.pack(pady=10)

        def preload():
            count = preload_var.get()
            messagebox.showinfo("Предзагрузка", f"Загрузка {count} изображений...")
            successful = self.wallpaper_manager.preload_images(theme, count)
            messagebox.showinfo("Готово", f"Загружено {successful} изображений")

        tk.Button(settings_window, text="Предзагрузить изображения",
                  command=preload, bg=self.colors['button_bg'],
                  fg=self.colors['button_fg']).pack(pady=10)

        def start():
            settings_window.destroy()
            self.show_control_window(theme, theme_name, interval_var.get(), use_web_var.get())

        def cancel():
            settings_window.destroy()
            self.show_theme_choice()

        btn_frame = tk.Frame(settings_window, bg=self.colors['bg'])
        btn_frame.pack(pady=20)

        tk.Button(btn_frame, text="Начать", command=start,
                  bg='#27ae60', fg='white', font=("Arial", 10, "bold"),
                  padx=20).pack(side='left', padx=10)

        tk.Button(btn_frame, text="Назад", command=cancel,
                  bg='#95a5a6', fg='white', padx=20).pack(side='left', padx=10)

    def show_control_window(self, theme, theme_name, interval, use_web):
        control_window = tk.Toplevel(self.root)
        control_window.title(f"Управление - {theme_name} обои")
        control_window.geometry("500x500")
        control_window.configure(bg=self.colors['bg'])

        self.wallpaper_manager.start_cycle(theme, interval, use_web)

        # Статус
        status_label = tk.Label(control_window,
                                text=f"🟢 Обои активны\nТема: {theme_name}\nИнтервал: {interval} сек",
                                bg=self.colors['bg'], fg=self.colors['fg'],
                                font=("Arial", 11))
        status_label.pack(pady=20)

        # Лог
        log_text = tk.Text(control_window, height=10, width=55,
                           bg=self.colors['entry_bg'], fg=self.colors['entry_fg'])
        log_text.pack(pady=10, padx=20)
        log_text.insert('1.0', "📝 Лог событий:\n")
        log_text.config(state='disabled')

        def add_log(msg):
            log_text.config(state='normal')
            log_text.insert('end', f"{datetime.now().strftime('%H:%M:%S')} - {msg}\n")
            log_text.see('end')
            log_text.config(state='disabled')

        add_log("Программа запущена")
        add_log(f"Тема: {theme_name}")

        # Кнопки
        btn_frame = tk.Frame(control_window, bg=self.colors['bg'])
        btn_frame.pack(pady=10)

        def stop():
            self.wallpaper_manager.stop_cycle()
            add_log("Цикл остановлен")
            start_btn.config(state='normal')
            stop_btn.config(state='disabled')

        def start():
            self.wallpaper_manager.start_cycle(theme, interval, use_web)
            add_log("Цикл возобновлен")
            start_btn.config(state='disabled')
            stop_btn.config(state='normal')

        start_btn = tk.Button(btn_frame, text="Запустить", command=start,
                              bg='#27ae60', fg='white', state='disabled')
        start_btn.pack(side='left', padx=5)

        stop_btn = tk.Button(btn_frame, text="Остановить", command=stop,
                             bg='#e74c3c', fg='white')
        stop_btn.pack(side='left', padx=5)

        def show_stats():
            stats = self.wallpaper_manager.get_statistics()
            msg = f"📊 Статистика:\n\nВсего изображений: {stats['total_images']}\n"
            msg += f"Средний размер: {stats['avg_file_size'] / 1024:.1f} KB\n"
            msg += f"\nИсточники:\n"
            for source, count in stats['sources_distribution']:
                msg += f"  • {source}: {count}\n"
            messagebox.showinfo("Статистика", msg)

        tk.Button(control_window, text="📊 Статистика", command=show_stats,
                  bg='#9b59b6', fg='white').pack(pady=5)

        def change_theme():
            if messagebox.askyesno("Смена темы", "Остановить текущую тему и выбрать новую?"):
                self.wallpaper_manager.stop_cycle()
                control_window.destroy()
                self.show_theme_choice()

        tk.Button(control_window, text="🎨 Сменить тему", command=change_theme,
                  bg='#f39c12', fg='white').pack(pady=5)

        def exit_app():
            if messagebox.askyesno("Выход", "Остановить смену обоев и выйти?"):
                self.wallpaper_manager.stop_cycle()
                self.wallpaper_manager.db.close()
                control_window.destroy()
                self.root.quit()

        tk.Button(control_window, text="❌ Выйти", command=exit_app,
                  bg='#c0392b', fg='white', font=("Arial", 10, "bold")).pack(pady=20)

        def on_closing():
            if messagebox.askyesno("Выход", "Остановить смену обоев и выйти?"):
                self.wallpaper_manager.stop_cycle()
                self.wallpaper_manager.db.close()
                control_window.destroy()
                self.root.quit()

        control_window.protocol("WM_DELETE_WINDOW", on_closing)

        # Обновление статуса
        def update_status():
            if control_window.winfo_exists():
                if self.wallpaper_manager.running:
                    status_label.config(
                        text=f"🟢 Обои активны\nТема: {theme_name}\nВремя: {datetime.now().strftime('%H:%M:%S')}")
                else:
                    status_label.config(text=f"🔴 Обои остановлены\nТема: {theme_name}")
                control_window.after(1000, update_status)

        update_status()

def main():
        """Главная функция запуска приложения"""
        try:
            # Создаем и запускаем GUI приложение
            root = tk.Tk()

            # Центрируем окно на экране
            root.update_idletasks()
            width = 500
            height = 600
            x = (root.winfo_screenwidth() // 2) - (width // 2)
            y = (root.winfo_screenheight() // 2) - (height // 2)
            root.geometry(f'{width}x{height}+{x}+{y}')

            app = WallpaperApp(root)

            # Запускаем главный цикл
            root.mainloop()

        except KeyboardInterrupt:
            print("\nПрограмма остановлена пользователем")
        except Exception as e:
            print(f"КРИТИЧЕСКАЯ ОШИБКА: {e}", file=sys.stderr)
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
        main()