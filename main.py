import os
import asyncio
from threading import Thread
from flask import Flask
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, FSInputFile
from aiogram.filters import CommandStart
import yt_dlp

# Токен бота (на Render мы свяжем эту переменную с реальным токеном)
BOT_TOKEN = os.environ.get("BOT_TOKEN", "ВАШ_ТОКЕН_БОТА")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
DOWNLOAD_DIR = "downloads"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

# --- БЛОК ДЛЯ RENDER: Веб-сервер для удержания бота в сети ---
app = Flask(__name__)

@app.route('/')
def home():
    return "Бот активен!"

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
# -------------------------------------------------------------

# Перевод таймкода ММ:СС в секунды
def time_to_seconds(time_str: str) -> int:
    try:
        parts = list(map(int, time_str.split(':')))
        if len(parts) == 2:
            return parts[0] * 60 + parts[1]
        elif len(parts) == 3:
            return parts[0] * 3600 + parts[1] * 60 + parts[2]
        return int(time_str)
    except ValueError:
        return -1

# Функция скачивания целого видео (до 50 МБ)
def download_youtube_video(url: str, output_path: str) -> str:
    ydl_opts = {
        'format': 'bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/best[height<=720]/best',
        'outtmpl': os.path.join(output_path, '%(id)s.%(ext)s'),
        'max_filesize': 48 * 1024 * 1024, 
        'quiet': True,
        'no_warnings': True,
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        return ydl.prepare_filename(info)

# Функция скачивания конкретного фрагмента
def download_youtube_video_range(url: str, start_sec: int, end_sec: int, output_path: str) -> str:
    ydl_opts = {
        'format': 'bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/best[height<=720]/best',
        'outtmpl': os.path.join(output_path, '%(id)s.%(ext)s'),
        'quiet': True,
        'no_warnings': True,
        'download_ranges': yt_dlp.utils.download_range_func(None, [{
            'start_time': start_sec,
            'end_time': end_sec,
        }]),
        'force_keyframes_at_cuts': True,
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        return ydl.prepare_filename(info)

@dp.message(CommandStart())
async def cmd_start(message: Message):
    await message.answer(
        "Привет! Я помогу скачать видео с YouTube.\n\n"
        "• Отправь просто ссылку, чтобы скачать видео целиком (до 50 МБ).\n"
        "• Или отправь ссылку и таймкод через пробел, чтобы вырезать кусок, например:\n"
        "`ссылка 01:00-01:30`"
    )

@dp.message(F.text.contains("youtube.com") | F.text.contains("youtu.be"))
async def handle_youtube_link(message: Message):
    text_parts = message.text.strip().split()
    url = text_parts[0]
    
    start_sec = None
    end_sec = None
    
    if len(text_parts) > 1:
        try:
            range_part = text_parts[1]
            start_str, end_str = range_part.split('-')
            start_sec = time_to_seconds(start_str)
            end_sec = time_to_seconds(end_str)
        except Exception:
            await message.answer("❌ Неверный формат времени. Пишите так: `ссылка 01:00-01:30`")
            return

    status_message = await message.answer("⏳ Начинаю обработку видео, пожалуйста, подождите...")
    loop = asyncio.get_event_loop()
    file_path = None
    
    try:
        if start_sec is not None and end_sec is not None:
            if start_sec >= end_sec or start_sec < 0:
                await status_message.edit_text("❌ Время начала должно быть меньше времени конца.")
                return
            if (end_sec - start_sec) > 300:
                await status_message.edit_text("❌ Длина фрагмента не должна превышать 5 минут.")
                return

            file_path = await loop.run_in_executor(
                None, download_youtube_video_range, url, start_sec, end_sec, DOWNLOAD_DIR
            )
        else:
            file_path = await loop.run_in_executor(None, download_youtube_video, url, DOWNLOAD_DIR)
        
        await status_message.edit_text("🚀 Видео успешно загружено! Отправляю в Telegram...")
        video_file = FSInputFile(file_path)
        await message.answer_video(video=video_file, caption="Вот ваше видео!")
        await status_message.delete()
        
    except yt_dlp.utils.DownloadError as e:
        error_msg = str(e)
        if "File is larger than max-filesize" in error_msg:
            await status_message.edit_text("❌ Ошибка: Видео слишком большое (лимит 50 МБ). Попробуйте вырезать фрагмент.")
        else:
            await status_message.edit_text("❌ Ошибка скачивания. Возможно, видео защищено или ссылка неверна.")
    except Exception as e:
        print(f"Ошибка: {e}")
        await status_message.edit_text("❌ Произошла ошибка при обработке видео.")
    finally:
        if file_path and os.path.exists(file_path):
            os.remove(file_path)

async def main():
    flask_thread = Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()
    
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
