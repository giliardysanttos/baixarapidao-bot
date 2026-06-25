#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🤖 Telegram Video Downloader Bot
Baixa vídeos de: YouTube, TikTok, Instagram, Twitter/X, Facebook, Reddit,
Vimeo, Dailymotion, e outras 1000+ plataformas suportadas pelo yt-dlp.

Autor: Gerado por IA | Requisitos: python-telegram-bot >=20, yt-dlp
"""

import os
import re
import asyncio
import tempfile
import logging
from pathlib import Path

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)
import yt_dlp

# ─── CONFIGURAÇÕES ───────────────────────────────────────────────
TOKEN = os.getenv("BOT_TOKEN", "SEU_TOKEN_AQUI")
MAX_FILE_SIZE_MB = 49  # Limite do Telegram para bots (50MB)
MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024

# Diretório temporário para downloads
TEMP_DIR = Path(tempfile.gettempdir()) / "tg_bot_downloads"
TEMP_DIR.mkdir(exist_ok=True)

# Logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# ─── COMANDOS ────────────────────────────────────────────────────

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Mensagem de boas-vindas."""
    user = update.effective_user
    await update.message.reply_html(
        f"👋 <b>Olá, {user.first_name}!</b>

"
        f"🎬 <b>Video Downloader Bot</b>
"
        f"Envie qualquer link de vídeo e eu baixo para você.

"
        f"✅ <b>Plataformas suportadas:</b>
"
        f"• YouTube | TikTok | Instagram
"
        f"• Twitter/X | Facebook | Reddit
"
        f"• Vimeo | Dailymotion | +1000 sites

"
        f"📏 <b>Limite:</b> até {MAX_FILE_SIZE_MB}MB por arquivo
"
        f"⚡ <b>Comandos:</b> /start /help /status",
        disable_web_page_preview=True,
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Ajuda."""
    await update.message.reply_text(
        "📖 <b>Como usar:</b>
"
        "1. Copie o link do vídeo
"
        "2. Cole aqui no chat
"
        "3. Aguarde o download e envio

"
        "⚠️ <b>Observações:</b>
"
        "• Vídeos muito longos podem exceder o limite de 50MB
"
        "• Stories do Instagram precisam de login (não suportado)
"
        "• Reels e posts públicos funcionam normalmente

"
        "🛠 <b>Comandos:</b>
"
        "/start - Iniciar o bot
"
        "/help - Esta mensagem
"
        "/status - Verificar status do bot",
        parse_mode="HTML",
    )


async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Status do bot."""
    await update.message.reply_text(
        "🟢 <b>Bot Online</b>
"
        "📥 Pronto para baixar vídeos
"
        "🔧 yt-dlp ativo | Limite: 50MB",
        parse_mode="HTML",
    )


# ─── DOWNLOAD E ENVIO ──────────────────────────────────────────

def progress_hook(d, chat_id, app):
    """Hook de progresso do yt-dlp (executado em thread separada)."""
    if d["status"] == "downloading":
        percent = d.get("_percent_str", "0%")
        speed = d.get("_speed_str", "N/A")
        logger.info(f"[{chat_id}] Downloading: {percent} @ {speed}")


async def download_video(url: str, chat_id: int, app) -> Path:
    """Baixa o vídeo usando yt-dlp e retorna o caminho do arquivo."""

    # Nome único baseado no chat_id + timestamp
    import time
    unique_id = f"{chat_id}_{int(time.time() * 1000)}"
    output_path = TEMP_DIR / f"{unique_id}.%(ext)s"

    ydl_opts = {
        "format": "best[filesize<50M] / best[filesize_approx<50M] / best",
        "outtmpl": str(output_path),
        "quiet": True,
        "no_warnings": True,
        "merge_output_format": "mp4",
        "postprocessors": [
            {
                "key": "FFmpegVideoConvertor",
                "preferedformat": "mp4",
            }
        ],
        "progress_hooks": [lambda d: progress_hook(d, chat_id, app)],
    }

    # Para TikTok/Instagram, forçar formato que funcione
    if "tiktok" in url or "instagram" in url:
        ydl_opts["format"] = "best"
        ydl_opts["addheaders"] = [
            ("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
        ]

    downloaded_file = None

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        # Pega o arquivo real que foi baixado
        if info:
            # Tenta encontrar o arquivo pelo template
            expected = str(output_path).replace(".%(ext)s", ".*")
            import glob
            matches = glob.glob(expected)
            if matches:
                downloaded_file = Path(matches[0])
            else:
                # Fallback: procura no diretório temp
                for f in TEMP_DIR.glob(f"{unique_id}*"):
                    if f.is_file():
                        downloaded_file = f
                        break

    if not downloaded_file or not downloaded_file.exists():
        raise FileNotFoundError("Arquivo não foi baixado corretamente")

    return downloaded_file


async def handle_url(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Processa links enviados pelo usuário."""
    message = update.message
    url = message.text.strip()
    chat_id = message.chat_id

    # Regex para detectar URLs de vídeo
    url_pattern = re.compile(
        r"https?://(?:www\.)?(?:youtube\.com|youtu\.be|tiktok\.com|"
        r"instagram\.com|twitter\.com|x\.com|facebook\.com|fb\.watch|"
        r"reddit\.com|vimeo\.com|dailymotion\.com|threads\.net)/[^\s]+"
    )

    if not url_pattern.search(url):
        await message.reply_text(
            "❌ Isso não parece ser um link de vídeo suportado.
"
            "Envie links de: YouTube, TikTok, Instagram, Twitter/X, Facebook, etc."
        )
        return

    # Mensagem de "processando"
    processing_msg = await message.reply_text("⏳ Analisando link...")

    try:
        # Baixa o vídeo
        await processing_msg.edit_text("📥 Baixando vídeo, aguarde...")

        loop = asyncio.get_event_loop()
        video_path = await loop.run_in_executor(
            None, lambda: asyncio.run(download_video(url, chat_id, context.application))
        )

        # Verifica tamanho
        file_size = video_path.stat().st_size
        if file_size > MAX_FILE_SIZE_BYTES:
            await processing_msg.edit_text(
                f"⚠️ O vídeo tem <b>{file_size / 1024 / 1024:.1f}MB</b> e excede o limite de "
                f"<b>{MAX_FILE_SIZE_MB}MB</b> do Telegram.
"
                f"Tente um vídeo mais curto ou com menor resolução.",
                parse_mode="HTML",
            )
            # Limpa arquivo
            video_path.unlink(missing_ok=True)
            return

        # Envia o vídeo
        await processing_msg.edit_text("📤 Enviando vídeo para você...")

        with open(video_path, "rb") as video_file:
            await message.reply_video(
                video=video_file,
                caption=f"✅ <b>Download concluído!</b>
"
                        f"📏 Tamanho: <b>{file_size / 1024 / 1024:.1f}MB</b>
"
                        f"🔗 Fonte: {url[:60]}...",
                parse_mode="HTML",
                supports_streaming=True,
            )

        await processing_msg.delete()

    except yt_dlp.utils.DownloadError as e:
        logger.error(f"Download error: {e}")
        error_msg = str(e)
        if "Private" in error_msg or "login" in error_msg.lower():
            await processing_msg.edit_text(
                "🔒 Este conteúdo é privado ou requer login.
"
                "Tente um link público."
            )
        elif "Unsupported URL" in error_msg:
            await processing_msg.edit_text(
                "❌ URL não suportada ou inválida.
"
                "Verifique o link e tente novamente."
            )
        else:
            await processing_msg.edit_text(
                f"❌ Erro ao baixar: {error_msg[:200]}"
            )
    except Exception as e:
        logger.exception("Erro inesperado")
        await processing_msg.edit_text(
            f"❌ Erro inesperado: {str(e)[:200]}
"
            f"Tente novamente mais tarde."
        )
    finally:
        # Limpa arquivos temporários
        try:
            if 'video_path' in locals() and video_path.exists():
                video_path.unlink(missing_ok=True)
        except Exception:
            pass


# ─── MAIN ───────────────────────────────────────────────────────

def main() -> None:
    """Inicia o bot."""
    if TOKEN == "SEU_TOKEN_AQUI":
        print("❌ ERRO: Configure a variável BOT_TOKEN no .env ou no código!")
        print("   Exemplo: export BOT_TOKEN='123456:ABC-DEF...'")
        return

    app = Application.builder().token(TOKEN).build()

    # Handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("status", status_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_url))

    logger.info("🤖 Bot iniciado! Aguardando mensagens...")

    # Inicia polling
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
