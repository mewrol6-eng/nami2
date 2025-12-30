import os
import logging
import sqlite3
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ConversationHandler,
    filters
)

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Состояния для ConversationHandler
ADD_TASK, DELETE_TASK = range(2)

# Инициализация базы данных
def init_db():
    conn = sqlite3.connect('planner.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            task TEXT NOT NULL,
            date TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()

# Команда /start
async def start(update: Update, context):
    user = update.effective_user
    await update.message.reply_text(
        f"Привет, {user.first_name}! ✨\n\n"
        "Я твой личный планер-бот! Вот что я умею:\n\n"
        "📌 /add - Добавить новую задачу\n"
        "🗑️ /delete - Удалить задачу\n"
        "📋 /list - Показать все задачи\n"
        "🗓️ /today - Задачи на сегодня\n"
        "❓ /help - Помощь"
    )

# Команда /help
async def help_command(update: Update, context):
    help_text = """
📋 **Доступные команды:**

/add - Добавить новую задачу
Пример: /add Сделать домашку по математике

/delete - Удалить задачу (покажет список для выбора)

/list - Показать все задачи

/today - Задачи на сегодня

/help - Эта справка
    """
    await update.message.reply_text(help_text, parse_mode='Markdown')

# Начало добавления задачи
async def add_task_start(update: Update, context):
    await update.message.reply_text(
        "📝 Напиши свою задачу:\n"
        "Например: 'Сделать презентацию к понедельнику'\n\n"
        "Или отправь /cancel чтобы отменить"
    )
    return ADD_TASK

# Получение текста задачи
async def add_task_text(update: Update, context):
    task_text = update.message.text
    user_id = update.effective_user.id
    today_date = datetime.now().strftime('%Y-%m-%d')
    
    conn = sqlite3.connect('planner.db')
    cursor = conn.cursor()
    cursor.execute(
        'INSERT INTO tasks (user_id, task, date) VALUES (?, ?, ?)',
        (user_id, task_text, today_date)
    )
    conn.commit()
    conn.close()
    
    await update.message.reply_text(
        "✅ Задача добавлена!\n"
        f"📌 {task_text}\n"
        f"📅 Дата: {today_date}"
    )
    return ConversationHandler.END

# Показать все задачи
async def list_tasks(update: Update, context):
    user_id = update.effective_user.id
    
    conn = sqlite3.connect('planner.db')
    cursor = conn.cursor()
    cursor.execute(
        'SELECT id, task, date FROM tasks WHERE user_id = ? ORDER BY date, id',
        (user_id,)
    )
    tasks = cursor.fetchall()
    conn.close()
    
    if not tasks:
        await update.message.reply_text("📭 У тебя пока нет задач!")
        return
    
    response = "📋 **Твои задачи:**\n\n"
    for task_id, task_text, task_date in tasks:
        response += f"🆔 {task_id}\n📌 {task_text}\n📅 {task_date}\n\n"
    
    await update.message.reply_text(response, parse_mode='Markdown')

# Показать задачи на сегодня
async def today_tasks(update: Update, context):
    user_id = update.effective_user.id
    today_date = datetime.now().strftime('%Y-%m-%d')
    
    conn = sqlite3.connect('planner.db')
    cursor = conn.cursor()
    cursor.execute(
        'SELECT id, task FROM tasks WHERE user_id = ? AND date = ? ORDER BY id',
        (user_id, today_date)
    )
    tasks = cursor.fetchall()
    conn.close()
    
    if not tasks:
        await update.message.reply_text(
            f"🎉 На сегодня ({today_date}) задач нет!\n"
            "Можешь отдохнуть или добавить новые задачи 😊"
        )
        return
    
    response = f"📅 **Задачи на сегодня ({today_date}):**\n\n"
    for task_id, task_text in tasks:
        response += f"🆔 {task_id}: {task_text}\n"
    
    await update.message.reply_text(response, parse_mode='Markdown')

# Начало удаления задачи
async def delete_task_start(update: Update, context):
    user_id = update.effective_user.id
    
    conn = sqlite3.connect('planner.db')
    cursor = conn.cursor()
    cursor.execute(
        'SELECT id, task FROM tasks WHERE user_id = ? ORDER BY id',
        (user_id,)
    )
    tasks = cursor.fetchall()
    conn.close()
    
    if not tasks:
        await update.message.reply_text("📭 Нет задач для удаления!")
        return ConversationHandler.END
    
    # Создаем инлайн-клавиатуру
    keyboard = []
    for task_id, task_text in tasks:
        # Обрезаем длинный текст
        display_text = task_text[:30] + "..." if len(task_text) > 30 else task_text
        keyboard.append([InlineKeyboardButton(
            f"❌ {task_id}: {display_text}", 
            callback_data=f"delete_{task_id}"
        )])
    
    keyboard.append([InlineKeyboardButton("❎ Отмена", callback_data="cancel")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "🗑️ Выбери задачу для удаления:",
        reply_markup=reply_markup
    )
    return DELETE_TASK

# Обработка нажатия кнопок удаления
async def delete_task_button(update: Update, context):
    query = update.callback_query
    await query.answer()
    
    if query.data == "cancel":
        await query.edit_message_text("🚫 Удаление отменено")
        return ConversationHandler.END
    
    if query.data.startswith("delete_"):
        task_id = query.data.split("_")[1]
        
        conn = sqlite3.connect('planner.db')
        cursor = conn.cursor()
        
        # Получаем задачу перед удалением для информации
        cursor.execute('SELECT task FROM tasks WHERE id = ?', (task_id,))
        task = cursor.fetchone()
        
        if task:
            cursor.execute('DELETE FROM tasks WHERE id = ?', (task_id,))
            conn.commit()
            await query.edit_message_text(
                f"✅ Задача удалена:\n{task[0]}"
            )
        else:
            await query.edit_message_text("⚠️ Задача не найдена!")
        
        conn.close()
    
    return ConversationHandler.END

# Отмена
async def cancel(update: Update, context):
    await update.message.reply_text("🚫 Действие отменено")
    return ConversationHandler.END

# Основная функция
def main():
    # Получаем токен из переменных окружения
    TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
    if not TOKEN:
        logger.error("Не установлен TELEGRAM_BOT_TOKEN!")
        return
    
    # Инициализируем базу данных
    init_db()
    
    # Создаем приложение
    application = Application.builder().token(TOKEN).build()
    
    # Настраиваем ConversationHandler для добавления задач
    add_conv_handler = ConversationHandler(
        entry_points=[CommandHandler('add', add_task_start)],
        states={
            ADD_TASK: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_task_text)]
        },
        fallbacks=[CommandHandler('cancel', cancel)]
    )
    
    # Настраиваем ConversationHandler для удаления задач
    delete_conv_handler = ConversationHandler(
        entry_points=[CommandHandler('delete', delete_task_start)],
        states={
            DELETE_TASK: [CallbackQueryHandler(delete_task_button)]
        },
        fallbacks=[CommandHandler('cancel', cancel)]
    )
    
    # Добавляем обработчики команд
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("list", list_tasks))
    application.add_handler(CommandHandler("today", today_tasks))
    application.add_handler(add_conv_handler)
    application.add_handler(delete_conv_handler)
    
    # Запускаем бота
    port = int(os.environ.get('PORT', 8443))
    
    # На Render используем webhook
    if 'RENDER' in os.environ:
        webhook_url = os.getenv('RENDER_EXTERNAL_URL')
        if webhook_url:
            application.run_webhook(
                listen="0.0.0.0",
                port=port,
                url_path=TOKEN,
                webhook_url=f"{webhook_url}/{TOKEN}"
            )
        else:
            logger.error("RENDER_EXTERNAL_URL не установлен!")
    else:
        # Локально используем polling
        application.run_polling()

if __name__ == '__main__':
    main()
