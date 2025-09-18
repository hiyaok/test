#!/usr/bin/env python3
"""
Telegram Bot Manager - Complete Fixed Version
Bot untuk mengelola multiple akun Telegram dengan Telethon
"""

import asyncio
import json
import os
import logging
import threading
import time
import shutil
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple

from telethon import TelegramClient, events, Button
from telethon.sessions import StringSession
from telethon.tl.types import InputPhoneContact, User, Chat, Channel
from telethon.errors import (
    SessionPasswordNeededError, PhoneCodeInvalidError, 
    PasswordHashInvalidError, FloodWaitError, PhoneNumberInvalidError,
    MessageNotModifiedError, MessageIdInvalidError
)
from telethon.tl.functions.contacts import (
    ImportContactsRequest, DeleteContactsRequest, GetContactsRequest
)
from telethon.tl.functions.channels import InviteToChannelRequest
from telethon.tl.functions.messages import AddChatUserRequest

# ==================== CONFIGURATION ====================
API_ID = "20755791"
API_HASH = "3d09356fe14a31a5baaad296a1abef80"
BOT_TOKEN = "8426128734:AAHYVpJCy7LrofTI3AzyUNhB_42hQnVNwiA"
ADMIN_UTAMA = 5988451717

DATA_DIR = "bot_data"
KATEGORI_FILE = os.path.join(DATA_DIR, "kategori.json")
AKUN_TG_FILE = os.path.join(DATA_DIR, "akun_tg.json")
TEMP_CONTACTS_FILE = os.path.join(DATA_DIR, "temp_contacts.json")
ADMIN_BOTS_FILE = os.path.join(DATA_DIR, "admin_bots.json")

# ==================== LOGGING SETUP ====================
def setup_logging():
    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR)
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(os.path.join(DATA_DIR, 'bot.log')),
            logging.StreamHandler()
        ]
    )
    logging.getLogger('telethon').setLevel(logging.WARNING)
    return logging.getLogger(__name__)

logger = setup_logging()

# ==================== STORAGE MANAGER ====================
file_lock = threading.RLock()

class JSONStorage:
    def __init__(self):
        self.ensure_data_dir()
        self.init_json_files()
    
    def ensure_data_dir(self):
        if not os.path.exists(DATA_DIR):
            os.makedirs(DATA_DIR)
    
    def init_json_files(self):
        default_data = {
            KATEGORI_FILE: [],
            AKUN_TG_FILE: [],
            TEMP_CONTACTS_FILE: [],
            ADMIN_BOTS_FILE: []
        }
        
        for file_path, default_content in default_data.items():
            if not os.path.exists(file_path):
                self.write_json(file_path, default_content)
    
    def read_json(self, file_path: str) -> List[Dict]:
        with file_lock:
            try:
                if not os.path.exists(file_path):
                    return []
                
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read().strip()
                    if not content:
                        return []
                    data = json.loads(content)
                    return data if isinstance(data, list) else []
            except (json.JSONDecodeError, FileNotFoundError):
                logger.error(f"Error reading {file_path}")
                return []
            except Exception as e:
                logger.error(f"Error reading {file_path}: {e}")
                return []
    
    def write_json(self, file_path: str, data: List[Dict]) -> bool:
        with file_lock:
            try:
                # Create backup
                backup_path = file_path + '.backup'
                if os.path.exists(file_path):
                    shutil.copy2(file_path, backup_path)
                
                # Write new data
                temp_path = file_path + '.tmp'
                with open(temp_path, 'w', encoding='utf-8') as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
                
                # Atomic rename
                if os.name == 'nt':  # Windows
                    if os.path.exists(file_path):
                        os.remove(file_path)
                os.rename(temp_path, file_path)
                
                # Remove backup if write successful
                if os.path.exists(backup_path):
                    os.remove(backup_path)
                
                return True
            except Exception as e:
                logger.error(f"Error writing {file_path}: {e}")
                # Restore backup if exists
                backup_path = file_path + '.backup'
                if os.path.exists(backup_path):
                    shutil.copy2(backup_path, file_path)
                    os.remove(backup_path)
                return False
    
    def get_next_id(self, file_path: str) -> int:
        data = self.read_json(file_path)
        if not data:
            return 1
        max_id = max([item.get('id', 0) for item in data], default=0)
        return max_id + 1

# Initialize storage
storage = JSONStorage()

# ==================== DATABASE FUNCTIONS ====================
# Kategori functions
def get_kategori() -> List[tuple]:
    data = storage.read_json(KATEGORI_FILE)
    return [(item['id'], item['nama']) for item in data]

def add_kategori(nama: str) -> bool:
    data = storage.read_json(KATEGORI_FILE)
    if any(item['nama'].lower() == nama.lower() for item in data):
        return False
    
    new_kategori = {
        'id': storage.get_next_id(KATEGORI_FILE),
        'nama': nama.strip(),
        'created_at': datetime.now().isoformat()
    }
    
    data.append(new_kategori)
    return storage.write_json(KATEGORI_FILE, data)

def update_kategori(kategori_id: int, nama_baru: str) -> bool:
    data = storage.read_json(KATEGORI_FILE)
    nama_baru = nama_baru.strip()
    if any(item['nama'].lower() == nama_baru.lower() and item['id'] != kategori_id for item in data):
        return False
    
    for item in data:
        if item['id'] == kategori_id:
            item['nama'] = nama_baru
            return storage.write_json(KATEGORI_FILE, data)
    return False

def get_kategori_by_id(kategori_id: int) -> Optional[Dict]:
    data = storage.read_json(KATEGORI_FILE)
    return next((item for item in data if item['id'] == kategori_id), None)

def delete_kategori(kategori_id: int) -> bool:
    data = storage.read_json(KATEGORI_FILE)
    original_length = len(data)
    data = [item for item in data if item['id'] != kategori_id]
    if len(data) < original_length:
        return storage.write_json(KATEGORI_FILE, data)
    return False

# Akun TG functions
def get_akun_by_kategori(kategori_id: int) -> List[tuple]:
    data = storage.read_json(AKUN_TG_FILE)
    filtered_data = [item for item in data if item['kategori_id'] == kategori_id]
    return [(item['id'], item['nomor'], item.get('nama_akun', '')) for item in filtered_data]

def add_akun_tg(nomor: str, session_string: str, kategori_id: int, nama_akun: str = '') -> bool:
    data = storage.read_json(AKUN_TG_FILE)
    if any(item['nomor'] == nomor for item in data):
        return False
    
    new_akun = {
        'id': storage.get_next_id(AKUN_TG_FILE),
        'nomor': nomor,
        'session_string': session_string,
        'kategori_id': kategori_id,
        'nama_akun': nama_akun,
        'created_at': datetime.now().isoformat()
    }
    
    data.append(new_akun)
    return storage.write_json(AKUN_TG_FILE, data)

def get_akun_by_id(akun_id: int) -> Optional[Dict]:
    data = storage.read_json(AKUN_TG_FILE)
    return next((item for item in data if item['id'] == akun_id), None)

def delete_akun_by_id(akun_id: int) -> bool:
    data = storage.read_json(AKUN_TG_FILE)
    original_length = len(data)
    data = [item for item in data if item['id'] != akun_id]
    if len(data) < original_length:
        return storage.write_json(AKUN_TG_FILE, data)
    return False

def update_akun_kategori(akun_id: int, new_kategori_id: int) -> bool:
    data = storage.read_json(AKUN_TG_FILE)
    for item in data:
        if item['id'] == akun_id:
            item['kategori_id'] = new_kategori_id
            return storage.write_json(AKUN_TG_FILE, data)
    return False

# Admin functions
def is_admin_utama(user_id: int) -> bool:
    return user_id == ADMIN_UTAMA

def is_admin_bot(user_id: int) -> bool:
    data = storage.read_json(ADMIN_BOTS_FILE)
    return any(item['user_id'] == user_id for item in data)

def is_authorized(user_id: int) -> bool:
    return is_admin_utama(user_id) or is_admin_bot(user_id)

def add_admin_bot(user_id: int, added_by: int) -> bool:
    data = storage.read_json(ADMIN_BOTS_FILE)
    if any(item['user_id'] == user_id for item in data):
        return False
    
    new_admin = {
        'user_id': user_id,
        'added_by': added_by,
        'added_at': datetime.now().isoformat()
    }
    
    data.append(new_admin)
    return storage.write_json(ADMIN_BOTS_FILE, data)

def get_all_admin_bots() -> List[tuple]:
    data = storage.read_json(ADMIN_BOTS_FILE)
    return [(item['user_id'], item['added_at']) for item in data]

