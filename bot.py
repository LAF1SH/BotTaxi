from telegram import Update, BotCommandScopeChat, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
    ConversationHandler
)
import logging
from logging.handlers import RotatingFileHandler
import pandas as pd
import json
import os
import asyncio
from datetime import datetime, timedelta
from dotenv import load_dotenv
from pathlib import Path
from achievements import get_achievement_instance

async def remove_keyboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Удаляет клавиатуру из предыдущего сообщения"""
    if 'keyboard_active' in context.user_data and context.user_data['keyboard_active']:
        await update.message.reply_text(
            "Убираю клавиатуру...",
            reply_markup=ReplyKeyboardRemove()
        )
        # Удаляем сообщение "Убираю клавиатуру..." через 1 секунду
        await asyncio.sleep(1)
        await context.bot.delete_message(
            chat_id=update.effective_chat.id,
            message_id=update.message.message_id + 1
        )
        context.user_data['keyboard_active'] = False

# Настройка логирования (должна быть в самом начале)
log_handler = RotatingFileHandler('bot.log', maxBytes=1024*1024, backupCount=3)
log_handler.setFormatter(logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
))
logger = logging.getLogger(__name__)
logger.addHandler(log_handler)
logger.setLevel(logging.INFO)

# Загрузка .env файла
env_path = Path(__file__).parent / '.env'
if not env_path.exists():
    logger.error(f"Файл .env не найден по пути: {env_path}")
    raise FileNotFoundError(f"Файл .env не найден по пути: {env_path}")

try:
    # Просто передаем путь к файлу
    load_dotenv(env_path)
    logger.info(".env файл успешно загружен")
except Exception as e:
    logger.error(f"Ошибка загрузки .env файла: {str(e)}")
    raise

# Получение переменных окружения
EXCEL_PATH = os.getenv("EXCEL_PATH")
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

if not TOKEN or not EXCEL_PATH:
    logger.error("Не заданы TOKEN или EXCEL_PATH в .env файле!")
    raise ValueError("Не заданы TOKEN или EXCEL_PATH в .env файле!")

class DriverDatabase:
    def __init__(self):
        self.last_modified = 0
        self.top_cache = None
        self.cache_time = None
        self.data = pd.DataFrame(columns=['ID', 'Имя', 'Вод. Удоств.', 'Часы', 'ЗП'])
        self.linked_users: Dict[int, Dict[str, Any]] = {}  # {tg_id: {license, name, driver_data}}
        self.storage_file = "driver_links.json"
        self.load_data()
        self.load_links()
        
    async def periodic_data_update(self, interval: int = 60):
        """Периодическое обновление данных из Excel"""
        while True:
            try:
                old_data = self.data.copy()
                self.load_data()
                
                # Обновляем данные для привязанных пользователей
                for user_id, user_data in self.linked_users.items():
                    license_number = user_data['license']
                    driver = self.find_driver_by_license(license_number)
                    if driver is not None:
                        self.linked_users[user_id]['driver_data'] = driver.to_dict()
                
                # Логируем изменения, если они есть
                if not self.data.equals(old_data):
                    logger.info("Данные из Excel успешно обновлены")
                    self.save_links()  # Сохраняем обновленные данные
                    
            except Exception as e:
                logger.error(f"Ошибка при периодическом обновлении данных: {e}")
            
            await asyncio.sleep(interval)

    def load_data(self):
        try:
            mod_time = os.path.getmtime(EXCEL_PATH)
            if mod_time != self.last_modified:
                # Читаем Excel файл
                new_data = pd.read_excel(EXCEL_PATH)
                
                # Проверяем обязательные столбцы
                required_columns = ['Имя', 'Часы', 'ЗП']
                for col in required_columns:
                    if col not in new_data.columns:
                        raise ValueError(f"Отсутствует обязательный столбец: {col}")
                
                # Преобразуем типы данных
                new_data['Часы'] = pd.to_numeric(new_data['Часы'], errors='coerce')
                new_data['ЗП'] = pd.to_numeric(new_data['ЗП'], errors='coerce')
                
                # Удаляем строки с пустыми значениями
                new_data = new_data.dropna(subset=['Имя', 'Часы', 'ЗП'])
                
                self.data = new_data
                self.last_modified = mod_time
                logger.info("Данные успешно загружены. Записей: %d", len(self.data))
                
                # Сбрасываем кэш топа
                self.top_cache = None
                
        except Exception as e:
            logger.error(f"Ошибка загрузки данных: {str(e)}", exc_info=True)
            self.data = pd.DataFrame(columns=['ID', 'Имя', 'Вод. Удоств.', 'Часы', 'ЗП'])
    
    def get_linked_users(self):
        """Возвращает копию текущих привязок"""
        return self.linked_users.copy()

    def load_links(self):
        """Загружает привязки из файла"""
        self.linked_users = {}  # Очищаем текущие данные
        if os.path.exists(self.storage_file):
            try:
                with open(self.storage_file, 'r', encoding='utf-8') as f:
                    saved_links = json.load(f)
                    for tg_id, link_data in saved_links.items():
                        driver = self.find_driver_by_license(link_data['license'])
                        if driver is not None:
                            self.linked_users[int(tg_id)] = {
                                'license': link_data['license'],
                                'name': link_data['name'],
                                'driver_data': driver.to_dict()
                            }
                        else:
                            # Если водитель не найден, удаляем привязку
                            continue
            except Exception as e:
                logger.error(f"Ошибка загрузки привязок: {e}")

    def save_links(self):
        """Сохраняет текущие привязки в файл"""
        try:
            # Подготовка данных для сохранения (только essentials)
            save_data = {
                str(tg_id): {
                    'license': data['license'],
                    'name': data['name']
                }
                for tg_id, data in self.linked_users.items()
            }
            with open(self.storage_file, 'w', encoding='utf-8') as f:
                json.dump(save_data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Ошибка сохранения привязок: {e}")

    def find_driver_by_license(self, license_number):
        """Поиск водителя по номеру удостоверения"""
        try:
            license_number = str(license_number).strip()
            driver = self.data[self.data['Вод. Удоств.'] == license_number]
            return driver.iloc[0] if not driver.empty else None
        except Exception as e:
            logger.error(f"Ошибка поиска водителя: {e}")
            return None

    def link_user(self, user_id, name, license_number):
        """Привязывает пользователя к удостоверению"""
        try:
            # Проверяем, не привязан ли уже этот TG ID
            if user_id in self.linked_users:
                return False, "Этот Telegram ID уже привязан"
                
            # Проверяем, не привязано ли уже это удостоверение
            if any(data['license'] == license_number for data in self.linked_users.values()):
                return False, "Это удостоверение уже привязано к другому пользователю"
                
            # Проверяем существование удостоверения
            driver = self.find_driver_by_license(license_number)
            if driver is None:
                return False, "Удостоверение не найдено"
            
            # Сохраняем привязку (используем имя из Excel)
            self.linked_users[user_id] = {
                'license': license_number,
                'name': driver['Имя'],  # Берем имя из Excel
                'driver_data': driver.to_dict()
            }
            
            self.save_links()
            logger.info(f"Пользователь {user_id} связан с удостоверением {license_number}")
            return True, "Успешная привязка"
            
        except Exception as e:
            logger.error(f"Ошибка привязки пользователя: {e}")
            return False, "Ошибка привязки"

    def unlink_user(self, user_id):
        """Отсоединяет пользователя"""
        try:
            if user_id in self.linked_users:
                del self.linked_users[user_id]
                self.save_links()
                logger.info(f"Пользователь {user_id} отсоединен")
                return True
            return False
        except Exception as e:
            logger.error(f"Ошибка при отсоединении пользователя: {e}")
            return False

    def get_linked_users(self):
        """Возвращает список привязанных пользователей"""
        return self.linked_users
    
    def get_top_drivers(self):
        """Возвращает топ-5 водителей с кэшированием"""
        try:
            now = datetime.now()
            
            # Принудительно обновляем данные, если кэш пустой или устарел
            if self.top_cache is None or (now - self.cache_time) > timedelta(minutes=1):
                self.load_data()  # Перезагружаем данные из Excel
                
                # Проверяем, что данные загружены корректно
                if self.data.empty:
                    logger.error("Данные не загружены или DataFrame пуст")
                    return pd.DataFrame()  # Возвращаем пустой DataFrame
                
                # Сортируем и кэшируем топ-5
                self.top_cache = self.data.sort_values('ЗП', ascending=False).head(5)
                self.cache_time = now
                logger.info("Кэш топа водителей обновлен")
            
            # Возвращаем копию кэша
            return self.top_cache.copy()
            
        except Exception as e:
            logger.error(f"Критическая ошибка при получении топа: {str(e)}", exc_info=True)
            return pd.DataFrame()  # Возвращаем пустой DataFrame при ошибке
    
    def find_driver_in_top(self, license_number):
        top = self.get_top_drivers()
        if top.empty:
            return False
        return license_number in top['Вод. Удоств.'].values
    
    def update_excel_path(self, new_path):
        """Обновляет путь к Excel файлу"""
        global EXCEL_PATH
        EXCEL_PATH = new_path
        self.last_modified = 0  # Сбрасываем время модификации для принудительной перезагрузки
        self.load_data()  # Перезагружаем данные

db = DriverDatabase()

async def post_init(application: Application):
    """Функция, которая выполняется после инициализации бота"""
    # Запускаем фоновую задачу для обновления данных
    asyncio.create_task(db.periodic_data_update(60))

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if user.id in db.linked_users:
        # Пользователь уже авторизован
        await update.message.reply_text(
            "Вы уже авторизованы!\n"
            "Используйте команды:\n"
            "/stats - ваша статистика\n"
            "/top - топ водителей"
        )
        return ConversationHandler.END
    else:
        # Пользователь не авторизован
        await update.message.reply_text(
            f"Привет, {user.full_name}! 👋\n"
            "Введите номер вашего водительского удостоверения:"
        )
        return 1  # Состояние ожидания номера прав

async def handle_license(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    license_number = update.message.text.strip()
    
    success, message = db.link_user(user.id, user.full_name, license_number)
    
    if success:
        # Обновляем меню команд для пользователя
        await context.bot.set_my_commands(
            commands=[
                ("stats", "Ваша статистика"),
                ("top", "Топ водителей")
            ],
            scope=BotCommandScopeChat(user.id)
        )
        
        await update.message.reply_text(
            "✅ Вы успешно авторизованы!\n"
            f"Номер удостоверения: {license_number}\n\n"
            "Используйте команды:\n"
            "/stats - ваша статистика\n"
            "/top - топ водителей"
        )
    else:
        await update.message.reply_text(
            f"❌ Ошибка: {message}\n"
            "Обратитесь к администратору для решения проблемы."
        )
    
    return ConversationHandler.END

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает статистику пользователя с достижениями"""
    user = update.effective_user
    
    # Проверка авторизации пользователя
    if user.id not in db.linked_users:
        await context.bot.set_my_commands(
            commands=[("start", "Начать авторизацию")],
            scope=BotCommandScopeChat(user.id)
        )
        await update.message.reply_text(
            "❌ Вы не авторизованы.\n"
            "Нажмите /start для ввода номера удостоверения."
        )
        return
    
    try:
        # Получаем данные водителя
        driver_data = db.linked_users[user.id]['driver_data']
        driver_data['is_in_top'] = db.find_driver_in_top(driver_data['Вод. Удоств.'])
        
        # Проверяем новые достижения
        achievement_system = get_achievement_instance()
        new_achievements = achievement_system.check_achievements(user.id, driver_data)
        
        # Формируем основное сообщение
        response = (
            "📊 <b>Ваша статистика</b>:\n\n"
            f"👤 <b>Имя</b>: {driver_data['Имя']}\n"
            f"📜 <b>Вод. удостоверение</b>: {driver_data['Вод. Удоств.']}\n"
            f"⏱ <b>Часы работы</b>: {driver_data['Часы']}\n"
            f"💰 <b>Зарплата</b>: {driver_data['ЗП']} руб.\n\n"
            "🏆 <b>Достижения</b>: "
            f"{len(achievement_system.get_user_achievements(user.id))} из {len(achievement_system.available_achievements)}"
        )
        
        # Создаем клавиатуру с кнопкой
        keyboard = [["Показать все достижения"]]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)
        
        # Сохраняем состояние клавиатуры
        context.user_data['keyboard_active'] = True
        
        await update.message.reply_text(
            response,
            parse_mode='HTML',
            reply_markup=reply_markup
        )
        
        # Уведомления о новых достижениях
        if new_achievements:
            for achievement in new_achievements:
                await update.message.reply_text(
                    f"🎉 <b>Новое достижение!</b> 🎉\n\n"
                    f"{achievement_system.format_achievement(achievement)}",
                    parse_mode='HTML'
                )
                
    except Exception as e:
        logger.error(f"Ошибка получения статистики: {e}", exc_info=True)
        # Не отсоединяем пользователя при ошибке, только сообщаем
        await update.message.reply_text(
            "⚠️ Временные проблемы с получением статистики.\n"
            "Попробуйте позже или обратитесь к администратору."
        )
                
    except Exception as e:
        logger.error(f"Ошибка получения статистики: {e}")
        db.unlink_user(user.id)
        await context.bot.set_my_commands(
            commands=[("start", "Начать авторизацию")],
            scope=BotCommandScopeChat(user.id)
        )
        await update.message.reply_text(
            "⚠️ Произошла ошибка при получении статистики.\n"
            "Пожалуйста, авторизуйтесь снова с помощью /start"
        )

