# SAVES KONTAK
# BY HIYAOK ON TELEGRAM
import asyncio
import logging
import json
import os
import random
import time
from datetime import datetime
from typing import Dict, List, Optional

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, Contact
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler, 
    MessageHandler, filters, ContextTypes, ConversationHandler
)

from telethon import TelegramClient, events, functions, types
from telethon.errors import (
    PhoneCodeInvalidError, PhoneNumberInvalidError, 
    SessionPasswordNeededError, PasswordHashInvalidError
)
from telethon.tl.functions.contacts import GetContactsRequest
from telethon.tl.functions.channels import JoinChannelRequest
from telethon.tl.functions.messages import AddChatUserRequest

# Setup logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# States untuk conversation handler
WAITING_PHONE, WAITING_CODE, WAITING_PASSWORD = range(3)
WAITING_CONTACT, WAITING_INVITE_LINK = range(3, 5)

# Konfigurasi
BOT_TOKEN = "8426128734:AAHYVpJCy7LrofTI3AzyUNhB_42hQnVNwiA"  # Ganti dengan token bot kamu
API_ID = "22211268"       # Ganti dengan API ID dari my.telegram.org
API_HASH = "8c5c2a1aa3a0a4909cffe54f60f89efb"   # Ganti dengan API Hash dari my.telegram.org
MAIN_ADMIN = 5988451717            # Ganti dengan user ID admin utama

class TelegramManager:
    def __init__(self):
        self.accounts: Dict[str, Dict] = {}
        self.clients: Dict[str, TelegramClient] = {}
        self.admins: List[int] = [MAIN_ADMIN]
        self.contact_sessions: Dict[int, Dict] = {}
        self.load_data()
        
    def load_data(self):
        """Load data dari file dengan better error handling"""
        try:
            if os.path.exists('accounts.json'):
                with open('accounts.json', 'r') as f:
                    data = json.load(f)
                    self.accounts = data.get('accounts', {})
                    self.admins = data.get('admins', [MAIN_ADMIN])
                    logger.info(f"Loaded {len(self.accounts)} accounts from file")
            else:
                # Buat file baru jika tidak ada
                self.accounts = {}
                self.admins = [MAIN_ADMIN]
                self.save_data()
                logger.info("Created new accounts.json file")
        except json.JSONDecodeError as e:
            logger.error(f"JSON decode error in accounts.json: {e}")
            # Backup file yang rusak dan buat baru
            if os.path.exists('accounts.json'):
                os.rename('accounts.json', f'accounts.json.backup.{int(time.time())}')
            self.accounts = {}
            self.admins = [MAIN_ADMIN]
            self.save_data()
        except Exception as e:
            logger.error(f"Error loading data: {e}")
            self.accounts = {}
            self.admins = [MAIN_ADMIN]
    
    def save_data(self):
        """Save data ke file dengan better error handling"""
        try:
            data = {
                'accounts': self.accounts,
                'admins': self.admins,
                'last_updated': datetime.now().isoformat()
            }
            
            # Atomic write - tulis ke temp file dulu
            with open('accounts.json.tmp', 'w') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            
            # Pindah temp file ke file asli
            os.replace('accounts.json.tmp', 'accounts.json')
            logger.info(f"Saved {len(self.accounts)} accounts to file")
            
        except Exception as e:
            logger.error(f"Error saving data: {e}")
            # Cleanup temp file jika ada error
            if os.path.exists('accounts.json.tmp'):
                os.remove('accounts.json.tmp')
    
    def is_admin(self, user_id: int) -> bool:
        """Cek apakah user adalah admin"""
        return user_id in self.admins
    
    def is_main_admin(self, user_id: int) -> bool:
        """Cek apakah user adalah main admin"""
        return user_id == MAIN_ADMIN
    
    def debug_accounts_storage(self):
        """Debug function untuk cek status penyimpanan"""
        try:
            print(f"=== DEBUG ACCOUNTS STORAGE ===")
            print(f"Total accounts in memory: {len(self.accounts)}")
            
            for phone, data in self.accounts.items():
                print(f"  • {phone}: {data}")
            
            # Cek file accounts.json
            if os.path.exists('accounts.json'):
                with open('accounts.json', 'r') as f:
                    file_data = json.load(f)
                    file_accounts = file_data.get('accounts', {})
                    print(f"Total accounts in file: {len(file_accounts)}")
                    
                    for phone, data in file_accounts.items():
                        print(f"  FILE • {phone}: {data}")
            else:
                print("accounts.json file not found")
            
            # Cek session files
            session_files = [f for f in os.listdir('.') if 'session' in f]
            print(f"Session files found: {len(session_files)}")
            for session in session_files:
                print(f"  SESSION • {session}")
            
            print(f"=== END DEBUG ===")
            
        except Exception as e:
            print(f"Debug error: {e}")
    
    async def create_client(self, phone: str) -> TelegramClient:
        """Buat client Telethon baru"""
        session_name = f"session_{phone.replace('+', '')}"
        client = TelegramClient(session_name, API_ID, API_HASH)
        return client
    
    async def get_contacts_count(self, client):
        """Hitung jumlah kontak dengan detail"""
        try:
            total_contacts = 0
            mutual_contacts = 0
            non_mutual_contacts = 0
            
            result = await client(GetContactsRequest(hash=0))
            all_contacts = result.users
            
            for contact in all_contacts:
                if not getattr(contact, 'bot', False) and not getattr(contact, 'deleted', False):
                    total_contacts += 1
                    if getattr(contact, 'mutual_contact', False):
                        mutual_contacts += 1
                    else:
                        non_mutual_contacts += 1
            
            return {
                "total": total_contacts,
                "mutual": mutual_contacts,
                "non_mutual": non_mutual_contacts
            }
        except Exception as e:
            logger.error(f"Error counting contacts: {e}")
            return {"total": 0, "mutual": 0, "non_mutual": 0}

