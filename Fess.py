from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler)
import os
from dotenv import load_dotenv
import re
import time
import json


load_dotenv("token.env")                            # baca file token.env
TOKEN = os.getenv("BOT_TOKEN")                      # Ganti dengan token bot kamu
CHANNEL_ID = int(os.getenv("CHANNEL_ID"))           # Ganti dengan ID channel kamu (format biasanya -100xxxxxxxxxx)
CHANNEL_USERNAME = os.getenv("CHANNEL_USERNAME")    # username channel kamu
ADMINS = [1660366579,]                              # ganti dengan Telegram ID admin kamu


# =========================================================
# 🔐 FITUR TAMBAHAN: SISTEM WARNING & BAN USER
# =========================================================

VIOLATOR_FILE = "violators.json"

def load_violators():
    """Memuat data pelanggar dari file JSON"""
    if os.path.exists(VIOLATOR_FILE):
        with open(VIOLATOR_FILE, "r", encoding="utf-8") as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return {}
    return {}

def save_violators(data):
    """Menyimpan data pelanggar ke file JSON"""
    with open(VIOLATOR_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def add_warning(user_id: int, username: str):
    """Menambah warning ke user. Return tuple (warnings, banned_status)."""
    data = load_violators()
    user_id = str(user_id)

    if user_id not in data:
        data[user_id] = {"username": username, "warnings": 0, "banned": False}

    # tambah warning
    data[user_id]["warnings"] += 1

    # jika warning >= 3 maka banned
    if data[user_id]["warnings"] >= 3:
        data[user_id]["banned"] = True

    save_violators(data)
    return data[user_id]["warnings"], data[user_id]["banned"]

def is_banned(user_id: int):
    """Cek apakah user sudah diban"""
    data = load_violators()
    user = data.get(str(user_id))
    if user and user.get("banned"):
        return True
    return False


# =========================================================
# BAGIAN SCRIPT ASLI
# =========================================================

# baca daftar kata terlarang dari file
with open("badwords.txt", "r", encoding="utf-8") as f:
    BAD_WORDS = [line.strip().lower() for line in f if line.strip()]

# mapping huruf mirip
LEET_MAP = {
    "4": "a", "@": "a",
    "1": "i", "!": "i", "|": "i",
    "3": "e",
    "5": "s", "$": "s",
    "0": "o",
    "7": "t"
}

def normalize_text(text: str) -> str:
    text = text.lower()
    # ganti huruf leetspeak
    for k, v in LEET_MAP.items():
        text = text.replace(k, v)
    # hapus huruf berulang lebih dari 2
    text = re.sub(r"(.)\1{2,}", r"\1", text)
    return text

def contains_badword(text: str, badwords: list) -> bool:
    norm = normalize_text(text)
    for bad in badwords:
        pattern = r"\b" + re.escape(bad) + r"\b"
        if re.search(pattern, norm):
            return True
    return False

# simpan waktu terakhir tiap user kirim menfess
user_last_sent = {}


# Command /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "===== ___\n\n"
        "🕯️ Selamat datang di Masker FESS — tempat rahasia menjadi suara.\n\n"
        "Di sini, kamu tidak perlu menjadi siapa-siapa.  \n"
        "Cukup kirimkan pesanmu ke bot ini, dan kami akan menyampaikannya ke dunia — tanpa nama, tanpa jejak.\n\n"
        "⚠️ Penting: Hanya anggota channel yang bisa berbicara lewat bot ini.  \n"
        "Masuk ke bayangan. Gabung dengan mereka yang bersuara di balik sunyi.\n\n"
        "Cara kerja:  \n"
        "Tulis. Kirim. Lepaskan.  \n"
        "Biarkan bot membawa pesanmu ke permukaan.\n\n"
        "Peraturan di balik layar:\n\n"
        "1. Satu suara setiap 5 menit. Jangan biarkan kebisingan mengaburkan yang penting.  \n"
        "2. Tidak ada tempat untuk spam. Hening lebih baik daripada kekacauan.  \n"
        "3. Jangan bawa politik, SARA, atau kebencian ke dalam ruang ini.  \n\n"
        "   Baca panduan lengkap di sini: https://t.me/Maskerfess/3\n"
        "   Form : https://t.me/Maskerfess/4\n\n"
        "Topeng sudah terpasang.  \n"
        "Sekarang saatnya bicara.\n\n"
        "___ ====="
    )
    await update.message.reply_text(text, parse_mode="Markdown")


