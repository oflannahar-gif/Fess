from telegram import Update, InputFile
from telegram.ext import (Application, CommandHandler, MessageHandler, filters, ContextTypes)
import os
from dotenv import load_dotenv
import re
import time
import json
import unicodedata
from datetime import datetime


# =========================================================
# 🔧 KONFIGURASI
# =========================================================
load_dotenv("Token.env")
TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_ID = int(os.getenv("CHANNEL_ID"))
CHANNEL_USERNAME = os.getenv("CHANNEL_USERNAME")
ADMINS = [7480707710,]  # Ganti dengan ID kamu

# =========================================================
# 🔐 SISTEM WARNING & BAN
# =========================================================
VIOLATOR_FILE = "violators.json"

def load_violators():
    if os.path.exists(VIOLATOR_FILE):
        with open(VIOLATOR_FILE, "r", encoding="utf-8") as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return {}
    return {}

def save_violators(data):
    with open(VIOLATOR_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

from datetime import datetime

def add_warning(user_id: int, username: str, badword: str, full_msg: str):
    """Tambah warning ke user + catat detail pelanggaran."""
    data = load_violators()
    user_id = str(user_id)
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    if user_id not in data:
        data[user_id] = {
            "username": username,
            "warnings": 0,
            "banned": False,
            "violations": []
        }

    # Tambahkan pelanggaran baru
    data[user_id]["warnings"] += 1
    data[user_id]["violations"].append({
        "word": badword,
        "message": full_msg,
        "timestamp": now
    })

    # Blokir kalau sudah 3x
    if data[user_id]["warnings"] >= 3:
        data[user_id]["banned"] = True

    save_violators(data)
    return data[user_id]["warnings"], data[user_id]["banned"]


def is_banned(user_id: int):
    data = load_violators()
    user = data.get(str(user_id))
    return bool(user and user.get("banned"))

# =========================================================
# 🧠 FILTER KATA KOTOR
# =========================================================

# baca file badwords.txt
with open("badwords.txt", "r", encoding="utf-8") as f:
    BAD_WORDS = [line.strip().lower() for line in f if line.strip()]

# mapping huruf mirip
LEET_MAP = {
    "4": "a", "@": "a",
    "1": "i", "!": "i", "|": "i", "¡": "i",
    "3": "e",
    "5": "s", "$": "s",
    "0": "o",
    "7": "t",
    "9": "g"
}

def normalize_text(text: str) -> str:
    text = text.lower()
    for k, v in LEET_MAP.items():
        text = text.replace(k, v)
    text = re.sub(r"(.)\1{2,}", r"\1", text)  # hapus huruf berulang
    text = re.sub(r"[^a-zA-Z\s]", " ", text)  # hapus simbol
    return text

import re
import unicodedata

def super_clean_text(text: str) -> str:
    # Normalisasi unicode (misal: huruf tebal, miring, font unik jadi standar)
    text = unicodedata.normalize("NFKD", text)
    # Ubah ke huruf kecil
    text = text.lower()
    # Ganti huruf mirip (leetspeak dan font variasi)
    replacements = {
        '0': 'o', '1': 'i', '3': 'e', '4': 'a', '5': 's', '7': 't', '@': 'a',
        '$': 's', '!': 'i', '|': 'i', '+': 't', '(': 'c', ')': 'c',
        '{': 'c', '}': 'c', '[': 'c', ']': 'c',
        'ᴏ': 'o', 'ʟ': 'l', 'ᴀ': 'a', 'ᴋ': 'k', 'ɴ': 'n', 'ᴅ': 'd', 'ʀ': 'r',
        'ʙ': 'b', 'ʜ': 'h', 'ɢ': 'g', 'ɪ': 'i', 'ꜱ': 's', 'ᴛ': 't',
        'ᴍ': 'm', 'ɯ': 'm', 'ʏ': 'y', 'ɾ': 'r', 'ᴘ': 'p', 'ꞯ': 'n'
    }
    for key, val in replacements.items():
        text = text.replace(key, val)

    # ✅ benar — sisakan spasi agar kata tidak menempel
    text = re.sub(r'[^a-z0-9\s]', '', text)
    return text



def escape_markdown(text: str) -> str:
    """Melindungi karakter spesial agar tidak error di Markdown."""
    escape_chars = r"\_*[]()~`>#+-=|{}.!"
    for ch in escape_chars:
        text = text.replace(ch, f"\\{ch}")
    return text

def contains_badword(message: str, badwords: list):
    """Kembalikan kata kotor yang terdeteksi, atau None jika aman."""
    cleaned = super_clean_text(message)
    for word in badwords:
        word_cleaned = super_clean_text(word)
        if word_cleaned in cleaned:
            print(f"[DEBUG] Kata terdeteksi: {word} -> {message}")
            return word  # ⬅️ Kembalikan kata yang ditemukan
    return None



# =========================================================
# ⚙️ SISTEM BOT
# =========================================================

user_last_sent = {}

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

async def check_membership(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    try:
        member = await context.bot.get_chat_member(CHANNEL_USERNAME, user_id)
        if member.status in ["left", "kicked"]:
            await update.message.reply_text(f"⚠️ Kamu harus join channel {CHANNEL_USERNAME} dulu!")
            return False
        return True
    except:
        await update.message.reply_text("⚠️ Gagal mengecek status keanggotaan channel. Pastikan bot sudah admin di channel.")
        return False

async def process_menfess_text(user_id, username, user_text, context, update, photo=None):
    now = time.time()

    # 🚫 cek banned
    if is_banned(user_id):
        await update.message.reply_text("🚫 Kamu telah diblokir karena berulang kali melanggar aturan.")
        return

    # cek cooldown (10 menit)
    if user_id not in ADMINS:
        if user_id in user_last_sent:
            elapsed = now - user_last_sent[user_id]
            if elapsed < 600:
                remaining = int((600 - elapsed) / 60) + 1
                await update.message.reply_text(f"⏳ Tunggu {remaining} menit lagi sebelum kirim menfess berikutnya.")
                return

    # 🚨 cek badword
    detected_word = contains_badword(user_text, BAD_WORDS)
    if detected_word:
        warnings, banned = add_warning(user_id, username, detected_word, user_text)
        safe_word = escape_markdown(detected_word)
        if banned:
            await update.message.reply_text(
                f"🚫 Kamu telah diblokir karena 3 pelanggaran.\nKata terakhir yang melanggar: `{safe_word}`",
                parse_mode="Markdown"
            )
        else:
            await update.message.reply_text(
                f"⚠️ Pesanmu mengandung kata tidak pantas: `{safe_word}`\nPeringatan ke-{warnings} dari 3.",
                parse_mode="Markdown"
            )
        return

    # cek format menfess
    pattern = (
        r"^Dibalik Masker\s*:\s*(.+)\n"
        r"Target\s*:\s*(.+)\n"
        r"Ungkapan\s*:\s*(.+)"
    )
    match = re.match(pattern, user_text, re.DOTALL | re.IGNORECASE)
    if not match:
        await update.message.reply_text(
            "❌ Format salah.\nGunakan format berikut:\n\n"
            "`Dibalik Masker : \nTarget : \nUngkapan : \n`",
            parse_mode="Markdown"
        )
        return

    dibalik_masker, target, ungkapan = match.groups()
    caption = f"📩 *Menfess Baru*\n\nDibalik Masker : {dibalik_masker.strip()}\nTarget : {target.strip()}\nUngkapan : {ungkapan.strip()}"

    # kirim ke channel — jika ada foto, kirim foto + caption
    if photo:
        await context.bot.send_photo(chat_id=CHANNEL_ID, photo=photo, caption=caption, parse_mode="Markdown")
    else:
        await context.bot.send_message(chat_id=CHANNEL_ID, text=caption, parse_mode="Markdown")

    user_last_sent[user_id] = now
    await update.message.reply_text("✅ Pssst... Pesanmu telah dilepaskan dari balik bayang. Kini biarlah mereka membacanya… tanpa tahu siapa yang menulisnya!")


async def menfess(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    username = update.effective_user.username or "-"

    # 🚫 cek ban
    if is_banned(user_id):
        await update.message.reply_text("🚫 Kamu telah diblokir karena berulang kali melanggar aturan.")
        return

    # cek membership
    if not await check_membership(update, context):
        return

    user_text = update.message.text.strip()
    now = time.time()

    # cek delay kirim
    if user_id not in ADMINS:
        if user_id in user_last_sent:
            elapsed = now - user_last_sent[user_id]
            if elapsed < 600:  # 10 menit
                remaining = int((600 - elapsed) / 60) + 1
                await update.message.reply_text(f"⏳ Kamu hanya bisa kirim 1 menfess setiap 10 menit.\nTunggu sekitar {remaining} menit lagi ya.")
                return

    # 🚨 filter badword
    detected_word = contains_badword(user_text, BAD_WORDS)
    if detected_word:
        warnings, banned = add_warning(user_id, username, detected_word, user_text)
        safe_word = escape_markdown(detected_word)
        if banned:
            await update.message.reply_text(
                f"🚫 Kamu telah diblokir karena 3 kali melanggar aturan.\n"
                f"Kata terakhir yang melanggar: `{safe_word}`",
                parse_mode="Markdown"
            )
        else:
            await update.message.reply_text(
                f"⚠️ Pesanmu mengandung kata yang tidak pantas: `{safe_word}`\n"
                f"Ini peringatan ke-{warnings} dari 3.",
                parse_mode="Markdown"
            )
        return



    # cek format
    pattern = (
        r"^Dibalik Masker\s*:\s*(.+)\n"
        r"Target\s*:\s*(.+)\n"
        r"Ungkapan\s*:\s*(.+)"
    )
    match = re.match(pattern, user_text, re.DOTALL | re.IGNORECASE)
    if not match:
        await update.message.reply_text(
            "❌ Format salah.\n\nGunakan format berikut:\n\n"
            "`Dibalik Masker : \nTarget : \nUngkapan : \n`",
            parse_mode="Markdown"
        )
        return

    dibalik_masker, target, ungkapan = match.groups()
    text = f"📩 *Menfess Baru*\n\nDibalik Masker : {dibalik_masker.strip()}\nTarget : {target.strip()}\nUngkapan : {ungkapan.strip()}"
    await context.bot.send_message(chat_id=CHANNEL_ID, text=text, parse_mode="Markdown")

    user_last_sent[user_id] = now
    await update.message.reply_text("✅ Pssst... Pesanmu telah dilepaskan dari balik bayang. Kini biarlah mereka membacanya… tanpa tahu siapa yang menulisnya!")

# 🔹 Handler foto + caption
async def menfess_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    caption = update.message.caption
    user_id = update.effective_user.id
    username = update.effective_user.username or "-"

    # kalau tidak ada caption, tolak
    if not caption:
        await update.message.reply_text("❌ Kirim foto dengan caption sesuai format menfess.")
        return

    # ambil file_id foto (foto paling besar)
    photo = update.message.photo[-1].file_id

    # lanjutkan ke fungsi yang sudah ada (menfess) tapi kirim caption + foto
    await process_menfess_text(user_id, username, caption, context, update, photo=photo)



async def violators(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in ADMINS:
        await update.message.reply_text("🚫 Kamu tidak memiliki izin untuk melihat data pelanggar.")
        return

    data = load_violators()
    if not data:
        await update.message.reply_text("✅ Belum ada pelanggar terdeteksi.")
        return

    text_list = []
    for uid, info in data.items():
        username = info.get("username", "-")
        warnings = info.get("warnings", 0)
        banned = "🚫" if info.get("banned") else "⚠️"
        last_word = info["violations"][-1]["word"] if info["violations"] else "-"
        text_list.append(f"{banned} `{uid}` ({username}) — {warnings}x pelanggaran\nTerakhir: {last_word}")

    text = "\n\n".join(text_list)
    await update.message.reply_text(f"📋 *Daftar Pelanggar:*\n\n{text}", parse_mode="Markdown")



def main():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("violators", violators))
    app.add_handler(MessageHandler(filters.PHOTO, menfess_photo))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, menfess))

    print("Bot menfess berjalan...")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
