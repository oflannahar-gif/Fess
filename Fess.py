from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
    ContextTypes,
)
import os
import re
import time
import json
import unicodedata
from datetime import datetime
from dotenv import load_dotenv

# =========================================================
# 🔧 KONFIGURASI
# =========================================================
load_dotenv("Token.env")
TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_ID = int(os.getenv("CHANNEL_ID"))
CHANNEL_USERNAME = os.getenv("CHANNEL_USERNAME")
ADMINS = [7480707710]  # Ganti dengan ID kamu

VIOLATOR_FILE = "violators.json"
BADWORDS_FILE = "badwords.txt"

# Cooldown dalam detik
COOLDOWN_SECONDS = 600  # 10 menit

# =========================================================
# 📌 KONSTANTA FORMAT MENFESS
# =========================================================
MENFESS_PATTERN = re.compile(
    r"^Dibalik Masker\s*:\s*(.+)\n"
    r"Target\s*:\s*(.+)\n"
    r"Ungkapan\s*:\s*(.+)",
    re.DOTALL | re.IGNORECASE
)

MENFESS_FORMAT_HELP_TEXT = (
    "❌ Format salah.\n\nGunakan format berikut:\n\n"
    "`Dibalik Masker : \nTarget : \nUngkapan : \n`"
)

MENFESS_SUCCESS_REPLY = (
    "✅ Pssst... Pesanmu telah dilepaskan dari balik bayang. Kini biarlah mereka membacanya… tanpa tahu siapa yang menulisnya!\n\n"
    "°❀⋆.ೃ࿔*:･°❀⋆.ೃ࿔*:･"
)

CONFIRM_DELETE_TEXT = "Apakah kamu yakin ingin menghapus pesan ini?"

# =========================================================
# 🔐 SISTEM WARNING & BAN
# =========================================================
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


def add_warning(user_id: int, username: str, badword: str, full_msg: str):
    """Tambah warning ke user + catat detail pelanggaran."""
    data = load_violators()
    user_id_str = str(user_id)
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    if user_id_str not in data:
        data[user_id_str] = {
            "username": username,
            "warnings": 0,
            "banned": False,
            "violations": []
        }

    # Tambahkan pelanggaran baru
    user_data = data[user_id_str]
    user_data["warnings"] += 1
    user_data["violations"].append({
        "word": badword,
        "message": full_msg,
        "timestamp": now
    })

    # Blokir kalau sudah 3x
    if user_data["warnings"] >= 3:
        user_data["banned"] = True

    save_violators(data)
    return user_data["warnings"], user_data["banned"]


def is_banned(user_id: int) -> bool:
    data = load_violators()
    user = data.get(str(user_id))
    return bool(user and user.get("banned"))


# =========================================================
# 🧠 FILTER KATA KOTOR
# =========================================================
# baca file badwords.txt
with open(BADWORDS_FILE, "r", encoding="utf-8") as f:
    BAD_WORDS = [line.strip().lower() for line in f if line.strip()]


def super_clean_text(text: str) -> str:
    """Normalisasi teks untuk deteksi kata kotor."""
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

    # Sisakan huruf/angka/spasi
    text = re.sub(r'[^a-z0-9\s]', '', text)
    return text


def escape_markdown(text: str) -> str:
    """Melindungi karakter spesial agar tidak error di Markdown."""
    escape_chars = r"\_*[]()~`>#+-=|{}.!"
    for ch in escape_chars:
        text = text.replace(ch, f"\\{ch}")
    return text


def contains_badword(message: str, badwords: list):
    """Cek apakah pesan mengandung kata kotor secara utuh (bukan di dalam kata lain)."""
    cleaned = super_clean_text(message)
    for word in badwords:
        word_cleaned = super_clean_text(word)
        # hanya deteksi kata utuh (pakai boundary \b)
        if re.search(rf"\b{re.escape(word_cleaned)}\b", cleaned):
            print(f"[DEBUG] Kata terdeteksi: {word} -> {message}")
            return word
    return None


# =========================================================
# 🔘 INLINE KEYBOARD BUILDER
# =========================================================
def build_channel_message_url(message_id: int) -> str:
    """
    Buat URL ke pesan channel.
    Pastikan CHANNEL_USERNAME berisi '@nama_channel' atau 'nama_channel'.
    """
    username = CHANNEL_USERNAME.lstrip('@')
    return f"https://t.me/{username}/{message_id}"


def build_initial_keyboard(message_id: int) -> InlineKeyboardMarkup:
    """Keyboard awal: Lihat Pesan + Hapus Pesan."""
    url = build_channel_message_url(message_id)
    keyboard = [
        [InlineKeyboardButton("👀 Lihat Pesan", url=url)],
        [InlineKeyboardButton("🗑 Hapus Pesan", callback_data=f"del:{message_id}"),]
    ]
    return InlineKeyboardMarkup(keyboard)


def build_confirm_keyboard(message_id: int) -> InlineKeyboardMarkup:
    """Keyboard konfirmasi hapus."""
    url = build_channel_message_url(message_id)
    keyboard = [
        [InlineKeyboardButton("👀 Lihat Pesan", url=url)],
        [InlineKeyboardButton("✅ Ya, Saya Yakin", callback_data=f"del_yes:{message_id}")],
        [InlineKeyboardButton("⬅ Kembali", callback_data=f"del_back:{message_id}")],
    ]
    return InlineKeyboardMarkup(keyboard)


# =========================================================
# ⚙️ SISTEM BOT
# =========================================================
user_last_sent: dict[int, float] = {}


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


