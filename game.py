import nest_asyncio
nest_asyncio.apply()

import asyncio
import os
import mysql.connector
from mysql.connector import Error
from datetime import datetime
from telegram import (
    Update, ReplyKeyboardMarkup, ReplyKeyboardRemove,
    InlineKeyboardMarkup, InlineKeyboardButton
)
from telegram.ext import (
    Application, ApplicationBuilder, CommandHandler,
    MessageHandler, ContextTypes, filters, CallbackQueryHandler
)

BOT_TOKEN = ""
DB_CONFIG = {
    "host": "localhost",
    "user": "ten",
    "password": "",
    "database": "ten",
    "charset": "utf8mb4",
    "collation": "utf8mb4_unicode_ci"
}

PHOTO_DIR = "photos"
os.makedirs(PHOTO_DIR, exist_ok=True)

def get_db_connection():
    return mysql.connector.connect(**DB_CONFIG)


def execute_query(query, params=()):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    result = None
    try:
        cursor.execute(query, params)
        if query.strip().upper().startswith("SELECT"):
            result = cursor.fetchall()
        else:
            conn.commit()
    except Error as e:
        print(f"Ошибка при выполнении запроса: {e}")
    finally:
        cursor.close()
        conn.close()
    return result

QUESTIONS = [
    "Введите ваше имя:",
    ("Введите ваш пол (М/Ж):",
     [["М"], ["Ж"]]),
    "Введите ваш возраст:",
    "Введите ваш город:",

    ("Ответь на 10 вопросов и жди свою любовь. ❤️❤️❤️\n\nВопрос 1. \nКто должен платить на первом свидании?",
     [["Мужчина"], ["Женщина"], ["Каждый за себя"], ["Тот, кто пригласил"]]),

    ("Вопрос 2. \nКак вы относитесь к брачному контракту?",
     [["Разумная предосторожность"], ["Показывает недоверие"]]),

    ("Вопрос 3. \nСобака или кошка?",
     [["Собака"], ["Кошка"]]),

    ("Вопрос 4. \nЛыжи или сноуборд?",
     [["Лыжи"], ["Сноуборд"]]),

    ("Вопрос 5. \nЛюбовь для вас — это…",
     [["Поддержка и уважение"], ["Страсть и эмоции"]]),

    ("Вопрос 6. \nКак вы расставите приоритеты?",
     [["Дети, партнер, я, родители"],
      ["Партнер, дети, я, родители"],
      ["Я, партнер, дети, родители"],
      ["Родители, дети, партнер, я"]]),

    ("Вопрос 7. \nКак вы относитесь к раздельному бюджету в отношениях?",
     [["Сохранять независимость"], ["Лучше общий бюджет"]]),

    ("Вопрос 8. \nВыберите отпуск вашей мечты:",
     [["Горы и активный отдых"], ["Море и спокойствие"]]),

    ("Вопрос 9. \nВажнее в партнере:",
     [["Умение заботиться и поддерживать"], ["Умение вдохновлять и мотивировать"]]),

    ("Вопрос 10. \nКто должен первым знакомиться?",
     [["Мужчина"], ["Женщина"]]),


    "Теперь, пожалуйста, отправьте своё фото для анкеты 📸"
]

COLUMN_NAMES = [
    "gender",  # question_index=1
    "age",     # question_index=2
    "city",    # question_index=3
    "q1",      # question_index=4
    "q2",      # question_index=5
    "q3",      # question_index=6
    "q4",      # question_index=7
    "q5",      # question_index=8
    "q6",      # question_index=9
    "q7",      # question_index=10
    "q8",      # question_index=11
    "q9",      # question_index=12
    "q10"      # question_index=13
]


def initialize_db():
    execute_query('''
        CREATE TABLE IF NOT EXISTS users (
            id INT AUTO_INCREMENT PRIMARY KEY,
            telegram_id BIGINT UNIQUE,
            username VARCHAR(255),
            name VARCHAR(255),
            gender VARCHAR(10),
            age INT,
            city VARCHAR(255),
            q1 VARCHAR(255),
            q2 VARCHAR(255),
            q3 VARCHAR(255),
            q4 VARCHAR(255),
            q5 VARCHAR(255),
            q6 VARCHAR(255),
            q7 VARCHAR(255),
            q8 VARCHAR(255),
            q9 VARCHAR(255),
            q10 VARCHAR(255),
            photo_url VARCHAR(255)
        ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
    ''')

    execute_query('''
        CREATE TABLE IF NOT EXISTS likes (
            id INT AUTO_INCREMENT PRIMARY KEY,
            user_id BIGINT,
            liked_user_id BIGINT,
            created_at DATETIME
        ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
    ''')