def delete_admin_bot(user_id: int) -> bool:
    data = storage.read_json(ADMIN_BOTS_FILE)
    original_length = len(data)
    data = [item for item in data if item['user_id'] != user_id]
    if len(data) < original_length:
        return storage.write_json(ADMIN_BOTS_FILE, data)
    return False

# Temp contacts functions
def add_temp_contact(user_id: int, contact_data: Dict) -> bool:
    data = storage.read_json(TEMP_CONTACTS_FILE)
    new_contact = {
        'user_id': user_id,
        'contact_data': contact_data,
        'created_at': datetime.now().isoformat()
    }
    data.append(new_contact)
    return storage.write_json(TEMP_CONTACTS_FILE, data)

def get_temp_contacts(user_id: int) -> List[Dict]:
    data = storage.read_json(TEMP_CONTACTS_FILE)
    return [item['contact_data'] for item in data if item['user_id'] == user_id]

def clear_temp_contacts(user_id: int) -> bool:
    data = storage.read_json(TEMP_CONTACTS_FILE)
    original_length = len(data)
    data = [item for item in data if item['user_id'] != user_id]
    if len(data) < original_length:
        return storage.write_json(TEMP_CONTACTS_FILE, data)
    return True

# ==================== UTILITY FUNCTIONS ====================
def format_message(title: str, content: str = "", success: bool = None) -> str:
    if success is True:
        icon = "✅"
    elif success is False:
        icon = "❌"
    else:
        icon = "🤖"
    
    msg = "━━━━━━━━━━━━━━━━━━\n"
    msg += f"{icon} **{title}** {icon}\n"
    msg += "━━━━━━━━━━━━━━━━━━\n"
    
    if content:
        msg += f"{content}\n"
    
    return msg

async def safe_edit_message(event, text, buttons=None):
    """Safely edit message with error handling"""
    try:
        if hasattr(event, 'edit'):
            await event.edit(text, buttons=buttons)
        else:
            await event.reply(text, buttons=buttons)
    except (MessageNotModifiedError, MessageIdInvalidError):
        # Message content is the same or message ID is invalid
        try:
            await event.reply(text, buttons=buttons)
        except Exception as e:
            logger.error(f"Error in safe_edit_message fallback: {e}")
    except Exception as e:
        logger.error(f"Error in safe_edit_message: {e}")
        try:
            await event.reply(text, buttons=buttons)
        except Exception as e2:
            logger.error(f"Error in safe_edit_message final fallback: {e2}")

async def safe_send_message(event, text, buttons=None):
    """Safely send message"""
    try:
        await event.reply(text, buttons=buttons)
    except Exception as e:
        logger.error(f"Error sending message: {e}")

# ==================== BOT INITIALIZATION ====================
bot = TelegramClient('bot_session', API_ID, API_HASH).start(bot_token=BOT_TOKEN)
user_states = {}

# ==================== MAIN HANDLERS ====================
@bot.on(events.NewMessage(pattern='/start'))
async def start_handler(event):
    if not is_authorized(event.sender_id):
        await safe_send_message(event, format_message(
            "AKSES DITOLAK", 
            "Anda tidak memiliki izin untuk menggunakan bot ini.",
            success=False
        ))
        return
    
    # Clear any existing state
    user_states.pop(event.sender_id, None)
    
    buttons = []
    if is_admin_utama(event.sender_id):
        buttons.append([Button.inline("👑 Menu Admin Utama", b"main_admin_menu")])
    
    buttons.extend([
        [Button.inline("📱 Login Nomor Baru", b"login_nomor")],
        [Button.inline("📋 List Semua Akun", b"list_akun")],
        [Button.inline("➕ Tambah Kontak", b"tambah_kontak")],
        [Button.inline("🗑️ Hapus Nomor", b"hapus_nomor")],
        [Button.inline("🧹 Clear Kontak", b"clear_kontak")],
        [Button.inline("👥 Invite ke Grup/Channel", b"invite_grup")]
    ])
    
    msg = format_message("SELAMAT DATANG", "Pilih menu yang ingin Anda gunakan:")
    await safe_send_message(event, msg, buttons)

# ==================== CALLBACK HANDLERS ====================
@bot.on(events.CallbackQuery(data=b'back_to_main'))
async def back_to_main_handler(event):
    if not is_authorized(event.sender_id):
        return
    
    user_states.pop(event.sender_id, None)
    
    buttons = []
    if is_admin_utama(event.sender_id):
        buttons.append([Button.inline("👑 Menu Admin Utama", b"main_admin_menu")])
    
    buttons.extend([
        [Button.inline("📱 Login Nomor Baru", b"login_nomor")],
        [Button.inline("📋 List Semua Akun", b"list_akun")],
        [Button.inline("➕ Tambah Kontak", b"tambah_kontak")],
        [Button.inline("🗑️ Hapus Nomor", b"hapus_nomor")],
        [Button.inline("🧹 Clear Kontak", b"clear_kontak")],
        [Button.inline("👥 Invite ke Grup/Channel", b"invite_grup")]
    ])
    
    msg = format_message("MENU UTAMA", "Pilih menu yang ingin Anda gunakan:")
    await safe_edit_message(event, msg, buttons)

# ==================== ADMIN MENU ====================
@bot.on(events.CallbackQuery(data=b'main_admin_menu'))
async def main_admin_menu(event):
    if not is_admin_utama(event.sender_id):
        await event.answer("❌ Akses ditolak!", alert=True)
        return
    
    buttons = [
        [Button.inline("👨‍💼 Kelola Admin Bot", b"kelola_admin")],
        [Button.inline("📁 Kelola Kategori", b"kelola_kategori")],
        [Button.inline("🔄 Pindah Nomor Kategori", b"pindah_kategori")],
        [Button.inline("🔙 Kembali", b"back_to_main")]
    ]
    
    msg = format_message("MENU ADMIN UTAMA", "Fitur khusus untuk admin utama:")
    await safe_edit_message(event, msg, buttons)

# ==================== KELOLA KATEGORI ====================
@bot.on(events.CallbackQuery(data=b'kelola_kategori'))
async def kelola_kategori_handler(event):
    if not is_admin_utama(event.sender_id):
        await event.answer("❌ Akses ditolak!", alert=True)
        return
    
    buttons = [
        [Button.inline("➕ Tambah Kategori", b"tambah_kategori")],
        [Button.inline("📝 Edit Kategori", b"edit_kategori")],
        [Button.inline("🗑️ Hapus Kategori", b"hapus_kategori")],
        [Button.inline("📋 List Kategori", b"list_kategori")],
        [Button.inline("🔙 Kembali", b"main_admin_menu")]
    ]
    
    msg = format_message("KELOLA KATEGORI", "Pilih aksi untuk kategori:")
    await safe_edit_message(event, msg, buttons)

@bot.on(events.CallbackQuery(data=b'tambah_kategori'))
async def tambah_kategori_handler(event):
    if not is_admin_utama(event.sender_id):
        return
    
    user_states[event.sender_id] = {"action": "tambah_kategori"}
    msg = format_message("TAMBAH KATEGORI BARU", "Kirim nama kategori yang ingin dibuat:")
    await safe_edit_message(event, msg)

@bot.on(events.CallbackQuery(data=b'edit_kategori'))
async def edit_kategori_handler(event):
    if not is_admin_utama(event.sender_id):
        return
    
    kategori_list = get_kategori()
    if not kategori_list:
        buttons = [[Button.inline("🔙 Kembali", b"kelola_kategori")]]
        msg = format_message("BELUM ADA KATEGORI", "Belum ada kategori yang dibuat.", success=False)
        await safe_edit_message(event, msg, buttons)
        return
    
    buttons = []
    for kat_id, kat_nama in kategori_list:
        buttons.append([Button.inline(f"📝 {kat_nama}", f"edit_kat_{kat_id}".encode())])
    
    buttons.append([Button.inline("🔙 Kembali", b"kelola_kategori")])
    
    msg = format_message("EDIT KATEGORI", "Pilih kategori yang ingin diedit:")
    await safe_edit_message(event, msg, buttons)

@bot.on(events.CallbackQuery(pattern=r'edit_kat_(\d+)'))
async def edit_kategori_nama_handler(event):
    if not is_admin_utama(event.sender_id):
        return
    
    kategori_id = int(event.data.decode().split('_')[-1])
    kategori = get_kategori_by_id(kategori_id)
    
    if not kategori:
        await event.answer("❌ Kategori tidak ditemukan!", alert=True)
        return
    
    user_states[event.sender_id] = {
        "action": "edit_nama_kategori",
        "kategori_id": kategori_id,
        "old_name": kategori['nama']
    }
    
    msg = format_message("EDIT NAMA KATEGORI", 
                       f"**Nama saat ini:** {kategori['nama']}\n\n" +
                       "Kirim nama baru untuk kategori ini:")
    
    await safe_edit_message(event, msg)

