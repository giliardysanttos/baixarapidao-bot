#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
BaixaRapidaoBot - Telegram Video Downloader
v7 - FORCED webhook cleanup + single instance
"""

import os
import sys
import re
import asyncio
import tempfile
import logging
import fcntl
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

# ─── SINGLE INSTANCE LOCK ────────────────────────────────────────
LOCK_FILE = "/tmp/baixarapidao_bot.lock"

def acquire_lock():
    global lock_fd
    lock_fd = open(LOCK_FILE, "w")
    try:
        fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        lock_fd.write(str(os.getpid()))
        lock_fd.flush()
        return True
    except (IOError, OSError):
        print("OUTRA INSTANCIA JA RODANDO. ENCERRANDO.")
        return False

# ─── CONFIG ──────────────────────────────────────────────────────
TOKEN = os.environ.get("BOT_TOKEN")
if not TOKEN:
    raise ValueError("BOT_TOKEN nao encontrado!")

PORT = int(os.environ.get("PORT", "10000"))
WEBHOOK_URL = os.environ.get("WEBHOOK_URL", "").rstrip("/")
MAX_FILE_SIZE_MB = 49
MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024
TEMP_DIR = Path(tempfile.gettempdir()) / "tg_bot_downloads"
TEMP_DIR.mkdir(exist_ok=True)

# ─── LOGGING ─────────────────────────────────────────────────────
logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)
for name in ["telegram", "telegram.ext", "httpx", "aiohttp", "yt_dlp"]:
    logging.getLogger(name).setLevel(logging.WARNING)

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
        "• Conteúdo privado não funciona\n"
        "• YouTube pode bloquear alguns vídeos (use TikTok/Instagram para 100% certeza)\n\n"
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

def get_ydl_opts(url: str, output_path: str) -> dict:
    base_opts = {
        "outtmpl": output_path,
        "quiet": True,
        "no_warnings": True,
        "merge_output_format": "mp4",
        "postprocessors": [{"key": "FFmpegVideoConvertor", "preferedformat": "mp4"}],
    }

    real_headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "DNT": "1",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
        "Cache-Control": "max-age=0",
    }

    if "youtube" in url or "youtu.be" in url:
        base_opts.update({
            "format": "best[filesize<50M] / best[filesize_approx<50M] / best",
            "headers": real_headers,
            "extractor_args": {
                "youtube": {
                    "player_client": ["web", "android", "ios", "tv_embedded"],
                    "player_skip": ["webpage", "configs", "js"],
                    "formats": ["missing_pot"],
                }
            },
            "no_check_certificate": True,
            "geo_bypass": True,
            "geo_bypass_country": "US",
        })
    elif "tiktok" in url:
        base_opts.update({
            "format": "best",
            "headers": {**real_headers, "Referer": "https://www.tiktok.com/"},
        })
    elif "instagram" in url:
        base_opts.update({
            "format": "best",
            "headers": {**real_headers, "Referer": "https://www.instagram.com/"},
        })
    elif "twitter" in url or "x.com" in url:
        base_opts.update({
            "format": "best[filesize<50M] / best",
            "headers": real_headers,
        })
    elif "facebook" in url or "fb.watch" in url:
        base_opts.update({
            "format": "best[filesize<50M] / best",
            "headers": real_headers,
        })
    else:
        base_opts.update({
            "format": "best[filesize<50M] / best[filesize_approx<50M] / best",
            "headers": real_headers,
        })

    return base_opts


async def download_video(url: str, chat_id: int) -> Path:
    import time
    import glob as glob_module
    unique_id = str(chat_id) + "_" + str(int(time.time() * 1000))
    output_path = str(TEMP_DIR / (unique_id + ".%(ext)s"))

    ydl_opts = get_ydl_opts(url, output_path)
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
        elif "Sign in" in error_msg or "confirm" in error_msg.lower() or "bot" in error_msg.lower():
            await processing_msg.edit_text(
                "⚠️ O YouTube bloqueou este vídeo por verificação anti-bot.\n\n"
                "💡 <b>Soluções:</b>\n"
                "• Tente um <b>Short</b> em vez de vídeo longo\n"
                "• Use <b>TikTok</b> ou <b>Instagram</b> (funcionam 100%)\n"
                "• Ou baixe do YouTube no seu PC e envie aqui",
                parse_mode="HTML",
            )
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


# ─── MAIN ────────────────────────────────────────────────────────

async def main() -> None:
    if not acquire_lock():
        sys.exit(1)

    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("status", status_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_url))

    # Webhook path
    webhook_path = "/webhook/" + TOKEN.split(":")[0]
    webhook_full_url = WEBHOOK_URL + webhook_path if WEBHOOK_URL else ""

    # Inicializa o bot
    await app.initialize()
    await app.start()

    # SEMPRE deleta webhook antigo primeiro (limpa sujeira de deploys anteriores)
    logger.info("Deletando webhook antigo...")
    try:
        await app.bot.delete_webhook(drop_pending_updates=True)
        logger.info("Webhook antigo deletado com sucesso")
    except Exception as e:
        logger.warning("Erro ao deletar webhook antigo: " + str(e))

    await asyncio.sleep(2)

    # Se tem WEBHOOK_URL, usa webhook. Senao, polling.
    if webhook_full_url:
        logger.info("Configurando webhook: " + webhook_full_url.replace(TOKEN.split(":")[0], "***"))
        try:
            await app.bot.set_webhook(url=webhook_full_url)
            logger.info("Webhook ativo")
        except Exception as e:
            logger.error("Falha ao setar webhook: " + str(e))
            logger.info("Fallback para polling...")
            await app.updater.start_polling(drop_pending_updates=True)
    else:
        logger.info("WEBHOOK_URL nao configurado. Usando polling.")
        await app.updater.start_polling(drop_pending_updates=True)

    # Servidor HTTP
    async def webhook_handler(request):
        data = await request.json()
        update = Update.de_json(data, app.bot)
        await app.process_update(update)
        return web.Response(text="OK")

    async def health_handler(request):
        return web.Response(text="BaixaRapidaoBot OK", status=200)

    async def reset_webhook_handler(request):
        """Endpoint para forçar reset do webhook."""
        try:
            await app.bot.delete_webhook(drop_pending_updates=True)
            await asyncio.sleep(1)
            if webhook_full_url:
                await app.bot.set_webhook(url=webhook_full_url)
            return web.Response(text="Webhook resetado", status=200)
        except Exception as e:
            return web.Response(text="Erro: " + str(e), status=500)

    web_app = web.Application()
    web_app.router.add_post(webhook_path, webhook_handler)
    web_app.router.add_get("/", health_handler)
    web_app.router.add_get("/health", health_handler)
    web_app.router.add_get("/reset-webhook", reset_webhook_handler)

    runner = web.AppRunner(web_app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", PORT)
    await site.start()
    logger.info("Servidor HTTP na porta " + str(PORT))

    while True:
        await asyncio.sleep(3600)


if __name__ == "__main__":
    asyncio.run(main())