def get_user_data(user_id: int):
    """ Достаём запись пользователя (пол, город, фото и т.д.). """
    rows = execute_query(
        "SELECT * FROM users WHERE telegram_id=%s LIMIT 1",
        (user_id,)
    )
    return rows[0] if rows else None

def get_opposite_gender(gender: str) -> str:
    """ М->Ж, Ж->М, иначе "" """
    if not gender:
        return ""
    g = gender.upper()
    if g == "М":
        return "Ж"
    elif g == "Ж":
        return "М"
    return ""

def get_candidates(user_id: int):
    """
    Ищем тех, кто:
      - Противоположный пол
      - Имеет фото
      - Не user_id
      - Сортируем: сначала город тот же (city_match=1)
    """
    user_row = get_user_data(user_id)
    if not user_row:
        return []
    opposite = get_opposite_gender(user_row["gender"])
    city = user_row["city"] or ""

    query = """
    SELECT *,
           CASE WHEN city = %s THEN 1 ELSE 0 END AS city_match
    FROM users
    WHERE telegram_id <> %s
      AND gender = %s
      AND photo_url IS NOT NULL
    ORDER BY city_match DESC
    """
    rows = execute_query(query, (city, user_id, opposite))
    return rows or []

async def show_next_candidate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает следующего кандидата из актуального списка"""
    user_id = update.effective_user.id
    user_data = context.user_data
    

    candidates = get_candidates(user_id)
    
    if not candidates:
        await update.effective_message.reply_text("К сожалению, нет анкет для показа.")
        return


    viewed_ids = user_data.get("viewed_ids", set())
    

    candidate = None
    for cand in candidates:
        if cand['telegram_id'] not in viewed_ids:
            candidate = cand
            break
    
    if not candidate:

        user_data["viewed_ids"] = set()
        await show_next_candidate(update, context)
        return


    viewed_ids.add(candidate['telegram_id'])
    user_data["viewed_ids"] = viewed_ids
    

    name = candidate["name"] or "Без имени"
    city = candidate["city"] or "Не указан"
    photo = candidate["photo_url"]
    
    keyboard = [
        [
            InlineKeyboardButton("❤️ Нравится", callback_data="like"),
            InlineKeyboardButton("Дальше", callback_data="skip")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    try:
        if photo and os.path.exists(photo):
            with open(photo, "rb") as f:
                await update.effective_message.reply_photo(
                    photo=f,
                    caption=f"Анкета: {name}, {city}",
                    reply_markup=reply_markup
                )
        else:
            await update.effective_message.reply_text(
                f"Анкета: {name}, {city}\n(Фото не найдено)",
                reply_markup=reply_markup
            )
    except Exception as e:
        print(f"Ошибка при показе кандидата: {e}")

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """ Обработка /start """
    context.user_data.clear()
    await update.message.reply_text(
        "Десяточка приветствует тебя! 🎉\n"
        "Давай познакомимся поближе. ✅\n\n"
        f"{QUESTIONS[0]}"
    )
    context.user_data["question_index"] = 0

async def handle_text_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """ Обработка текстовых ответов (имя, пол, возраст, город + 10 вопросов). """
    if "question_index" not in context.user_data:
        await update.message.reply_text("Чтобы начать, введите /start.")
        return

    question_index = context.user_data["question_index"]
    user_id = update.message.from_user.id
    username = update.message.from_user.username
    if not username:
        await update.message.reply_text("❌ Для использования бота необходимо установить username в настройках Telegram.")
        context.user_data["question_index"] = 0  # Сброс анкеты
        return
    text = update.message.text.strip()


    if context.user_data.get("waiting_for_photo"):
        await update.message.reply_text("Сейчас нужно фото, а не текст!")
        return

    if question_index == 0:

        execute_query(
            """
            INSERT INTO users (telegram_id, username, name)
            VALUES (%s, %s, %s)
            ON DUPLICATE KEY UPDATE
                name=VALUES(name),
                username=VALUES(username)
            """,
            (user_id, username, text)
        )
    else:

        if 1 <= question_index <= 13:
            col = COLUMN_NAMES[question_index - 1]
            execute_query(
                f"UPDATE users SET {col}=%s WHERE telegram_id=%s",
                (text, user_id)
            )

    question_index += 1
    context.user_data["question_index"] = question_index

    if question_index < len(QUESTIONS) - 1:
        nxt = QUESTIONS[question_index]
        if isinstance(nxt, tuple):
            q_text, options = nxt
            kb = ReplyKeyboardMarkup(options, one_time_keyboard=True, resize_keyboard=True)
            await update.message.reply_text(q_text, reply_markup=kb)
        else:
            await update.message.reply_text(nxt, reply_markup=ReplyKeyboardRemove())
    elif question_index == len(QUESTIONS) - 1:

        await update.message.reply_text(QUESTIONS[-1], reply_markup=ReplyKeyboardRemove())
        context.user_data["waiting_for_photo"] = True
    else:
        await update.message.reply_text("Все вопросы уже заданы. Жду фото!")

async def handle_photo_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """ Сохраняем фото, показываем список кандидатов. """
    if not context.user_data.get("waiting_for_photo"):
        await update.message.reply_text("Сейчас фото не нужно. Введите /start.")
        return

    user_id = update.message.from_user.id
    photo = update.message.photo[-1]
    file = await context.bot.get_file(photo.file_id)
    path = os.path.join(PHOTO_DIR, f"{user_id}.jpg")
    await file.download_to_drive(custom_path=path)

    execute_query(
        "UPDATE users SET photo_url=%s WHERE telegram_id=%s",
        (path, user_id)
    )
    context.user_data["waiting_for_photo"] = False
    await update.message.reply_text("Фото получено! Спасибо.")

    context.user_data["viewed_ids"] = set()
    await show_next_candidate(update, context)

    if not cands:
        await update.message.reply_text("Пока нет подходящих анкет. Попробуйте позже.")
        return

    await show_next_candidate(update, context)

async def callback_query_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка лайка/пропуска с обновлением списка"""
    query = update.callback_query
    data = query.data
    user_id = query.from_user.id

    await query.answer()
    await query.edit_message_reply_markup(reply_markup=None)

    if data == "like":

        viewed_ids = context.user_data.get("viewed_ids", set())
        if not viewed_ids:
            return
        

        candidate_id = list(viewed_ids)[-1]

        execute_query(
            "INSERT INTO likes (user_id, liked_user_id, created_at) VALUES (%s, %s, %s)",
            (user_id, candidate_id, datetime.now())
        )
        await query.message.reply_text("Вы нажали «Нравится»! (сохранено)")


        row = execute_query(
            "SELECT id FROM likes WHERE user_id=%s AND liked_user_id=%s LIMIT 1",
            (candidate_id, user_id)
        )
        if row:
            await notify_mutual_like(user_id, candidate_id, context)


    await show_next_candidate(update, context)