async def check_membership(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    user_id = update.effective_user.id
    try:
        member = await context.bot.get_chat_member(CHANNEL_USERNAME, user_id)
        if member.status in ["left", "kicked"]:
            await update.message.reply_text(f"⚠️ Kamu harus join channel {CHANNEL_USERNAME} dulu!")
            return False
        return True
    except Exception:
        await update.message.reply_text(
            "⚠️ Gagal mengecek status keanggotaan channel. Pastikan bot sudah admin di channel."
        )
        return False


async def process_menfess_text(
    user_id: int,
    username: str,
    user_text: str,
    context: ContextTypes.DEFAULT_TYPE,
    update: Update,
    photo: str | None = None
):
    now = time.time()

    # 🚫 cek banned
    if is_banned(user_id):
        await update.message.reply_text("🚫 Kamu telah diblokir karena berulang kali melanggar aturan.")
        return

    # cek cooldown (10 menit)
    if user_id not in ADMINS:
        if user_id in user_last_sent:
            elapsed = now - user_last_sent[user_id]
            if elapsed < COOLDOWN_SECONDS:
                remaining = int((COOLDOWN_SECONDS - elapsed) / 60) + 1
                await update.message.reply_text(
                    f"⏳ Tunggu {remaining} menit lagi sebelum kirim menfess berikutnya."
                )
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
    match = MENFESS_PATTERN.match(user_text)
    if not match:
        await update.message.reply_text(MENFESS_FORMAT_HELP_TEXT, parse_mode="Markdown")
        return

    dibalik_masker, target, ungkapan = match.groups()
    caption = (
        f"📩 *Menfess Baru*\n\n"
        f"Dibalik Masker : {dibalik_masker.strip()}\n"
        f"Target : {target.strip()}\n"
        f"Ungkapan : {ungkapan.strip()}"
    )

    # kirim ke channel — jika ada foto, kirim foto + caption
    if photo:
        sent = await context.bot.send_photo(
            chat_id=CHANNEL_ID,
            photo=photo,
            caption=caption,
            parse_mode="Markdown"
        )
    else:
        sent = await context.bot.send_message(
            chat_id=CHANNEL_ID,
            text=caption,
            parse_mode="Markdown"
        )

    channel_message_id = sent.message_id
    user_last_sent[user_id] = now

    # kirim balasan ke user dengan tombol inline
    keyboard = build_initial_keyboard(channel_message_id)
    await update.message.reply_text(MENFESS_SUCCESS_REPLY, reply_markup=keyboard)


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
            if elapsed < COOLDOWN_SECONDS:
                remaining = int((COOLDOWN_SECONDS - elapsed) / 60) + 1
                await update.message.reply_text(
                    "⏳ Kamu hanya bisa kirim 1 menfess setiap 10 menit.\n"
                    f"Tunggu sekitar {remaining} menit lagi ya."
                )
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
    match = MENFESS_PATTERN.match(user_text)
    if not match:
        await update.message.reply_text(MENFESS_FORMAT_HELP_TEXT, parse_mode="Markdown")
        return

    dibalik_masker, target, ungkapan = match.groups()
    text = (
        f"📩 *Menfess Baru*\n\n"
        f"Dibalik Masker : {dibalik_masker.strip()}\n"
        f"Target : {target.strip()}\n"
        f"Ungkapan : {ungkapan.strip()}"
    )

    # kirim ke channel
    sent = await context.bot.send_message(chat_id=CHANNEL_ID, text=text, parse_mode="Markdown")

    channel_message_id = sent.message_id
    user_last_sent[user_id] = now

    # balasan ke user + tombol
    keyboard = build_initial_keyboard(channel_message_id)
    await update.message.reply_text(MENFESS_SUCCESS_REPLY, reply_markup=keyboard)


# 🔹 Handler foto + caption
async def menfess_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    caption = update.message.caption
    user_id = update.effective_user.id
    username = update.effective_user.username or "-"

    # cek membership
    if not await check_membership(update, context):
        return

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
        banned_flag = "🚫" if info.get("banned") else "⚠️"
        last_word = info["violations"][-1]["word"] if info["violations"] else "-"
        text_list.append(
            f"{banned_flag} `{uid}` ({username}) — {warnings}x pelanggaran\nTerakhir: {last_word}"
        )

    text = "\n\n".join(text_list)
    await update.message.reply_text(f"📋 *Daftar Pelanggar:*\n\n{text}", parse_mode="Markdown")


# =========================================================
# 🔁 CALLBACK UNTUK TOMBOL INLINE
# =========================================================
async def menfess_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    data = query.data or ""

    # del:<message_id>
    if data.startswith("del:"):
        msg_id = int(data.split(":")[1])
        keyboard = build_confirm_keyboard(msg_id)
        await query.edit_message_text(CONFIRM_DELETE_TEXT, reply_markup=keyboard)

    # del_back:<message_id>
    elif data.startswith("del_back:"):
        msg_id = int(data.split(":")[1])
        keyboard = build_initial_keyboard(msg_id)
        await query.edit_message_text(MENFESS_SUCCESS_REPLY, reply_markup=keyboard)

    # del_yes:<message_id>
    elif data.startswith("del_yes:"):
        msg_id = int(data.split(":")[1])
        # coba hapus pesan di channel
        try:
            await context.bot.delete_message(chat_id=CHANNEL_ID, message_id=msg_id)
            await query.edit_message_text("✅ Pesanmu di channel sudah dihapus.")
        except Exception:
            # kalau gagal (misalnya sudah dihapus manual)
            await query.edit_message_text(
                "⚠️ Gagal menghapus pesan di channel. Mungkin pesan sudah dihapus sebelumnya."
            )


def main():
    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("violators", violators))
    app.add_handler(MessageHandler(filters.PHOTO, menfess_photo))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, menfess))
    app.add_handler(CallbackQueryHandler(menfess_callback))

    print("Bot menfess berjalan...")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
