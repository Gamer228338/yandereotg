from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
    CallbackContext,
)
import os
import logging
import requests
from yandex_music import Client
import asyncio
import nest_asyncio
from mutagen.mp3 import MP3
from mutagen.id3 import ID3, TIT2, TPE1, TALB, APIC

# Настройки
TOKEN = "6699774063:AAG5VD0_nQwfhrry09rvlA0n7uJkNs-bLpc"
YANDEX_TOKEN = "y0_AgAAAAAa5tojAAG8XgAAAADxSLamXYmdsKcIS5eWcpGT46RO-KIuwdQ"

# Инициализация клиента Яндекс.Музыки
client = Client(YANDEX_TOKEN).init()

# Логирование
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

async def start(update: Update, context: CallbackContext) -> None:
    await update.message.reply_text("Привет! Отправь мне название трека для поиска.")

async def search(update: Update, context: CallbackContext) -> None:
    query = update.message.text
    search_result = client.search(query, type_="track")

    if not search_result.tracks:
        await update.message.reply_text("Ничего не найдено 😢")
        return

    tracks = search_result.tracks.results[:5]  # Первые 5 результатов
    keyboard = []
    for idx, track in enumerate(tracks):
        artists = ", ".join(artist.name for artist in track.artists)
        title = f"{artists} - {track.title}"
        keyboard.append([InlineKeyboardButton(title, callback_data=f"track_{idx}")])

    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Результаты поиска:", reply_markup=reply_markup)
    context.user_data["current_tracks"] = tracks

def download_track(track) -> str:
    download_info = track.get_download_info(get_direct_links=True)[0]
    direct_link = download_info.direct_link
    filename = f"{track.artists[0].name} - {track.title}.mp3".replace("/", "_")

    response = requests.get(direct_link)
    if response.status_code != 200:
        logger.error("Ошибка при загрузке трека: статус код не 200")
        return None

    with open(filename, "wb") as f:
        f.write(response.content)

    # Добавление метаданных
    try:
        audio = MP3(filename)

        # Проверка наличия тегов ID3
        if audio.tags is None:
            audio.add_tags()  # Создание нового ID3 заголовка

        # Установка названия трека
        audio.tags.add(TIT2(encoding=3, text=str(track.title)))  # Преобразование в строку
        # Установка исполнителя
        audio.tags.add(TPE1(encoding=3, text=str(", ".join(artist.name for artist in track.artists))))  # Преобразование в строку
        # Установка названия альбома
        audio.tags.add(TALB(encoding=3, text=str(track.albums[0].title) if track.albums else "Unknown Album"))  # Преобразование в строку

        # Добавление обложки
        if hasattr(track, 'cover') and track.cover:
            cover_url = track.cover
            cover_response = requests.get(cover_url)
            if cover_response.status_code == 200:
                audio.tags.add(APIC(
                    encoding=3,  # 3 is for UTF-8
                    mime='image/jpeg',  # image/jpeg or image/png
                    type=3,  # 3 is for the cover image
                    desc='Cover',
                    data=cover_response.content
                ))

        audio.save()

    except Exception as e:
        logger.error(f"Ошибка при добавлении метаданных: {e}")

    return filename


async def button_click(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    await query.answer()

    if query.data.startswith("track_"):
        idx = int(query.data.split("_")[1])
        tracks = context.user_data.get("current_tracks", [])

        if not tracks or idx >= len(tracks):
            await query.edit_message_text("Ошибка: трек не найден.")
            return

        track = tracks[idx]
        try:
            filename = download_track(track)
            with open(filename, "rb") as audio_file:
                await context.bot.send_audio(
                    chat_id=query.message.chat_id,
                    audio=audio_file,
                    title=f"{track.title}",
                    performer=", ".join(artist.name for artist in track.artists),
                )
            os.remove(filename)
        except Exception as e:
            logger.error(f"Ошибка при скачивании: {e}")
            await query.edit_message_text("Не удалось скачать трек 😢")

# Применяем фикс для PyCharm / Jupyter Notebook
nest_asyncio.apply()

async def main():
    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, search))
    app.add_handler(CallbackQueryHandler(button_click))

    print("Бот запущен!")
    await app.run_polling()

if __name__ == "__main__":
    asyncio.run(main())  # Теперь должно работать корректно