async def notify_mutual_like(userA_id: int, userB_id: int, context: ContextTypes.DEFAULT_TYPE):
    """
    Отправляем обоим пользователям сообщение:
    "Вы нравитесь друг другу..." + фото партнёра + кнопки (общение / Дальше).
    """
    userA = get_user_data(userA_id)
    userB = get_user_data(userB_id)
    if not userA or not userB:
        return

    nameA = userA["name"] or "Без имени"
    usernameA = userA["username"]
    photoA = userA["photo_url"]

    nameB = userB["name"] or "Без имени"
    usernameB = userB["username"]
    photoB = userB["photo_url"]


    def build_keyboard(partner_username):
        rows = []
        if partner_username:
            rows.append([InlineKeyboardButton("Начать личное общение", url=f"https://t.me/{partner_username}")])
        rows.append([InlineKeyboardButton("Дальше", callback_data="skip")])
        return InlineKeyboardMarkup(rows)

    textA = f"Вы нравитесь друг другу ❤️❤️❤️\nИмя: {nameB}"
    markupA = build_keyboard(usernameB)
    if photoB and os.path.exists(photoB):
        await context.bot.send_photo(
            chat_id=userA_id,
            photo=open(photoB, "rb"),
            caption=textA,
            reply_markup=markupA
        )
    else:
        await context.bot.send_message(
            chat_id=userA_id,
            text=f"{textA}\n(Фото партнёра не найдено)",
            reply_markup=markupA
        )


    textB = f"Вы нравитесь друг другу ❤️❤️❤️\nИмя: {nameA}"
    markupB = build_keyboard(usernameA)
    if photoA and os.path.exists(photoA):
        await context.bot.send_photo(
            chat_id=userB_id,
            photo=open(photoA, "rb"),
            caption=textB,
            reply_markup=markupB
        )
    else:
        await context.bot.send_message(
            chat_id=userB_id,
            text=f"{textB}\n(Фото партнёра не найдено)",
            reply_markup=markupB
        )

async def main():
    initialize_db()
    application = ApplicationBuilder().token(BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", cmd_start))
    application.add_handler(MessageHandler(filters.PHOTO, handle_photo_message))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_message))
    application.add_handler(CallbackQueryHandler(callback_query_handler))

    print("Бот запущен и находится в режиме ожидания...")
    await application.run_polling()

if __name__ == "__main__":
    asyncio.run(main())
