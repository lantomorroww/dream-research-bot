"""
Dream Research Bot — Telegram-бот для 7-дневного дневника сновидений.

Запуск:
    cp .env.example .env        # заменить заглушку на реальный BOT_TOKEN
    python main.py              # или: make run
"""
import csv
import json
import logging
import os
from datetime import date, datetime, time as dt_time
from pathlib import Path

from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import (
    Application, CommandHandler, ContextTypes, ConversationHandler,
    MessageHandler, filters,
)
from telegram.request import HTTPXRequest

from config import TOKEN, DAYS_TOTAL

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# ---------- Пути данных ----------
DEMOGRAPHICS_CSV = "demographics.csv"
DESCRIPTIONS_CSV = "descriptions.csv"
ANSWERS_CSV = "answers.csv"
USER_DATA_FILE = "users.json"
VOICE_NOTES_DIR = "voice_notes"
Path(VOICE_NOTES_DIR).mkdir(exist_ok=True)

# ---------- Вопросы ----------
QUESTIONS = [
    "Насколько ярким и отчетливым было переживание сновидения?\n"
    "(от 1 до 5)\n1️⃣ - очень тусклое, смутное, едва различимое\n"
    "5️⃣ - яркое как в бодрствующем восприятии, почти как наяву",
    "Насколько сильные эмоции вы испытывали во сне?\n"
    "(от 1 до 5)\n1️⃣ - никаких эмоций или полное равнодушие\n"
    "5️⃣ - очень сильные эмоции, захватывающие целиком",
    "Было ли у вас во сне ощущение, что это именно вы совершаете действия, "
    "а не просто наблюдаете?\n(от 1 до 5)\n1️⃣ - я был чистым наблюдателем, "
    "как будто смотрел кино\n5️⃣ - полностью действовал сам, все действия были моими",
    "Помнили ли вы во сне что-то из своей бодрствующей жизни?\n"
    "(от 1 до 5)\n1️⃣ - совсем не помнил, я был как чистый лист\n"
    "5️⃣ - помнил все как наяву, полностью знал, кто я и что со мной происходит",
    "Было ли у вас ощущение, что пространство во сне подчиняется обычной логике?\n"
    "(от 1 до 5)\n1️⃣ - полный пространственный хаос, все менялось без правил\n"
    "5️⃣ - полностью как в реальности, пространство было привычным",
    "Было ли у вас ощущение, что время во сне течет как в реальности?\n"
    "(от 1 до 5)\n1️⃣ - время было сильно искажено, сжималось или растягивалось\n"
    "5️⃣ - время ощущалось обычным, секунды шли за секундами",
    "Насколько вы были уверены во сне, что происходящее реально (а не сон)?\n"
    "(от 1 до 5)\n1️⃣ - я точно знал, что сплю (осознанное сновидение)\n"
    "5️⃣ - абсолютно верил в реальность, ни на секунду не сомневался",
    "Было ли у вас во сне ощущение собственного тела?\n"
    "(от 1 до 5)\n1️⃣ - тела не чувствовал, был как чистое сознание или камера\n"
    "5️⃣ - ощущение тела было столь же отчетливым, как наяву",
]

# ---------- Состояния ----------
(ASK_CONSENT, ASK_TIME, ASK_RESPONDENT_ID, ASK_GENDER, ASK_AGE, ASK_EDUCATION,
 ASK_DREAM_DESCRIPTION, ASK_DREAM_FEELINGS,
 Q1, Q2, Q3, Q4, Q5, Q6, Q7, Q8,
 ASK_EARLY_DREAM_CONFIRM, ASK_VAGUE_FEELINGS,
 RESET_DAY_CONFIRM) = range(19)


def get_consent_keyboard():
    return ReplyKeyboardMarkup([["✅ Да", "❌ Нет"]], one_time_keyboard=True, resize_keyboard=True)


def get_rating_keyboard():
    return ReplyKeyboardMarkup([["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣"]], one_time_keyboard=True, resize_keyboard=True)


def get_main_keyboard():
    return ReplyKeyboardMarkup(
        [["🚀 /start", "🌙 /dream", "⭐ /extradream"]], resize_keyboard=True
    )


def get_gender_keyboard():
    return ReplyKeyboardMarkup([["👨 Мужской", "👩 Женский"]], one_time_keyboard=True, resize_keyboard=True)


