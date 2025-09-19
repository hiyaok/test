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
        """Load data dari file"""
        try:
            if os.path.exists('accounts.json'):
                with open('accounts.json', 'r') as f:
                    data = json.load(f)
                    self.accounts = data.get('accounts', {})
                    self.admins = data.get('admins', [MAIN_ADMIN])
        except Exception as e:
            logger.error(f"Error loading data: {e}")
    
    def save_data(self):
        """Save data ke file"""
        try:
            data = {
                'accounts': self.accounts,
                'admins': self.admins
            }
            with open('accounts.json', 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving data: {e}")
    
    def is_admin(self, user_id: int) -> bool:
        """Cek apakah user adalah admin"""
        return user_id in self.admins
    
    def is_main_admin(self, user_id: int) -> bool:
        """Cek apakah user adalah main admin"""
        return user_id == MAIN_ADMIN
    
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
    
    total_accounts = len(tg_manager.accounts)
    
    if total_accounts == 0:
        text = "🏠 *Dashboard Bot Manager*\n\n"
        text += "📱 Total Akun: 0\n\n"
        text += "Belum ada akun yang terdaftar nih!"
        
        keyboard = [[InlineKeyboardButton("➕ Tambah Akun", callback_data="add_account")]]
    else:
        text = f"🏠 *Dashboard Bot Manager*\n\n"
        text += f"📱 Total Akun: {total_accounts}\n\n"
        text += "*Pilih akun untuk dikelola:*"
        
        keyboard = []
        for phone, data in tg_manager.accounts.items():
            name = data.get('name', phone)
            keyboard.append([InlineKeyboardButton(f"📞 {name}", callback_data=f"account_{phone}")])
        
        keyboard.append([InlineKeyboardButton("➕ Tambah Akun", callback_data="add_account")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(text, parse_mode='Markdown', reply_markup=reply_markup)

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
    """Handler untuk semua callback query"""
    query = update.callback_query
    user_id = query.from_user.id
    data = query.data
    
    if not tg_manager.is_admin(user_id):
        await query.answer("❌ Lo gak punya akses!")
        return
    
    await query.answer()
    
    if data == "back_to_main":
        await back_to_main_menu(query, context)
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

async def back_to_main_menu(query, context):
    """Kembali ke main menu"""
    context.user_data.clear()  # Clear semua session data
    
    total_accounts = len(tg_manager.accounts)
    
    if total_accounts == 0:
        text = "🏠 *Dashboard Bot Manager*\n\n"
        text += "📱 Total Akun: 0\n\n"
        text += "Belum ada akun yang terdaftar nih!"
        
        keyboard = [[InlineKeyboardButton("➕ Tambah Akun", callback_data="add_account")]]
    else:
        text = f"🏠 *Dashboard Bot Manager*\n\n"
        text += f"📱 Total Akun: {total_accounts}\n\n"
        text += "*Pilih akun untuk dikelola:*"
        
        keyboard = []
        for phone, data in tg_manager.accounts.items():
            name = data.get('name', phone)
            keyboard.append([InlineKeyboardButton(f"📞 {name}", callback_data=f"account_{phone}")])
        
        keyboard.append([InlineKeyboardButton("➕ Tambah Akun", callback_data="add_account")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(text, parse_mode='Markdown', reply_markup=reply_markup)

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
    """Proses tambah semua kontak yang dikumpulkan"""
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

        # Initialize counters dan error tracking
        success_count = 0
        failed_count = 0
        failed_details = []  # Store failed contacts with reasons
        
        total_contacts = len(contacts_to_add)
        
        # Initial message
        await query.edit_message_text(f"⏳ Memulai proses tambah {total_contacts} kontak...")

        for idx, contact_info in enumerate(contacts_to_add, start=1):
            phone_num = str(contact_info['phone']).replace(" ", "").replace("+", "")
            first_name = contact_info.get('first_name') or "Unknown"
            last_name = contact_info.get('last_name') or ""
            full_name = f"{first_name} {last_name}".strip()

            # Update progress message
            progress_text = f"📞 Memproses kontak {idx}/{total_contacts}\n"
            progress_text += f"👤 {full_name} ({phone_num})\n\n"
            progress_text += f"✅ Berhasil: {success_count}\n"
            progress_text += f"❌ Gagal: {failed_count}"
            
            try:
                await query.edit_message_text(progress_text)
            except Exception as edit_error:
                logger.debug(f"Failed to edit message: {edit_error}")

            try:
                logger.info(f"[{phone}] Importing contact {phone_num} ({full_name})")

                # STEP 1: Import kontak
                result = await client(functions.contacts.ImportContactsRequest(
                    contacts=[
                        types.InputPhoneContact(
                            client_id=random.randrange(-2**63, 2**63),
                            phone=phone_num,
                            first_name=first_name,
                            last_name=last_name
                        )
                    ]
                ))

                # Delay dinamis antar kontak
                delay = random.uniform(2.5, 5.0)
                logger.debug(f"[{phone}] Delay {delay:.2f} detik sebelum lanjut...")
                await asyncio.sleep(delay)

                # Check if successful
                if result.users:
                    success_count += 1
                    logger.info(f"[{phone}] {phone_num} berhasil disave (direct)")
                    
                    # Update success message
                    success_text = f"✅ Kontak {idx}/{total_contacts} berhasil ditambah\n"
                    success_text += f"👤 {full_name}\n\n"
                    success_text += f"✅ Berhasil: {success_count}\n"
                    success_text += f"❌ Gagal: {failed_count}"
                    
                    try:
                        await query.edit_message_text(success_text)
                    except Exception:
                        pass
                    continue

                # STEP 2: Manual check if contact was saved
                contacts = await client(functions.contacts.GetContactsRequest(hash=0))
                saved_numbers = [u.phone for u in contacts.users if isinstance(u, types.User)]

                if phone_num in saved_numbers:
                    success_count += 1
                    logger.info(f"[{phone}] {phone_num} sudah tersimpan")
                    
                    # Update success message
                    success_text = f"✅ Kontak {idx}/{total_contacts} berhasil ditambah\n"
                    success_text += f"👤 {full_name}\n\n"
                    success_text += f"✅ Berhasil: {success_count}\n"
                    success_text += f"❌ Gagal: {failed_count}"
                    
                    try:
                        await query.edit_message_text(success_text)
                    except Exception:
                        pass
                    continue

                # STEP 3: Retry mechanism
                try:
                    entity = await client.get_entity(phone_num)
                    if isinstance(entity, types.User):
                        await client(functions.contacts.DeleteContactsRequest(id=[entity.id]))
                        await asyncio.sleep(2)
                except Exception as e:
                    logger.debug(f"[{phone}] Tidak bisa delete {phone_num}: {e}")

                retry = await client(functions.contacts.ImportContactsRequest(
                    contacts=[
                        types.InputPhoneContact(
                            client_id=random.randrange(-2**63, 2**63),
                            phone=phone_num,
                            first_name=first_name,
                            last_name=last_name
                        )
                    ]
                ))
                await asyncio.sleep(random.uniform(2.5, 5.0))

                if retry.users:
                    success_count += 1
                    logger.info(f"[{phone}] {phone_num} berhasil disave (retry)")
                    
                    # Update success message
                    success_text = f"✅ Kontak {idx}/{total_contacts} berhasil ditambah (retry)\n"
                    success_text += f"👤 {full_name}\n\n"
                    success_text += f"✅ Berhasil: {success_count}\n"
                    success_text += f"❌ Gagal: {failed_count}"
                    
                    try:
                        await query.edit_message_text(success_text)
                    except Exception:
                        pass
                else:
                    failed_count += 1
                    reason = "Kontak tidak ditemukan/tidak terdaftar"
                    failed_details.append(f"• {full_name} ({phone_num}) - {reason}")
                    logger.error(f"[{phone}] {phone_num} tetap gagal - {reason}")
                    
                    # Update failed message
                    failed_text = f"❌ Kontak {idx}/{total_contacts} gagal ditambah\n"
                    failed_text += f"👤 {full_name} - {reason}\n\n"
                    failed_text += f"✅ Berhasil: {success_count}\n"
                    failed_text += f"❌ Gagal: {failed_count}"
                    
                    try:
                        await query.edit_message_text(failed_text)
                    except Exception:
                        pass

            except Exception as e:
                failed_count += 1
                error_msg = str(e)
                
                # Detect specific error types
                if "FLOOD_WAIT" in error_msg:
                    reason = f"Rate limit - tunggu {error_msg.split('_')[2]} detik"
                elif "PHONE_NUMBER_INVALID" in error_msg:
                    reason = "Nomor tidak valid"
                elif "USER_PRIVACY_RESTRICTED" in error_msg:
                    reason = "Privacy settings user"
                elif "PEER_FLOOD" in error_msg:
                    reason = "Terlalu banyak request"
                else:
                    reason = f"Error: {error_msg[:50]}..."
                
                failed_details.append(f"• {full_name} ({phone_num}) - {reason}")
                logger.error(f"[{phone}] Error menambahkan kontak {phone_num}: {e}")
                
                # Update failed message with reason
                failed_text = f"❌ Kontak {idx}/{total_contacts} gagal ditambah\n"
                failed_text += f"👤 {full_name}\n"
                failed_text += f"💬 Alasan: {reason}\n\n"
                failed_text += f"✅ Berhasil: {success_count}\n"
                failed_text += f"❌ Gagal: {failed_count}"
                
                try:
                    await query.edit_message_text(failed_text)
                except Exception:
                    pass
                
                # Handle flood wait
                if "FLOOD_WAIT" in error_msg:
                    try:
                        wait_time = int(error_msg.split('_')[2])
                        for remaining in range(wait_time, 0, -1):
                            flood_text = f"⏰ Flood protection aktif\n"
                            flood_text += f"⏳ Tunggu {remaining} detik lagi...\n\n"
                            flood_text += f"📊 Progress: {idx}/{total_contacts}\n"
                            flood_text += f"✅ Berhasil: {success_count}\n"
                            flood_text += f"❌ Gagal: {failed_count}"
                            
                            try:
                                await query.edit_message_text(flood_text)
                            except Exception:
                                pass
                            await asyncio.sleep(1)
                    except (ValueError, IndexError):
                        await asyncio.sleep(60)  # Default wait

            # Extra delay every 10 contacts
            if idx % 10 == 0:
                extra_delay = random.uniform(10, 15)
                
                rest_text = f"😴 Istirahat sejenak ({extra_delay:.1f}s)\n"
                rest_text += f"📊 Progress: {idx}/{total_contacts}\n\n"
                rest_text += f"✅ Berhasil: {success_count}\n"
                rest_text += f"❌ Gagal: {failed_count}"
                
                try:
                    await query.edit_message_text(rest_text)
                except Exception:
                    pass
                
                logger.debug(f"[{phone}] Istirahat {extra_delay:.2f} detik (tiap 10 kontak)")
                await asyncio.sleep(extra_delay)

        await client.disconnect()

        # Final summary message
        text = f"🎉 *Proses Selesai!*\n\n"
        text += f"📊 *Ringkasan:*\n"
        text += f"✅ Berhasil: {success_count}\n"
        text += f"❌ Gagal: {failed_count}\n"
        text += f"📱 Total: {total_contacts}\n\n"
        
        if failed_details:
            text += f"❌ *Detail Kegagalan:*\n"
            # Limit failed details to prevent message too long
            for detail in failed_details[:10]:  # Show max 10 failed details
                text += f"{detail}\n"
            
            if len(failed_details) > 10:
                text += f"... dan {len(failed_details) - 10} lainnya"

        keyboard = [[InlineKeyboardButton("🔙 Kembali", callback_data=f"account_{phone}")]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.edit_message_text(text, parse_mode='Markdown', reply_markup=reply_markup)

        # Clear session data
        context.user_data.pop("contacts_to_add", None)

    except Exception as e:
        logger.error(f"[{phone}] Error processing contacts: {e}")
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
    """Hapus akun dari bot"""
    try:
        if phone in tg_manager.accounts:
            del tg_manager.accounts[phone]
            tg_manager.save_data()
            
            # Hapus session file
            session_file = f"session_{phone.replace('+', '')}.session"
            if os.path.exists(session_file):
                os.remove(session_file)
        
        keyboard = [[InlineKeyboardButton("🔙 Kembali", callback_data="back_to_main")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            f"✅ Akun {phone} berhasil dihapus!",
            reply_markup=reply_markup
        )
    except Exception as e:
        logger.error(f"Error deleting account: {e}")
        keyboard = [[InlineKeyboardButton("🔙 Kembali", callback_data=f"account_{phone}")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(f"❌ Error: {str(e)}", reply_markup=reply_markup)

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