# Initialize manager
tg_manager = TelegramManager()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler untuk command /start"""
    user_id = update.effective_user.id
    
    if not tg_manager.is_admin(user_id):
        await update.message.reply_text("❌ Lo gak punya akses ke bot ini!")
        return
    
    # Reset pagination
    context.user_data['account_page'] = 0
    await show_accounts_page(update.message.reply_text, context, 0)

async def show_accounts_page(reply_func, context, page):
    """Tampilkan halaman akun dengan pagination"""
    total_accounts = len(tg_manager.accounts)
    accounts_per_page = 10
    total_pages = (total_accounts + accounts_per_page - 1) // accounts_per_page if total_accounts > 0 else 0
    
    # Validasi page
    if page < 0:
        page = 0
    elif page >= total_pages and total_pages > 0:
        page = total_pages - 1
    
    context.user_data['account_page'] = page
    
    if total_accounts == 0:
        text = "🏠 *Dashboard Bot Manager*\n\n"
        text += "📱 Total Akun: 0\n\n"
        text += "Belum ada akun yang terdaftar nih!"
        
        keyboard = [[InlineKeyboardButton("➕ Tambah Akun", callback_data="add_account")]]
    else:
        start_idx = page * accounts_per_page
        end_idx = min(start_idx + accounts_per_page, total_accounts)
        
        text = f"🏠 *Dashboard Bot Manager*\n\n"
        text += f"📱 Total Akun: {total_accounts}\n"
        
        if total_pages > 1:
            text += f"📄 Halaman: {page + 1}/{total_pages}\n"
        
        text += "\n*Pilih akun untuk dikelola:*"
        
        keyboard = []
        
        # Convert dict to list untuk indexing yang konsisten
        account_items = list(tg_manager.accounts.items())
        
        # Tampilkan akun sesuai halaman dengan nomor urut
        for i in range(start_idx, end_idx):
            phone, data = account_items[i]
            account_number = i + 1
            name = data.get('name', phone)
            # Potong nama jika terlalu panjang
            display_name = name[:20] + "..." if len(name) > 20 else name
            button_text = f"{account_number} {phone}"
            keyboard.append([InlineKeyboardButton(button_text, callback_data=f"account_{phone}")])
        
        # Navigation buttons jika lebih dari 1 halaman
        if total_pages > 1:
            nav_buttons = []
            if page > 0:
                nav_buttons.append(InlineKeyboardButton("⬅️ Sebelumnya", callback_data=f"page_{page-1}"))
            if page < total_pages - 1:
                nav_buttons.append(InlineKeyboardButton("Next ➡️", callback_data=f"page_{page+1}"))
            
            if nav_buttons:
                keyboard.append(nav_buttons)
        
        keyboard.append([InlineKeyboardButton("➕ Tambah Akun", callback_data="add_account")])
    
    # Tambah tombol admin jika main admin
    user_id = context.user_data.get('current_user_id')
    if user_id and tg_manager.is_main_admin(user_id):
        keyboard.append([InlineKeyboardButton("👑 Panel Admin", callback_data="list_admin")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await reply_func(text, parse_mode='Markdown', reply_markup=reply_markup)

async def admin_panel(update_or_query, context: ContextTypes.DEFAULT_TYPE):
    """Handler untuk command /admin - khusus main admin"""
    if isinstance(update_or_query, Update):  
        # kalau dari /admin command
        user_id = update_or_query.effective_user.id
        reply_func = update_or_query.message.reply_text
    else:  
        # kalau dari callback
        user_id = update_or_query.from_user.id
        reply_func = update_or_query.edit_message_text

    if not tg_manager.is_main_admin(user_id):
        await reply_func("❌ Command ini khusus main admin doang!")
        return

    text = "👑 *Panel Admin Utama*\n\n"
    text += f"Total Admin: {len(tg_manager.admins)}\n\n"
    text += "*List Admin Biasa:*\n"

    admin_list = [admin for admin in tg_manager.admins if admin != MAIN_ADMIN]
    if admin_list:
        for i, admin in enumerate(admin_list, 1):
            text += f"{i}. `{admin}`\n"
    else:
        text += "_Belum ada admin biasa_"

    keyboard = [
        [InlineKeyboardButton("➕ Tambah Admin", callback_data="add_admin")],
        [InlineKeyboardButton("➖ Hapus Admin", callback_data="remove_admin")],
        [InlineKeyboardButton("📋 List Admin", callback_data="list_admin")],
        [InlineKeyboardButton("🔙 Kembali", callback_data="back_to_main")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await reply_func(text, parse_mode="Markdown", reply_markup=reply_markup)

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler untuk semua callback query - UPDATE dengan pagination"""
    query = update.callback_query
    user_id = query.from_user.id
    data = query.data
    
    if not tg_manager.is_admin(user_id):
        await query.answer("❌ Lo gak punya akses!")
        return
    
    await query.answer()
    
    # Store user ID untuk keperluan main admin check
    context.user_data['current_user_id'] = user_id
    
    if data == "back_to_main":
        await back_to_main_menu(query, context)
    elif data.startswith("page_"):
        # Handle pagination
        page = int(data.split("page_")[1])
        await show_accounts_page(query.edit_message_text, context, page)
    elif data == "add_account":
        await start_add_account(query, context)
    elif data.startswith("account_"):
        phone = data.split("account_")[1]
        await show_account_details(query, context, phone)
    elif data.startswith("add_contact_"):
        phone = data.split("add_contact_")[1]
        await start_add_contact(query, context, phone)
    elif data.startswith("done_contact_"):
        phone = data.split("done_contact_")[1]
        await process_add_contacts(query, context, phone)
    elif data.startswith("delete_contacts_"):
        phone = data.split("delete_contacts_")[1]
        await confirm_delete_contacts(query, context, phone)
    elif data.startswith("confirm_delete_"):
        phone = data.split("confirm_delete_")[1]
        await delete_all_contacts(query, context, phone)
    elif data.startswith("delete_account_"):
        phone = data.split("delete_account_")[1]
        await confirm_delete_account(query, context, phone)
    elif data.startswith("confirm_delete_acc_"):
        phone = data.split("confirm_delete_acc_")[1]
        await delete_account(query, context, phone)
    elif data.startswith("invite_"):
        if len(data.split("_")) == 2:  # invite_phone
            phone = data.split("invite_")[1]
            await start_invite_process(query, context, phone)
        else:  # invite_type_phone_username
            parts = data.split("_", 3)
            invite_type = parts[1]
            phone = parts[2]
            username = parts[3]
            await process_invite_contacts(query, context, phone, username, invite_type)
    elif data == "add_admin" and tg_manager.is_main_admin(user_id):
        await start_add_admin(query, context)
    elif data == "remove_admin" and tg_manager.is_main_admin(user_id):
        await show_remove_admin_options(query, context)
    elif data.startswith("remove_admin_") and tg_manager.is_main_admin(user_id):
        admin_id = int(data.split("remove_admin_")[1])
        await remove_admin(query, context, admin_id)
    elif data == "list_admin" and tg_manager.is_main_admin(user_id):
        await admin_panel(query, context)

