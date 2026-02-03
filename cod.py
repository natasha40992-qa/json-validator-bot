!pip install python-telegram-bot nest_asyncio json_repair

import nest_asyncio
nest_asyncio.apply()

import json
import re
from json_repair import repair_json
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

TOKEN = "You_token_bot_telegram"

def find_error_position(text, pos):
    """Найти строку и позицию ошибки"""
    lines = text.split('\n')
    current_pos = 0
    
    for i, line in enumerate(lines):
        line_length = len(line) + 1  # +1 для символа новой строки
        if current_pos + line_length > pos:
            # Ошибка в этой строке
            col = pos - current_pos
            return i + 1, col + 1, line
        current_pos += line_length
    
    return len(lines), len(lines[-1]) + 1, lines[-1]

def highlight_error_in_line(line, col, context=30):
    """Выделить ошибку в строке с цветами"""
    start = max(0, col - context - 2)
    end = min(len(line), col + context)
    snippet = line[start:end]
    
    # Позиция ошибки в сниппете
    error_pos = col - start - 1
    
    # Создаю выделение с использованием Markdown
    if error_pos < len(snippet):
        before_error = snippet[:error_pos]
        error_char = snippet[error_pos] if error_pos < len(snippet) else ''
        after_error = snippet[error_pos + 1:] if error_pos + 1 < len(snippet) else ''
        
        return f"`{before_error}`**`{error_char}`**`{after_error}`"
    
    return f"`{snippet}`"

def suggest_fix_with_json_repair(text):
    """Исправить JSON с помощью json_repair"""
    try:
        # Пробую исправить JSON
        fixed = repair_json(text)
        
        # Проверяю, стал ли он валидным
        json.loads(fixed)
        
        # Форматирую для красоты
        parsed = json.loads(fixed)
        formatted = json.dumps(parsed, indent=2, ensure_ascii=False)
        
        return True, formatted
    except Exception as e:
        return False, str(e)

def analyze_common_errors(text, error_msg, line_num, col_num):
    """Анализ типичных ошибок и предложение исправлений"""
    lines = text.split('\n')
    if line_num - 1 >= len(lines):
        return []
    
    error_line = lines[line_num - 1]
    suggestions = []
    
    # Проверяю на одинарные кавычки
    if "'" in error_line:
        suggestions.append("🔹 *Одинарные кавычки:* Замени `'` на `\"`")
    
    # Проверяю на отсутствие кавычек у ключей
    if re.search(r'\s*(\w+)\s*:', error_line):
        suggestions.append("🔹 *Ключи без кавычек:* Оберни ключи в двойные кавычки: `{\"ключ\": значение}`")
    
    # Проверяю на лишние запятые
    if re.search(r',\s*[}\]}]', error_line):
        suggestions.append("🔹 *Лишняя запятая:* Удали запятую перед закрывающей скобкой `}` или `]`")
    
    # Проверяю на пропущенные запятые
    if re.search(r'["\w\d]\s+["{]', error_line):
        suggestions.append("🔹 *Пропущена запятая:* Добавь запятую между элементами объекта или массива")
    
    # Проверяю на незакрытые строки
    if error_line.count('"') % 2 == 1:
        suggestions.append("🔹 *Незакрытая строка:* Добавь закрывающую кавычку `\"`")
    
    return suggestions

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start с приветствием"""
    welcome_text = "👋 Привет! Я бот для проверки JSON.\n\n📋 Отправь мне JSON или нажми кнопку 'Проверить JSON'"
    
    keyboard = [['🚀 Старт', '📝 Проверить JSON']]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text(welcome_text, reply_markup=reply_markup, parse_mode='Markdown')

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    
    # Обработка нажатий кнопок
    if text == "🚀 Старт" or text == "Старт":
        await start(update, context)
        return
    elif text == "📝 Проверить JSON" or text == "Проверить JSON":
        await update.message.reply_text("Отправь текст JSON для проверки:")
        return
    
    try:
        # Пытаюсь проверить JSON
        parsed = json.loads(text)
        formatted = json.dumps(parsed, indent=2, ensure_ascii=False)
        
        # Успешный ответ с красивым выводом
        response = "✅ *JSON ВАЛИДЕН*\n\n"
        response += "```json\n"
        response += formatted
        response += "\n```"
        
        # Добавляю информацию о структуре
        if isinstance(parsed, dict):
            response += f"\n📁 *Тип:* Объект с {len(parsed)} ключами"
        elif isinstance(parsed, list):
            response += f"\n📋 *Тип:* Массив с {len(parsed)} элементами"
        
        await update.message.reply_text(response, parse_mode='Markdown')
        
    except json.JSONDecodeError as e:
        # Получаю информацию об ошибке
        line_num, col_num, error_line = find_error_position(text, e.pos)
        
        # Формирую сообщение об ошибке
        response = "❌ *ОШИБКА В JSON*\n\n"
        response += f"📝 *Тип ошибки:* `{e.msg}`\n"
        response += f"📍 *Место:* Строка {line_num}, Позиция {col_num}\n\n"
        
        # Выделяю место ошибки
        response += "🔴 *Ошибка в строке:*\n"
        response += highlight_error_in_line(error_line, col_num)
        response += "\n"
        
        # Показываю контекст строки
        lines = text.split('\n')
        if line_num <= len(lines):
            context_start = max(0, line_num - 2)
            context_end = min(len(lines), line_num + 1)
            
            response += "\n📄 *Контекст:*\n"
            for i in range(context_start, context_end):
                line_prefix = "➤ " if i == line_num - 1 else "   "
                response += f"`{i+1:3d}{line_prefix}{lines[i]}`\n"
        
        # Пробую автоматически исправить JSON
        response += "\n🛠 *Автоматическое исправление:*\n"
        success, fixed_json = suggest_fix_with_json_repair(text)
        
        if success:
            response += "✅ *Исправленный JSON:*\n"
            response += f"```json\n{fixed_json}\n```\n"
        else:
            response += f"❌ Не удалось автоматически исправить: `{fixed_json}`\n"
        
        # Анализирую типичные ошибки
        common_suggestions = analyze_common_errors(text, e.msg, line_num, col_num)
        if common_suggestions:
            response += "\n💡 *Возможные проблемы:*\n"
            for suggestion in common_suggestions:
                response += f"{suggestion}\n"
        
        # Советы
        response += "\n🔧 *Советы по исправлению:*\n"
        response += "• Используй только **двойные кавычки** `\"`\n"
        response += "• Все **ключи** должны быть в кавычках\n"
        response += "• Разделяй элементы **запятыми**, кроме последнего\n"
        response += "• Закрывай все **скобки** `{}` и **кавычки**\n"
        response += "• Используй **онлайн валидатор** для сложных случаев"
        
        await update.message.reply_text(response, parse_mode='Markdown')
    
    except Exception as e:
        await update.message.reply_text(f"❌ Неизвестная ошибка: `{str(e)}`", parse_mode='Markdown')

# Запускаю бота
application = Application.builder().token(TOKEN).build()
application.add_handler(CommandHandler("start", start))
application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

print("🤖 Бот JSON валидатор запущен...")
print("📱 Используйте /start в Telegram для начала работы")
application.run_polling(drop_pending_updates=True)