@bot.on(events.CallbackQuery(data=b'hapus_kategori'))
async def hapus_kategori_handler(event):
    if not is_admin_utama(event.sender_id):
        return
    
    kategori_list = get_kategori()
    if not kategori_list:
        buttons = [[Button.inline("🔙 Kembali", b"kelola_kategori")]]
        msg = format_message("BELUM ADA KATEGORI", "Belum ada kategori yang dibuat.", success=False)
        await safe_edit_message(event, msg, buttons)
        return
    
    buttons = []
    for kat_id, kat_nama in kategori_list:
        buttons.append([Button.inline(f"🗑️ {kat_nama}", f"confirm_hapus_kat_{kat_id}".encode())])
    
    buttons.append([Button.inline("🔙 Kembali", b"kelola_kategori")])
    
    msg = format_message("HAPUS KATEGORI", "Pilih kategori yang ingin dihapus:")
    await safe_edit_message(event, msg, buttons)

@bot.on(events.CallbackQuery(pattern=r'confirm_hapus_kat_(\d+)'))
async def confirm_hapus_kategori_handler(event):
    if not is_admin_utama(event.sender_id):
        return
    
    kategori_id = int(event.data.decode().split('_')[-1])
    kategori = get_kategori_by_id(kategori_id)
    
    if not kategori:
        await event.answer("❌ Kategori tidak ditemukan!", alert=True)
        return
    
    # Check if category has accounts
    akun_list = get_akun_by_kategori(kategori_id)
    if akun_list:
        await event.answer(f"❌ Tidak bisa hapus kategori '{kategori['nama']}' karena masih ada {len(akun_list)} akun!", alert=True)
        return
    
    buttons = [
        [Button.inline("✅ Ya, Hapus!", f"execute_hapus_kat_{kategori_id}".encode())],
        [Button.inline("❌ Batal", b"hapus_kategori")]
    ]
    
    msg = format_message("KONFIRMASI HAPUS KATEGORI", 
                       f"Yakin ingin menghapus kategori **{kategori['nama']}**?\n\n" +
                       "**PERINGATAN:** Aksi ini tidak dapat dibatalkan!")
    
    await safe_edit_message(event, msg, buttons)

@bot.on(events.CallbackQuery(pattern=r'execute_hapus_kat_(\d+)'))
async def execute_hapus_kategori_handler(event):
    if not is_admin_utama(event.sender_id):
        return
    
    kategori_id = int(event.data.decode().split('_')[-1])
    kategori = get_kategori_by_id(kategori_id)
    
    if not kategori:
        await event.answer("❌ Kategori tidak ditemukan!", alert=True)
        return
    
    if delete_kategori(kategori_id):
        buttons = [[Button.inline("🔙 Kembali ke Menu Admin", b"main_admin_menu")]]
        msg = format_message("KATEGORI BERHASIL DIHAPUS", 
                           f"Kategori **{kategori['nama']}** telah dihapus!",
                           success=True)
        await safe_edit_message(event, msg, buttons)
    else:
        await event.answer("❌ Gagal menghapus kategori!", alert=True)

@bot.on(events.CallbackQuery(data=b'list_kategori'))
async def list_kategori_handler(event):
    if not is_admin_utama(event.sender_id):
        return
    
    kategori_list = get_kategori()
    
    if not kategori_list:
        content = "Belum ada kategori yang dibuat."
    else:
        content = "**DAFTAR KATEGORI:**\n\n"
        for kat_id, kat_nama in kategori_list:
            akun_count = len(get_akun_by_kategori(kat_id))
            content += f"📁 **{kat_nama}**\n"
            content += f"🆔 ID: {kat_id}\n"
            content += f"📱 Akun: {akun_count}\n\n"
    
    buttons = [[Button.inline("🔙 Kembali", b"kelola_kategori")]]
    msg = format_message("DAFTAR KATEGORI", content)
    await safe_edit_message(event, msg, buttons)

# ==================== KELOLA ADMIN BOT ====================
@bot.on(events.CallbackQuery(data=b'kelola_admin'))
async def kelola_admin_menu(event):
    if not is_admin_utama(event.sender_id):
        await event.answer("❌ Akses ditolak!", alert=True)
        return
    
    buttons = [
        [Button.inline("➕ Tambah Admin", b"tambah_admin")],
        [Button.inline("➖ Hapus Admin", b"hapus_admin")],
        [Button.inline("📋 List Admin", b"list_admin")],
        [Button.inline("🔙 Kembali", b"main_admin_menu")]
    ]
    
    msg = format_message("KELOLA ADMIN BOT")
    await safe_edit_message(event, msg, buttons)

@bot.on(events.CallbackQuery(data=b'tambah_admin'))
async def tambah_admin_handler(event):
    if not is_admin_utama(event.sender_id):
        return
    
    user_states[event.sender_id] = {"action": "tambah_admin"}
    msg = format_message("TAMBAH ADMIN BARU", 
                        "Forward pesan dari user yang ingin dijadikan admin atau kirim user ID:")
    await safe_edit_message(event, msg)

@bot.on(events.CallbackQuery(data=b'list_admin'))
async def list_admin_handler(event):
    if not is_admin_utama(event.sender_id):
        return
    
    admins = get_all_admin_bots()
    
    if not admins:
        content = "Belum ada admin bot yang ditambahkan."
    else:
        content = "**LIST ADMIN BOT:**\n\n"
        for admin_id, added_at in admins:
            try:
                user = await bot.get_entity(admin_id)
                name = user.first_name + (f" {user.last_name}" if user.last_name else "")
                username = f"@{user.username}" if user.username else "No username"
            except:
                name = "Unknown User"
                username = ""
            
            content += f"👤 **{name}** {username}\n"
            content += f"🆔 ID: `{admin_id}`\n"
            content += f"📅 Ditambahkan: {added_at[:10]}\n\n"
    
    buttons = [[Button.inline("🔙 Kembali", b"kelola_admin")]]
    msg = format_message("DAFTAR ADMIN BOT", content)
    await safe_edit_message(event, msg, buttons)

@bot.on(events.CallbackQuery(data=b'hapus_admin'))
async def hapus_admin_handler(event):
    if not is_admin_utama(event.sender_id):
        return
    
    admins = get_all_admin_bots()
    
    if not admins:
        buttons = [[Button.inline("🔙 Kembali", b"kelola_admin")]]
        msg = format_message("TIDAK ADA ADMIN BOT", 
                            "Belum ada admin bot yang bisa dihapus.")
        await safe_edit_message(event, msg, buttons)
        return
    
    buttons = []
    for admin_id, _ in admins:
        try:
            user = await bot.get_entity(admin_id)
            name = user.first_name + (f" {user.last_name}" if user.last_name else "")
            username = f"@{user.username}" if user.username else ""
            display_name = f"{name} {username}".strip()
        except:
            display_name = f"User ID: {admin_id}"
        
        buttons.append([Button.inline(f"🗑️ {display_name}", f"confirm_hapus_admin_{admin_id}".encode())])
    
    buttons.append([Button.inline("🔙 Kembali", b"kelola_admin")])
    
    msg = format_message("HAPUS ADMIN BOT", "Pilih admin yang ingin dihapus:")
    await safe_edit_message(event, msg, buttons)

@bot.on(events.CallbackQuery(pattern=r'confirm_hapus_admin_(\d+)'))
async def confirm_hapus_admin_handler(event):
    if not is_admin_utama(event.sender_id):
        return
    
    admin_id = int(event.data.decode().split('_')[-1])
    
    try:
        user = await bot.get_entity(admin_id)
        name = user.first_name + (f" {user.last_name}" if user.last_name else "")
        display_name = name
    except:
        display_name = f"User ID: {admin_id}"
    
    buttons = [
        [Button.inline("✅ Ya, Hapus!", f"execute_hapus_admin_{admin_id}".encode())],
        [Button.inline("❌ Batal", b"hapus_admin")]
    ]
    
    msg = format_message("KONFIRMASI HAPUS ADMIN", 
                       f"Yakin ingin menghapus **{display_name}** dari admin bot?")
    
    await safe_edit_message(event, msg, buttons)

