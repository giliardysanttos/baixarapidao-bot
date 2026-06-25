# 🤖 Telegram Video Downloader Bot

Bot para Telegram que baixa vídeos de praticamente qualquer rede social.

## ✅ Plataformas Suportadas

- **YouTube** (vídeos, shorts)
- **TikTok** (vídeos, sem watermark)
- **Instagram** (Reels, posts públicos)
- **Twitter / X** (posts com vídeo)
- **Facebook** (vídeos públicos)
- **Reddit** (vídeos de posts)
- **Vimeo**, **Dailymotion**, **Threads**, e **+1000 sites**

## 🚀 Instalação Rápida

### 1. Pré-requisitos

- Python 3.9+
- FFmpeg (para conversão de vídeo)

**Instalar FFmpeg:**
```bash
# Ubuntu/Debian
sudo apt update && sudo apt install ffmpeg -y

# macOS
brew install ffmpeg

# Windows (com chocolatey)
choco install ffmpeg
```

### 2. Configurar o Bot no Telegram

1. Vá até [@BotFather](https://t.me/BotFather) no Telegram
2. Envie `/newbot`
3. Dê um nome e username para o bot
4. Copie o **token** fornecido

### 3. Instalar e Rodar

```bash
# Clone ou baixe os arquivos
cd telegram-video-bot

# Crie ambiente virtual (recomendado)
python -m venv venv

# Ative (Linux/Mac)
source venv/bin/activate
# Ative (Windows)
venv\Scripts\activate

# Instale dependências
pip install -r requirements.txt

# Configure o token
# Linux/Mac:
export BOT_TOKEN="SEU_TOKEN_AQUI"
# Windows:
set BOT_TOKEN=SEU_TOKEN_AQUI

# Rode o bot
python bot.py
```

## ☁️ Deploy Gratuito (Render.com)

1. Crie conta em [render.com](https://render.com)
2. New → Web Service → Connect repo (GitHub/GitLab)
3. Configure:
   - **Runtime:** Python 3
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `python bot.py`
   - **Environment Variable:** `BOT_TOKEN` = seu token
4. Deploy!

> ⚠️ No plano gratuito, o serviço "dorme" após inatividade. Para manter ativo, use um serviço de ping (UptimeRobot) ou upgrade.

## 📋 Comandos do Bot

| Comando | Descrição |
|---------|-----------|
| `/start` | Inicia o bot e mostra boas-vindas |
| `/help` | Mostra ajuda e instruções |
| `/status` | Verifica se o bot está online |

## ⚠️ Limitações

- **Limite de 50MB** por arquivo (restrição do Telegram para bots)
- Conteúdo privado (stories, posts fechados) não são acessíveis
- Vídeos muito longos em alta resolução podem exceder o limite

## 🔧 Solução de Problemas

**Erro: "FFmpeg not found"**
→ Instale o FFmpeg no sistema (veja passo 1)

**Erro: "Private video"**
→ O vídeo é privado. Use links públicos.

**Bot não responde**
→ Verifique se o token está correto e o bot está rodando.

---

Desenvolvido com Python + python-telegram-bot + yt-dlp 🐍
