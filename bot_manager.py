import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import subprocess
import os
import psutil
import sys
from bot import get_database_instance
from achievements import get_achievement_instance
import time

def configure_styles():
    """Настройка стилей для виджетов"""
    style = ttk.Style()
    style.configure("Accent.TButton", foreground="white", background="#5cb85c")  # Зеленый цвет
    style.map("Accent.TButton",
              foreground=[('pressed', 'white'), ('active', 'white')],
              background=[('pressed', '#449d44'), ('active', '#449d44')])
    
    # Стиль для черных кнопок
    style.configure("Black.TButton", 
                  foreground='black',
                  background='white',
                  bordercolor='black',
                  borderwidth=2)
    style.map("Black.TButton",
            foreground=[('active', 'black'), ('pressed', 'black')],
            background=[('active', '#f0f0f0'), ('pressed', '#e0e0f0')])

class UserManagerWindow:
    def __init__(self, parent, bot_db, bot_manager=None):
        self.parent = parent
        self.bot_db = bot_db
        self.bot_manager = bot_manager
            
        self.achievement_system = get_achievement_instance()
        self.last_update_time = 0
        
        self.window = tk.Toplevel(parent)
        self.window.title("Список привязанных пользователей")
        self.window.geometry("800x500")
        
        # Стиль для кнопок
        style = ttk.Style()
        style.configure('Black.TButton', 
                      foreground='black',
                      background='white',
                      bordercolor='black',
                      borderwidth=2)
        style.map('Black.TButton',
                foreground=[('active', 'black'), ('pressed', 'black')],
                background=[('active', '#f0f0f0'), ('pressed', '#e0e0e0')])
        
        # Основной фрейм
        main_frame = ttk.Frame(self.window)
        main_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        # Таблица пользователей
        columns = ("TG ID", "Имя", "Вод. Удоств.")
        self.tree = ttk.Treeview(main_frame, columns=columns, show="headings", height=20)
        
        # Настройка колонок
        self.tree.heading("TG ID", text="TG ID", anchor="center")
        self.tree.heading("Имя", text="Имя", anchor="center")
        self.tree.heading("Вод. Удоств.", text="Вод. Удоств.", anchor="center")
        
        # Ширина колонок
        self.tree.column("TG ID", width=150, anchor="center")
        self.tree.column("Имя", width=300, anchor="center")
        self.tree.column("Вод. Удоств.", width=200, anchor="center")
        
        # Прокрутка
        scrollbar = ttk.Scrollbar(main_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        
        self.tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # Фрейм для кнопок
        button_frame = ttk.Frame(self.window)
        button_frame.pack(fill="x", pady=10, padx=10)
        
        # Кнопка обновить (теперь работает)
        self.refresh_btn = ttk.Button(
            button_frame, 
            text="Обновить список", 
            command=self.reload_users,  # Изменено на reload_users
            style='Black.TButton'
        )
        self.refresh_btn.pack(side="left", padx=5, ipadx=10, ipady=5)
        
        # Кнопка отсоединить
        self.unlink_btn = ttk.Button(
            button_frame,
            text="Отсоединить выбранного",
            command=self.unlink_selected,
            style='Black.TButton'
        )
        self.unlink_btn.pack(side="left", padx=5, ipadx=10, ipady=5)
        
        # Кнопка закрыть
        close_btn = ttk.Button(
            button_frame,
            text="Закрыть",
            command=self.close_window,
            style='Black.TButton'
        )
        close_btn.pack(side="right", padx=5, ipadx=10, ipady=5)
        
        # Контекстное меню
        self.context_menu = tk.Menu(self.window, tearoff=0)
        self.context_menu.add_command(
            label="Отсоединить пользователя",
            command=self.unlink_selected,
            foreground="black"
        )
        self.tree.bind("<Button-3>", self.show_context_menu)
        
        self.achievements_btn = ttk.Button(
            button_frame,
            text="Достижения",
            command=self.show_achievements,
            style='Black.TButton'
        )
        self.achievements_btn.pack(side="left", padx=5, ipadx=10, ipady=5)
        
        # Загружаем данные
        self.load_users()
        
    def close_window(self):
        """Закрывает окно и восстанавливает главное"""
        if hasattr(self, 'bot_manager') and self.bot_manager:  # Двойная проверка
            self.bot_manager.on_child_close(self.window)
        else:
            self.window.destroy()
    
    def reload_users(self):
        """Полностью перезагружает данные из базы"""
        self.bot_db.load_links()  # Принудительно перезагружаем данные
        self.load_users()
    
    def load_users(self):
        """Загружает привязанных пользователей"""
        self.tree.delete(*self.tree.get_children())
        
        # Получаем свежие данные
        linked_users = self.bot_db.get_linked_users()
        
        for tg_id, data in linked_users.items():
            # Проверяем что данные существуют
            if 'driver_data' in data and 'Имя' in data['driver_data']:
                self.tree.insert("", "end", values=(
                    tg_id,
                    data['driver_data']['Имя'],
                    data.get('license', '')
                ))
            else:
                # Если данные повреждены, удаляем запись
                self.bot_db.unlink_user(tg_id)
    
    def show_context_menu(self, event):
        """Показывает контекстное меню"""
        item = self.tree.identify_row(event.y)
        if item:
            self.tree.selection_set(item)
            self.context_menu.post(event.x_root, event.y_root)
    
    def unlink_selected(self):
        """Отсоединяет выбранного пользователя"""
        selected = self.tree.selection()
        if not selected:
            messagebox.showwarning("Внимание", "Выберите пользователя")
            return
            
        tg_id = int(self.tree.item(selected[0])['values'][0])
        if self.bot_db.unlink_user(tg_id):
            messagebox.showinfo("Успех", "Пользователь отсоединен")
            self.reload_users()  # Используем reload_users вместо load_users
        else:
            messagebox.showerror("Ошибка", "Не удалось отсоединить пользователя")
    
    def show_achievements(self):
        # Проверяем, нужно ли обновить данные (каждые 5 секунд)
        current_time = time.time()
        if current_time - self.last_update_time > 5:
            self.achievement_system.load_data()
            self.last_update_time = current_time
            
        selected = self.tree.selection()
        if not selected:
            messagebox.showwarning("Внимание", "Выберите пользователя")
            return
            
        tg_id = int(self.tree.item(selected[0])['values'][0])
        achievement_system = get_achievement_instance()
        
        # Принудительно обновляем данные перед показом
        achievement_system.load_data()
        
        achievements = achievement_system.get_all_achievements_info(tg_id)
        
        win = tk.Toplevel(self.window)
        win.title(f"Достижения пользователя {tg_id}")
        win.geometry("600x500")
        
        main_frame = ttk.Frame(win)
        main_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        if not achievements:
            label = ttk.Label(main_frame, text="У пользователя нет достижений")
            label.pack(pady=20)
        else:
            # Таблица достижений
            columns = ("Статус", "Достижение", "Описание")
            tree = ttk.Treeview(main_frame, columns=columns, show="headings", height=20)
            
            tree.heading("Статус", text="Статус", anchor="center")
            tree.heading("Достижение", text="Достижение", anchor="center")
            tree.heading("Описание", text="Описание", anchor="center")
            
            tree.column("Статус", width=100, anchor="center")
            tree.column("Достижение", width=200, anchor="center")
            tree.column("Описание", width=300, anchor="center")
            
            for ach in achievements:
                status = "✅" if ach['achieved'] else "❌"
                tree.insert("", "end", values=(
                    status,
                    f"{ach['icon']} {ach['title']}",
                    ach['description']
                ))
                
            
            scrollbar = ttk.Scrollbar(main_frame, orient="vertical", command=tree.yview)
            tree.configure(yscrollcommand=scrollbar.set)
            
            tree.pack(side="left", fill="both", expand=True)
            scrollbar.pack(side="right", fill="y")
            
            # Добавляем кнопку обновления
        refresh_btn = ttk.Button(
            win,
            text="Обновить",
            command=lambda: self.refresh_achievements(tree)
        )
        refresh_btn.pack(pady=5)
    
    def refresh_achievements(self, tree):
        """Обновляет список достижений"""
        selected = self.tree.selection()
        if not selected:
            return
            
        tg_id = int(self.tree.item(selected[0])['values'][0])
        self.achievement_system.load_data()
        achievements = self.achievement_system.get_all_achievements_info(tg_id)
        
        # Очищаем и обновляем таблицу
        tree.delete(*tree.get_children())
        for ach in achievements:
            status = "✅" if ach['achieved'] else "❌"
            tree.insert("", "end", values=(
                status,
                f"{ach['icon']} {ach['title']}",
                ach['description']
            ))

class BotManager:
    def __init__(self, root):
        self.root = root
        self.bot_process = None
        self.bot_script = "bot.py"
        self.log_file = "bot.log"
        self.bot_db = get_database_instance()
        
        # Иконка для окон (добавьте файл icon.ico в папку с проектом)
        try:
            self.root.iconbitmap('icon.ico')
        except:
            pass
        
        self.setup_ui()
        self.update_status()
        self.center_window(self.root)
        
        # Задержка перед первым обновлением статуса
        self.root.after(1000, self.update_status)
    
    def center_window(self, window):
        """Центрирует окно на экране с плавной анимацией"""
        window.update_idletasks()
        width = window.winfo_width()
        height = window.winfo_height()
        screen_width = window.winfo_screenwidth()
        screen_height = window.winfo_screenheight()
        
        # Плавное появление по центру
        for i in range(0, 101, 10):
            x = (screen_width - width*i//100) // 2
            y = (screen_height - height*i//100) // 2
            window.geometry(f"{width*i//100}x{height*i//100}+{x}+{y}")
            window.update()
            time.sleep(0.02)
        
        window.geometry(f"{width}x{height}+{(screen_width - width) // 2}+{(screen_height - height) // 2}")
    
    def setup_ui(self):
        """Настройка пользовательского интерфейса с улучшенным дизайном"""
        self.root.title("TaxiBot Manager")
        self.root.geometry("600x350")
        self.root.resizable(False, False)
        
        # Стили для виджетов
        style = ttk.Style()
        style.configure('TFrame', background='#f0f0f0')
        style.configure('TLabel', background='#f0f0f0', font=('Arial', 10))
        style.configure('TButton', font=('Arial', 10, 'bold'), padding=5)  # Добавлен жирный шрифт
        
        # Главный фрейм
        main_frame = ttk.Frame(self.root)
        main_frame.pack(fill='both', expand=True, padx=10, pady=10)
        
        # Фрейм статуса с иконкой
        self.status_frame = ttk.LabelFrame(main_frame, text=" Статус бота ", padding=10)
        self.status_frame.pack(fill='x', pady=(0, 15))
        
        status_content = ttk.Frame(self.status_frame)
        status_content.pack(fill='x')
        
        # Иконка статуса
        self.status_icon = ttk.Label(status_content, text="", font=('Arial', 14))
        self.status_icon.pack(side='left', padx=(0, 10))
        
        # Текст статуса
        self.status_label = ttk.Label(status_content, text="Проверка состояния...", font=('Arial', 10))
        self.status_label.pack(side='left')
        
        # Фрейм с кнопками управления
        control_frame = ttk.Frame(main_frame)
        control_frame.pack(fill='x', pady=5)
        
        # Создаем кнопки как атрибуты класса
        self.start_btn = tk.Button(
            control_frame,
            text="Запустить бота",
            command=self.start_bot,
            bg="#5cb85c",
            fg='white',
            activebackground="#449d44",
            activeforeground='white',
            relief='flat',
            font=('Arial', 10, 'bold'),  # Жирный шрифт
            padx=10,
            pady=8,
            bd=0
        )
        self.start_btn.grid(row=0, column=0, padx=5, pady=5, sticky='nsew')
        
        self.stop_btn = tk.Button(
            control_frame,
            text="Остановить бот",
            command=self.stop_bot,
            bg="#d9534f",
            fg='white',  # Белый текст
            activebackground="#c9302c",
            activeforeground='white',  # Белый текст при нажатии
            relief='flat',
            font=('Arial', 10, 'bold'),  # Жирный шрифт
            padx=10,
            pady=8,
            bd=0
        )
        self.stop_btn.grid(row=0, column=1, padx=5, pady=5, sticky='nsew')
        
        users_btn = tk.Button(
            control_frame,
            text="Управление пользователями",
            command=self.show_users_window,
            bg="#337ab7",
            fg='white',
            activebackground="#286090",
            activeforeground='white',
            relief='flat',
            font=('Arial', 10, 'bold'),  # Жирный шрифт
            padx=10,
            pady=8,
            bd=0
        )
        users_btn.grid(row=1, column=0, padx=5, pady=5, sticky='nsew')
        
        settings_btn = tk.Button(
            control_frame,
            text="Настройки системы",
            command=self.show_settings,
            bg="#5bc0de",
            fg='white',
            activebackground="#46b8da",
            activeforeground='white',
            relief='flat',
            font=('Arial', 10, 'bold'),  # Жирный шрифт
            padx=10,
            pady=8,
            bd=0
        )
        settings_btn.grid(row=1, column=1, padx=5, pady=5, sticky='nsew')
        
        # Настройка веса колонок
        control_frame.grid_columnconfigure(0, weight=1)
        control_frame.grid_columnconfigure(1, weight=1)
        
        # Нижняя панель
        bottom_frame = ttk.Frame(main_frame)
        bottom_frame.pack(fill='x', pady=(10, 0))
        
        # Кнопка выхода
        self.exit_btn = ttk.Button(
            bottom_frame,
            text="Выход",
            command=self.on_close,
            style='Black.TButton'
        )
        self.exit_btn.pack(side='right', padx=5)
        
        # Информация о версии
        version_label = ttk.Label(
            bottom_frame,
            text="TaxiBot Manager v1.0",
            foreground='gray'
        )
        version_label.pack(side='left')
        
        self.update_buttons()
    
    def show_settings(self):
        """Улучшенное окно настроек с валидацией"""
        self.root.withdraw()
        
        settings_win = tk.Toplevel(self.root)
        settings_win.title("Настройки системы")
        settings_win.geometry("600x400")
        settings_win.resizable(False, False)
        
        try:
            settings_win.iconbitmap('icon.ico')
        except:
            pass
        
        self.center_window(settings_win)
        settings_win.protocol("WM_DELETE_WINDOW", lambda: self.on_child_close(settings_win))
        
        # Notebook с вкладками
        notebook = ttk.Notebook(settings_win)
        notebook.pack(fill='both', expand=True, padx=10, pady=10)
        
        # Вкладка основных настроек
        main_frame = ttk.Frame(notebook)
        notebook.add(main_frame, text="Основные")
        
        # Путь к Excel
        excel_frame = ttk.LabelFrame(main_frame, text=" Настройки Excel ", padding=10)
        excel_frame.pack(fill='x', pady=5)
        
        ttk.Label(excel_frame, text="Путь к файлу данных:").pack(anchor='w')
        
        excel_row = ttk.Frame(excel_frame)
        excel_row.pack(fill='x', pady=5)
        
        self.excel_path_var = tk.StringVar(value=os.getenv("EXCEL_PATH", ""))
        excel_entry = ttk.Entry(
            excel_row,
            textvariable=self.excel_path_var,
            width=50,
            font=('Arial', 9)
        )
        excel_entry.pack(side='left', fill='x', expand=True, padx=(0, 5))
        
        browse_btn = ttk.Button(
            excel_row,
            text="Обзор...",
            command=lambda: self.browse_excel_file(excel_entry),
            style='Black.TButton'
        )
        browse_btn.pack(side='right')
        
        # Токен бота
        token_frame = ttk.LabelFrame(main_frame, text=" Настройки бота ", padding=10)
        token_frame.pack(fill='x', pady=5)
        
        ttk.Label(token_frame, text="Токен Telegram бота:").pack(anchor='w')
        
        self.token_var = tk.StringVar(value=os.getenv("TELEGRAM_BOT_TOKEN", ""))
        token_entry = ttk.Entry(
            token_frame,
            textvariable=self.token_var,
            width=50,
            font=('Arial', 9),
            show="*"  # Скрываем ввод токена
        )
        token_entry.pack(fill='x', pady=5)
        
        # Чекбокс для показа/скрытия токена
        show_token = tk.IntVar()
        ttk.Checkbutton(
            token_frame,
            text="Показать токен",
            variable=show_token,
            command=lambda: token_entry.config(show="" if show_token.get() else "*")
        ).pack(anchor='w')
        
        # Вкладка логов
        log_frame = ttk.Frame(notebook)
        notebook.add(log_frame, text="Логи и диагностика")
        
        log_content = ttk.Frame(log_frame)
        log_content.pack(fill='both', expand=True, padx=10, pady=10)
        
        # Кнопка просмотра логов
        log_btn = ttk.Button(
            log_content,
            text="Открыть файл логов",
            command=self.open_logs,
            style='Black.TButton'
        )
        log_btn.pack(pady=10)
        
        # Информация о системе
        sys_info = ttk.LabelFrame(log_content, text=" Информация о системе ", padding=10)
        sys_info.pack(fill='x', pady=10)
        
        # Добавляем системную информацию
        info_labels = [
            f"ОС: {os.name}",
            f"Python: {sys.version.split()[0]}",
            f"Путь к боту: {os.path.abspath(self.bot_script)}",
            f"Размер лог-файла: {self.get_log_size()}"
        ]
        
        for text in info_labels:
            ttk.Label(sys_info, text=text).pack(anchor='w', pady=2)
        
        # Кнопки сохранения/отмены
        btn_frame = ttk.Frame(settings_win)
        btn_frame.pack(fill='x', pady=10, padx=10)
        
        save_btn = tk.Button(
            btn_frame,
            text="Сохранить настройки",
            command=lambda: self.save_settings(settings_win),
            bg="#5cb85c",  # Зеленый фон
            fg='black',    # Черный текст
            activebackground="#449d44",
            activeforeground='black',
            relief='flat',
            font=('Arial', 10, 'bold'),
            padx=10,
            pady=5,
            bd=0
        )
        save_btn.pack(side='left', expand=True, padx=5)
        
        cancel_btn = tk.Button(
            btn_frame,
            text="Отмена",
            command=lambda: self.on_child_close(settings_win),
            bg="#cccccc",  # Серый фон
            fg='black',    # Черный текст
            activebackground="#aaaaaa",  # Темнее серый при нажатии
            activeforeground='black',
            relief='flat',
            font=('Arial', 10, 'bold'),
            padx=10,
            pady=5,
            bd=0
        )
        cancel_btn.pack(side='right', expand=True, padx=5)
    
    def get_log_size(self):
        """Возвращает размер лог-файла в удобочитаемом формате"""
        if os.path.exists(self.log_file):
            size = os.path.getsize(self.log_file)
            for unit in ['B', 'KB', 'MB', 'GB']:
                if size < 1024:
                    return f"{size:.2f} {unit}"
                size /= 1024
        return "Файл не найден"
    
    def save_settings(self, window):
        """Улучшенное сохранение настроек с проверками"""
        excel_path = self.excel_path_var.get().strip()
        bot_token = self.token_var.get().strip()
        
        # Валидация данных
        errors = []
        if not excel_path:
            errors.append("Не указан путь к Excel файлу")
        elif not os.path.exists(excel_path):
            errors.append("Указанный Excel файл не существует")
        
        if not bot_token:
            errors.append("Не указан токен бота")
        elif not bot_token.startswith('') or len(bot_token) < 30:  # Простая проверка формата токена
            errors.append("Токен бота выглядит некорректно")
        
        if errors:
            messagebox.showerror(
                "Ошибка в настройках",
                "Обнаружены следующие ошибки:\n\n- " + "\n- ".join(errors)
            )
            return
        
        try:
            # Обновляем путь в боте
            self.bot_db.update_excel_path(excel_path)
            
            # Читаем текущий .env файл
            env_lines = []
            if os.path.exists('.env'):
                with open('.env', 'r', encoding='utf-8') as f:
                    env_lines = f.readlines()
            
            # Обновляем параметры
            new_lines = []
            updated_excel = updated_token = False
            
            for line in env_lines:
                if line.startswith('EXCEL_PATH='):
                    new_lines.append(f'EXCEL_PATH={excel_path}\n')
                    updated_excel = True
                elif line.startswith('TELEGRAM_BOT_TOKEN='):
                    new_lines.append(f'TELEGRAM_BOT_TOKEN={bot_token}\n')
                    updated_token = True
                else:
                    new_lines.append(line)
            
            if not updated_excel:
                new_lines.append(f'EXCEL_PATH={excel_path}\n')
            if not updated_token:
                new_lines.append(f'TELEGRAM_BOT_TOKEN={bot_token}\n')
            
            # Создаем резервную копию старого файла
            if os.path.exists('.env'):
                os.rename('.env', '.env.bak')
            
            # Записываем новый файл
            with open('.env', 'w', encoding='utf-8') as f:
                f.writelines(new_lines)
            
            # Показываем уведомление с иконкой
            self.show_notification(
                "Настройки сохранены",
                "Изменения вступят в силу после перезапуска бота",
                'info'
            )
            self.on_child_close(window)
            
        except Exception as e:
            # Восстанавливаем backup при ошибке
            if os.path.exists('.env.bak'):
                os.rename('.env.bak', '.env')
            
            messagebox.showerror(
                "Ошибка сохранения",
                f"Не удалось сохранить настройки:\n\n{str(e)}"
            )
    
    def show_notification(self, title, message, type_='info'):
        """Показывает стилизованное уведомление"""
        if type_ == 'info':
            messagebox.showinfo(title, message)
        elif type_ == 'warning':
            messagebox.showwarning(title, message)
        elif type_ == 'error':
            messagebox.showerror(title, message)
    
    def browse_excel_file(self, entry_widget):
        """Улучшенный диалог выбора файла"""
        filepath = filedialog.askopenfilename(
            title="Выберите файл данных",
            filetypes=[
                ("Excel files", "*.xlsx *.xls"),
                ("All files", "*.*")
            ],
            initialdir=os.path.dirname(self.excel_path_var.get()) if self.excel_path_var.get() else os.getcwd()
        )
        if filepath:
            self.excel_path_var.set(filepath)
    
    def show_users_window(self):
        """Открывает окно управления пользователями"""
        self.root.withdraw()
        
        user_window = UserManagerWindow(self.root, self.bot_db, self)
        self.center_window(user_window.window)
        
        user_window.window.protocol(
            "WM_DELETE_WINDOW",
            lambda: self.on_child_close(user_window.window)
        )
    
    def on_child_close(self, child_window):
        """Обработчик закрытия дочерних окон с анимацией"""
        try:
            # Плавное исчезновение окна
            for i in range(100, 0, -10):
                if not child_window.winfo_exists():  # Проверяем, существует ли еще окно
                    break
                child_window.attributes('-alpha', i/100)
                child_window.update()
                time.sleep(0.02)
        except tk.TclError:
            pass  # Окно уже было уничтожено
        
        if child_window.winfo_exists():
            child_window.destroy()
        
        self.root.deiconify()
        self.center_window(self.root)
        self.root.attributes('-alpha', 1.0)
    
    def is_bot_running(self):
        """Проверяет, работает ли бот"""
        if self.bot_process is None:
            return False
        return self.bot_process.poll() is None
    
    def start_bot(self):
        """Запускает бота с улучшенным интерфейсом"""
        if not self.is_bot_running():
            try:
                # Показываем индикатор загрузки
                self.status_label.config(text="Запуск бота...")
                self.status_icon.config(text="⏳")
                self.root.update()
                
                self.bot_process = subprocess.Popen(
                    ["python", self.bot_script],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE
                )
                
                # Даем время на инициализацию
                self.root.after(1000, lambda: self.show_notification(
                    "Бот запущен",
                    "Telegram бот успешно запущен",
                    'info'
                ))
                
            except Exception as e:
                self.show_notification(
                    "Ошибка запуска",
                    f"Не удалось запустить бота:\n\n{str(e)}",
                    'error'
                )
        else:
            self.show_notification(
                "Бот уже работает",
                "Telegram бот уже запущен",
                'warning'
            )
        
        self.update_status()
    
    def stop_bot(self):
        """Останавливает бота с подтверждением"""
        if self.is_bot_running():
            if messagebox.askyesno(
                "Подтверждение",
                "Вы уверены, что хотите остановить бота?",
                icon='warning'
            ):
                try:
                    # Показываем индикатор
                    self.status_label.config(text="Остановка бота...")
                    self.status_icon.config(text="⏳")
                    self.root.update()
                    
                    for proc in psutil.process_iter():
                        if proc.name() == "python.exe" and self.bot_script in " ".join(proc.cmdline()):
                            proc.terminate()
                    
                    self.bot_process = None
                    self.show_notification(
                        "Бот остановлен",
                        "Telegram бот успешно остановлен",
                        'info'
                    )
                    
                except Exception as e:
                    self.show_notification(
                        "Ошибка остановки",
                        f"Не удалось остановить бота:\n\n{str(e)}",
                        'error'
                    )
        else:
            self.show_notification(
                "Бот не запущен",
                "Telegram бот в настоящее время не работает",
                'warning'
            )
        
        self.update_status()
    
    def open_logs(self):
        """Открывает файл логов с проверкой"""
        if os.path.exists(self.log_file):
            try:
                if os.name == 'nt':  # Windows
                    os.startfile(self.log_file)
                else:  # MacOS, Linux
                    subprocess.run(['xdg-open', self.log_file])
            except Exception as e:
                self.show_notification(
                    "Ошибка открытия",
                    f"Не удалось открыть файл логов:\n\n{str(e)}",
                    'error'
                )
        else:
            self.show_notification(
                "Файл не найден",
                "Лог-файл не найден. Возможно, бот еще не запускался.",
                'warning'
            )
    
    def update_status(self):
        """Обновляет статус с иконками"""
        if self.is_bot_running():
            self.status_label.config(text="Статус: Работает", foreground="green")
            self.status_icon.config(text="🟢")
        else:
            self.status_label.config(text="Статус: Остановлен", foreground="red")
            self.status_icon.config(text="🔴")
        
        self.update_buttons()
        self.root.after(2000, self.update_status)
    
    def update_buttons(self):
        """Обновляет состояние кнопок"""
        running = self.is_bot_running()
        self.start_btn.config(state='disabled' if running else 'normal')
        self.stop_btn.config(state='normal' if running else 'disabled')
    
    def on_close(self):
        """Обработчик закрытия главного окна"""
        if self.is_bot_running():
            if messagebox.askyesno(
                "Подтверждение",
                "Бот все еще работает. Вы уверены, что хотите выйти?",
                icon='warning'
            ):
                self.stop_bot()
                self.root.destroy()
        else:
            self.root.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    configure_styles()
    app = BotManager(root)
    root.protocol("WM_DELETE_WINDOW", app.on_close)
    root.mainloop()