@bot.on(events.CallbackQuery(pattern=r'execute_hapus_admin_(\d+)'))
async def execute_hapus_admin_handler(event):
    if not is_admin_utama(event.sender_id):
        return
    
    admin_id = int(event.data.decode().split('_')[-1])
    
    if delete_admin_bot(admin_id):
        try:
            user = await bot.get_entity(admin_id)
            name = user.first_name + (f" {user.last_name}" if user.last_name else "")
            display_name = name
        except:
            display_name = f"User ID: {admin_id}"
        
        buttons = [[Button.inline("🔙 Kembali ke Menu Admin", b"main_admin_menu")]]
        msg = format_message("ADMIN BERHASIL DIHAPUS", 
                           f"**{display_name}** telah dihapus dari admin bot!",
                           success=True)
        
        await safe_edit_message(event, msg, buttons)
    else:
        await event.answer("❌ Gagal menghapus admin!", alert=True)

# ==================== LOGIN NOMOR ====================
@bot.on(events.CallbackQuery(data=b'login_nomor'))
async def login_nomor_handler(event):
    if not is_authorized(event.sender_id):
        return
    
    user_states[event.sender_id] = {"action": "login_step1"}
    msg = format_message("LOGIN NOMOR BARU", 
                        "Kirim nomor HP yang ingin di-login (format: +628123456789):")
    await safe_edit_message(event, msg)

# ==================== LIST AKUN ====================
@bot.on(events.CallbackQuery(data=b'list_akun'))
async def list_akun_handler(event):
    if not is_authorized(event.sender_id):
        return
    
    kategori_list = get_kategori()
    if not kategori_list:
        buttons = [[Button.inline("🔙 Kembali", b"back_to_main")]]
        msg = format_message("BELUM ADA KATEGORI", 
                            "Belum ada kategori yang dibuat. Buat kategori dulu!",
                            success=False)
        await safe_edit_message(event, msg, buttons)
        return
    
    buttons = []
    for kat_id, kat_nama in kategori_list:
        buttons.append([Button.inline(f"📁 {kat_nama}", f"list_akun_kat_{kat_id}".encode())])
    
    buttons.append([Button.inline("🔙 Kembali", b"back_to_main")])
    
    msg = format_message("PILIH KATEGORI", 
                        "Pilih kategori untuk melihat akun-akun di dalamnya:")
    await safe_edit_message(event, msg, buttons)

@bot.on(events.CallbackQuery(pattern=r'list_akun_kat_(\d+)'))
async def list_akun_kategori_handler(event):
    if not is_authorized(event.sender_id):
        return
    
    kategori_id = int(event.data.decode().split('_')[-1])
    kategori = get_kategori_by_id(kategori_id)
    
    if not kategori:
        await event.answer("❌ Kategori tidak ditemukan!", alert=True)
        return
    
    kategori_nama = kategori['nama']
    akun_list = get_akun_by_kategori(kategori_id)
    
    if not akun_list:
        content = f"Belum ada akun di kategori **{kategori_nama}**"
    else:
        content = f"**AKUN DI KATEGORI: {kategori_nama}**\n\n"
        for akun_id, nomor, nama_akun in akun_list:
            status_emoji = "🟢"
            content += f"{status_emoji} **{nomor}**\n"
            if nama_akun:
                content += f"👤 Nama: {nama_akun}\n"
            content += f"🆔 ID: {akun_id}\n\n"
    
    buttons = [[Button.inline("🔙 Kembali", b"list_akun")]]
    msg = format_message(f"KATEGORI: {kategori_nama.upper()}", content)
    await safe_edit_message(event, msg, buttons)

# ==================== TAMBAH KONTAK ====================
@bot.on(events.CallbackQuery(data=b'tambah_kontak'))
async def tambah_kontak_handler(event):
    if not is_authorized(event.sender_id):
        return
    
    user_states[event.sender_id] = {"action": "tambah_kontak_step1", "contacts": []}
    msg = format_message("TAMBAH KONTAK", 
                        "Kirim kontak yang ingin ditambahkan satu per satu.\n\n" +
                        "Setelah selesai kirim semua kontak, ketik `/done` untuk lanjut ke step berikutnya.")
    await safe_edit_message(event, msg)

# ==================== HAPUS NOMOR ====================
@bot.on(events.CallbackQuery(data=b'hapus_nomor'))
async def hapus_nomor_handler(event):
    if not is_authorized(event.sender_id):
        return
    
    kategori_list = get_kategori()
    if not kategori_list:
        buttons = [[Button.inline("🔙 Kembali", b"back_to_main")]]
        msg = format_message("BELUM ADA KATEGORI", 
                            "Belum ada kategori yang dibuat.")
        await safe_edit_message(event, msg, buttons)
        return
    
    buttons = []
    for kat_id, kat_nama in kategori_list:
        buttons.append([Button.inline(f"📁 {kat_nama}", f"hapus_nomor_kat_{kat_id}".encode())])
    
    buttons.append([Button.inline("🔙 Kembali", b"back_to_main")])
    
    msg = format_message("HAPUS NOMOR", "Pilih kategori untuk melihat nomor yang bisa dihapus:")
    await safe_edit_message(event, msg, buttons)

@bot.on(events.CallbackQuery(pattern=r'hapus_nomor_kat_(\d+)'))
async def hapus_nomor_kategori_handler(event):
    if not is_authorized(event.sender_id):
        return
    
    kategori_id = int(event.data.decode().split('_')[-1])
    kategori = get_kategori_by_id(kategori_id)
    
    if not kategori:
        await event.answer("❌ Kategori tidak ditemukan!", alert=True)
        return
    
    kategori_nama = kategori['nama']
    akun_list = get_akun_by_kategori(kategori_id)
    
    if not akun_list:
        buttons = [[Button.inline("🔙 Kembali", b"hapus_nomor")]]
        msg = format_message(f"KATEGORI: {kategori_nama.upper()}", 
                           "Belum ada akun di kategori ini.")
        await safe_edit_message(event, msg, buttons)
        return
    
    buttons = []
    for akun_id, nomor, nama_akun in akun_list:
        display_name = f"{nomor}"
        if nama_akun:
            display_name += f" ({nama_akun})"
        buttons.append([Button.inline(f"🗑️ {display_name}", f"confirm_hapus_{akun_id}".encode())])
    
    buttons.append([Button.inline("🔙 Kembali", b"hapus_nomor")])
    
    msg = format_message(f"HAPUS NOMOR - {kategori_nama.upper()}", 
                       "Pilih nomor yang ingin dihapus:")
    await safe_edit_message(event, msg, buttons)

@bot.on(events.CallbackQuery(pattern=r'confirm_hapus_(\d+)'))
async def confirm_hapus_handler(event):
    if not is_authorized(event.sender_id):
        return
    
    akun_id = int(event.data.decode().split('_')[-1])
    akun = get_akun_by_id(akun_id)
    
    if not akun:
        await event.answer("❌ Akun tidak ditemukan!", alert=True)
        return
    
    nomor = akun['nomor']
    nama_akun = akun.get('nama_akun', '')
    display_name = f"{nomor}"
    if nama_akun:
        display_name += f" ({nama_akun})"
    
    buttons = [
        [Button.inline("✅ Ya, Hapus!", f"execute_hapus_{akun_id}".encode())],
        [Button.inline("❌ Batal", b"hapus_nomor")]
    ]
    
    msg = format_message("KONFIRMASI HAPUS", 
                       f"Yakin ingin menghapus akun **{display_name}**?\n\n" +
                       "**PERINGATAN:** Data session akan dihapus permanen!")
    
    await safe_edit_message(event, msg, buttons)

@bot.on(events.CallbackQuery(pattern=r'execute_hapus_(\d+)'))
async def execute_hapus_handler(event):
    if not is_authorized(event.sender_id):
        return
    
    akun_id = int(event.data.decode().split('_')[-1])
    akun = get_akun_by_id(akun_id)
    
    if not akun:
        await event.answer("❌ Akun tidak ditemukan!", alert=True)
        return
    
    nomor = akun['nomor']
    
    if delete_akun_by_id(akun_id):
        buttons = [[Button.inline("🔙 Kembali ke Menu", b"back_to_main")]]
        msg = format_message("BERHASIL DIHAPUS", 
                           f"Akun **{nomor}** berhasil dihapus dari database!",
                           success=True)
        
        await safe_edit_message(event, msg, buttons)
    else:
        await event.answer("❌ Gagal menghapus akun!", alert=True)

