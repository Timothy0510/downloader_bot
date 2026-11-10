import os
import asyncio
from threading import Thread
from flask import Flask
import aiohttp
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, URLInputFile
from aiogram.filters import CommandStart

BOT_TOKEN = os.environ.get("BOT_TOKEN", "ВАШ_ТОКЕН_БОТА")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# --- БЛОК ДЛЯ RENDER: Веб-сервер ---
app = Flask(__name__)

@app.route('/')
def home():
    return "Бот активен!"

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
# -------------------------------------------------------------

# Функция для получения прямой ссылки на MP4 через сторонний API
async def get_video_download_url(youtube_url: str) -> str:
    # Используем публичный открытый API для конвертации YouTube в MP4
    api_url = f"https://cobalt.tools"
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json"
    }
    payload = {
        "url": youtube_url,
        "vQuality": "720",  # Ограничиваем качество до 720p для надежности
        "isAudioOnly": False
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(api_url, json=payload, headers=headers) as response:
                if response.status == 200:
                    data = await response.json()
                    return data.get("url")
    except Exception as e:
        print(f"Ошибка API: {e}")
    return None

@dp.message(CommandStart())
async def cmd_start(message: Message):
    await message.answer(
        "Привет! Я помогу скачать видео с YouTube.\n\n"
        "Просто отправь мне ссылку на видео (Shorts или обычный ролик), и я пришлю тебе файл!"
    )

@dp.message(F.text.contains("youtube.com") | F.text.contains("youtu.be"))
async def handle_youtube_link(message: Message):
    url = message.text.strip()
    status_message = await message.answer("⏳ Подключаюсь к серверам загрузки, подождите...")
    
    # Получаем прямую ссылку на файл
    download_url = await get_video_download_url(url)
    
    if not download_url:
        await status_message.edit_text("❌ Не удалось обработать видео. Возможно, оно защищено или сервер перегружен.")
        return
        
    try:
        await status_message.edit_text("🚀 Видео найдено! Отправляю в Telegram...")
        
        # Скачиваем напрямую по URL-ссылке без сохранения на диск Render!
        video_file = URLInputFile(download_url)
        await message.answer_video(video=video_file, caption="Вот ваше видео!")
        await status_message.delete()
        
    except Exception as e:
        print(f"Ошибка отправки: {e}")
        await status_message.edit_text("❌ Ошибка отправки. Возможно, файл весит больше 50 МБ.")

async def main():
    flask_thread = Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()
    
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