async def achievements(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if user.id not in db.linked_users:
        await update.message.reply_text(
            "❌ Вы не авторизованы.\n"
            "Нажмите /start для ввода номера удостоверения."
        )
        return
    
    achievement_system = get_achievement_instance()
    user_achievements = achievement_system.get_user_achievements(user.id)
    message = achievement_system.format_achievements_list(user_achievements)
    await update.message.reply_text(message, parse_mode='HTML')
    
async def all_achievements(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает все возможные достижения"""
    # Скрываем клавиатуру после использования
    if context.user_data.get('keyboard_active', False):
        context.user_data['keyboard_active'] = False
    
    user = update.effective_user
    achievement_system = get_achievement_instance()
    
    achievements = achievement_system.get_all_achievements_info(user.id if user.id in db.linked_users else None)
    
    message = "🏆 <b>Все возможные достижения</b>:\n\n"
    for ach in achievements:
        status = "✅" if ach.get('achieved', False) else "◻️"
        message += (
            f"{status} <b>{ach['icon']} {ach['title']}</b>\n"
            f"{ach['description']}\n\n"
        )
    
    message += "Продолжайте работать, чтобы получить все достижения!"
    await update.message.reply_text(message, parse_mode='HTML')

async def top_drivers(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Проверяем и скрываем клавиатуру, если она была показана
    if context.user_data.get('keyboard_active', False):
        await remove_keyboard(update, context)  # Передаём оба аргумента
        context.user_data['keyboard_active'] = False
    
    # Остальной код функции...
    try:
        logger.info("Запрос на получение топа водителей")
        top = db.get_top_drivers()
        
        if top.empty:
            await update.message.reply_text("⚠️ Нет данных о водителях. Проверьте файл Excel.")
            return
            
        response = "🏆 <b>Топ-5 водителей по зарплате</b>:\n\n"
        
        for i, (_, row) in enumerate(top.iterrows(), 1):
            try:
                name = str(row['Имя']) if pd.notna(row['Имя']) else "Не указано"
                hours = str(row['Часы']) if pd.notna(row['Часы']) else "Не указано"
                salary = str(row['ЗП']) if pd.notna(row['ЗП']) else "Не указано"
                
                salary_emoji = " 🔥" if i == 1 else ""
                response += (
                    f"{i}. <b>{name}</b>\n"
                    f"   ⏱ Часы работы: {hours}\n"
                    f"   💰 Зарплата: {salary} руб.{salary_emoji}\n\n"
                )
            except Exception as row_error:
                logger.error(f"Ошибка обработки строки {i}: {row_error}")
                continue
                
        await update.message.reply_text(response, parse_mode='HTML')
        
    except Exception as e:
        logger.error(f"Фатальная ошибка при формировании топа: {str(e)}", exc_info=True)
        await update.message.reply_text("⚠️ Произошла критическая ошибка при формировании топа. Администратор уведомлен.")

def get_database_instance():
    return db

async def check_drivers_updates(context: ContextTypes.DEFAULT_TYPE):
    """Периодическая проверка обновлений данных водителей"""
    try:
        # Получаем экземпляр базы данных
        db = get_database_instance()
        
        # Сохраняем старые данные для сравнения
        old_data = db.data.copy()
        
        # Загружаем обновленные данные
        db.load_data()
        
        # Если данные изменились, обновляем информацию о достижениях
        if not db.data.equals(old_data):
            logger.info("Данные водителей обновлены, проверяем достижения")
            
            # Проверяем достижения для всех привязанных пользователей
            achievement_system = get_achievement_instance()
            for user_id, user_data in db.linked_users.items():
                try:
                    license_number = user_data['license']
                    driver = db.find_driver_by_license(license_number)
                    if driver is not None:
                        driver_data = driver.to_dict()
                        driver_data['is_in_top'] = db.find_driver_in_top(license_number)
                        achievement_system.check_achievements(user_id, driver_data)
                except Exception as e:
                    logger.error(f"Ошибка при проверке достижений для пользователя {user_id}: {e}")
                    
    except Exception as e:
        logger.error(f"Ошибка при периодической проверке данных: {e}")
        
def main():
    application = Application.builder().token(TOKEN).post_init(post_init).build()
    
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={1: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_license)]},
        fallbacks=[]
    )
    
    application.add_handler(conv_handler)
    application.add_handler(CommandHandler('stats', stats))
    application.add_handler(CommandHandler('top', top_drivers))
    application.add_handler(CommandHandler('achievements', achievements))
    application.add_handler(CommandHandler('all_achievements', all_achievements))
    
    # Добавляем обработчик текстовых сообщений для кнопки
    application.add_handler(MessageHandler(
        filters.Text("Показать все достижения") & ~filters.COMMAND, 
        all_achievements
    ))
    
    # Добавляем обработчик для скрытия клавиатуры при других сообщениях
    application.add_handler(MessageHandler(
        filters.TEXT & ~filters.Text("Показать все достижения") & ~filters.COMMAND, 
        lambda update, context: remove_keyboard(update, context)
    ))
    
    application.job_queue.run_repeating(
        callback=check_drivers_updates,
        interval=300,
        first=10
    )
    
    application.run_polling()

if __name__ == '__main__':
    main()