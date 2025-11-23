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
import logging
from datetime import datetime
from dotenv import load_dotenv

# =========================================================
# 🔧 LOGGING
# =========================================================
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# =========================================================
# 🔧 KONFIGURASI
# =========================================================
load_dotenv("Token.env")
TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_ID = int(os.getenv("CHANNEL_ID"))
CHANNEL_USERNAME = os.getenv("CHANNEL_USERNAME")
GROUP_ID = int(os.getenv("GROUP_ID"))  # <-- pastikan ada di Token.env

ADMINS = [7480707710]  # Ganti dengan ID kamu

VIOLATOR_FILE = "violators.json"
BADWORDS_FILE = "badwords.txt"
MENFESS_FILE = "menfess_map.json"  # mapping menfess

COOLDOWN_SECONDS = 600  # 10 menit

# =========================================================
# 📌 KONSTANTA FORMAT MENFESS
# =========================================================
MENFESS_PATTERN = re.compile(
    r"^Dibalik Masker\s*:\s*(.+)\n"
    r"Target\s*:\s*(.+)\n"
    r"Ungkapan\s*:\s*(.+)",
    re.DOTALL | re.IGNORECASE,
)

MENFESS_FORMAT_HELP_TEXT = (
    "❌ Format salah.\n\nGunakan format berikut:\n\n"
    "`Dibalik Masker : \nTarget : \nUngkapan : \n`"
)

