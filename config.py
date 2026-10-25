"""Конфигурация приложения. Токен берётся из переменной окружения BOT_TOKEN."""
import os
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.environ.get("BOT_TOKEN")
_PLACEHOLDER = "здесь_будет_ваш_токен"
if not TOKEN or TOKEN == _PLACEHOLDER:
    raise RuntimeError(
        "BOT_TOKEN не задан.\n"
        "1) Скопируйте .env.example в .env:  cp .env.example .env\n"
        "2) Откройте .env и замените 'здесь_будет_ваш_токен' на токен от @BotFather."
    )

DAYS_TOTAL = 7
