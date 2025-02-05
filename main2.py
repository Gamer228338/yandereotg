import os
import logging
import requests
import asyncio
import nest_asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
    CallbackContext,
)
from yandex_music import Client
import speech_recognition as sr
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials

# Настройки
TOKEN = "7805948171:AAHmbtv_ZvN5AQQam9-uOQGJG7GrRYelx-M"
YANDEX_TOKEN = "y0_AgAAAAAa5tojAAG8XgAAAADxSLamXYmdsKcIS5eWcpGT46RO-KIuwdQ"
SPOTIFY_CLIENT_ID = "db3982856e154607a2b0d379b69c826d"
SPOTIFY_CLIENT_SECRET = "8a081ba863354a6f9616e3e5d867aafd"

# Инициализация клиентов
yandex_client = Client(YANDEX_TOKEN).init()
spotify_client = spotipy.Spotify(auth_manager=SpotifyClientCredentials(client_id=SPOTIFY_CLIENT_ID, client_secret=SPOTIFY_CLIENT_SECRET))

# Логирование
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

async def start(update: Update, context: CallbackContext) -> None:
    await show_main_menu(update)

async def show_main_menu(update: Update) -> None:
    keyboard = [
        [InlineKeyboardButton("Яндекс Музыка", callback_data="source_yandex")],
        [InlineKeyboardButton("Spotify", callback_data="source_spotify")],
        [InlineKeyboardButton("Домой", callback_data="home")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Выберите источник музыки:", reply_markup=reply_markup)

async def handle_source_selection(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    await query.answer()

    if query.data == "home":
        await show_main_menu(update)
    elif query.data == "source_yandex":
        await query.edit_message_text("Введите название трека для поиска в Яндекс Музыке:")
        context.user_data['source'] = 'yandex'
    elif query.data == "source_spotify":
        await query.edit_message_text("Введите название трека для поиска в Spotify:")
        context.user_data['source'] = 'spotify'

async def search(update: Update, context: CallbackContext) -> None:
    query = update.message.text
    source = context.user_data.get('source')

    if source == 'yandex':
        await search_yandex(update, context, query)
    elif source == 'spotify':
        await search_spotify(update, context, query)
    else:
        await handle_link(update, query)

async def handle_link(update: Update, query: str) -> None:
    if "yandex" in query:
        # Обработка ссылки на Яндекс Музыку
        await update.message.reply_text("Обработка ссылки на Яндекс Музыку...")
        # Здесь можно добавить логику для извлечения информации о треке из ссылки
    elif "spotify" in query:
        # Обработка ссылки на Spotify
        await update.message.reply_text("Обработка ссылки на Spotify...")

async def search_yandex(update: Update, context: CallbackContext, query: str) -> None:
    search_result = yandex_client.search(query, type_="track")

    if not search_result.tracks:
        await update.message.reply_text("Ничего не найдено в Яндекс Музыке 😢")
        return

    tracks = search_result.tracks.results[:7]  # Первые 5 результатов
    keyboard = []
    for idx, track in enumerate(tracks):
        artists = ", ".join(artist.name for artist in track.artists)
        title = f"{artists} - {track.title}"
        keyboard.append([InlineKeyboardButton(title, callback_data=f"yandex_track_{idx}")])

    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Результаты поиска в Яндекс Музыке:", reply_markup=reply_markup)
    context.user_data["current_yandex_tracks"] = tracks

async def search_spotify(update: Update, context: CallbackContext, query: str) -> None:
    search_result = spotify_client.search(q=query, type='track', limit=7)

    if not search_result['tracks']['items']:
        await update.message.reply_text(" Ничего не найдено в Spotify 😢")
        return

    tracks = search_result['tracks']['items']  # Первые 5 результатов
    keyboard = []
    for idx, track in enumerate(tracks):
        artists = ", ".join(artist['name'] for artist in track['artists'])
        title = f"{artists} - {track['name']}"
        keyboard.append([InlineKeyboardButton(title, callback_data=f"spotify_track_{idx}")])

    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Результаты поиска в Spotify:", reply_markup=reply_markup)
    context.user_data["current_spotify_tracks"] = tracks

async def button_click(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    await query.answer()

    if query.data.startswith("yandex_track_"):
        idx = int(query.data.split("_")[1])
        tracks = context.user_data.get("current_yandex_tracks", [])

        if not tracks or idx >= len(tracks):
            await query.edit_message_text("Ошибка: трек не найден в Яндекс Музыке.")
            return

        track = tracks[idx]
        try:
            filename = download_yandex_track(track)
            with open(filename, "rb") as audio_file:
                await context.bot.send_audio(
                    chat_id=query.message.chat_id,
                    audio=audio_file,
                    title=f"{track.title}",
                    performer=", ".join(artist.name for artist in track.artists),
                )
            os.remove(filename)
        except Exception as e:
            logger.error(f"Ошибка при скачивании из Яндекс Музыки: {e}")
            await query.edit_message_text("Не удалось скачать трек из Яндекс Музыки 😢")

    elif query.data.startswith("spotify_track_"):
        idx = int(query.data.split("_")[1])
        tracks = context.user_data.get("current_spotify_tracks", [])

        if not tracks or idx >= len(tracks):
            await query.edit_message_text("Ошибка: трек не найден в Spotify.")
            return

        track = tracks[idx]
        await query.edit_message_text(f"Трек из Spotify: {track['name']} - {', '.join(artist['name'] for artist in track['artists'])}. Обратите внимание, что прямое скачивание не поддерживается.")

def download_yandex_track(track) -> str:
    download_info = track.get_download_info(get_direct_links=True)[0]
    direct_link = download_info.direct_link
    filename = f"{track.artists[0].name} - {track.title}.mp3".replace("/", "_")

    response = requests.get(direct_link)
    with open(filename, "wb") as f:
        f.write(response.content)

    return filename

# Добавьте обработку ссылок на Яндекс Музыку, Spotify
async def handle_link(update: Update, query: str) -> None:
    if "yandex" in query:
        # Обработка ссылки на Яндекс Музыку
        track_id = extract_yandex_track_id(query)
        track = yandex_client.tracks(track_id)
        await update.message.reply_text(f"Трек из Яндекс Музыки: {track.title} - {', '.join(artist.name for artist in track.artists)}")
    elif "spotify" in query:
        # Обработка ссылки на Spotify
        track_id = extract_spotify_track_id(query)
        track = spotify_client.track(track_id)
        await update.message.reply_text(f"Трек из Spotify: {track['name']} - {', '.join(artist['name'] for artist in track['artists'])}")

def extract_yandex_track_id(url: str) -> str:
    # Логика для извлечения ID трека из ссылки Яндекс Музыки
    return url.split('/')[-1]

def extract_spotify_track_id(url: str) -> str:
    # Логика для извлечения ID трека из ссылки Spotify
    return url.split('/')[-1].split('?')[0]

# Применяем фикс для PyCharm / Jupyter Notebook
nest_asyncio.apply()

async def main():
    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, search))
    app.add_handler(CallbackQueryHandler(handle_source_selection))
    app.add_handler(CallbackQueryHandler(button_click))

    print("Бот запущен!")
    await app.run_polling()

if __name__ == "__main__":
    asyncio.run(main())  # Теперь должно работать корректно ```python