# ==================== CLEAR KONTAK ====================
@bot.on(events.CallbackQuery(data=b'clear_kontak'))
async def clear_kontak_handler(event):
    if not is_authorized(event.sender_id):
        return
    
    kategori_list = get_kategori()
    if not kategori_list:
        buttons = [[Button.inline("🔙 Kembali", b"back_to_main")]]
        msg = format_message("BELUM ADA KATEGORI", 
                            "Belum ada kategori yang dibuat.")
        await safe_edit_message(event, msg, buttons)
        return
    
    buttons = []
    for kat_id, kat_nama in kategori_list:
        buttons.append([Button.inline(f"📁 {kat_nama}", f"clear_kontak_kat_{kat_id}".encode())])
    
    buttons.append([Button.inline("🔙 Kembali", b"back_to_main")])
    
    msg = format_message("CLEAR KONTAK", "Pilih kategori untuk clear kontak dari akun:")
    await safe_edit_message(event, msg, buttons)

@bot.on(events.CallbackQuery(pattern=r'clear_kontak_kat_(\d+)'))
async def clear_kontak_kategori_handler(event):
    if not is_authorized(event.sender_id):
        return
    
    kategori_id = int(event.data.decode().split('_')[-1])
    kategori = get_kategori_by_id(kategori_id)
    
    if not kategori:
        await event.answer("❌ Kategori tidak ditemukan!", alert=True)
        return
    
    kategori_nama = kategori['nama']
    akun_list = get_akun_by_kategori(kategori_id)
    
    if not akun_list:
        buttons = [[Button.inline("🔙 Kembali", b"clear_kontak")]]
        msg = format_message(f"KATEGORI: {kategori_nama.upper()}", 
                           "Belum ada akun di kategori ini.")
        await safe_edit_message(event, msg, buttons)
        return
    
    buttons = []
    for akun_id, nomor, nama_akun in akun_list:
        display_name = f"{nomor}"
        if nama_akun:
            display_name += f" ({nama_akun})"
        buttons.append([Button.inline(f"🧹 {display_name}", f"confirm_clear_{akun_id}".encode())])
    
    buttons.append([Button.inline("🔙 Kembali", b"clear_kontak")])
    
    msg = format_message(f"CLEAR KONTAK - {kategori_nama.upper()}", 
                       "Pilih akun yang ingin di-clear kontaknya:")
    await safe_edit_message(event, msg, buttons)

@bot.on(events.CallbackQuery(pattern=r'confirm_clear_(\d+)'))
async def confirm_clear_handler(event):
    if not is_authorized(event.sender_id):
        return
    
    akun_id = int(event.data.decode().split('_')[-1])
    akun = get_akun_by_id(akun_id)
    
    if not akun:
        await event.answer("❌ Akun tidak ditemukan!", alert=True)
        return
    
    nomor = akun['nomor']
    nama_akun = akun.get('nama_akun', '')
    display_name = f"{nomor}"
    if nama_akun:
        display_name += f" ({nama_akun})"
    
    buttons = [
        [Button.inline("✅ Ya, Clear Semua!", f"execute_clear_{akun_id}".encode())],
        [Button.inline("❌ Batal", b"clear_kontak")]
    ]
    
    msg = format_message("KONFIRMASI CLEAR KONTAK", 
                       f"Yakin ingin clear SEMUA kontak dari **{display_name}**?\n\n" +
                       "**PERINGATAN:** Semua kontak akan dihapus permanen!")
    
    await safe_edit_message(event, msg, buttons)

@bot.on(events.CallbackQuery(pattern=r'execute_clear_(\d+)'))
async def execute_clear_handler(event):
    if not is_authorized(event.sender_id):
        return
    
    akun_id = int(event.data.decode().split('_')[-1])
    akun = get_akun_by_id(akun_id)
    
    if not akun:
        await event.answer("❌ Akun tidak ditemukan!", alert=True)
        return
    
    nomor = akun['nomor']
    session_string = akun['session_string']
    
    try:
        client = TelegramClient(StringSession(session_string), API_ID, API_HASH)
        await client.connect()
        
        contacts = await client(GetContactsRequest(hash=0))
        
        if not contacts.users:
            await client.disconnect()
            buttons = [[Button.inline("🔙 Kembali ke Menu", b"back_to_main")]]
            msg = format_message("TIDAK ADA KONTAK", 
                               f"Akun **{nomor}** tidak punya kontak untuk di-clear.")
            await safe_edit_message(event, msg, buttons)
            return
        
        user_ids = [user.id for user in contacts.users]
        await client(DeleteContactsRequest(user_ids))
        
        await client.disconnect()
        
        buttons = [[Button.inline("🔙 Kembali ke Menu", b"back_to_main")]]
        msg = format_message("KONTAK BERHASIL DI-CLEAR", 
                           f"**{len(user_ids)} kontak** berhasil dihapus dari akun **{nomor}**!",
                           success=True)
        
        await safe_edit_message(event, msg, buttons)
        
    except Exception as e:
        logger.error(f"Error clearing contacts: {e}")
        await event.answer(f"❌ Error: {str(e)}", alert=True)

# ==================== INVITE KE GRUP/CHANNEL ====================
@bot.on(events.CallbackQuery(data=b'invite_grup'))
async def invite_grup_handler(event):
    if not is_authorized(event.sender_id):
        return
    
    kategori_list = get_kategori()
    if not kategori_list:
        buttons = [[Button.inline("🔙 Kembali", b"back_to_main")]]
        msg = format_message("BELUM ADA KATEGORI", 
                            "Belum ada kategori yang dibuat.")
        await safe_edit_message(event, msg, buttons)
        return
    
    buttons = []
    for kat_id, kat_nama in kategori_list:
        buttons.append([Button.inline(f"📁 {kat_nama}", f"invite_grup_kat_{kat_id}".encode())])
    
    buttons.append([Button.inline("🔙 Kembali", b"back_to_main")])
    
    msg = format_message("INVITE KE GRUP/CHANNEL", 
                        "Pilih kategori akun yang ingin digunakan:")
    await safe_edit_message(event, msg, buttons)

@bot.on(events.CallbackQuery(pattern=r'invite_grup_kat_(\d+)'))
async def invite_grup_kategori_handler(event):
    if not is_authorized(event.sender_id):
        return
    
    kategori_id = int(event.data.decode().split('_')[-1])
    kategori = get_kategori_by_id(kategori_id)
    
    if not kategori:
        await event.answer("❌ Kategori tidak ditemukan!", alert=True)
        return
    
    kategori_nama = kategori['nama']
    akun_list = get_akun_by_kategori(kategori_id)
    
    if not akun_list:
        buttons = [[Button.inline("🔙 Kembali", b"invite_grup")]]
        msg = format_message(f"KATEGORI: {kategori_nama.upper()}", 
                           "Belum ada akun di kategori ini.")
        await safe_edit_message(event, msg, buttons)
        return
    
    buttons = []
    for akun_id, nomor, nama_akun in akun_list:
        display_name = f"{nomor}"
        if nama_akun:
            display_name += f" ({nama_akun})"
        buttons.append([Button.inline(f"👥 {display_name}", f"pilih_akun_invite_{akun_id}".encode())])
    
    buttons.append([Button.inline("🔙 Kembali", b"invite_grup")])
    
    msg = format_message(f"PILIH AKUN - {kategori_nama.upper()}", 
                       "Pilih akun yang ingin digunakan untuk invite kontak:")
    await safe_edit_message(event, msg, buttons)

@bot.on(events.CallbackQuery(pattern=r'pilih_akun_invite_(\d+)'))
async def pilih_akun_invite_handler(event):
    if not is_authorized(event.sender_id):
        return
    
    akun_id = int(event.data.decode().split('_')[-1])
    
    user_states[event.sender_id] = {
        "action": "invite_input_grup",
        "akun_id": akun_id
    }
    
    msg = format_message("INPUT GRUP/CHANNEL", 
                       "Kirim username grup/channel atau invite link nya:\n\n" +
                       "**Contoh:**\n" +
                       "• @namagrup\n" +
                       "• https://t.me/namagrup\n" +
                       "• https://t.me/+AbCdEfGhIjK")
    
    await safe_edit_message(event, msg)

# ==================== PINDAH KATEGORI ====================
@bot.on(events.CallbackQuery(data=b'pindah_kategori'))
async def pindah_kategori_handler(event):
    if not is_admin_utama(event.sender_id):
        await event.answer("❌ Akses ditolak!", alert=True)
        return
    
    kategori_list = get_kategori()
    
    if not kategori_list:
        buttons = [[Button.inline("🔙 Kembali", b"main_admin_menu")]]
        msg = format_message("BELUM ADA KATEGORI", 
                            "Belum ada kategori yang dibuat.")
        await safe_edit_message(event, msg, buttons)
        return
    
    buttons = []
    for kat_id, kat_nama in kategori_list:
        buttons.append([Button.inline(f"📁 {kat_nama}", f"pindah_dari_kat_{kat_id}".encode())])
    
    buttons.append([Button.inline("🔙 Kembali", b"main_admin_menu")])
    
    msg = format_message("PINDAH NOMOR KATEGORI", 
                        "Pilih kategori ASAL (kategori yang punya nomor yang ingin dipindah):")
    await safe_edit_message(event, msg, buttons)

