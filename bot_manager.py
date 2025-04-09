import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import subprocess
import os
import psutil
from bot import get_database_instance
from achievements import get_achievement_instance
import time

def configure_styles():
    """Настройка стилей для виджетов"""
    style = ttk.Style()
    style.configure("Accent.TButton", foreground="white", background="#d9534f")
    style.map("Accent.TButton",
              foreground=[('pressed', 'white'), ('active', 'white')],
              background=[('pressed', '#c9302c'), ('active', '#c9302c')])

class UserManagerWindow:
    def __init__(self, parent, bot_db):
        self.parent = parent
        self.bot_db = bot_db
        
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
            command=self.window.destroy,
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
        
        self.setup_ui()
        self.update_status()
    
    def setup_ui(self):
        self.root.title("Управление Telegram ботом")
        self.root.geometry("400x200")
        
        style = ttk.Style()
        style.configure('TButton', font=('Arial', 10))
        style.configure('TLabel', font=('Arial', 10))
        
        self.status_frame = ttk.LabelFrame(self.root, text="Статус бота")
        self.status_frame.pack(pady=10, padx=10, fill="x")
        
        self.status_label = ttk.Label(self.status_frame, text="Проверка...")
        self.status_label.pack(pady=5)
        
        self.control_frame = ttk.Frame(self.root)
        self.control_frame.pack(pady=10)
        
        self.start_btn = ttk.Button(self.control_frame, text="Запустить", command=self.start_bot)
        self.start_btn.pack(side="left", padx=5)
        
        self.stop_btn = ttk.Button(self.control_frame, text="Остановить", command=self.stop_bot)
        self.stop_btn.pack(side="left", padx=5)
        
        self.users_btn = ttk.Button(self.control_frame, text="Пользователи", command=self.show_users_window)
        self.users_btn.pack(side="left", padx=5)
        
        self.log_btn = ttk.Button(self.control_frame, text="Логи", command=self.open_logs)
        self.log_btn.pack(side="left", padx=5)
        
        self.exit_btn = ttk.Button(self.root, text="Выход", command=self.on_close)
        self.exit_btn.pack(pady=10)
        
        self.update_buttons()
    
    def show_users_window(self):
        UserManagerWindow(self.root, self.bot_db)
    
    def is_bot_running(self):
        if self.bot_process is None:
            return False
        return self.bot_process.poll() is None
        
    def start_bot(self):
        if not self.is_bot_running():
            try:
                self.bot_process = subprocess.Popen(["python", self.bot_script])
                messagebox.showinfo("Успех", "Бот успешно запущен")
            except Exception as e:
                messagebox.showerror("Ошибка", f"Не удалось запустить бот: {str(e)}")
        else:
            messagebox.showwarning("Внимание", "Бот уже запущен")
        
        self.update_status()
        
    def stop_bot(self):
        if self.is_bot_running():
            try:
                for proc in psutil.process_iter():
                    if proc.name() == "python.exe" and self.bot_script in " ".join(proc.cmdline()):
                        proc.terminate()
                self.bot_process = None
                messagebox.showinfo("Успех", "Бот успешно остановлен")
            except Exception as e:
                messagebox.showerror("Ошибка", f"Не удалось остановить бот: {str(e)}")
        else:
            messagebox.showwarning("Внимание", "Бот не запущен")
        
        self.update_status()
        
    def open_logs(self):
        if os.path.exists(self.log_file):
            try:
                os.startfile(self.log_file)
            except:
                filedialog.askopenfilename(initialfile=self.log_file)
        else:
            messagebox.showwarning("Внимание", "Лог-файл не найден")
        
    def update_status(self):
        if self.is_bot_running():
            self.status_label.config(text="Статус: Работает", foreground="green")
        else:
            self.status_label.config(text="Статус: Остановлен", foreground="red")
        
        self.update_buttons()
        self.root.after(2000, self.update_status)
        
    def update_buttons(self):
        running = self.is_bot_running()
        self.start_btn.state(["!disabled" if not running else "disabled"])
        self.stop_btn.state(["!disabled" if running else "disabled"])
        
    def on_close(self):
        if self.is_bot_running():
            if messagebox.askyesno("Подтверждение", "Бот все еще работает. Завершить его?"):
                self.stop_bot()
        self.root.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    configure_styles()
    app = BotManager(root)
    root.protocol("WM_DELETE_WINDOW", app.on_close)
    root.mainloop()