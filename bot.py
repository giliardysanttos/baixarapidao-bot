#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
BaixaRapidaoBot - Telegram Video Downloader
Render.com compatible | Token leak protection
"""

import os
import re
import asyncio
import tempfile
import logging
from pathlib import Path
from aiohttp import web

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)
import yt_dlp

# ─── CONFIG ──────────────────────────────────────────────────────
TOKEN = os.environ.get("BOT_TOKEN")
if not TOKEN:
    raise ValueError("BOT_TOKEN nao encontrado! Configure no Render Dashboard.")

PORT = int(os.environ.get("PORT", "10000"))
MAX_FILE_SIZE_MB = 49
MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024
TEMP_DIR = Path(tempfile.gettempdir()) / "tg_bot_downloads"
TEMP_DIR.mkdir(exist_ok=True)

# ─── LOGGING (protege token) ─────────────────────────────────────
logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# Desativa logs detalhados que podem vazar o token
logging.getLogger("telegram").setLevel(logging.WARNING)
logging.getLogger("telegram.ext").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("aiohttp").setLevel(logging.WARNING)

# ─── COMANDOS ────────────────────────────────────────────────────

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    text = (
        "👋 <b>Ola, " + user.first_name + "!</b>\n\n"
        "🎬 <b>Baixa Rápidão Bot</b>\n"
        "Envie qualquer link de vídeo e eu baixo para você.\n\n"
        "✅ <b>Plataformas:</b> YouTube, TikTok, Instagram, Twitter/X, Facebook, Reddit e +1000\n"
        "📏 <b>Limite:</b> até " + str(MAX_FILE_SIZE_MB) + "MB por arquivo\n"
        "⚡ <b>Comandos:</b> /start /help /status"
    )
    await update.message.reply_html(text, disable_web_page_preview=True)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = (
        "📖 <b>Como usar:</b>\n"
        "1. Copie o link do vídeo\n"
        "2. Cole aqui no chat\n"
        "3. Aguarde o download e envio\n\n"
        "⚠️ <b>Observações:</b>\n"
        "• Vídeos muito longos podem exceder o limite de 50MB\n"
        "• Conteúdo privado não funciona\n\n"
        "🛠 <b>Comandos:</b> /start /help /status"
    )
    await update.message.reply_text(text, parse_mode="HTML")


async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = (
        "🟢 <b>BaixaRapidaoBot Online</b>\n"
        "📥 Pronto para baixar vídeos\n"
        "🔧 yt-dlp ativo | Limite: 50MB"
    )
    await update.message.reply_text(text, parse_mode="HTML")


# ─── DOWNLOAD ────────────────────────────────────────────────────

async def download_video(url: str, chat_id: int) -> Path:
    import time
    import glob as glob_module
    unique_id = str(chat_id) + "_" + str(int(time.time() * 1000))
    output_path = str(TEMP_DIR / (unique_id + ".%(ext)s"))

    ydl_opts = {
        "format": "best[filesize<50M] / best[filesize_approx<50M] / best",
        "outtmpl": output_path,
        "quiet": True,
        "no_warnings": True,
        "merge_output_format": "mp4",
        "postprocessors": [{"key": "FFmpegVideoConvertor", "preferedformat": "mp4"}],
    }

    if "tiktok" in url or "instagram" in url:
        ydl_opts["format"] = "best"
        ydl_opts["addheaders"] = [
            ("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
        ]

    downloaded_file = None

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        if info:
            expected = output_path.replace(".%(ext)s", ".*")
            matches = glob_module.glob(expected)
            if matches:
                downloaded_file = Path(matches[0])
            else:
                for f in TEMP_DIR.glob(unique_id + "*"):
                    if f.is_file():
                        downloaded_file = f
                        break

    if not downloaded_file or not downloaded_file.exists():
        raise FileNotFoundError("Arquivo nao baixado")

    return downloaded_file


# ─── HANDLE URL ──────────────────────────────────────────────────

async def handle_url(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.message
    url = message.text.strip()
    chat_id = message.chat_id

    url_pattern = re.compile(
        r"https?://(?:www\.)?(?:youtube\.com|youtu\.be|tiktok\.com|"
        r"instagram\.com|twitter\.com|x\.com|facebook\.com|fb\.watch|"
        r"reddit\.com|vimeo\.com|dailymotion\.com|threads\.net)/[^\s]+"
    )

    if not url_pattern.search(url):
        await message.reply_text(
            "❌ Isso não parece ser um link de vídeo suportado.\n"
            "Envie links de: YouTube, TikTok, Instagram, Twitter/X, Facebook, etc."
        )
        return

    processing_msg = await message.reply_text("⏳ Analisando link...")

    try:
        await processing_msg.edit_text("📥 Baixando vídeo, aguarde...")

        loop = asyncio.get_event_loop()
        video_path = await loop.run_in_executor(
            None, lambda: asyncio.run(download_video(url, chat_id))
        )

        file_size = video_path.stat().st_size
        if file_size > MAX_FILE_SIZE_BYTES:
            size_mb = round(file_size / 1024 / 1024, 1)
            await processing_msg.edit_text(
                "⚠️ O vídeo tem <b>" + str(size_mb) + "MB</b> e excede o limite de "
                "<b>" + str(MAX_FILE_SIZE_MB) + "MB</b> do Telegram.\n"
                "Tente um vídeo mais curto.",
                parse_mode="HTML",
            )
            video_path.unlink(missing_ok=True)
            return

        await processing_msg.edit_text("📤 Enviando vídeo para você...")

        with open(video_path, "rb") as video_file:
            size_mb = round(file_size / 1024 / 1024, 1)
            caption = (
                "✅ <b>Download concluído!</b>\n"
                "📏 Tamanho: <b>" + str(size_mb) + "MB</b>\n"
                "🔗 Fonte: " + url[:60] + "..."
            )
            await message.reply_video(
                video=video_file,
                caption=caption,
                parse_mode="HTML",
                supports_streaming=True,
            )

        await processing_msg.delete()

    except yt_dlp.utils.DownloadError as e:
        error_msg = str(e)
        if "Private" in error_msg or "login" in error_msg.lower():
            await processing_msg.edit_text("🔒 Conteúdo privado. Tente um link público.")
        elif "Unsupported URL" in error_msg:
            await processing_msg.edit_text("❌ URL não suportada. Verifique o link.")
        else:
            await processing_msg.edit_text("❌ Erro ao baixar: " + error_msg[:200])
    except Exception as e:
        logger.exception("Erro inesperado")
        await processing_msg.edit_text("❌ Erro: " + str(e)[:200])
    finally:
        try:
            if 'video_path' in locals() and video_path.exists():
                video_path.unlink(missing_ok=True)
        except Exception:
            pass


# ─── HTTP SERVER ─────────────────────────────────────────────────

async def health_handler(request):
    return web.Response(text="BaixaRapidaoBot OK", status=200)


async def start_http_server():
    app = web.Application()
    app.router.add_get("/", health_handler)
    app.router.add_get("/health", health_handler)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", PORT)
    await site.start()
    logger.info("HTTP server iniciado na porta " + str(PORT))


# ─── MAIN ────────────────────────────────────────────────────────

async def main() -> None:
    await start_http_server()

    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("status", status_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_url))

    logger.info("BaixaRapidaoBot iniciado! Aguardando mensagens...")

    await app.initialize()
    await app.start()
    await app.updater.start_polling()

    while True:
        await asyncio.sleep(3600)


if __name__ == "__main__":
    asyncio.run(main())