@bot.on(events.CallbackQuery(pattern=r'pindah_dari_kat_(\d+)'))
async def pindah_dari_kategori_handler(event):
    if not is_admin_utama(event.sender_id):
        return
    
    kategori_id = int(event.data.decode().split('_')[-1])
    kategori = get_kategori_by_id(kategori_id)
    
    if not kategori:
        await event.answer("❌ Kategori tidak ditemukan!", alert=True)
        return
    
    kategori_nama = kategori['nama']
    akun_list = get_akun_by_kategori(kategori_id)
    
    if not akun_list:
        buttons = [[Button.inline("🔙 Kembali", b"pindah_kategori")]]
        msg = format_message(f"KATEGORI: {kategori_nama.upper()}", 
                           "Belum ada akun di kategori ini.")
        await safe_edit_message(event, msg, buttons)
        return
    
    buttons = []
    for akun_id, nomor, nama_akun in akun_list:
        display_name = f"{nomor}"
        if nama_akun:
            display_name += f" ({nama_akun})"
        buttons.append([Button.inline(f"📱 {display_name}", f"pilih_nomor_pindah_{akun_id}".encode())])
    
    buttons.append([Button.inline("🔙 Kembali", b"pindah_kategori")])
    
    msg = format_message(f"PILIH NOMOR - {kategori_nama.upper()}", 
                       "Pilih nomor yang ingin dipindah:")
    await safe_edit_message(event, msg, buttons)

@bot.on(events.CallbackQuery(pattern=r'pilih_nomor_pindah_(\d+)'))
async def pilih_nomor_pindah_handler(event):
    if not is_admin_utama(event.sender_id):
        return
    
    akun_id = int(event.data.decode().split('_')[-1])
    akun = get_akun_by_id(akun_id)
    
    if not akun:
        await event.answer("❌ Akun tidak ditemukan!", alert=True)
        return
    
    nomor = akun['nomor']
    nama_akun = akun.get('nama_akun', '')
    current_kategori_id = akun['kategori_id']
    
    # Get all kategori except current
    all_kategori = get_kategori()
    other_kategori = [(kat_id, kat_nama) for kat_id, kat_nama in all_kategori if kat_id != current_kategori_id]
    
    if not other_kategori:
        buttons = [[Button.inline("🔙 Kembali", b"pindah_kategori")]]
        msg = format_message("TIDAK ADA KATEGORI LAIN", 
                           "Tidak ada kategori lain untuk memindahkan nomor ini.")
        await safe_edit_message(event, msg, buttons)
        return
    
    display_name = f"{nomor}"
    if nama_akun:
        display_name += f" ({nama_akun})"
    
    buttons = []
    for kat_id, kat_nama in other_kategori:
        buttons.append([Button.inline(f"📁 {kat_nama}", f"pindah_ke_kat_{akun_id}_{kat_id}".encode())])
    
    buttons.append([Button.inline("🔙 Kembali", b"pindah_kategori")])
    
    msg = format_message("PILIH KATEGORI TUJUAN", 
                       f"Mau pindahkan **{display_name}** ke kategori mana?")
    await safe_edit_message(event, msg, buttons)

@bot.on(events.CallbackQuery(pattern=r'pindah_ke_kat_(\d+)_(\d+)'))
async def pindah_ke_kategori_handler(event):
    if not is_admin_utama(event.sender_id):
        return
    
    data_parts = event.data.decode().split('_')
    akun_id = int(data_parts[-2])
    new_kategori_id = int(data_parts[-1])
    
    akun = get_akun_by_id(akun_id)
    kategori = get_kategori_by_id(new_kategori_id)
    
    if not akun or not kategori:
        await event.answer("❌ Data tidak ditemukan!", alert=True)
        return
    
    nomor = akun['nomor']
    nama_akun = akun.get('nama_akun', '')
    kategori_nama = kategori['nama']
    
    if update_akun_kategori(akun_id, new_kategori_id):
        display_name = f"{nomor}"
        if nama_akun:
            display_name += f" ({nama_akun})"
        
        buttons = [[Button.inline("🔙 Kembali ke Menu Admin", b"main_admin_menu")]]
        msg = format_message("NOMOR BERHASIL DIPINDAH", 
                           f"**Nomor:** {display_name}\n" +
                           f"**Kategori baru:** {kategori_nama}",
                           success=True)
        
        await safe_edit_message(event, msg, buttons)
    else:
        await event.answer("❌ Gagal memindahkan nomor!", alert=True)

# ==================== KATEGORI SELECTION HANDLERS ====================
@bot.on(events.CallbackQuery(data=b'buat_kategori_baru'))
async def buat_kategori_handler(event):
    if not is_authorized(event.sender_id):
        return
    
    user_states[event.sender_id] = {"action": "buat_kategori"}
    msg = format_message("BUAT KATEGORI BARU", 
                        "Kirim nama kategori yang ingin dibuat:")
    await safe_edit_message(event, msg)

@bot.on(events.CallbackQuery(pattern=r'pilih_kategori_(\d+)'))
async def pilih_kategori_handler(event):
    if not is_authorized(event.sender_id):
        return
    
    kategori_id = int(event.data.decode().split('_')[-1])
    user_id = event.sender_id
    
    if user_id not in user_states:
        return
    
    state = user_states[user_id]
    kategori = get_kategori_by_id(kategori_id)
    
    if not kategori:
        await event.answer("❌ Kategori tidak ditemukan!", alert=True)
        return
    
    kategori_nama = kategori['nama']
    
    if state["action"] == "login_step3_pilih_kategori":
        # Save akun to database
        if add_akun_tg(state["nomor"], state["session_string"], kategori_id, state["nama_akun"]):
            msg = format_message("LOGIN BERHASIL", 
                               f"Akun **{state['nomor']}** berhasil ditambahkan ke kategori **{kategori_nama}**!\n\n" +
                               f"👤 **Nama Akun:** {state['nama_akun']}",
                               success=True)
            
            buttons = [[Button.inline("🔙 Kembali ke Menu", b"back_to_main")]]
            await safe_edit_message(event, msg, buttons)
        else:
            await event.answer("❌ Nomor ini sudah ada di database!", alert=True)
        
        user_states.pop(user_id, None)
    
    elif state["action"] == "tambah_kontak_step2_pilih_kategori":
        # Get akun in selected kategori
        akun_list = get_akun_by_kategori(kategori_id)
        
        if not akun_list:
            await event.answer(f"❌ Belum ada akun di kategori {kategori_nama}!", alert=True)
            return
        
        # Show akun selection
        buttons = []
        for akun_id, nomor, nama_akun in akun_list:
            display_name = f"{nomor}"
            if nama_akun:
                display_name += f" ({nama_akun})"
            buttons.append([Button.inline(f"📱 {display_name}", f"pilih_akun_kontak_{akun_id}".encode())])
        
        buttons.append([Button.inline("🔙 Kembali", b"tambah_kontak")])
        
        user_states[user_id]["selected_kategori"] = kategori_id
        
        msg = format_message(f"PILIH AKUN - {kategori_nama.upper()}", 
                           "Pilih akun yang ingin digunakan untuk menyimpan kontak:")
        await safe_edit_message(event, msg, buttons)

@bot.on(events.CallbackQuery(pattern=r'pilih_akun_kontak_(\d+)'))
async def pilih_akun_kontak_handler(event):
    if not is_authorized(event.sender_id):
        return
    
    akun_id = int(event.data.decode().split('_')[-1])
    user_id = event.sender_id
    
    # Get akun data
    akun = get_akun_by_id(akun_id)
    
    # Get temp contacts
    temp_contacts = get_temp_contacts(user_id)
    
    if not akun or not temp_contacts:
        await event.answer("❌ Data tidak ditemukan!", alert=True)
        return
    
    nomor = akun['nomor']
    session_string = akun['session_string']
    
    try:
        # Connect with the selected account
        client = TelegramClient(StringSession(session_string), API_ID, API_HASH)
        await client.connect()
        
        # Prepare contacts for import
        contacts_to_import = []
        for i, contact_data in enumerate(temp_contacts):
            contact = InputPhoneContact(
                client_id=i,
                phone='+' + contact_data['phone'].replace('+', ''),
                first_name=contact_data['first_name'],
                last_name=contact_data['last_name'] or ''
            )
            contacts_to_import.append(contact)
        
        # Import contacts
        result = await client(ImportContactsRequest(contacts_to_import))
        
        await client.disconnect()
        
        # Clear temp contacts
        clear_temp_contacts(user_id)
        
        success_count = len(result.imported)
        total_count = len(contacts_to_import)
        
        msg = format_message("KONTAK BERHASIL DITAMBAHKAN", 
                           f"**Akun:** {nomor}\n" +
                           f"**Berhasil:** {success_count}/{total_count} kontak\n\n" +
                           "Semua kontak sudah disimpan ke akun Telegram yang dipilih!",
                           success=True)
        
        buttons = [[Button.inline("🔙 Kembali ke Menu", b"back_to_main")]]
        await safe_edit_message(event, msg, buttons)
        
        user_states.pop(user_id, None)
            
    except Exception as e:
        logger.error(f"Error adding contacts: {e}")
        await event.answer(f"❌ Error: {str(e)}", alert=True)