def get_no_dream_keyboard():
    return ReplyKeyboardMarkup([["🚫 Нет сна", "🤔 Помню смутно"]], one_time_keyboard=True, resize_keyboard=True)


def get_confirm_keyboard():
    return ReplyKeyboardMarkup([["✅ Да", "❌ Нет"]], one_time_keyboard=True, resize_keyboard=True)


# ---------- Пользователи (JSON) ----------
def load_users() -> dict:
    if Path(USER_DATA_FILE).exists():
        with open(USER_DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_users(users: dict) -> None:
    with open(USER_DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(users, f, ensure_ascii=False, indent=2)


def get_user(user_id: int) -> dict:
    return load_users().get(str(user_id), {})


def update_user(user_id: int, data: dict) -> None:
    users = load_users()
    users[str(user_id)] = data
    save_users(users)


def delete_user(user_id: int) -> None:
    users = load_users()
    users.pop(str(user_id), None)
    save_users(users)


# ---------- CSV-хранилище ----------
def save_demographics(user_id, respondent_id, gender, age, education):
    file_exists = Path(DEMOGRAPHICS_CSV).exists()
    with open(DEMOGRAPHICS_CSV, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["user_id", "respondent_id", "gender", "age", "education"])
        if not file_exists:
            w.writeheader()
        w.writerow({
            "user_id": user_id, "respondent_id": respondent_id,
            "gender": gender, "age": age, "education": education,
        })


def save_dream_description(respondent_id, day, dream_type, dream_content, feelings):
    weekday = date.today().strftime("%A")
    file_exists = Path(DESCRIPTIONS_CSV).exists()
    with open(DESCRIPTIONS_CSV, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=[
            "weekday", "respondent_id", "day", "date", "dream_type",
            "dream_content", "feelings",
        ])
        if not file_exists:
            w.writeheader()
        w.writerow({
            "weekday": weekday, "respondent_id": respondent_id, "day": day,
            "date": date.today().isoformat(), "dream_type": dream_type,
            "dream_content": dream_content, "feelings": feelings,
        })


def save_answers(respondent_id, day, answers):
    weekday = date.today().strftime("%A")
    file_exists = Path(ANSWERS_CSV).exists()
    fieldnames = ["weekday", "respondent_id", "day", "date"] + [f"q{i}" for i in range(1, 9)]
    with open(ANSWERS_CSV, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        if not file_exists:
            w.writeheader()
        row = {
            "weekday": weekday, "respondent_id": respondent_id,
            "day": day, "date": date.today().isoformat(),
        }
        for i, ans in enumerate(answers, 1):
            row[f"q{i}"] = ans
        w.writerow(row)


def delete_day_records(respondent_id: str, day: int) -> None:
    """Удаляет все записи за указанный день и связанные голосовые файлы."""
    for csv_path in (DESCRIPTIONS_CSV, ANSWERS_CSV):
        if not Path(csv_path).exists():
            continue
        with open(csv_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = [
                r for r in reader
                if not (r["respondent_id"] == respondent_id and int(r["day"]) == day)
            ]
            fieldnames = reader.fieldnames
        with open(csv_path, "w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=fieldnames)
            w.writeheader()
            w.writerows(rows)
    for f in Path(VOICE_NOTES_DIR).glob(f"user_*_day_{day}_*.ogg"):
        f.unlink()


async def save_voice_file(update: Update) -> str | None:
    user_id = update.effective_user.id
    day = get_user(user_id).get("day", 1)
    voice = update.message.voice
    if not voice:
        return None
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    file_path = os.path.join(VOICE_NOTES_DIR, f"user_{user_id}_day_{day}_{timestamp}.ogg")
    try:
        tg_file = await voice.get_file()
        await tg_file.download_to_drive(file_path)
        logger.info("Голосовое сохранено: %s", file_path)
        return file_path
    except Exception as e:
        logger.error("Ошибка сохранения голосового: %s", e)
        return None


# ---------- Планировщик ----------
def delete_job_if_exists(user_id, context):
    for job in context.job_queue.get_jobs_by_name(str(user_id)):
        job.schedule_removal()


def schedule_notification(user_id, time_str, context):
    hour, minute = map(int, time_str.split(":"))
    t = dt_time(hour=hour, minute=minute)
    delete_job_if_exists(user_id, context)
    job = context.job_queue.run_daily(
        callback=send_reminder, time=t, days=tuple(range(7)),
        data=user_id, name=str(user_id),
    )
    user_data = get_user(user_id)
    user_data["job_id"] = job.id
    update_user(user_id, user_data)


async def send_reminder(context: ContextTypes.DEFAULT_TYPE):
    user_id = context.job.data
    chat_id = get_user(user_id).get("chat_id")
    if chat_id:
        await context.bot.send_message(
            chat_id=chat_id,
            text="🔔 **Напоминание!** Пора ответить на вопросы о сегодняшнем сне. "
                 "Нажмите /start или /dream",
            parse_mode="Markdown",
            reply_markup=get_main_keyboard(),
        )


# ---------- Завершение дня ----------
async def finish_day(update, context, user_id, skip_survey=False,
                     vague_feelings=None, extra=False):
    user_data = get_user(user_id)
    day = user_data.get("day", 1)
    respondent_id = user_data.get("respondent_id", "")

    if skip_survey:
        if vague_feelings:
            dream_type = "vague_extra" if extra else "vague"
            save_dream_description(respondent_id, day, dream_type, "", vague_feelings)
        else:
            dream_type = "no_dream_extra" if extra else "no_dream"
            save_dream_description(respondent_id, day, dream_type, "", "")
    else:
        dream_desc = context.user_data.get("dream_description")
        feelings = context.user_data.get("dream_feelings", "")
        if dream_desc:
            base = dream_desc["type"]
            dream_type = f"{base}_extra" if extra else base
            save_dream_description(respondent_id, day, dream_type,
                                   dream_desc["content"], feelings)
        answers = context.user_data.get("answers", [])
        if answers:
            save_answers(respondent_id, day, answers)

    if not extra:
        user_data["last_answer_date"] = date.today().isoformat()
        user_data["day"] = day + 1
        update_user(user_id, user_data)
        context.user_data.clear()
        notif_time = user_data.get("notification_time", "09:00")
        try:
            h, m = map(int, notif_time.split(":"))
            notif_time = f"{h}:{m:02d}"
        except ValueError:
            pass
        await update.message.reply_text(
            f"✅ **День {day} завершён!**\nСпасибо за участие.\n\n"
            f"Хорошего дня! Завтра в {notif_time} я напомню вам снова.\n\n"
            "Вы всегда можете изменить время уведомлений с помощью /settime.\n"
            "Если хотите добавить ещё один сон за сегодня, используйте /extradream.",
            parse_mode="Markdown", reply_markup=get_main_keyboard(),
        )
        return ConversationHandler.END
    context.user_data.clear()
    await update.message.reply_text(
        "✅ **Дополнительный сон сохранён!**\n"
        "Если хотите добавить ещё один — снова /extradream.",
        parse_mode="Markdown", reply_markup=get_main_keyboard(),
    )
    return ConversationHandler.END


# ---------- Хэндлеры ----------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    user_data = get_user(user_id)

    if not user_data:
        await update.message.reply_text(
            "🌙✨ **Добро пожаловать в исследование сновидений!** ✨🌙\n\n"
            "📜 Ваши данные будут использоваться только в исследовательских целях, "
            "конфиденциальность гарантируется.\n"
            "Вы можете в любой момент прервать участие командой /reset.\n\n"
            "**Соглашаетесь ли вы на участие?**",
            parse_mode="Markdown", reply_markup=get_consent_keyboard(),
        )
        update_user(user_id, {"chat_id": chat_id})
        return ASK_CONSENT

    if user_data.get("day", 1) > DAYS_TOTAL:
        await update.message.reply_text(
            "🏁 **Вы завершили 7-дневный опрос!** Спасибо за участие!",
            parse_mode="Markdown", reply_markup=get_main_keyboard(),
        )
        return ConversationHandler.END

    if user_data.get("last_answer_date") == date.today().isoformat():
        await update.message.reply_text(
            "📅 **Вы уже отвечали сегодня.** Возвращайтесь завтра!",
            parse_mode="Markdown", reply_markup=get_main_keyboard(),
        )
        return ConversationHandler.END

    if not user_data.get("respondent_id"):
        await update.message.reply_text(
            "📝 **Пройдём сбор информации.**\n\nВведите ваш **номер респондента**:",
            parse_mode="Markdown", reply_markup=ReplyKeyboardRemove(),
        )
        return ASK_RESPONDENT_ID

    await update.message.reply_text(
        f"🌟 **День {user_data['day']} из {DAYS_TOTAL}** 🌟\n\n"
        "Опишите сновидение в свободной форме. Вы можете сделать это **текстом** "
        "или **голосовым сообщением**. Фиксируйте как можно больше деталей:\n"
        "○ визуальные образы;\n○ действия и события;\n○ диалоги и звуки;\n"
        "○ эмоциональные состояния;\n○ ощущение себя и окружающего пространства.\n\n"
        "Если вы **не помните сон**, нажмите **'Нет сна'**.\n"
        "Если помните, что сон был, но **смутно**, нажмите **'Помню смутно'**.",
        parse_mode="Markdown", reply_markup=get_no_dream_keyboard(),
    )
    return ASK_DREAM_DESCRIPTION


async def dream_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text(
        "🌙 **Вы желаете раньше записать сон?**",
        parse_mode="Markdown", reply_markup=get_confirm_keyboard(),
    )
    return ASK_EARLY_DREAM_CONFIRM


async def early_dream_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.message.text != "✅ Да":
        await update.message.reply_text(
            "❌ Хорошо, вернёмся к основному меню.",
            reply_markup=get_main_keyboard(),
        )
        return ConversationHandler.END

    user_id = update.effective_user.id
    user_data = get_user(user_id)
    if not user_data:
        await update.message.reply_text("❌ Сначала /start.", reply_markup=get_main_keyboard())
        return ConversationHandler.END
    if user_data.get("day", 1) > DAYS_TOTAL:
        await update.message.reply_text("🏁 Опрос завершён.", reply_markup=get_main_keyboard())
        return ConversationHandler.END
    if user_data.get("last_answer_date") == date.today().isoformat():
        await update.message.reply_text(
            "📅 Вы уже отвечали сегодня. Возвращайтесь завтра!",
            reply_markup=get_main_keyboard(),
        )
        return ConversationHandler.END
    if not user_data.get("respondent_id"):
        await update.message.reply_text(
            "📝 Введите ваш **номер респондента**:",
            parse_mode="Markdown", reply_markup=ReplyKeyboardRemove(),
        )
        return ASK_RESPONDENT_ID

    await update.message.reply_text(
        f"🌟 **День {user_data['day']} из {DAYS_TOTAL}** 🌟\n\n"
        "Опишите сновидение текстом или голосовым сообщением.",
        parse_mode="Markdown", reply_markup=get_no_dream_keyboard(),
    )
    return ASK_DREAM_DESCRIPTION


async def extradream_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id = update.effective_user.id
    user_data = get_user(user_id)
    if not user_data:
        await update.message.reply_text("❌ Сначала /start.", reply_markup=get_main_keyboard())
        return ConversationHandler.END
    if user_data.get("day", 1) > DAYS_TOTAL:
        await update.message.reply_text("🏁 Опрос завершён.", reply_markup=get_main_keyboard())
        return ConversationHandler.END
    if user_data.get("last_answer_date") != date.today().isoformat():
        await update.message.reply_text(
            "❌ Сначала пройдите основной сон за сегодня через /start.",
            reply_markup=get_main_keyboard(),
        )
        return ConversationHandler.END
    context.user_data["is_extra"] = True
    await update.message.reply_text(
        f"🌟 **День {user_data['day'] - 1} (дополнительный сон)** 🌟\n\n"
        "Опишите ещё одно сновидение текстом или голосом.",
        parse_mode="Markdown", reply_markup=get_no_dream_keyboard(),
    )
    return ASK_DREAM_DESCRIPTION


async def consent(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.message.text == "✅ Да":
        await update.message.reply_text(
            "✅ **Отлично!**\nУкажите удобное **время для уведомлений** (например, 09:00):",
            parse_mode="Markdown", reply_markup=ReplyKeyboardRemove(),
        )
        return ASK_TIME
    await update.message.reply_text(
        "❌ Вы отказались от участия. /start — если передумаете.",
        reply_markup=get_main_keyboard(),
    )
    return ConversationHandler.END


async def get_time(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    time_str = update.message.text.strip()
    try:
        hour, minute = map(int, time_str.split(":"))
        if not (0 <= hour <= 23 and 0 <= minute <= 59):
            raise ValueError
    except ValueError:
        await update.message.reply_text("⚠️ Введите время в формате **ЧЧ:ММ**.",
                                         parse_mode="Markdown")
        return ASK_TIME

    user_id = update.effective_user.id
    user_data = get_user(user_id)
    user_data["notification_time"] = time_str
    update_user(user_id, user_data)
    schedule_notification(user_id, time_str, context)

    formatted = f"{hour}:{minute:02d}"
    await update.message.reply_text(
        f"⏰ **Время уведомлений установлено на {formatted}.**",
        parse_mode="Markdown",
    )
    if not user_data.get("respondent_id"):
        await update.message.reply_text("📝 **Теперь введите номер респондента:**",
                                         parse_mode="Markdown")
        return ASK_RESPONDENT_ID
    await update.message.reply_text(
        "Вы всегда можете изменить его с помощью /settime.",
        reply_markup=get_main_keyboard(),
    )
    return ConversationHandler.END


async def get_respondent_id(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    rid = update.message.text.strip()
    if not rid:
        await update.message.reply_text("❌ Номер не может быть пустым.")
        return ASK_RESPONDENT_ID
    context.user_data["respondent_id"] = rid
    await update.message.reply_text("👤 **Укажите ваш пол:**",
                                     parse_mode="Markdown",
                                     reply_markup=get_gender_keyboard())
    return ASK_GENDER


async def get_gender(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["gender"] = update.message.text
    await update.message.reply_text("📅 **Ваш возраст** (полных лет):",
                                     parse_mode="Markdown",
                                     reply_markup=ReplyKeyboardRemove())
    return ASK_AGE


async def get_age(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["age"] = update.message.text
    await update.message.reply_text("🎓 **Ваша специальность**:",
                                     parse_mode="Markdown")
    return ASK_EDUCATION


async def get_education(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["education"] = update.message.text
    user_id = update.effective_user.id
    save_demographics(
        user_id, context.user_data["respondent_id"],
        context.user_data["gender"], context.user_data["age"],
        context.user_data["education"],
    )
    user_data = get_user(user_id)
    user_data.update({
        "respondent_id": context.user_data["respondent_id"],
        "day": 1,
        "last_answer_date": None,
    })
    update_user(user_id, user_data)
    await update.message.reply_text(
        f"🎉 **Спасибо!** Начнём ежедневный опрос.\n\n"
        f"🌟 **День 1 из {DAYS_TOTAL}** 🌟\n\n"
        "Опишите сновидение текстом или голосом.",
        parse_mode="Markdown", reply_markup=get_no_dream_keyboard(),
    )
    return ASK_DREAM_DESCRIPTION


async def dream_description(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id = update.effective_user.id
    text = update.message.text or ""

    if text == "🚫 Нет сна":
        await finish_day(update, context, user_id, skip_survey=True,
                         extra=context.user_data.get("is_extra", False))
        return ConversationHandler.END
    if text == "🤔 Помню смутно":
        await update.message.reply_text(
            "Опишите свои впечатления или остаточные чувства после сновидения.",
            reply_markup=ReplyKeyboardRemove(),
        )
        return ASK_VAGUE_FEELINGS
    if text.startswith("/"):
        await update.message.reply_text(
            "Сейчас команды недоступны. Опишите сон или нажмите кнопку."
        )
        return ASK_DREAM_DESCRIPTION

    if update.message.voice:
        path = await save_voice_file(update)
        if not path:
            await update.message.reply_text("❌ Ошибка, попробуйте ещё раз.")
            return ASK_DREAM_DESCRIPTION
        context.user_data["dream_description"] = {"type": "voice", "content": path}
    elif text.strip():
        context.user_data["dream_description"] = {"type": "text", "content": text.strip()}
    else:
        await update.message.reply_text("Опишите сон или нажмите действие.",
                                         reply_markup=get_no_dream_keyboard())
        return ASK_DREAM_DESCRIPTION

    await update.message.reply_text(
        "💭 **Напишите ваше отношение ко сну, переживания** и что показалось интересным:",
        parse_mode="Markdown",
    )
    return ASK_DREAM_FEELINGS


async def vague_feelings(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    feelings = update.message.text.strip()
    if not feelings:
        await update.message.reply_text("Пожалуйста, опишите впечатления.")
        return ASK_VAGUE_FEELINGS
    await finish_day(update, context, update.effective_user.id, skip_survey=True,
                     vague_feelings=feelings,
                     extra=context.user_data.get("is_extra", False))
    return ConversationHandler.END


async def dream_feelings(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["dream_feelings"] = update.message.text
    await ask_question(update, context, 0)
    return Q1


async def ask_question(update, context, idx):
    await update.message.reply_text(
        f"**{idx + 1}/{len(QUESTIONS)}** {QUESTIONS[idx]}",
        parse_mode="Markdown", reply_markup=get_rating_keyboard(),
    )


async def handle_answer(update, context, idx, next_state):
    raw = update.message.text
    rating = None
    if raw in ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣"]:
        rating = int(raw[0])
    else:
        try:
            rating = int(raw)
        except ValueError:
            pass
    if rating is None or not (1 <= rating <= 5):
        await update.message.reply_text("⚠️ Выберите оценку 1–5 кнопкой.")
        return next_state

    context.user_data.setdefault("answers", []).append(rating)
    if idx + 1 < len(QUESTIONS):
        await ask_question(update, context, idx + 1)
        return next_state
    await finish_day(update, context, update.effective_user.id,
                     extra=context.user_data.get("is_extra", False))
    return ConversationHandler.END


async def q1(u, c): return await handle_answer(u, c, 0, Q2)
async def q2(u, c): return await handle_answer(u, c, 1, Q3)
async def q3(u, c): return await handle_answer(u, c, 2, Q4)
async def q4(u, c): return await handle_answer(u, c, 3, Q5)
async def q5(u, c): return await handle_answer(u, c, 4, Q6)
async def q6(u, c): return await handle_answer(u, c, 5, Q7)
async def q7(u, c): return await handle_answer(u, c, 6, Q8)
async def q8(u, c): return await handle_answer(u, c, 7, Q8)


async def reset_day(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id = update.effective_user.id
    user_data = get_user(user_id)
    if not user_data:
        await update.message.reply_text("❌ Нет данных. /start.",
                                         reply_markup=get_main_keyboard())
        return ConversationHandler.END
    await update.message.reply_text(
        f"Введите номер дня (1–{DAYS_TOTAL}), который хотите сбросить и перезаписать.\n"
        f"Текущий день: {user_data.get('day', 1)}\n"
        "Данные за этот день будут удалены.",
        reply_markup=ReplyKeyboardRemove(),
    )
    return RESET_DAY_CONFIRM


async def reset_day_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id = update.effective_user.id
    user_data = get_user(user_id)
    if not user_data:
        await update.message.reply_text("❌ Нет данных.")
        return ConversationHandler.END
    try:
        day_to_reset = int(update.message.text.strip())
        if not (1 <= day_to_reset <= DAYS_TOTAL):
            raise ValueError
    except ValueError:
        await update.message.reply_text(f"❌ Введите число от 1 до {DAYS_TOTAL}.")
        return RESET_DAY_CONFIRM
    rid = user_data.get("respondent_id")
    if not rid:
        await update.message.reply_text("❌ respondent_id не найден.",
                                         reply_markup=get_main_keyboard())
        return ConversationHandler.END
    try:
        delete_day_records(rid, day_to_reset)
    except Exception as e:
        logger.error("Ошибка удаления дня %s: %s", day_to_reset, e)
        await update.message.reply_text(f"⚠️ Ошибка удаления: {e}")
        return ConversationHandler.END
    if day_to_reset == user_data.get("day", 1):
        user_data["last_answer_date"] = None
        update_user(user_id, user_data)
    await update.message.reply_text(
        f"✅ **День {day_to_reset} удалён.**\n"
        "Можете заново описать сон за этот день через /start.",
        parse_mode="Markdown", reply_markup=get_main_keyboard(),
    )
    return ConversationHandler.END


async def reset(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id = update.effective_user.id
    if not get_user(user_id):
        await update.message.reply_text("❌ Нет данных.", reply_markup=get_main_keyboard())
        return ConversationHandler.END
    delete_job_if_exists(user_id, context)
    for f in Path(VOICE_NOTES_DIR).glob(f"user_{user_id}_*"):
        f.unlink()
    delete_user(user_id)
    context.user_data.clear()
    await update.message.reply_text(
        "✅ **Все ваши данные удалены.** Начать заново: /start.",
        parse_mode="Markdown", reply_markup=get_main_keyboard(),
    )
    return ConversationHandler.END


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📖 **Помощь**\n\n"
        "🚀 /start — основной опрос\n"
        "🌙 /dream — записать сон раньше\n"
        "⭐ /extradream — дополнительный сон за сегодня\n"
        "🔄 /reset — удалить все свои данные\n"
        "🗑️ /resetday — удалить один день\n"
        "⏰ /settime — изменить время уведомлений\n"
        "❓ /help — справка",
        parse_mode="Markdown", reply_markup=get_main_keyboard(),
    )


async def settime(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not get_user(update.effective_user.id):
        await update.message.reply_text("❌ Сначала /start.", reply_markup=get_main_keyboard())
        return ConversationHandler.END
    await update.message.reply_text(
        "🕒 Введите новое время уведомлений (ЧЧ:ММ):",
        reply_markup=ReplyKeyboardRemove(),
    )
    return ASK_TIME


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text(
        "❌ Опрос прерван. /start — заново.",
        reply_markup=get_main_keyboard(),
    )
    return ConversationHandler.END


async def post_init(app: Application):
    for uid_str, data in load_users().items():
        uid = int(uid_str)
        if "notification_time" in data and data.get("day", 1) <= DAYS_TOTAL:
            try:
                h, m = map(int, data["notification_time"].split(":"))
                app.job_queue.run_daily(
                    send_reminder, time=dt_time(hour=h, minute=m),
                    days=tuple(range(7)), data=uid, name=str(uid),
                )
            except Exception:
                pass


def main():
    request = HTTPXRequest(connect_timeout=60, read_timeout=60, pool_timeout=60)
    app = Application.builder().token(TOKEN).request(request).post_init(post_init).build()

    conv = ConversationHandler(
        entry_points=[
            CommandHandler("start", start),
            CommandHandler("dream", dream_command),
            CommandHandler("extradream", extradream_command),
            CommandHandler("settime", settime),
            CommandHandler("resetday", reset_day),
        ],
        states={
            ASK_CONSENT: [MessageHandler(filters.TEXT & ~filters.COMMAND, consent)],
            ASK_TIME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_time)],
            ASK_RESPONDENT_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_respondent_id)],
            ASK_GENDER: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_gender)],
            ASK_AGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_age)],
            ASK_EDUCATION: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_education)],
            ASK_DREAM_DESCRIPTION: [MessageHandler(filters.ALL, dream_description)],
            ASK_DREAM_FEELINGS: [MessageHandler(filters.TEXT & ~filters.COMMAND, dream_feelings)],
            Q1: [MessageHandler(filters.TEXT & ~filters.COMMAND, q1)],
            Q2: [MessageHandler(filters.TEXT & ~filters.COMMAND, q2)],
            Q3: [MessageHandler(filters.TEXT & ~filters.COMMAND, q3)],
            Q4: [MessageHandler(filters.TEXT & ~filters.COMMAND, q4)],
            Q5: [MessageHandler(filters.TEXT & ~filters.COMMAND, q5)],
            Q6: [MessageHandler(filters.TEXT & ~filters.COMMAND, q6)],
            Q7: [MessageHandler(filters.TEXT & ~filters.COMMAND, q7)],
            Q8: [MessageHandler(filters.TEXT & ~filters.COMMAND, q8)],
            ASK_EARLY_DREAM_CONFIRM: [MessageHandler(filters.TEXT & ~filters.COMMAND, early_dream_confirm)],
            ASK_VAGUE_FEELINGS: [MessageHandler(filters.TEXT & ~filters.COMMAND, vague_feelings)],
            RESET_DAY_CONFIRM: [MessageHandler(filters.TEXT & ~filters.COMMAND, reset_day_confirm)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    app.add_handler(conv)
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("reset", reset))
    app.run_polling(drop_pending_updates=True,
                    allowed_updates=Update.ALL_TYPES, timeout=60)


if __name__ == "__main__":
    main()