# Fungsi cek membership
async def check_membership(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    try:
        member = await context.bot.get_chat_member(CHANNEL_USERNAME, user_id)
        if member.status in ["left", "kicked"]:
            await update.message.reply_text(
                f"⚠️ Kamu harus join channel {CHANNEL_USERNAME} dulu!"
            )
            return False
        return True
    except:
        await update.message.reply_text(
            "⚠️ Gagal mengecek status keanggotaan channel. "
            "Pastikan bot sudah admin di channel."
        )
        return False



# Handler pesan user
async def menfess(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    username = update.effective_user.username or "-"
    
    # 🚫 Cek apakah user dibanned
    if is_banned(user_id):
        await update.message.reply_text(
            "🚫 Kamu telah diblokir karena berulang kali melanggar aturan."
        )
        return

    # cek membership channel dulu
    if not await check_membership(update, context):
        return  # hentikan jika belum join
        
    user_text = update.message.text.strip()
    now = time.time()

    # cek jeda 10 menit, kecuali admin
    if user_id not in ADMINS:
        if user_id in user_last_sent:
            elapsed = now - user_last_sent[user_id]
            if elapsed < 600:  # 600 detik = 10 menit
                remaining = int((600 - elapsed) / 60) + 1
                await update.message.reply_text(
                    f"⏳ Kamu hanya bisa kirim 1 menfess setiap 10 menit.\n"
                    f"Tunggu sekitar {remaining} menit lagi ya."
                )
                return

    # 🚨 CEK KATA TERLARANG
    if contains_badword(user_text, BAD_WORDS):
        warnings, banned = add_warning(user_id, username)
        if banned:
            await update.message.reply_text(
                "🚫 Kamu telah diblokir karena 3 kali melanggar aturan. "
                "Kamu tidak bisa lagi menggunakan bot ini."
            )
        else:
            await update.message.reply_text(
                f"⚠️ Pesanmu mengandung kata yang tidak pantas.\n"
                f"Ini peringatan ke-{warnings} dari 3. "
                "Jika kamu melanggar lagi, kamu akan diblokir."
            )
        return


    # Regex untuk cek format wajib
    pattern = (
        r"^Dibalik Masker\s*:\s*(.+)\n"     # grup 1 = Dibalik Masker
        r"Target\s*:\s*(.+)\n"               # grup 2 = Target
        r"Ungkapan\s*:\s*(.+)"               # grup 3 = Ungkapan
    )

    match = re.match(pattern, user_text, re.DOTALL | re.IGNORECASE)
    if not match:
        await update.message.reply_text(
            "❌ Format salah.\n\n"
            "Gunakan format berikut:\n\n"
            "`"
            "Dibalik Masker : \n"
            "Target : \n"
            "Ungkapan : \n"
            "`",
            parse_mode="Markdown"
        )
        return

    dibalik_masker = match.group(1).strip()
    target = match.group(2).strip()
    ungkapan = match.group(3).strip()

    # kirim ke channel
    text = (
        "📩 *Menfess Baru*\n\n"
        f"Dibalik Masker : {dibalik_masker}\n"
        f"Target : {target}\n"
        f"Ungkapan : {ungkapan}"
    )
    await context.bot.send_message(chat_id=CHANNEL_ID, text=text, parse_mode="Markdown")

    # update waktu terakhir user kirim
    user_last_sent[user_id] = now

    # konfirmasi ke user
    await update.message.reply_text("✅ Pssst... Pesanmu telah dilepaskan dari balik bayang. Kini biarlah mereka membacanya… tanpa tahu siapa yang menulisnya!")


def main():
    app = Application.builder().token(TOKEN).build()

    # daftar handler
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, menfess))

    # jalankan polling
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
# bot.py