# ==================== MESSAGE HANDLERS ====================
@bot.on(events.NewMessage(func=lambda e: not e.message.text.startswith('/') if e.message.text else True))
async def message_handler(event):
    if not is_authorized(event.sender_id):
        return
    
    user_id = event.sender_id
    
    if user_id not in user_states:
        return
    
    state = user_states[user_id]
    
    # Handle Login Steps
    if state["action"] == "login_step1":
        nomor = event.message.text.strip()
        if not nomor.startswith('+'):
            await safe_send_message(event, "❌ Format nomor salah! Harus dimulai dengan + (contoh: +628123456789)")
            return
        
        try:
            # Create new client for this number
            client = TelegramClient(StringSession(), API_ID, API_HASH)
            await client.connect()
            
            result = await client.send_code_request(nomor)
            
            user_states[user_id] = {
                "action": "login_step2", 
                "nomor": nomor,
                "client": client,
                "phone_code_hash": result.phone_code_hash
            }
            
            msg = format_message("KODE OTP DIKIRIM", 
                               f"Kode OTP telah dikirim ke **{nomor}**\n\nKirim kode OTP yang Anda terima:")
            await safe_send_message(event, msg)
        except Exception as e:
            logger.error(f"Error in login step 1: {e}")
            await safe_send_message(event, f"❌ **Error:** {str(e)}")
            user_states.pop(user_id, None)
    
    elif state["action"] == "login_step2":
        code = event.message.text.strip()
        
        try:
            client = state["client"]
            nomor = state["nomor"]
            
            await client.sign_in(nomor, code, phone_code_hash=state["phone_code_hash"])
            
            # Get session string
            session_string = client.session.save()
            
            # Get user info
            me = await client.get_me()
            nama_akun = me.first_name + (f" {me.last_name}" if me.last_name else "")
            
            await client.disconnect()
            
            user_states[user_id] = {
                "action": "login_step3_pilih_kategori",
                "nomor": nomor,
                "session_string": session_string,
                "nama_akun": nama_akun
            }
            
            # Show kategori selection
            await show_kategori_selection(event, "Pilih kategori untuk nomor ini:")
            
        except SessionPasswordNeededError:
            user_states[user_id]["action"] = "login_step2_password"
            msg = format_message("BUTUH PASSWORD 2FA", 
                               "Akun ini menggunakan 2FA. Kirim password 2FA Anda:")
            await safe_send_message(event, msg)
        except PhoneCodeInvalidError:
            await safe_send_message(event, "❌ **Kode OTP salah!** Coba lagi dengan kode yang benar:")
        except Exception as e:
            logger.error(f"Error in login step 2: {e}")
            await safe_send_message(event, f"❌ **Error:** {str(e)}")
            user_states.pop(user_id, None)
    
    elif state["action"] == "login_step2_password":
        password = event.message.text.strip()
        
        try:
            client = state["client"]
            await client.sign_in(password=password)
            
            # Get session string
            session_string = client.session.save()
            
            # Get user info
            me = await client.get_me()
            nama_akun = me.first_name + (f" {me.last_name}" if me.last_name else "")
            
            await client.disconnect()
            
            user_states[user_id] = {
                "action": "login_step3_pilih_kategori",
                "nomor": state["nomor"],
                "session_string": session_string,
                "nama_akun": nama_akun
            }
            
            await show_kategori_selection(event, "Pilih kategori untuk nomor ini:")
            
        except PasswordHashInvalidError:
            await safe_send_message(event, "❌ **Password salah!** Coba lagi:")
        except Exception as e:
            logger.error(f"Error in login password step: {e}")
            await safe_send_message(event, f"❌ **Error:** {str(e)}")
            user_states.pop(user_id, None)
    
    # Handle Tambah Kontak
    elif state["action"] == "tambah_kontak_step1":
        if event.message.contact:
            contact_data = {
                "phone": event.message.contact.phone_number,
                "first_name": event.message.contact.first_name,
                "last_name": event.message.contact.last_name
            }
            state["contacts"].append(contact_data)
            
            count = len(state["contacts"])
            msg = f"✅ **Kontak ke-{count} berhasil ditambahkan!**\n\n"
            msg += f"👤 **Nama:** {contact_data['first_name']} {contact_data['last_name'] or ''}\n"
            msg += f"📞 **Nomor:** +{contact_data['phone']}\n\n"
            msg += "Kirim kontak lain atau ketik `/done` jika sudah selesai."
            
            await safe_send_message(event, msg)
        else:
            await safe_send_message(event, "❌ **Kirim kontak yang valid!** Bukan text biasa.")
    
    # Handle Tambah Admin
    elif state["action"] == "tambah_admin":
        if event.forward and event.forward.from_id:
            new_admin_id = event.forward.from_id.user_id
        else:
            try:
                new_admin_id = int(event.message.text.strip())
            except ValueError:
                await safe_send_message(event, "❌ **Format salah!** Kirim user ID yang valid atau forward pesan dari user.")
                return
        
        # Check if already admin
        if is_admin_utama(new_admin_id) or is_admin_bot(new_admin_id):
            await safe_send_message(event, "❌ **User ini sudah jadi admin!**")
            return
        
        # Add to database
        if add_admin_bot(new_admin_id, user_id):
            try:
                user = await bot.get_entity(new_admin_id)
                name = user.first_name + (f" {user.last_name}" if user.last_name else "")
                await safe_send_message(event, f"✅ **{name}** berhasil ditambahkan sebagai admin bot!")
            except:
                await safe_send_message(event, f"✅ **User ID {new_admin_id}** berhasil ditambahkan sebagai admin bot!")
        else:
            await safe_send_message(event, "❌ **User ini sudah jadi admin!**")
        
        user_states.pop(user_id, None)
    
    elif state["action"] == "buat_kategori" or state["action"] == "tambah_kategori":
        nama_kategori = event.message.text.strip()
        
        if not nama_kategori:
            await safe_send_message(event, "❌ **Nama kategori tidak boleh kosong!**")
            return
        
        if add_kategori(nama_kategori):
            msg = format_message("KATEGORI BERHASIL DIBUAT", 
                               f"Kategori **{nama_kategori}** telah dibuat!",
                               success=True)
            await safe_send_message(event, msg)
            
            # Continue with previous flow if needed
            if user_id in user_states:
                previous_state = user_states[user_id]
                if "login_step3_pilih_kategori" in str(previous_state.get("action", "")):
                    await show_kategori_selection(event, "Pilih kategori untuk nomor ini:")
                    return
                elif "tambah_kontak_step2_pilih_kategori" in str(previous_state.get("action", "")):
                    await show_kategori_selection(event, "Pilih kategori akun yang ingin digunakan:")
                    return
        else:
            await safe_send_message(event, "❌ **Nama kategori sudah ada!** Gunakan nama yang lain.")
            return
        
        user_states.pop(user_id, None)
    
    elif state["action"] == "edit_nama_kategori":
        nama_baru = event.message.text.strip()
        
        if not nama_baru:
            await safe_send_message(event, "❌ **Nama kategori tidak boleh kosong!**")
            return
        
        kategori_id = state["kategori_id"]
        old_name = state["old_name"]
        
        if update_kategori(kategori_id, nama_baru):
            buttons = [[Button.inline("🔙 Kembali ke Menu Admin", b"main_admin_menu")]]
            msg = format_message("NAMA KATEGORI BERHASIL DIUBAH", 
                               f"**Nama lama:** {old_name}\n**Nama baru:** {nama_baru}",
                               success=True)
            await safe_send_message(event, msg, buttons)
        else:
            await safe_send_message(event, "❌ **Nama kategori sudah ada!** Gunakan nama yang lain.")
            return
        
        user_states.pop(user_id, None)
    
    elif state["action"] == "invite_input_grup":
        grup_input = event.message.text.strip()
        akun_id = state["akun_id"]
        
        try:
            # Get akun data
            akun = get_akun_by_id(akun_id)
            
            if not akun:
                await safe_send_message(event, "❌ **Akun tidak ditemukan!**")
                user_states.pop(user_id, None)
                return
            
            nomor = akun['nomor']
            session_string = akun['session_string']
            
            # Connect with the account
            client = TelegramClient(StringSession(session_string), API_ID, API_HASH)
            await client.connect()
            
            # Get the target entity (group/channel)
            try:
                target_entity = await client.get_entity(grup_input)
            except Exception:
                await safe_send_message(event, "❌ **Grup/Channel tidak ditemukan!** Cek lagi username atau link nya.")
                await client.disconnect()
                return
            
            # Get all contacts
            contacts = await client(GetContactsRequest(hash=0))
            
            if not contacts.users:
                await client.disconnect()
                await safe_send_message(event, "❌ **Akun ini tidak punya kontak untuk di-invite!**")
                user_states.pop(user_id, None)
                return
            
            # Invite contacts to the group/channel
            success_count = 0
            total_count = len(contacts.users)
            
            msg_status = await safe_send_message(event, format_message(
                "PROSES INVITE...", 
                f"Mulai invite {total_count} kontak ke grup/channel..."
            ))
            
            for i, user in enumerate(contacts.users):
                try:
                    if isinstance(target_entity, Channel):
                        await client(InviteToChannelRequest(target_entity, [user]))
                    else:
                        await client(AddChatUserRequest(target_entity.id, user.id, 0))
                    
                    success_count += 1
                    
                    # Update progress every 10 invites
                    if (i + 1) % 10 == 0:
                        try:
                            progress_msg = format_message(
                                "PROSES INVITE...", 
                                f"Progress: {i + 1}/{total_count}\nBerhasil: {success_count}"
                            )
                            await safe_edit_message(msg_status, progress_msg)
                        except:
                            pass  # Ignore edit errors during progress updates
                        
                        # Add delay to avoid flood limits
                        await asyncio.sleep(2)
                
                except Exception:
                    # Skip users that can't be added
                    continue
            
            await client.disconnect()
            
            # Final result
            buttons = [[Button.inline("🔙 Kembali ke Menu", b"back_to_main")]]
            msg = format_message(
                "INVITE SELESAI", 
                f"**Akun:** {nomor}\n"
                f"**Target:** {target_entity.title if hasattr(target_entity, 'title') else grup_input}\n"
                f"**Berhasil di-invite:** {success_count}/{total_count} kontak\n\n"
                "Proses invite sudah selesai!",
                success=True
            )
            try:
                await safe_edit_message(msg_status, msg, buttons)
            except:
                await safe_send_message(event, msg, buttons)
            
        except Exception as e:
            logger.error(f"Error in invite process: {e}")
            await safe_send_message(event, f"❌ **Error:** {str(e)}")
        finally:
            user_states.pop(user_id, None)