MENFESS_SUCCESS_REPLY = (
    "✅ Pssst... Pesanmu telah dilepaskan dari balik bayang. Kini biarlah mereka "
    "membacanya… tanpa tahu siapa yang menulisnya!\n\n"
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
    data = load_violators()
    user_id_str = str(user_id)
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    if user_id_str not in data:
        data[user_id_str] = {
            "username": username,
            "warnings": 0,
            "banned": False,
            "violations": [],
        }

    user_data = data[user_id_str]
    user_data["warnings"] += 1
    user_data["violations"].append(
        {"word": badword, "message": full_msg, "timestamp": now}
    )

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
with open(BADWORDS_FILE, "r", encoding="utf-8") as f:
    BAD_WORDS = [line.strip().lower() for line in f if line.strip()]


def super_clean_text(text: str) -> str:
    text = unicodedata.normalize("NFKD", text)
    text = text.lower()

    replacements = {
        "0": "o",
        "1": "i",
        "3": "e",
        "4": "a",
        "5": "s",
        "7": "t",
        "@": "a",
        "$": "s",
        "!": "i",
        "|": "i",
        "+": "t",
        "(": "c",
        ")": "c",
        "{": "c",
        "}": "c",
        "[": "c",
        "]": "c",
        "ᴏ": "o",
        "ʟ": "l",
        "ᴀ": "a",
        "ᴋ": "k",
        "ɴ": "n",
        "ᴅ": "d",
        "ʀ": "r",
        "ʙ": "b",
        "ʜ": "h",
        "ɢ": "g",
        "ɪ": "i",
        "ꜱ": "s",
        "ᴛ": "t",
        "ᴍ": "m",
        "ɯ": "m",
        "ʏ": "y",
        "ɾ": "r",
        "ᴘ": "p",
        "ꞯ": "n",
    }
    for key, val in replacements.items():
        text = text.replace(key, val)

    text = re.sub(r"[^a-z0-9\s]", "", text)
    return text


def escape_markdown(text: str) -> str:
    escape_chars = r"\_*[]()~`>#+-=|{}.!"
    for ch in escape_chars:
        text = text.replace(ch, f"\\{ch}")
    return text


def contains_badword(message: str, badwords: list):
    cleaned = super_clean_text(message)
    for word in badwords:
        word_cleaned = super_clean_text(word)
        if re.search(rf"\b{re.escape(word_cleaned)}\b", cleaned):
            logger.info("[DEBUG] Kata terdeteksi: %s -> %s", word, message)
            return word
    return None


# =========================================================
# 🗂️ MENFESS MAP (pakai teks dinormalisasi + group_root_id)
# =========================================================
def normalize_link_text(text: str) -> str:
    """Normalisasi teks untuk mapping channel ↔ grup (hapus *, rapikan spasi)."""
    if not text:
        return ""
    t = text.replace("*", "")
    t = t.replace("\r\n", "\n")
    t = re.sub(r"\s+", " ", t.strip())
    return t


def load_menfess_map():
    if os.path.exists(MENFESS_FILE):
        with open(MENFESS_FILE, "r", encoding="utf-8") as f:
            try:
                data = json.load(f)
                if isinstance(data, dict):
                    return data
                return {}
            except json.JSONDecodeError:
                return {}
    return {}


def save_menfess_map(data):
    with open(MENFESS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def register_menfess(channel_message_id: int, sender_user_id: int, full_text: str):
    """Simpan data menfess berdasarkan ID pesan di channel + teks normalisasi."""
    data = load_menfess_map()
    norm = normalize_link_text(full_text)

    existing = data.get(str(channel_message_id)) or {}
    group_msg_id = existing.get("group_message_id")

    data[str(channel_message_id)] = {
        "user_id": sender_user_id,
        "text": full_text,
        "norm_text": norm,
        "group_message_id": group_msg_id,
    }
    save_menfess_map(data)
    logger.info(
        "Register menfess channel_message_id=%s user_id=%s norm_len=%s",
        channel_message_id,
        sender_user_id,
        len(norm),
    )


def link_group_root_by_text(group_message_id: int, text: str):
    """Cocokkan teks dari pesan auto-forward di grup dengan data menfess."""
    norm = normalize_link_text(text)
    data = load_menfess_map()
    found_key = None

    for ch_id, info in data.items():
        if not info.get("group_message_id") and info.get("norm_text") == norm:
            info["group_message_id"] = group_message_id
            found_key = ch_id
            break

    if found_key:
        save_menfess_map(data)
        logger.info(
            "Link text->menfess: channel_message_id=%s group_message_id=%s norm_len=%s",
            found_key,
            group_message_id,
            len(norm),
        )
    else:
        logger.info(
            "Tidak ada entry menfess cocok untuk text_norm (len=%s) group_msg_id=%s",
            len(norm),
            group_message_id,
        )


def build_group_message_url(message_id: int) -> str:
    gid = str(GROUP_ID)
    if gid.startswith("-100"):
        gid = gid[4:]
    return f"https://t.me/c/{gid}/{message_id}"


# =========================================================
# 🔘 INLINE KEYBOARD BUILDER
# =========================================================
def build_channel_message_url(message_id: int) -> str:
    username = CHANNEL_USERNAME.lstrip("@")
    return f"https://t.me/{username}/{message_id}"


def build_initial_keyboard(message_id: int) -> InlineKeyboardMarkup:
    url = build_channel_message_url(message_id)
    keyboard = [
        [InlineKeyboardButton("👀 Lihat Pesan", url=url)],
        [InlineKeyboardButton("🗑 Hapus Pesan", callback_data=f"del:{message_id}")],
    ]
    return InlineKeyboardMarkup(keyboard)


def build_confirm_keyboard(message_id: int) -> InlineKeyboardMarkup:
    url = build_channel_message_url(message_id)
    keyboard = [
        [InlineKeyboardButton("👀 Lihat Pesan", url=url)],
        [InlineKeyboardButton("✅ Ya, Saya Yakin", callback_data=f"del_yes:{message_id}")],
        [InlineKeyboardButton("⬅ Kembali", callback_data=f"del_back:{message_id}")],
    ]
    return InlineKeyboardMarkup(keyboard)


def build_see_message_keyboard(group_message_id: int) -> InlineKeyboardMarkup:
    """Tombol untuk lihat komentar di GRUP (bukan channel)."""
    url = build_group_message_url(group_message_id)
    keyboard = [[InlineKeyboardButton("👁 Lihat balasan", url=url)]]
    return InlineKeyboardMarkup(keyboard)


# =========================================================
# ⚙️ SISTEM BOT
# =========================================================
user_last_sent: dict[int, float] = {}
notif_reply_map: dict[int, int] = {}  # DM notif msg_id -> komentar msg_id di grup


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
            await update.message.reply_text(
                f"⚠️ Kamu harus join channel {CHANNEL_USERNAME} dulu!"
            )
            return False
        return True
    except Exception:
        await update.message.reply_text(
            "⚠️ Gagal mengecek status keanggotaan channel. Pastikan bot sudah admin di channel."
        )
        return False


# =========================================================
# 💬 REPLY ANON: pengirim menfess balas komentar
# =========================================================
async def handle_reply_to_comment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if msg is None or not msg.reply_to_message:
        return

    user_id = msg.from_user.id
    username = msg.from_user.username or "-"
    parent = msg.reply_to_message
    parent_id = parent.message_id

    if parent_id not in notif_reply_map:
        return

    group_comment_msg_id = notif_reply_map[parent_id]
    text = msg.text.strip()

    if is_banned(user_id):
        await msg.reply_text(
            "🚫 Kamu telah diblokir karena berulang kali melanggar aturan."
        )
        return

    detected_word = contains_badword(text, BAD_WORDS)
    if detected_word:
        warnings, banned = add_warning(user_id, username, detected_word, text)
        safe_word = escape_markdown(detected_word)
        if banned:
            await msg.reply_text(
                f"🚫 Kamu telah diblokir karena 3 kali melanggar aturan.\n"
                f"Kata terakhir yang melanggar: `{safe_word}`",
                parse_mode="Markdown",
            )
        else:
            await msg.reply_text(
                f"⚠️ Balasanmu mengandung kata yang tidak pantas: `{safe_word}`\n"
                f"Ini peringatan ke-{warnings} dari 3.",
                parse_mode="Markdown",
            )
        return

    reply_text = f"{text}"
    await context.bot.send_message(
        chat_id=GROUP_ID,
        text=reply_text,
        parse_mode="Markdown",
        reply_to_message_id=group_comment_msg_id,
    )

    await msg.reply_text("✅ Balasanmu sudah dikirim secara anonim.")


# =========================================================
# 💬 HANDLER DI GRUP DISKUSI
# =========================================================
async def handle_group(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if msg is None:
        return

    logger.info(
        "Pesan di grup: chat_id=%s from=%s text=%r reply_to=%s",
        msg.chat.id,
        msg.from_user.id if msg.from_user else None,
        msg.text,
        msg.reply_to_message.message_id if msg.reply_to_message else None,
    )

    # 1) Pesan auto-forward dari channel (service message)
    if (
        msg.from_user
        and msg.from_user.id == 777000
        and msg.sender_chat
        and msg.sender_chat.id == CHANNEL_ID
        and msg.reply_to_message is None
    ):
        text = msg.text or msg.caption or ""
        link_group_root_by_text(msg.message_id, text)
        return

    # 2) Komentar user di thread
    if not msg.reply_to_message:
        return

    if msg.from_user and msg.from_user.is_bot:
        return

    # cari root paling atas
    root = msg.reply_to_message
    while root.reply_to_message:
        root = root.reply_to_message

    group_root_id = root.message_id

    data = load_menfess_map()
    target_user_id = None
    for ch_id, info in data.items():
        if info.get("group_message_id") == group_root_id:
            target_user_id = info.get("user_id")
            break

    if not target_user_id:
        logger.info("Tidak ditemukan menfess untuk group_root_id=%s", group_root_id)
        return

    commenter_name = (
        msg.from_user.first_name or msg.from_user.username or "Seseorang"
    )

    notif_text = (
        f"{commenter_name}, baru saja mengomentari postinganmu!\n\n"
        "Balas pesan ini untuk mengirim secara anonim"
    )

    keyboard = build_see_message_keyboard(msg.message_id)

    try:
        notif_msg = await context.bot.send_message(
            chat_id=target_user_id,
            text=notif_text,
            reply_markup=keyboard,
        )
        notif_reply_map[notif_msg.message_id] = msg.message_id
        logger.info(
            "Notif terkirim ke %s untuk komentar msg_id=%s",
            target_user_id,
            msg.message_id,
        )
    except Exception as e:
        logger.warning("Gagal kirim notif ke pengirim menfess: %s", e)


# =========================================================
# 📨 PROSES MENFESS (TEKS / FOTO)
# =========================================================
async def process_menfess_text(
    user_id: int,
    username: str,
    user_text: str,
    context: ContextTypes.DEFAULT_TYPE,
    update: Update,
    photo: str | None = None,
):
    now = time.time()

    if is_banned(user_id):
        await update.message.reply_text(
            "🚫 Kamu telah diblokir karena berulang kali melanggar aturan."
        )
        return

    if user_id not in ADMINS and user_id in user_last_sent:
        elapsed = now - user_last_sent[user_id]
        if elapsed < COOLDOWN_SECONDS:
            remaining = int((COOLDOWN_SECONDS - elapsed) / 60) + 1
            await update.message.reply_text(
                f"⏳ Tunggu {remaining} menit lagi sebelum kirim menfess berikutnya."
            )
            return

    detected_word = contains_badword(user_text, BAD_WORDS)
    if detected_word:
        warnings, banned = add_warning(user_id, username, detected_word, user_text)
        safe_word = escape_markdown(detected_word)
        if banned:
            await update.message.reply_text(
                f"🚫 Kamu telah diblokir karena 3 pelanggaran.\n"
                f"Kata terakhir yang melanggar: `{safe_word}`",
                parse_mode="Markdown",
            )
        else:
            await update.message.reply_text(
                f"⚠️ Pesanmu mengandung kata tidak pantas: `{safe_word}`\n"
                f"Peringatan ke-{warnings} dari 3.",
                parse_mode="Markdown",
            )
        return

    match = MENFESS_PATTERN.match(user_text)
    if not match:
        await update.message.reply_text(MENFESS_FORMAT_HELP_TEXT, parse_mode="Markdown")
        return

    dibalik_masker, target, ungkapan = match.groups()
    caption = (
        "📩 *Menfess Baru*\n\n"
        f"Dibalik Masker : {dibalik_masker.strip()}\n"
        f"Target : {target.strip()}\n"
        f"Ungkapan : {ungkapan.strip()}"
    )

    if photo:
        sent = await context.bot.send_photo(
            chat_id=CHANNEL_ID,
            photo=photo,
            caption=caption,
            parse_mode="Markdown",
        )
    else:
        sent = await context.bot.send_message(
            chat_id=CHANNEL_ID,
            text=caption,
            parse_mode="Markdown",
        )

    channel_message_id = sent.message_id
    register_menfess(channel_message_id, user_id, caption)

    user_last_sent[user_id] = now

    keyboard = build_initial_keyboard(channel_message_id)
    await update.message.reply_text(MENFESS_SUCCESS_REPLY, reply_markup=keyboard)


async def menfess(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    username = update.effective_user.username or "-"

    # kalau ini reply ke notif komentar → balasan anonim
    if update.message.reply_to_message:
        parent_id = update.message.reply_to_message.message_id
        if parent_id in notif_reply_map:
            await handle_reply_to_comment(update, context)
            return

    if is_banned(user_id):
        await update.message.reply_text(
            "🚫 Kamu telah diblokir karena berulang kali melanggar aturan."
        )
        return

    if not await check_membership(update, context):
        return

    user_text = update.message.text.strip()
    now = time.time()

    if user_id not in ADMINS and user_id in user_last_sent:
        elapsed = now - user_last_sent[user_id]
        if elapsed < COOLDOWN_SECONDS:
            remaining = int((COOLDOWN_SECONDS - elapsed) / 60) + 1
            await update.message.reply_text(
                "⏳ Kamu hanya bisa kirim 1 menfess setiap 10 menit.\n"
                f"Tunggu sekitar {remaining} menit lagi ya."
            )
            return

    detected_word = contains_badword(user_text, BAD_WORDS)
    if detected_word:
        warnings, banned = add_warning(user_id, username, detected_word, user_text)
        safe_word = escape_markdown(detected_word)
        if banned:
            await update.message.reply_text(
                f"🚫 Kamu telah diblokir karena 3 kali melanggar aturan.\n"
                f"Kata terakhir yang melanggar: `{safe_word}`",
                parse_mode="Markdown",
            )
        else:
            await update.message.reply_text(
                f"⚠️ Pesanmu mengandung kata yang tidak pantas: `{safe_word}`\n"
                f"Ini peringatan ke-{warnings} dari 3.",
                parse_mode="Markdown",
            )
        return

    match = MENFESS_PATTERN.match(user_text)
    if not match:
        await update.message.reply_text(MENFESS_FORMAT_HELP_TEXT, parse_mode="Markdown")
        return

    dibalik_masker, target, ungkapan = match.groups()
    text = (
        "📩 *Menfess Baru*\n\n"
        f"Dibalik Masker : {dibalik_masker.strip()}\n"
        f"Target : {target.strip()}\n"
        f"Ungkapan : {ungkapan.strip()}"
    )

    sent = await context.bot.send_message(
        chat_id=CHANNEL_ID, text=text, parse_mode="Markdown"
    )

    channel_message_id = sent.message_id
    register_menfess(channel_message_id, user_id, text)

    user_last_sent[user_id] = now

    keyboard = build_initial_keyboard(channel_message_id)
    await update.message.reply_text(MENFESS_SUCCESS_REPLY, reply_markup=keyboard)


# 🔹 Handler foto + caption
async def menfess_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    caption = update.message.caption
    user_id = update.effective_user.id
    username = update.effective_user.username or "-"

    if not await check_membership(update, context):
        return

    if not caption:
        await update.message.reply_text("❌ Kirim foto dengan caption sesuai format menfess.")
        return

    photo = update.message.photo[-1].file_id

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
    await update.message.reply_text(
        f"📋 *Daftar Pelanggar:*\n\n{text}", parse_mode="Markdown"
    )


# =========================================================
# 🔁 CALLBACK UNTUK TOMBOL INLINE
# =========================================================
async def menfess_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    data = query.data or ""

    if data.startswith("del:"):
        msg_id = int(data.split(":")[1])
        keyboard = build_confirm_keyboard(msg_id)
        await query.edit_message_text(CONFIRM_DELETE_TEXT, reply_markup=keyboard)

    elif data.startswith("del_back:"):
        msg_id = int(data.split(":")[1])
        keyboard = build_initial_keyboard(msg_id)
        await query.edit_message_text(MENFESS_SUCCESS_REPLY, reply_markup=keyboard)

    elif data.startswith("del_yes:"):
        msg_id = int(data.split(":")[1])
        try:
            await context.bot.delete_message(chat_id=CHANNEL_ID, message_id=msg_id)
            await query.edit_message_text("✅ Pesanmu di channel sudah dihapus.")
        except Exception:
            await query.edit_message_text(
                "⚠️ Gagal menghapus pesan di channel. Mungkin pesan sudah dihapus sebelumnya."
            )


def main():
    if not TOKEN:
        raise RuntimeError("BOT_TOKEN belum di-set di Token.env")

    logger.info("Bot menfess berjalan...")

    app = Application.builder().token(TOKEN).build()

    # PM bot (kirim menfess / reply notif)
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("violators", violators))
    app.add_handler(
        MessageHandler(filters.ChatType.PRIVATE & filters.PHOTO, menfess_photo)
    )
    app.add_handler(
        MessageHandler(
            filters.ChatType.PRIVATE & filters.TEXT & ~filters.COMMAND, menfess
        )
    )

    # semua pesan teks di grup diskusi
    app.add_handler(
        MessageHandler(
            filters.Chat(GROUP_ID) & filters.TEXT & ~filters.COMMAND,
            handle_group,
        )
    )

    # callback tombol inline hapus
    app.add_handler(CallbackQueryHandler(menfess_callback))

    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