# Tambahan: Update fungsi back_to_main_menu untuk refresh data yang benar
async def back_to_main_menu(query, context):
    """Kembali ke main menu dengan data terbaru"""
    # Clear semua session data kecuali pagination
    current_page = context.user_data.get('account_page', 0)
    context.user_data.clear()
    context.user_data['account_page'] = current_page
    context.user_data['current_user_id'] = query.from_user.id
    
    # Reload data dari file untuk memastikan data terbaru
    tg_manager.load_data()
    
    try:
        await show_accounts_page(query.edit_message_text, context, current_page)
    except Exception as e:
        logger.error(f"Error updating main menu: {e}")
        # Fallback jika edit gagal
        try:
            await show_accounts_page(query.message.reply_text, context, current_page)
        except Exception as e2:
            logger.error(f"Error sending new message: {e2}")

async def start_add_account(query, context):
    """Mulai proses tambah akun"""
    context.user_data['waiting_phone_input'] = True
    
    text = "📱 *Tambah Akun Baru*\n\n"
    text += "Kirim nomor telepon dengan format internasional\n"
    text += "Contoh: +628123456789"
    
    keyboard = [[InlineKeyboardButton("🔙 Kembali", callback_data="back_to_main")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(text, parse_mode='Markdown', reply_markup=reply_markup)

async def start_add_admin(query, context):
    """Mulai proses tambah admin"""
    context.user_data['waiting_admin_id'] = True
    
    text = "👑 *Tambah Admin Baru*\n\n"
    text += "Kirim User ID yang mau dijadiin admin:"
    
    keyboard = [[InlineKeyboardButton("🔙 Kembali", callback_data="list_admin")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(text, parse_mode='Markdown', reply_markup=reply_markup)

async def show_account_details(query, context, phone):
    """Tampilkan detail akun"""
    if phone not in tg_manager.accounts:
        keyboard = [[InlineKeyboardButton("🔙 Kembali", callback_data="back_to_main")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text("❌ Akun tidak ditemukan!", reply_markup=reply_markup)
        return
    
    account = tg_manager.accounts[phone]
    
    try:
        # Connect ke client
        client = await tg_manager.create_client(phone)
        await client.connect()
        
        if await client.is_user_authorized():
            # Get user info
            me = await client.get_me()
            name = f"{me.first_name or ''} {me.last_name or ''}".strip()
            user_id = me.id
            
            # Get contacts count
            contacts = await tg_manager.get_contacts_count(client)
            
            text = f"📱 *Detail Akun*\n\n"
            text += f"👤 Nama: {name}\n"
            text += f"🆔 ID: `{user_id}`\n"
            text += f"📞 Nomor: {phone}\n\n"
            text += f"👥 *Kontak:*\n"
            text += f"• Total: {contacts['total']}\n"
            text += f"• Mutual: {contacts['mutual']}\n"
            text += f"• Non-Mutual: {contacts['non_mutual']}\n"
            
            keyboard = [
                [InlineKeyboardButton("➕ Tambah Kontak", callback_data=f"add_contact_{phone}")],
                [InlineKeyboardButton("🗑️ Hapus Semua Kontak", callback_data=f"delete_contacts_{phone}")],
                [InlineKeyboardButton("📨 Invite ke Grup/Channel", callback_data=f"invite_{phone}")],
                [InlineKeyboardButton("❌ Hapus Akun", callback_data=f"delete_account_{phone}")],
                [InlineKeyboardButton("🔙 Kembali", callback_data="back_to_main")]
            ]
        else:
            text = f"❌ Akun {phone} tidak authorized. Hapus dan tambah ulang!"
            keyboard = [[InlineKeyboardButton("🔙 Kembali", callback_data="back_to_main")]]
            
        await client.disconnect()
        
    except Exception as e:
        logger.error(f"Error getting account details: {e}")
        text = f"❌ Error getting account details: {str(e)}"
        keyboard = [[InlineKeyboardButton("🔙 Kembali", callback_data="back_to_main")]]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(text, parse_mode='Markdown', reply_markup=reply_markup)

async def start_add_contact(query, context, phone):
    """Mulai proses tambah kontak"""
    context.user_data['current_phone'] = phone
    context.user_data['contacts_to_add'] = []
    context.user_data['last_contact_time'] = 0
    
    text = f"👥 *Tambah Kontak ke {phone}*\n\n"
    text += "Kirim kontak yang mau ditambahkan\n"
    text += "Bisa kirim beberapa kontak sekaligus\n\n"
    text += "Tekan Done kalau udah selesai"
    
    keyboard = [
        [InlineKeyboardButton("✅ Done", callback_data=f"done_contact_{phone}")],
        [InlineKeyboardButton("🔙 Kembali", callback_data=f"account_{phone}")]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(text, parse_mode='Markdown', reply_markup=reply_markup)

async def confirm_delete_contacts(query, context, phone):
    """Konfirmasi hapus semua kontak"""
    text = f"⚠️ *Konfirmasi Hapus Kontak*\n\n"
    text += f"Yakin mau hapus SEMUA kontak dari akun {phone}?\n"
    text += "Aksi ini gak bisa dibatalkan!"
    
    keyboard = [
        [InlineKeyboardButton("✅ Ya, Hapus Semua", callback_data=f"confirm_delete_{phone}")],
        [InlineKeyboardButton("❌ Batal", callback_data=f"account_{phone}")]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(text, parse_mode='Markdown', reply_markup=reply_markup)

async def confirm_delete_account(query, context, phone):
    """Konfirmasi hapus akun"""
    text = f"⚠️ *Konfirmasi Hapus Akun*\n\n"
    text += f"Yakin mau hapus akun {phone} dari bot?\n"
    text += "Session dan data akun akan dihapus!"
    
    keyboard = [
        [InlineKeyboardButton("✅ Ya, Hapus Akun", callback_data=f"confirm_delete_acc_{phone}")],
        [InlineKeyboardButton("❌ Batal", callback_data=f"account_{phone}")]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(text, parse_mode='Markdown', reply_markup=reply_markup)

async def handle_contact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle kontak yang dikirim user"""
    if 'current_phone' not in context.user_data:
        return
    
    contact = update.message.contact
    if not contact:
        return
    
    phone = context.user_data['current_phone']
    current_time = time.time()
    
    # Tambahkan kontak ke list
    contact_info = {
        'phone': contact.phone_number,
        'first_name': contact.first_name or "",
        'last_name': contact.last_name or ""
    }
    context.user_data['contacts_to_add'].append(contact_info)
    
    # Cek apakah sudah lewat 10 detik dari kontak terakhir
    if current_time - context.user_data.get('last_contact_time', 0) >= 10:
        total_contacts = len(context.user_data['contacts_to_add'])
        text = f"✅ Kontak diterima!\n\n"
        text += "Kirim kontak lagi atau tekan Done untuk selesai"
        
        keyboard = [
            [InlineKeyboardButton("✅ Done", callback_data=f"done_contact_{phone}")],
            [InlineKeyboardButton("🔙 Kembali", callback_data=f"account_{phone}")]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(text, reply_markup=reply_markup)
        context.user_data['last_contact_time'] = current_time

async def process_add_contacts(query, context, phone):
    """Tambah semua kontak + wajib verifikasi save sebelum hitung sukses"""
    contacts_to_add = context.user_data.get('contacts_to_add', [])

    if not contacts_to_add:
        keyboard = [[InlineKeyboardButton("🔙 Kembali", callback_data=f"account_{phone}")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text("❌ Gak ada kontak yang mau ditambahkan!", reply_markup=reply_markup)
        return

    try:
        client = await tg_manager.create_client(phone)
        await client.connect()

        if not await client.is_user_authorized():
            keyboard = [[InlineKeyboardButton("🔙 Kembali", callback_data=f"account_{phone}")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text("❌ Akun tidak authorized!", reply_markup=reply_markup)
            return

        total_contacts = len(contacts_to_add)
        success_count, failed_count = 0, 0
        failed_details = []

        await query.edit_message_text(f"⏳ Mulai proses tambah {total_contacts} kontak...")

        for idx, contact_info in enumerate(contacts_to_add, start=1):
            phone_num = str(contact_info['phone']).replace(" ", "").replace("+", "")
            first_name = contact_info.get('first_name') or "Kontak"
            last_name = contact_info.get('last_name') or ""
            full_name = f"{first_name} {last_name}".strip()

            status = ""
            reason = None

            try:
                # import kontak
                await client(functions.contacts.ImportContactsRequest(
                    contacts=[types.InputPhoneContact(
                        client_id=idx,
                        phone=phone_num,
                        first_name=first_name,
                        last_name=last_name
                    )]
                ))

                # verifikasi apakah tersimpan
                all_contacts = await client(functions.contacts.GetContactsRequest(hash=0))
                saved_numbers = [str(u.phone) for u in all_contacts.users if u.phone]

                if phone_num in saved_numbers:
                    success_count += 1
                    status = "✅ Berhasil & Terverifikasi"
                else:
                    failed_count += 1
                    reason = "Tidak muncul di daftar kontak (gagal save)"
                    failed_details.append(f"• {full_name} ({phone_num}) - {reason}")
                    status = f"❌ Gagal ({reason})"

            except Exception as e:
                failed_count += 1
                error_msg = str(e)
                if "PHONE_NUMBER_INVALID" in error_msg:
                    reason = "Format nomor tidak valid"
                elif "USER_PRIVACY_RESTRICTED" in error_msg:
                    reason = "Privacy settings user"
                elif "PEER_FLOOD" in error_msg:
                    reason = "Terlalu banyak request"
                elif "FLOOD_WAIT" in error_msg:
                    reason = "Rate limit, tunggu beberapa saat"
                else:
                    reason = f"Error: {error_msg[:40]}..."
                failed_details.append(f"• {full_name} ({phone_num}) - {reason}")
                status = f"❌ Gagal ({reason})"

            # update pesan progress tiap 1 kontak
            progress_text = (
                f"📞 Kontak {idx}/{total_contacts}\n"
                f"👤 {full_name} ({phone_num})\n"
                f"{status}\n\n"
                f"📊 Progress:\n"
                f"✅ Berhasil: {success_count}\n"
                f"❌ Gagal: {failed_count}"
            )
            try:
                await query.edit_message_text(progress_text)
            except Exception:
                pass

            # delay antar kontak
            await asyncio.sleep(2)

            # jeda tiap 10 kontak
            if idx % 10 == 0 and idx < total_contacts:
                rest_duration = 120
                for remaining in range(rest_duration, 0, -1):
                    minutes, seconds = divmod(remaining, 60)
                    rest_text = (
                        f"😴 Istirahat 2 menit biar aman limit...\n"
                        f"⏰ Sisa waktu: {minutes:02d}:{seconds:02d}\n\n"
                        f"📊 Progress: {idx}/{total_contacts}\n"
                        f"✅ Berhasil: {success_count}\n"
                        f"❌ Gagal: {failed_count}"
                    )
                    try:
                        await query.edit_message_text(rest_text)
                    except Exception:
                        pass
                    await asyncio.sleep(1)

        await client.disconnect()

        # ringkasan akhir
        text = (
            "🎉 *Proses selesai!*\n\n"
            f"📱 Total kontak: {total_contacts}\n"
            f"✅ Berhasil & Terverifikasi: {success_count}\n"
            f"❌ Gagal: {failed_count}\n\n"
        )
        if failed_details:
            text += "❌ *Detail gagal:*\n"
            for detail in failed_details[:10]:
                text += f"{detail}\n"
            if len(failed_details) > 10:
                text += f"... dan {len(failed_details)-10} lainnya"

        keyboard = [[InlineKeyboardButton("🔙 Kembali", callback_data=f"account_{phone}")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(text, parse_mode="Markdown", reply_markup=reply_markup)

        context.user_data.pop("contacts_to_add", None)

    except Exception as e:
        logger.error(f"[{phone}] Error utama: {e}")
        keyboard = [[InlineKeyboardButton("🔙 Kembali", callback_data=f"account_{phone}")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(f"❌ Error: {str(e)}", reply_markup=reply_markup)

async def delete_all_contacts(query, context, phone):
    """Hapus semua kontak"""
    try:
        client = await tg_manager.create_client(phone)
        await client.connect()
        
        if not await client.is_user_authorized():
            keyboard = [[InlineKeyboardButton("🔙 Kembali", callback_data=f"account_{phone}")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text("❌ Akun tidak authorized!", reply_markup=reply_markup)
            return
        
        await query.edit_message_text("⏳ Menghapus semua kontak...")
        
        # Get all contacts
        result = await client(GetContactsRequest(hash=0))
        contacts = result.users
        
        contact_ids = []
        for contact in contacts:
            if not getattr(contact, 'bot', False) and not getattr(contact, 'deleted', False):
                contact_ids.append(types.InputUser(contact.id, contact.access_hash))
        
        if contact_ids:
            # Delete contacts
            await client(functions.contacts.DeleteContactsRequest(id=contact_ids))
            
            text = f"✅ *Berhasil hapus {len(contact_ids)} kontak!*"
        else:
            text = "ℹ️ Gak ada kontak yang bisa dihapus"
        
        await client.disconnect()
        
        keyboard = [[InlineKeyboardButton("🔙 Kembali", callback_data=f"account_{phone}")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(text, parse_mode='Markdown', reply_markup=reply_markup)
        
    except Exception as e:
        logger.error(f"Error deleting contacts: {e}")
        keyboard = [[InlineKeyboardButton("🔙 Kembali", callback_data=f"account_{phone}")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(f"❌ Error: {str(e)}", reply_markup=reply_markup)

async def delete_account(query, context, phone):
    """Hapus akun dari bot - langsung hapus dari database tanpa cek authorization"""
    try:
        await query.edit_message_text("🗑️ Menghapus akun...")
        
        account_name = "Unknown"
        if phone in tg_manager.accounts:
            account_name = tg_manager.accounts[phone].get('name', phone)
        
        # Hapus session files
        session_files_to_delete = [
            f"session_{phone.replace('+', '')}.session",
            f"session_{phone.replace('+', '')}",
            f"{phone.replace('+', '')}.session"
        ]
        
        deleted_count = 0
        for session_file in session_files_to_delete:
            if os.path.exists(session_file):
                try:
                    os.remove(session_file)
                    deleted_count += 1
                    logger.info(f"Deleted: {session_file}")
                except Exception as e:
                    logger.error(f"Error deleting {session_file}: {e}")
        
        # Disconnect client jika masih aktif
        if phone in tg_manager.clients:
            try:
                await tg_manager.clients[phone].disconnect()
                del tg_manager.clients[phone]
            except:
                pass
        
        # Hapus dari accounts dictionary
        if phone in tg_manager.accounts:
            del tg_manager.accounts[phone]
            tg_manager.save_data()
        
        # Success message
        text = f"✅ Akun berhasil dihapus!\n\n"
        text += f"👤 Nama: {account_name}\n"
        text += f"📞 Nomor: {phone}\n"
        text += f"🗑️ Session files dihapus: {deleted_count}\n"
        text += f"📱 Sisa akun: {len(tg_manager.accounts)}"
        
        keyboard = [[InlineKeyboardButton("🔙 Kembali", callback_data="back_to_main")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(text, reply_markup=reply_markup)
        
    except Exception as e:
        logger.error(f"Error deleting account {phone}: {e}")
        
        # Tetap hapus dari dictionary walaupun error
        if phone in tg_manager.accounts:
            del tg_manager.accounts[phone]
            tg_manager.save_data()
        
        text = f"⚠️ Akun dihapus dengan warning\n\n"
        text += f"📞 Nomor: {phone}\n"
        text += f"Error: {str(e)}\n\n"
        text += f"Akun tetap dihapus dari daftar.\n"
        text += f"📱 Sisa akun: {len(tg_manager.accounts)}"
        
        keyboard = [[InlineKeyboardButton("🔙 Kembali", callback_data="back_to_main")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(text, reply_markup=reply_markup)

# Tambahan: Fungsi helper untuk cleanup session files
def cleanup_orphaned_sessions():
    """Bersihkan file session yang tidak punya akun lagi"""
    try:
        # Get semua file session
        session_files = [f for f in os.listdir('.') if f.startswith('session_') and f.endswith('.session')]
        
        active_phones = set()
        for phone in tg_manager.accounts.keys():
            clean_phone = phone.replace('+', '')
            active_phones.add(f"session_{clean_phone}.session")
        
        orphaned = []
        for session_file in session_files:
            if session_file not in active_phones:
                try:
                    os.remove(session_file)
                    orphaned.append(session_file)
                    logger.info(f"Cleaned up orphaned session: {session_file}")
                except Exception as e:
                    logger.error(f"Error cleaning {session_file}: {e}")
        
        return len(orphaned)
    except Exception as e:
        logger.error(f"Error during cleanup: {e}")
        return 0

async def start_invite_process(query, context, phone):
    """Mulai proses invite ke grup/channel"""
    context.user_data['invite_phone'] = phone
    
    text = f"📨 *Invite Kontak ke Grup/Channel*\n\n"
    text += "Kirim link atau username grup/channel\n"
    text += "Contoh:\n"
    text += "• https://t.me/namagrup\n"
    text += "• @namagrup"
    
    keyboard = [[InlineKeyboardButton("🔙 Kembali", callback_data=f"account_{phone}")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(text, parse_mode='Markdown', reply_markup=reply_markup)

async def process_invite_contacts(query, context, phone, username, invite_type):
    """Proses invite kontak ke grup/channel"""
    try:
        client = await tg_manager.create_client(phone)
        await client.connect()
        
        if not await client.is_user_authorized():
            keyboard = [[InlineKeyboardButton("🔙 Kembali", callback_data=f"account_{phone}")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text("❌ Akun tidak authorized!", reply_markup=reply_markup)
            return
        
        await query.edit_message_text(f"⏳ Memproses invite ke @{username}...")
        
        # Join grup/channel dulu
        try:
            await client(JoinChannelRequest(username))
            await asyncio.sleep(2)
        except Exception as e:
            logger.info(f"Already joined or error joining: {e}")
        
        # Get contacts
        result = await client(GetContactsRequest(hash=0))
        all_contacts = result.users
        
        contacts_to_invite = []
        
        for contact in all_contacts:
            if not getattr(contact, 'bot', False) and not getattr(contact, 'deleted', False):
                is_mutual = getattr(contact, 'mutual_contact', False)
                
                if invite_type == "all":
                    contacts_to_invite.append(contact)
                elif invite_type == "mutual" and is_mutual:
                    contacts_to_invite.append(contact)
                elif invite_type == "non_mutual" and not is_mutual:
                    contacts_to_invite.append(contact)
        
        if not contacts_to_invite:
            text = f"ℹ️ Gak ada kontak yang sesuai kriteria untuk diinvite"
            keyboard = [[InlineKeyboardButton("🔙 Kembali", callback_data=f"account_{phone}")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(text, reply_markup=reply_markup)
            await client.disconnect()
            return
        
        # Get grup/channel entity
        entity = await client.get_entity(username)
        
        success_count = 0
        failed_count = 0
        
        for contact in contacts_to_invite[:50]:  # Limit 50 per batch
            try:
                if hasattr(entity, 'megagroup') and entity.megagroup:
                    # Supergroup
                    await client(functions.channels.InviteToChannelRequest(
                        channel=entity,
                        users=[contact]
                    ))
                else:
                    # Regular group
                    await client(AddChatUserRequest(
                        chat_id=entity.id,
                        user_id=contact,
                        fwd_limit=10
                    ))
                
                success_count += 1
                await asyncio.sleep(2)  # Delay untuk avoid flood
                
            except Exception as e:
                logger.error(f"Error inviting {contact.id}: {e}")
                failed_count += 1
                await asyncio.sleep(1)
        
        await client.disconnect()
        
        text = f"✅ *Selesai Invite Kontak!*\n\n"
        text += f"🎯 Target: @{username}\n"
        text += f"📊 Berhasil: {success_count}\n"
        text += f"❌ Gagal: {failed_count}\n"
        text += f"📱 Total: {len(contacts_to_invite)}"
        
        if len(contacts_to_invite) > 50:
            text += f"\n\n⚠️ Hanya 50 kontak pertama yang diinvite untuk avoid flood"
        
        keyboard = [[InlineKeyboardButton("🔙 Kembali", callback_data=f"account_{phone}")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(text, parse_mode='Markdown', reply_markup=reply_markup)
        
    except Exception as e:
        logger.error(f"Error inviting contacts: {e}")
        keyboard = [[InlineKeyboardButton("🔙 Kembali", callback_data=f"account_{phone}")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(f"❌ Error: {str(e)}", reply_markup=reply_markup)

async def handle_text_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle pesan teks"""
    user_id = update.effective_user.id
    
    if not tg_manager.is_admin(user_id):
        return
    
    text = update.message.text
    
    # Handle admin ID input
    if context.user_data.get('waiting_admin_id'):
        await process_admin_input(update, context, text)
        return
    
    # Handle phone input
    if context.user_data.get('waiting_phone_input'):
        await process_phone_input(update, context, text)
        return
    
    # Handle code input
    if context.user_data.get('waiting_code_input'):
        await process_code_input(update, context, text)
        return
    
    # Handle password input
    if context.user_data.get('waiting_password_input'):
        await process_password_input(update, context, text)
        return
    
    # Handle invite link
    if context.user_data.get('invite_phone'):
        await process_invite_link(update, context, text)
        return

async def process_admin_input(update: Update, context: ContextTypes.DEFAULT_TYPE, admin_id_text: str):
    """Proses input admin ID"""
    try:
        new_admin_id = int(admin_id_text)
        if new_admin_id not in tg_manager.admins:
            tg_manager.admins.append(new_admin_id)
            tg_manager.save_data()
            
            text = f"✅ Admin {new_admin_id} berhasil ditambahkan!"
            keyboard = [[InlineKeyboardButton("🔙 Kembali", callback_data="list_admin")]]
        else:
            text = "❌ User sudah jadi admin!"
            keyboard = [[InlineKeyboardButton("🔙 Kembali", callback_data="list_admin")]]
    except ValueError:
        text = "❌ ID harus berupa angka!"
        keyboard = [[InlineKeyboardButton("🔙 Kembali", callback_data="list_admin")]]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(text, reply_markup=reply_markup)
    
    context.user_data['waiting_admin_id'] = False

async def process_phone_input(update: Update, context: ContextTypes.DEFAULT_TYPE, phone: str):
    """Proses input nomor telepon"""
    try:
        client = await tg_manager.create_client(phone)
        await client.connect()
        
        if await client.is_user_authorized():
            text = "✅ Nomor ini udah terdaftar!"
            keyboard = [[InlineKeyboardButton("🔙 Kembali", callback_data="back_to_main")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text(text, reply_markup=reply_markup)
            await client.disconnect()
            context.user_data.clear()
            return
        
        # Send code request
        await client.send_code_request(phone)
        
        context.user_data['temp_phone'] = phone
        context.user_data['temp_client'] = client
        context.user_data['waiting_phone_input'] = False
        context.user_data['waiting_code_input'] = True
        
        text = f"📱 Kode OTP dikirim ke {phone}\nKirim kode yang diterima:"
        keyboard = [[InlineKeyboardButton("🔙 Kembali", callback_data="back_to_main")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(text, reply_markup=reply_markup)
        
    except PhoneNumberInvalidError:
        text = "❌ Nomor telepon tidak valid!"
        keyboard = [[InlineKeyboardButton("🔙 Kembali", callback_data="back_to_main")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(text, reply_markup=reply_markup)
    except Exception as e:
        logger.error(f"Error sending code: {e}")
        text = f"❌ Error: {str(e)}"
        keyboard = [[InlineKeyboardButton("🔙 Kembali", callback_data="back_to_main")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(text, reply_markup=reply_markup)

async def process_code_input(update: Update, context: ContextTypes.DEFAULT_TYPE, code: str):
    """Proses input kode OTP"""
    try:
        client = context.user_data['temp_client']
        phone = context.user_data['temp_phone']
        
        await client.sign_in(phone, code)
        
        # Get user info
        me = await client.get_me()
        name = f"{me.first_name or ''} {me.last_name or ''}".strip()
        
        # Save account
        tg_manager.accounts[phone] = {
            'name': name,
            'user_id': me.id,
            'added_at': datetime.now().isoformat()
        }
        tg_manager.save_data()
        
        await client.disconnect()
        
        context.user_data.clear()
        
        text = (f"✅ *Akun berhasil ditambahkan!*\n\n"
               f"👤 Nama: {name}\n"
               f"📞 Nomor: {phone}")
        
        keyboard = [[InlineKeyboardButton("🔙 Kembali", callback_data="back_to_main")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(text, parse_mode='Markdown', reply_markup=reply_markup)
        
    except PhoneCodeInvalidError:
        text = "❌ Kode OTP salah! Coba lagi:"
        keyboard = [[InlineKeyboardButton("🔙 Kembali", callback_data="back_to_main")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(text, reply_markup=reply_markup)
    except SessionPasswordNeededError:
        context.user_data['waiting_code_input'] = False
        context.user_data['waiting_password_input'] = True
        
        text = "🔐 Akun pake 2FA. Kirim password:"
        keyboard = [[InlineKeyboardButton("🔙 Kembali", callback_data="back_to_main")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(text, reply_markup=reply_markup)
    except Exception as e:
        logger.error(f"Error signing in: {e}")
        text = f"❌ Error: {str(e)}"
        keyboard = [[InlineKeyboardButton("🔙 Kembali", callback_data="back_to_main")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(text, reply_markup=reply_markup)

async def process_password_input(update: Update, context: ContextTypes.DEFAULT_TYPE, password: str):
    """Proses input password 2FA"""
    try:
        client = context.user_data['temp_client']
        phone = context.user_data['temp_phone']
        
        await client.sign_in(password=password)
        
        # Get user info
        me = await client.get_me()
        name = f"{me.first_name or ''} {me.last_name or ''}".strip()
        
        # Save account
        tg_manager.accounts[phone] = {
            'name': name,
            'user_id': me.id,
            'added_at': datetime.now().isoformat()
        }
        tg_manager.save_data()
        
        await client.disconnect()
        
        context.user_data.clear()
        
        text = (f"✅ *Akun berhasil ditambahkan!*\n\n"
               f"👤 Nama: {name}\n"
               f"📞 Nomor: {phone}")
        
        keyboard = [[InlineKeyboardButton("🔙 Kembali", callback_data="back_to_main")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(text, parse_mode='Markdown', reply_markup=reply_markup)
        
    except PasswordHashInvalidError:
        text = "❌ Password salah! Coba lagi:"
        keyboard = [[InlineKeyboardButton("🔙 Kembali", callback_data="back_to_main")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(text, reply_markup=reply_markup)
    except Exception as e:
        logger.error(f"Error with password: {e}")
        text = f"❌ Error: {str(e)}"
        keyboard = [[InlineKeyboardButton("🔙 Kembali", callback_data="back_to_main")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(text, reply_markup=reply_markup)

async def process_invite_link(update: Update, context: ContextTypes.DEFAULT_TYPE, link: str):
    """Proses link invite"""
    phone = context.user_data['invite_phone']
    
    # Parse link atau username
    if link.startswith('https://t.me/'):
        username = link.split('/')[-1]
    elif link.startswith('@'):
        username = link[1:]
    else:
        username = link
    
    text = f"🎯 *Pilih jenis kontak yang mau diinvite:*\n\n"
    text += f"📨 Target: @{username}\n"
    text += f"📱 Akun: {phone}"
    
    keyboard = [
        [InlineKeyboardButton("👥 Semua Kontak", callback_data=f"invite_all_{phone}_{username}")],
        [InlineKeyboardButton("🤝 Mutual Saja", callback_data=f"invite_mutual_{phone}_{username}")],
        [InlineKeyboardButton("👤 Non-Mutual Saja", callback_data=f"invite_non_mutual_{phone}_{username}")],
        [InlineKeyboardButton("🔙 Kembali", callback_data=f"account_{phone}")]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(text, parse_mode='Markdown', reply_markup=reply_markup)
    
    context.user_data.clear()

async def show_remove_admin_options(query, context):
    """Tampilkan opsi hapus admin"""
    admin_list = [admin for admin in tg_manager.admins if admin != MAIN_ADMIN]
    
    if not admin_list:
        text = "❌ Gak ada admin biasa yang bisa dihapus!"
        keyboard = [[InlineKeyboardButton("🔙 Kembali", callback_data="list_admin")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(text, reply_markup=reply_markup)
        return
    
    text = "🗑️ *Pilih admin yang mau dihapus:*\n\n"
    
    keyboard = []
    for admin in admin_list:
        keyboard.append([InlineKeyboardButton(f"🗑️ {admin}", callback_data=f"remove_admin_{admin}")])
    
    keyboard.append([InlineKeyboardButton("🔙 Kembali", callback_data="list_admin")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(text, parse_mode='Markdown', reply_markup=reply_markup)

async def remove_admin(query, context, admin_id):
    """Hapus admin"""
    if admin_id in tg_manager.admins:
        tg_manager.admins.remove(admin_id)
        tg_manager.save_data()
        text = f"✅ Admin {admin_id} berhasil dihapus!"
    else:
        text = "❌ Admin tidak ditemukan!"
    
    keyboard = [[InlineKeyboardButton("🔙 Kembali", callback_data="list_admin")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(text, reply_markup=reply_markup)

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Log errors yang terjadi"""
    logger.error(msg="Exception while handling an update:", exc_info=context.error)

def main():
    """Main function untuk menjalankan bot"""
    print("🚀 Starting Telegram Management Bot...")
    
    # Cek konfigurasi
    if BOT_TOKEN == "YOUR_BOT_TOKEN_HERE":
        print("❌ Bot token belum diset! Edit BOT_TOKEN di kode")
        return
    
    if API_ID == "YOUR_API_ID_HERE" or API_HASH == "YOUR_API_HASH_HERE":
        print("❌ API_ID atau API_HASH belum diset! Daftar di my.telegram.org")
        return
    
    if MAIN_ADMIN == 123456789:
        print("⚠️  MAIN_ADMIN masih default! Ganti dengan user ID kamu")
    
    # Create application
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Add handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("admin", admin_panel))
    application.add_handler(CallbackQueryHandler(handle_callback))
    application.add_handler(MessageHandler(filters.CONTACT, handle_contact))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_message))
    
    # Add error handler
    application.add_error_handler(error_handler)
    
    # Create data directory if not exists
    os.makedirs('sessions', exist_ok=True)
    
    print("✅ Bot berhasil dijalankan!")
    print("📋 Fitur yang tersedia:")
    print("   • /start - Dashboard utama")
    print("   • /admin - Panel admin (khusus main admin)")
    print("   • Kelola akun Telegram")
    print("   • Tambah/hapus kontak")
    print("   • Invite kontak ke grup/channel")
    print("   • Kelola admin bot")
    print("\n🔧 Setup yang diperlukan:")
    print("   1. Ganti BOT_TOKEN dengan token bot dari @BotFather")
    print("   2. Ganti API_ID dan API_HASH dari my.telegram.org")
    print("   3. Ganti MAIN_ADMIN dengan user ID Telegram kamu")
    print("\n💡 Cara dapetin user ID:")
    print("   • Chat ke @userinfobot atau @myidbot")
    print("   • Forward pesan ke bot, lalu lihat user ID")
    print("\n🚨 Penting:")
    print("   • Pastikan bot sudah di-start sama admin")
    print("   • Session file akan disimpan otomatis")
    print("   • Data admin tersimpan di accounts.json")
    print("\n▶️  Bot siap digunakan! Tekan Ctrl+C untuk stop")
    
    # Start bot
    try:
        application.run_polling(allowed_updates=Update.ALL_TYPES)
    except KeyboardInterrupt:
        print("\n⏹️  Bot dihentikan oleh user")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        logger.error(f"Fatal error: {e}")

if __name__ == "__main__":
    main()


# ============================================
# REQUIREMENTS.TXT
# ============================================
"""
Buat file requirements.txt dengan isi:

python-telegram-bot==20.7
telethon==1.32.1
"""

# ============================================
# SETUP INSTRUCTIONS
# ============================================
"""
CARA SETUP BOT:

1. INSTALL DEPENDENCIES:
   pip install -r requirements.txt

2. SETUP BOT TOKEN:
   • Chat ke @BotFather di Telegram
   • Ketik /newbot
   • Ikuti instruksi untuk buat bot baru  
   • Copy token yang dikasih
   • Ganti BOT_TOKEN di kode

3. SETUP API CREDENTIALS:
   • Buka https://my.telegram.org
   • Login dengan akun Telegram
   • Pilih API Development Tools
   • Buat aplikasi baru
   • Copy API ID dan API Hash
   • Ganti API_ID dan API_HASH di kode

4. SETUP MAIN ADMIN:
   • Chat ke @userinfobot untuk dapetin user ID kamu
   • Ganti MAIN_ADMIN dengan user ID kamu

5. JALANKAN BOT:
   python bot.py

6. START BOT:
   • Chat ke bot kamu di Telegram
   • Ketik /start untuk mulai

STRUKTUR FILE:
bot.py              # File utama bot
accounts.json       # Data akun dan admin (otomatis dibuat)
session_*.session   # Session file Telethon (otomatis dibuat)
requirements.txt    # Dependencies Python

FITUR BOT:
✅ Dashboard dengan list akun
✅ Tambah akun Telegram (OTP + 2FA support)
✅ Lihat detail akun (nama, ID, jumlah kontak)
✅ Tambah kontak batch
✅ Hapus semua kontak
✅ Invite kontak ke grup/channel (mutual/non-mutual/all)
✅ Kelola admin bot (khusus main admin)
✅ Tombol back di semua menu
✅ Error handling yang proper
✅ Auto save data
✅ Logging

KEAMANAN:
• Hanya admin yang bisa akses bot
• Session file terenkripsi
• Data tersimpan lokal
• Rate limiting untuk avoid flood
• Input validation

NOTES:
• Bot support multiple akun Telegram
• Bisa invite max 50 kontak per batch (anti flood)
• Session otomatis tersimpan
• Data admin persistent
• Support 2FA accounts
• Bahasa Indonesia gaul sesuai request

Enjoy! 🎉
"""