# Done Command Handler
@bot.on(events.NewMessage(pattern='/done'))
async def done_handler(event):
    if not is_authorized(event.sender_id):
        return
    
    user_id = event.sender_id
    
    if user_id not in user_states:
        return
    
    state = user_states[user_id]
    
    if state["action"] == "tambah_kontak_step1":
        if not state["contacts"]:
            await safe_send_message(event, "❌ **Belum ada kontak yang ditambahkan!**")
            return
        
        # Save contacts temporarily
        clear_temp_contacts(user_id)  # Clear old temp contacts
        
        for contact in state["contacts"]:
            add_temp_contact(user_id, contact)
        
        user_states[user_id] = {"action": "tambah_kontak_step2_pilih_kategori"}
        
        message_text = f"✅ **{len(state['contacts'])} kontak telah disimpan sementara!**\n\n"
        message_text += "Sekarang pilih kategori akun yang ingin digunakan untuk menyimpan kontak:"
        
        await show_kategori_selection(event, message_text)

# Helper function to show kategori selection
async def show_kategori_selection(event, message_text):
    kategori_list = get_kategori()
    
    buttons = []
    for kat_id, kat_nama in kategori_list:
        buttons.append([Button.inline(f"📁 {kat_nama}", f"pilih_kategori_{kat_id}".encode())])
    
    buttons.append([Button.inline("➕ Buat Kategori Baru", b"buat_kategori_baru")])
    
    if not kategori_list:
        message_text = "Belum ada kategori yang dibuat.\n\nBuat kategori baru dulu:"
        buttons = [[Button.inline("➕ Buat Kategori Baru", b"buat_kategori_baru")]]
    
    msg = format_message("PILIH KATEGORI", message_text)
    
    if hasattr(event, 'edit'):
        await safe_edit_message(event, msg, buttons)
    else:
        await safe_send_message(event, msg, buttons)

# ==================== ERROR HANDLER ====================
@bot.on(events.NewMessage)
async def error_handler(event):
    # Skip if already handled by other handlers
    if event.message.text and (event.message.text.startswith('/') or 
                               event.sender_id not in user_states):
        return
    
    # Handle unknown messages
    if not is_authorized(event.sender_id):
        return
    
    user_id = event.sender_id
    if user_id in user_states:
        state = user_states[user_id]
        
        # Handle states that expect text input but not handled by message_handler
        expected_text_states = ["buat_kategori", "tambah_kategori", "edit_nama_kategori", "invite_input_grup", 
                               "login_step1", "login_step2", "login_step2_password", 
                               "tambah_admin"]
        
        if state["action"] not in expected_text_states:
            msg = "❌ **Perintah tidak dikenali!**\n\n" + \
                  "Gunakan tombol yang tersedia atau ketik /start untuk kembali ke menu utama."
            await safe_send_message(event, msg)

# ==================== MAIN FUNCTION ====================
async def main():
    async with TelegramClient("bot", api_id, api_hash) as bot:
        await bot.start(bot_token=bot_token)
        print("🤖 Bot jalan...")
        await bot.run_until_disconnected()

# ==================== HEALTH CHECK & BACKUP ====================
def health_check():
    """Check kesehatan JSON files"""
    try:
        if not os.path.exists(DATA_DIR):
            print("❌ Data directory tidak ditemukan!")
            return False
        
        files_to_check = [KATEGORI_FILE, AKUN_TG_FILE, TEMP_CONTACTS_FILE, ADMIN_BOTS_FILE]
        
        for file_path in files_to_check:
            data = storage.read_json(file_path)
            if not isinstance(data, list):
                print(f"❌ File {file_path} format tidak valid!")
                return False
        
        print("✅ Semua JSON files sehat")
        return True
        
    except Exception as e:
        print(f"❌ Health check error: {e}")
        return False

def create_backup():
    """Buat backup dari semua data JSON"""
    try:
        backup_dir = os.path.join(DATA_DIR, "backups")
        if not os.path.exists(backup_dir):
            os.makedirs(backup_dir)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_subdir = os.path.join(backup_dir, f"backup_{timestamp}")
        os.makedirs(backup_subdir)
        
        files_to_backup = [KATEGORI_FILE, AKUN_TG_FILE, TEMP_CONTACTS_FILE, ADMIN_BOTS_FILE]
        
        for file_path in files_to_backup:
            if os.path.exists(file_path):
                filename = os.path.basename(file_path)
                backup_path = os.path.join(backup_subdir, filename)
                shutil.copy2(file_path, backup_path)
        
        print(f"✅ Backup berhasil dibuat di: {backup_subdir}")
        return backup_subdir
        
    except Exception as e:
        print(f"❌ Backup error: {e}")
        return None

def cleanup_old_backups(keep_days=7):
    """Hapus backup lama"""
    try:
        backup_dir = os.path.join(DATA_DIR, "backups")
        if not os.path.exists(backup_dir):
            return
        
        current_time = time.time()
        cutoff_time = current_time - (keep_days * 24 * 60 * 60)
        
        removed_count = 0
        for backup_folder in os.listdir(backup_dir):
            backup_path = os.path.join(backup_dir, backup_folder)
            if os.path.isdir(backup_path):
                folder_time = os.path.getctime(backup_path)
                if folder_time < cutoff_time:
                    shutil.rmtree(backup_path)
                    removed_count += 1
        
        if removed_count > 0:
            print(f"🧹 {removed_count} backup lama berhasil dihapus")
        
    except Exception as e:
        print(f"❌ Cleanup error: {e}")

# ==================== ENTRY POINT ====================
if __name__ == "__main__":
    asyncio.run(main())
