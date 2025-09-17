import asyncio
import json
import os
from datetime import datetime
from typing import Dict, List, Optional, Any
import threading
from telethon import TelegramClient, events, Button
from telethon.sessions import StringSession
from telethon.tl.types import InputPhoneContact, User, Chat, Channel
from telethon.errors import SessionPasswordNeededError, PhoneCodeInvalidError, PasswordHashInvalidError
from telethon.tl.functions.contacts import ImportContactsRequest, DeleteContactsRequest, GetContactsRequest
from telethon.tl.functions.channels import InviteToChannelRequest
from telethon.tl.functions.messages import AddChatUserRequest

# Konfigurasi Bot
API_ID = "20755791"
API_HASH = "3d09356fe14a31a5baaad296a1abef80"
BOT_TOKEN = "8426128734:AAHYVpJCy7LrofTI3AzyUNhB_42hQnVNwiA"

# Admin Configuration
ADMIN_UTAMA = 5988451717
ADMIN_BOTS = []

# JSON Storage Configuration
DATA_DIR = "bot_data"
KATEGORI_FILE = os.path.join(DATA_DIR, "kategori.json")
AKUN_TG_FILE = os.path.join(DATA_DIR, "akun_tg.json")
TEMP_CONTACTS_FILE = os.path.join(DATA_DIR, "temp_contacts.json")
ADMIN_BOTS_FILE = os.path.join(DATA_DIR, "admin_bots.json")

# Thread lock untuk file operations
file_lock = threading.Lock()

class JSONStorage:
    """Thread-safe JSON storage manager"""
    
    def __init__(self):
        self.ensure_data_dir()
        self.init_json_files()
    
    def ensure_data_dir(self):
        """Pastikan direktori data ada"""
        if not os.path.exists(DATA_DIR):
            os.makedirs(DATA_DIR)
    
    def init_json_files(self):
        """Inisialisasi file JSON jika belum ada"""
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
        """Baca data dari file JSON dengan thread safety"""
        with file_lock:
            try:
                if not os.path.exists(file_path):
                    return []
                
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    return data if isinstance(data, list) else []
            except (json.JSONDecodeError, FileNotFoundError):
                return []
            except Exception as e:
                print(f"Error reading {file_path}: {e}")
                return []
    
    def write_json(self, file_path: str, data: List[Dict]) -> bool:
        """Tulis data ke file JSON dengan thread safety"""
        with file_lock:
            try:
                # Create backup
                backup_path = file_path + '.backup'
                if os.path.exists(file_path):
                    import shutil
                    shutil.copy2(file_path, backup_path)
                
                # Write new data
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
                
                # Remove backup if write successful
                if os.path.exists(backup_path):
                    os.remove(backup_path)
                
                return True
            except Exception as e:
                print(f"Error writing {file_path}: {e}")
                # Restore backup if exists
                backup_path = file_path + '.backup'
                if os.path.exists(backup_path):
                    import shutil
                    shutil.copy2(backup_path, file_path)
                    os.remove(backup_path)
                return False
    
    def get_next_id(self, file_path: str) -> int:
        """Generate ID berikutnya untuk data"""
        data = self.read_json(file_path)
        if not data:
            return 1
        
        max_id = max([item.get('id', 0) for item in data], default=0)
        return max_id + 1

# Initialize storage
storage = JSONStorage()

# Helper Functions untuk Kategori
def get_kategori() -> List[tuple]:
    """Get semua kategori"""
    data = storage.read_json(KATEGORI_FILE)
    return [(item['id'], item['nama']) for item in data]

def add_kategori(nama: str) -> bool:
    """Tambah kategori baru"""
    data = storage.read_json(KATEGORI_FILE)
    
    # Check duplicate
    if any(item['nama'].lower() == nama.lower() for item in data):
        return False
    
    new_kategori = {
        'id': storage.get_next_id(KATEGORI_FILE),
        'nama': nama,
        'created_at': datetime.now().isoformat()
    }
    
    data.append(new_kategori)
    return storage.write_json(KATEGORI_FILE, data)

def update_kategori(kategori_id: int, nama_baru: str) -> bool:
    """Update nama kategori"""
    data = storage.read_json(KATEGORI_FILE)
    
    # Check duplicate (exclude current)
    if any(item['nama'].lower() == nama_baru.lower() and item['id'] != kategori_id for item in data):
        return False
    
    for item in data:
        if item['id'] == kategori_id:
            item['nama'] = nama_baru
            return storage.write_json(KATEGORI_FILE, data)
    
    return False

def get_kategori_by_id(kategori_id: int) -> Optional[Dict]:
    """Get kategori by ID"""
    data = storage.read_json(KATEGORI_FILE)
    return next((item for item in data if item['id'] == kategori_id), None)

# Helper Functions untuk Akun TG
def get_akun_by_kategori(kategori_id: int) -> List[tuple]:
    """Get akun berdasarkan kategori"""
    data = storage.read_json(AKUN_TG_FILE)
    filtered_data = [item for item in data if item['kategori_id'] == kategori_id]
    return [(item['id'], item['nomor'], item.get('nama_akun', '')) for item in filtered_data]

def add_akun_tg(nomor: str, session_string: str, kategori_id: int, nama_akun: str = '') -> bool:
    """Tambah akun TG baru"""
    data = storage.read_json(AKUN_TG_FILE)
    
    # Check duplicate
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
    """Get akun by ID"""
    data = storage.read_json(AKUN_TG_FILE)
    return next((item for item in data if item['id'] == akun_id), None)

def delete_akun_by_id(akun_id: int) -> bool:
    """Hapus akun by ID"""
    data = storage.read_json(AKUN_TG_FILE)
    original_length = len(data)
    data = [item for item in data if item['id'] != akun_id]
    
    if len(data) < original_length:
        return storage.write_json(AKUN_TG_FILE, data)
    return False

def update_akun_kategori(akun_id: int, new_kategori_id: int) -> bool:
    """Update kategori akun"""
    data = storage.read_json(AKUN_TG_FILE)
    
    for item in data:
        if item['id'] == akun_id:
            item['kategori_id'] = new_kategori_id
            return storage.write_json(AKUN_TG_FILE, data)
    
    return False

# Helper Functions untuk Temp Contacts
def add_temp_contact(user_id: int, contact_data: Dict) -> bool:
    """Tambah temporary contact"""
    data = storage.read_json(TEMP_CONTACTS_FILE)
    
    new_contact = {
        'user_id': user_id,
        'contact_data': contact_data,
        'created_at': datetime.now().isoformat()
    }
    
    data.append(new_contact)
    return storage.write_json(TEMP_CONTACTS_FILE, data)

def get_temp_contacts(user_id: int) -> List[Dict]:
    """Get temporary contacts by user ID"""
    data = storage.read_json(TEMP_CONTACTS_FILE)
    return [item['contact_data'] for item in data if item['user_id'] == user_id]

def clear_temp_contacts(user_id: int) -> bool:
    """Clear temporary contacts by user ID"""
    data = storage.read_json(TEMP_CONTACTS_FILE)
    original_length = len(data)
    data = [item for item in data if item['user_id'] != user_id]
    
    if len(data) < original_length:
        return storage.write_json(TEMP_CONTACTS_FILE, data)
    return True

# Helper Functions untuk Admin Bots
def is_admin_utama(user_id: int) -> bool:
    return user_id == ADMIN_UTAMA

def is_admin_bot(user_id: int) -> bool:
    data = storage.read_json(ADMIN_BOTS_FILE)
    return any(item['user_id'] == user_id for item in data)

def is_authorized(user_id: int) -> bool:
    return is_admin_utama(user_id) or is_admin_bot(user_id)

def add_admin_bot(user_id: int, added_by: int) -> bool:
    """Tambah admin bot"""
    data = storage.read_json(ADMIN_BOTS_FILE)
    
    # Check duplicate
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
    """Get semua admin bots"""
    data = storage.read_json(ADMIN_BOTS_FILE)
    return [(item['user_id'], item['added_at']) for item in data]

def delete_admin_bot(user_id: int) -> bool:
    """Hapus admin bot"""
    data = storage.read_json(ADMIN_BOTS_FILE)
    original_length = len(data)
    data = [item for item in data if item['user_id'] != user_id]
    
    if len(data) < original_length:
        return storage.write_json(ADMIN_BOTS_FILE, data)
    return False

# Utility Functions
def format_message(title: str, content: str = "", buttons: List = None) -> str:
    """Format pesan dengan style yang keren"""
    msg = f"━━━━━━━━━━━━━━━━━━\n"
    msg += f"🤖 **{title}** 🤖\n"
    msg += f"━━━━━━━━━━━━━━━━━━\n"
    if content:
        msg += f"{content}\n"
    return msg

# Initialize Bot
bot = TelegramClient('bot_session', API_ID, API_HASH).start(bot_token=BOT_TOKEN)

# State Management
user_states = {}

@bot.on(events.NewMessage(pattern='/start'))
async def start_handler(event):
    if not is_authorized(event.sender_id):
        await event.reply("❌ **Akses Ditolak!** ❌\n\nLu gak punya izin buat pake bot ini, bro!")
        return
    
    buttons = []
    if is_admin_utama(event.sender_id):
        buttons.extend([
            [Button.inline("👑 Menu Admin Utama", "main_admin_menu")],
            [Button.inline("📱 Login Nomor Baru", "login_nomor")],
            [Button.inline("📋 List Semua Akun", "list_akun")],
            [Button.inline("➕ Tambah Kontak", "tambah_kontak")],
            [Button.inline("🗑️ Hapus Nomor", "hapus_nomor")],
            [Button.inline("🧹 Clear Kontak", "clear_kontak")],
            [Button.inline("👥 Invite ke Grup/Channel", "invite_grup")]
        ])
    else:
        buttons.extend([
            [Button.inline("📱 Login Nomor Baru", "login_nomor")],
            [Button.inline("📋 List Semua Akun", "list_akun")],
            [Button.inline("➕ Tambah Kontak", "tambah_kontak")],
            [Button.inline("🗑️ Hapus Nomor", "hapus_nomor")],
            [Button.inline("🧹 Clear Kontak", "clear_kontak")],
            [Button.inline("👥 Invite ke Grup/Channel", "invite_grup")]
        ])
    
    msg = format_message("SELAMAT DATANG BRO! 🔥", 
                        "Pilih menu yang lu mau dibawah ini:")
    
    await event.reply(msg, buttons=buttons)

# Admin Utama Menu
@bot.on(events.CallbackQuery(data=b'main_admin_menu'))
async def main_admin_menu(event):
    if not is_admin_utama(event.sender_id):
        await event.answer("❌ Lu bukan admin utama!", alert=True)
        return
    
    buttons = [
        [Button.inline("👨‍💼 Kelola Admin Bot", "kelola_admin")],
        [Button.inline("📝 Edit Kategori", "edit_kategori")],
        [Button.inline("🔄 Pindah Nomor Kategori", "pindah_kategori")],
        [Button.inline("🔙 Kembali", "back_to_main")]
    ]
    
    msg = format_message("MENU ADMIN UTAMA 👑", 
                        "Fitur khusus buat admin utama:")
    
    await event.edit(msg, buttons=buttons)

# Kelola Admin Bot
@bot.on(events.CallbackQuery(data=b'kelola_admin'))
async def kelola_admin_menu(event):
    if not is_admin_utama(event.sender_id):
        await event.answer("❌ Akses ditolak!", alert=True)
        return
    
    buttons = [
        [Button.inline("➕ Tambah Admin", "tambah_admin")],
        [Button.inline("➖ Hapus Admin", "hapus_admin")],
        [Button.inline("📋 List Admin", "list_admin")],
        [Button.inline("🔙 Kembali", "main_admin_menu")]
    ]
    
    msg = format_message("KELOLA ADMIN BOT 👨‍💼")
    await event.edit(msg, buttons=buttons)

@bot.on(events.CallbackQuery(data=b'tambah_admin'))
async def tambah_admin_handler(event):
    if not is_admin_utama(event.sender_id):
        return
    
    user_states[event.sender_id] = {"action": "tambah_admin"}
    msg = format_message("TAMBAH ADMIN BARU", 
                        "Forward pesan dari user yang mau dijadikan admin atau kirim user ID:")
    await event.edit(msg)

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
            content += f"📅 Ditambahkan: {added_at}\n\n"
    
    buttons = [[Button.inline("🔙 Kembali", "kelola_admin")]]
    msg = format_message("DAFTAR ADMIN BOT", content)
    await event.edit(msg, buttons=buttons)

@bot.on(events.CallbackQuery(data=b'hapus_admin'))
async def hapus_admin_handler(event):
    if not is_admin_utama(event.sender_id):
        return
    
    admins = get_all_admin_bots()
    
    if not admins:
        buttons = [[Button.inline("🔙 Kembali", "kelola_admin")]]
        msg = format_message("TIDAK ADA ADMIN BOT", 
                            "Belum ada admin bot yang bisa dihapus.")
        await event.edit(msg, buttons=buttons)
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
        
        buttons.append([Button.inline(f"🗑️ {display_name}", f"confirm_hapus_admin_{admin_id}")])
    
    buttons.append([Button.inline("🔙 Kembali", "kelola_admin")])
    
    msg = format_message("HAPUS ADMIN BOT 🗑️", 
                        "Pilih admin yang mau dihapus:")
    await event.edit(msg, buttons=buttons)

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
        [Button.inline("✅ Ya, Hapus!", f"execute_hapus_admin_{admin_id}")],
        [Button.inline("❌ Batal", "hapus_admin")]
    ]
    
    msg = format_message("KONFIRMASI HAPUS ADMIN ⚠️", 
                       f"Lu yakin mau hapus **{display_name}** dari admin bot?")
    
    await event.edit(msg, buttons=buttons)

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
        
        buttons = [[Button.inline("🔙 Kembali ke Menu Admin", "main_admin_menu")]]
        msg = format_message("ADMIN BERHASIL DIHAPUS! ✅", 
                           f"**{display_name}** udah dihapus dari admin bot!")
        
        await event.edit(msg, buttons=buttons)
    else:
        await event.answer("❌ Gagal menghapus admin!", alert=True)

# Login Nomor Handler
@bot.on(events.CallbackQuery(data=b'login_nomor'))
async def login_nomor_handler(event):
    if not is_authorized(event.sender_id):
        return
    
    user_states[event.sender_id] = {"action": "login_step1"}
    msg = format_message("LOGIN NOMOR BARU 📱", 
                        "Kirim nomor HP yang mau di-login (format: +628123456789):")
    await event.edit(msg)

# List Akun Handler  
@bot.on(events.CallbackQuery(data=b'list_akun'))
async def list_akun_handler(event):
    if not is_authorized(event.sender_id):
        return
    
    kategori_list = get_kategori()
    if not kategori_list:
        buttons = [[Button.inline("🔙 Kembali", "back_to_main")]]
        msg = format_message("BELUM ADA KATEGORI", 
                            "Belum ada kategori yang dibuat. Buat kategori dulu ya!")
        await event.edit(msg, buttons=buttons)
        return
    
    buttons = []
    for kat_id, kat_nama in kategori_list:
        buttons.append([Button.inline(f"📁 {kat_nama}", f"list_akun_kat_{kat_id}")])
    
    buttons.append([Button.inline("🔙 Kembali", "back_to_main")])
    
    msg = format_message("PILIH KATEGORI 📁", 
                        "Pilih kategori buat liat akun-akun di dalamnya:")
    await event.edit(msg, buttons=buttons)

@bot.on(events.CallbackQuery(pattern=r'list_akun_kat_(\d+)'))
async def list_akun_kategori_handler(event):
    if not is_authorized(event.sender_id):
        return
    
    kategori_id = int(event.data.decode().split('_')[-1])
    
    # Get kategori name
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
            status_emoji = "🟢"  # Default online
            content += f"{status_emoji} **{nomor}**\n"
            if nama_akun:
                content += f"👤 Nama: {nama_akun}\n"
            content += f"🆔 ID: {akun_id}\n\n"
    
    buttons = [[Button.inline("🔙 Kembali", "list_akun")]]
    msg = format_message(f"KATEGORI: {kategori_nama.upper()}", content)
    await event.edit(msg, buttons=buttons)

# Tambah Kontak Handler
@bot.on(events.CallbackQuery(data=b'tambah_kontak'))
async def tambah_kontak_handler(event):
    if not is_authorized(event.sender_id):
        return
    
    user_states[event.sender_id] = {"action": "tambah_kontak_step1", "contacts": []}
    msg = format_message("TAMBAH KONTAK 📞", 
                        "Kirim kontak yang mau ditambahin satu per satu.\n\n" +
                        "Setelah selesai kirim semua kontak, ketik `/done` buat lanjut ke step berikutnya.")
    await event.edit(msg)

# Message Handler untuk berbagai state
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
            await event.reply("❌ Format nomor salah! Harus dimulai dengan + (contoh: +628123456789)")
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
            
            await event.reply(format_message(
                "KODE OTP DIKIRIM 📩", 
                f"Kode OTP udah dikirim ke **{nomor}**\n\nKirim kode OTP yang lu terima:"
            ))
        except Exception as e:
            await event.reply(f"❌ **Error:** {str(e)}")
            del user_states[user_id]
    
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
            await show_kategori_selection(event, "Pilih kategori buat nomor ini:")
            
        except SessionPasswordNeededError:
            user_states[user_id]["action"] = "login_step2_password"
            await event.reply(format_message("BUTUH PASSWORD 🔐", 
                                           "Akun ini pake 2FA. Kirim password 2FA lu:"))
        except PhoneCodeInvalidError:
            await event.reply("❌ **Kode OTP salah!** Coba lagi dengan kode yang benar:")
        except Exception as e:
            await event.reply(f"❌ **Error:** {str(e)}")
            del user_states[user_id]
    
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
            
            await show_kategori_selection(event, "Pilih kategori buat nomor ini:")
            
        except PasswordHashInvalidError:
            await event.reply("❌ **Password salah!** Coba lagi:")
        except Exception as e:
            await event.reply(f"❌ **Error:** {str(e)}")
            del user_states[user_id]
    
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
            await event.reply(
                f"✅ **Kontak ke-{count} berhasil ditambahin!**\n\n"
                f"👤 **Nama:** {contact_data['first_name']} {contact_data['last_name'] or ''}\n"
                f"📞 **Nomor:** +{contact_data['phone']}\n\n"
                "Kirim kontak lain atau ketik `/done` kalo udah selesai."
            )
        else:
            await event.reply("❌ **Kirim kontak yang valid!** Bukan text biasa.")
    
    # Handle Tambah Admin
    elif state["action"] == "tambah_admin":
        if event.forward and event.forward.from_id:
            new_admin_id = event.forward.from_id.user_id
        else:
            try:
                new_admin_id = int(event.message.text.strip())
            except ValueError:
                await event.reply("❌ **Format salah!** Kirim user ID yang valid atau forward pesan dari user.")
                return
        
        # Check if already admin
        if is_admin_utama(new_admin_id) or is_admin_bot(new_admin_id):
            await event.reply("❌ **User ini udah jadi admin!**")
            return
        
        # Add to database
        if add_admin_bot(new_admin_id, user_id):
            try:
                user = await bot.get_entity(new_admin_id)
                name = user.first_name + (f" {user.last_name}" if user.last_name else "")
                await event.reply(f"✅ **{name}** berhasil ditambahin sebagai admin bot!")
            except:
                await event.reply(f"✅ **User ID {new_admin_id}** berhasil ditambahin sebagai admin bot!")
        else:
            await event.reply("❌ **User ini udah jadi admin!**")
        
        del user_states[user_id]
    
    elif state["action"] == "buat_kategori":
        nama_kategori = event.message.text.strip()
        
        if not nama_kategori:
            await event.reply("❌ **Nama kategori tidak boleh kosong!**")
            return
        
        if add_kategori(nama_kategori):
            await event.reply(format_message("KATEGORI BERHASIL DIBUAT! ✅", 
                                           f"Kategori **{nama_kategori}** udah dibuat!"))
            
            # Continue with previous flow if needed
            if user_id in user_states:
                previous_state = user_states[user_id]
                if "login_step3_pilih_kategori" in str(previous_state):
                    await show_kategori_selection(event, "Pilih kategori buat nomor ini:")
                    return
                elif "tambah_kontak_step2_pilih_kategori" in str(previous_state):
                    await show_kategori_selection(event, "Pilih kategori akun yang mau dipake:")
                    return
        else:
            await event.reply("❌ **Nama kategori udah ada!** Pake nama yang lain.")
            return
        
        if user_id in user_states:
            del user_states[user_id]
    
    elif state["action"] == "edit_nama_kategori":
        nama_baru = event.message.text.strip()
        
        if not nama_baru:
            await event.reply("❌ **Nama kategori tidak boleh kosong!**")
            return
        
        kategori_id = state["kategori_id"]
        old_name = state["old_name"]
        
        if update_kategori(kategori_id, nama_baru):
            buttons = [[Button.inline("🔙 Kembali ke Menu Admin", b"main_admin_menu")]]
            msg = format_message(
                "NAMA KATEGORI BERHASIL DIUBAH! ✅", 
                f"**Nama lama:** {old_name}\n**Nama baru:** {nama_baru}"
            )
            await event.reply(msg, buttons=buttons)
        else:
            await event.reply("❌ **Nama kategori udah ada!** Pake nama yang lain.")
            return
        
        del user_states[user_id]
    
    elif state["action"] == "invite_input_grup":
        grup_input = event.message.text.strip()
        akun_id = state["akun_id"]
        
        try:
            # Get akun data
            akun = get_akun_by_id(akun_id)
            
            if not akun:
                await event.reply("❌ **Akun tidak ditemukan!**")
                del user_states[user_id]
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
                await event.reply("❌ **Grup/Channel tidak ditemukan!** Cek lagi username atau link nya.")
                await client.disconnect()
                return
            
            # Get all contacts
            contacts = await client(GetContactsRequest(hash=0))
            
            if not contacts.users:
                await client.disconnect()
                await event.reply("❌ **Akun ini tidak punya kontak untuk di-invite!**")
                del user_states[user_id]
                return
            
            # Invite contacts to the group/channel
            success_count = 0
            total_count = len(contacts.users)
            
            msg_status = await event.reply(format_message(
                "PROSES INVITE... ⏳", 
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
                        progress_msg = format_message(
                            "PROSES INVITE... ⏳", 
                            f"Progress: {i + 1}/{total_count}\nBerhasil: {success_count}"
                        )
                        await msg_status.edit(progress_msg)
                        
                        # Add delay to avoid flood limits
                        await asyncio.sleep(2)
                
                except Exception:
                    # Skip users that can't be added
                    continue
            
            await client.disconnect()
            
            # Final result
            buttons = [[Button.inline("🔙 Kembali ke Menu", b"back_to_main")]]
            msg = format_message(
                "INVITE SELESAI! 🎉", 
                f"**Akun:** {nomor}\n"
                f"**Target:** {target_entity.title if hasattr(target_entity, 'title') else grup_input}\n"
                f"**Berhasil di-invite:** {success_count}/{total_count} kontak\n\n"
                "Proses invite sudah selesai!"
            )
            await msg_status.edit(msg, buttons=buttons)
            
        except Exception as e:
            await event.reply(f"❌ **Error:** {str(e)}")
        finally:
            if user_id in user_states:
                del user_states[user_id]

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
            await event.reply("❌ **Belum ada kontak yang ditambahin!**")
            return
        
        # Save contacts temporarily
        clear_temp_contacts(user_id)  # Clear old temp contacts
        
        for contact in state["contacts"]:
            add_temp_contact(user_id, contact)
        
        user_states[user_id] = {"action": "tambah_kontak_step2_pilih_kategori"}
        
        await show_kategori_selection(event, f"✅ **{len(state['contacts'])} kontak udah disimpen sementara!**\n\n" +
                                            "Sekarang pilih kategori akun yang mau dipake buat nyimpen kontak:")

# Helper function to show kategori selection
async def show_kategori_selection(event, message_text):
    kategori_list = get_kategori()
    
    buttons = []
    for kat_id, kat_nama in kategori_list:
        buttons.append([Button.inline(f"📁 {kat_nama}", f"pilih_kategori_{kat_id}")])
    
    buttons.append([Button.inline("➕ Buat Kategori Baru", "buat_kategori_baru")])
    
    if not kategori_list:
        message_text = "Belum ada kategori yang dibuat.\n\nBuat kategori baru dulu:"
        buttons = [[Button.inline("➕ Buat Kategori Baru", "buat_kategori_baru")]]
    
    msg = format_message("PILIH KATEGORI 📁", message_text)
    
    if hasattr(event, 'edit'):
        await event.edit(msg, buttons=buttons)
    else:
        await event.reply(msg, buttons=buttons)

# Kategori Selection Handler
@bot.on(events.CallbackQuery(pattern=r'pilih_kategori_(\d+)'))
async def pilih_kategori_handler(event):
    if not is_authorized(event.sender_id):
        return
    
    kategori_id = int(event.data.decode().split('_')[-1])
    user_id = event.sender_id
    
    if user_id not in user_states:
        return
    
    state = user_states[user_id]
    
    # Get kategori name
    kategori = get_kategori_by_id(kategori_id)
    
    if not kategori:
        await event.answer("❌ Kategori tidak ditemukan!", alert=True)
        return
    
    kategori_nama = kategori['nama']
    
    if state["action"] == "login_step3_pilih_kategori":
        # Save akun to database
        if add_akun_tg(state["nomor"], state["session_string"], kategori_id, state["nama_akun"]):
            msg = format_message("LOGIN BERHASIL! 🎉", 
                               f"Akun **{state['nomor']}** berhasil ditambahin ke kategori **{kategori_nama}**!\n\n" +
                               f"👤 **Nama Akun:** {state['nama_akun']}")
            
            buttons = [[Button.inline("🔙 Kembali ke Menu", "back_to_main")]]
            await event.edit(msg, buttons=buttons)
        else:
            await event.answer("❌ Nomor ini udah ada di database!", alert=True)
        
        del user_states[user_id]
    
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
            buttons.append([Button.inline(f"📱 {display_name}", f"pilih_akun_kontak_{akun_id}")])
        
        buttons.append([Button.inline("🔙 Kembali", "tambah_kontak")])
        
        user_states[user_id]["selected_kategori"] = kategori_id
        
        msg = format_message(f"PILIH AKUN - {kategori_nama.upper()}", 
                           "Pilih akun yang mau dipake buat nyimpen kontak:")
        await event.edit(msg, buttons=buttons)

# Akun Selection for Tambah Kontak
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
        
        msg = format_message("KONTAK BERHASIL DITAMBAHIN! ✅", 
                           f"**Akun:** {nomor}\n" +
                           f"**Berhasil:** {success_count}/{total_count} kontak\n\n" +
                           "Semua kontak udah disimpen ke akun Telegram yang dipilih!")
        
        buttons = [[Button.inline("🔙 Kembali ke Menu", "back_to_main")]]
        await event.edit(msg, buttons=buttons)
        
        if user_id in user_states:
            del user_states[user_id]
            
    except Exception as e:
        await event.answer(f"❌ Error: {str(e)}", alert=True)

# Buat Kategori Baru Handler
@bot.on(events.CallbackQuery(data=b'buat_kategori_baru'))
async def buat_kategori_handler(event):
    if not is_authorized(event.sender_id):
        return
    
    user_states[event.sender_id] = {"action": "buat_kategori"}
    msg = format_message("BUAT KATEGORI BARU 📁", 
                        "Kirim nama kategori yang mau lu buat:")
    await event.edit(msg)

# Back to Main Handler
@bot.on(events.CallbackQuery(data=b'back_to_main'))
async def back_to_main_handler(event):
    if not is_authorized(event.sender_id):
        return
    
    # Clear user state
    if event.sender_id in user_states:
        del user_states[event.sender_id]
    
    buttons = []
    if is_admin_utama(event.sender_id):
        buttons.extend([
            [Button.inline("👑 Menu Admin Utama", "main_admin_menu")],
            [Button.inline("📱 Login Nomor Baru", "login_nomor")],
            [Button.inline("📋 List Semua Akun", "list_akun")],
            [Button.inline("➕ Tambah Kontak", "tambah_kontak")],
            [Button.inline("🗑️ Hapus Nomor", "hapus_nomor")],
            [Button.inline("🧹 Clear Kontak", "clear_kontak")],
            [Button.inline("👥 Invite ke Grup/Channel", "invite_grup")]
        ])
    else:
        buttons.extend([
            [Button.inline("📱 Login Nomor Baru", "login_nomor")],
            [Button.inline("📋 List Semua Akun", "list_akun")],
            [Button.inline("➕ Tambah Kontak", "tambah_kontak")],
            [Button.inline("🗑️ Hapus Nomor", "hapus_nomor")],
            [Button.inline("🧹 Clear Kontak", "clear_kontak")],
            [Button.inline("👥 Invite ke Grup/Channel", "invite_grup")]
        ])
    
    msg = format_message("MENU UTAMA 🏠", 
                        "Pilih menu yang lu mau:")
    
    await event.edit(msg, buttons=buttons)

# Hapus Nomor Handler
@bot.on(events.CallbackQuery(data=b'hapus_nomor'))
async def hapus_nomor_handler(event):
    if not is_authorized(event.sender_id):
        return
    
    kategori_list = get_kategori()
    if not kategori_list:
        buttons = [[Button.inline("🔙 Kembali", "back_to_main")]]
        msg = format_message("BELUM ADA KATEGORI", 
                            "Belum ada kategori yang dibuat.")
        await event.edit(msg, buttons=buttons)
        return
    
    buttons = []
    for kat_id, kat_nama in kategori_list:
        buttons.append([Button.inline(f"📁 {kat_nama}", f"hapus_nomor_kat_{kat_id}")])
    
    buttons.append([Button.inline("🔙 Kembali", "back_to_main")])
    
    msg = format_message("HAPUS NOMOR 🗑️", 
                        "Pilih kategori buat liat nomor yang bisa dihapus:")
    await event.edit(msg, buttons=buttons)

@bot.on(events.CallbackQuery(pattern=r'hapus_nomor_kat_(\d+)'))
async def hapus_nomor_kategori_handler(event):
    if not is_authorized(event.sender_id):
        return
    
    kategori_id = int(event.data.decode().split('_')[-1])
    
    # Get kategori name
    kategori = get_kategori_by_id(kategori_id)
    
    if not kategori:
        await event.answer("❌ Kategori tidak ditemukan!", alert=True)
        return
    
    kategori_nama = kategori['nama']
    akun_list = get_akun_by_kategori(kategori_id)
    
    if not akun_list:
        buttons = [[Button.inline("🔙 Kembali", "hapus_nomor")]]
        msg = format_message(f"KATEGORI: {kategori_nama.upper()}", 
                           "Belum ada akun di kategori ini.")
        await event.edit(msg, buttons=buttons)
        return
    
    buttons = []
    for akun_id, nomor, nama_akun in akun_list:
        display_name = f"{nomor}"
        if nama_akun:
            display_name += f" ({nama_akun})"
        buttons.append([Button.inline(f"🗑️ {display_name}", f"confirm_hapus_{akun_id}")])
    
    buttons.append([Button.inline("🔙 Kembali", "hapus_nomor")])
    
    msg = format_message(f"HAPUS NOMOR - {kategori_nama.upper()}", 
                       "Pilih nomor yang mau dihapus:")
    await event.edit(msg, buttons=buttons)

@bot.on(events.CallbackQuery(pattern=r'confirm_hapus_(\d+)'))
async def confirm_hapus_handler(event):
    if not is_authorized(event.sender_id):
        return
    
    akun_id = int(event.data.decode().split('_')[-1])
    
    # Get akun info
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
        [Button.inline("✅ Ya, Hapus!", f"execute_hapus_{akun_id}")],
        [Button.inline("❌ Batal", "hapus_nomor")]
    ]
    
    msg = format_message("KONFIRMASI HAPUS ⚠️", 
                       f"Lu yakin mau hapus akun **{display_name}**?\n\n" +
                       "**PERINGATAN:** Data session akan dihapus permanen!")
    
    await event.edit(msg, buttons=buttons)

@bot.on(events.CallbackQuery(pattern=r'execute_hapus_(\d+)'))
async def execute_hapus_handler(event):
    if not is_authorized(event.sender_id):
        return
    
    akun_id = int(event.data.decode().split('_')[-1])
    
    # Get akun info before deletion
    akun = get_akun_by_id(akun_id)
    
    if not akun:
        await event.answer("❌ Akun tidak ditemukan!", alert=True)
        return
    
    nomor = akun['nomor']
    
    if delete_akun_by_id(akun_id):
        buttons = [[Button.inline("🔙 Kembali ke Menu", "back_to_main")]]
        msg = format_message("BERHASIL DIHAPUS! ✅", 
                           f"Akun **{nomor}** berhasil dihapus dari database!")
        
        await event.edit(msg, buttons=buttons)
    else:
        await event.answer("❌ Gagal menghapus akun!", alert=True)

# Clear Kontak Handler
@bot.on(events.CallbackQuery(data=b'clear_kontak'))
async def clear_kontak_handler(event):
    if not is_authorized(event.sender_id):
        return
    
    kategori_list = get_kategori()
    if not kategori_list:
        buttons = [[Button.inline("🔙 Kembali", "back_to_main")]]
        msg = format_message("BELUM ADA KATEGORI", 
                            "Belum ada kategori yang dibuat.")
        await event.edit(msg, buttons=buttons)
        return
    
    buttons = []
    for kat_id, kat_nama in kategori_list:
        buttons.append([Button.inline(f"📁 {kat_nama}", f"clear_kontak_kat_{kat_id}")])
    
    buttons.append([Button.inline("🔙 Kembali", "back_to_main")])
    
    msg = format_message("CLEAR KONTAK 🧹", 
                        "Pilih kategori buat clear kontak dari akun:")
    await event.edit(msg, buttons=buttons)

@bot.on(events.CallbackQuery(pattern=r'clear_kontak_kat_(\d+)'))
async def clear_kontak_kategori_handler(event):
    if not is_authorized(event.sender_id):
        return
    
    kategori_id = int(event.data.decode().split('_')[-1])
    
    # Get kategori name and akun list
    kategori = get_kategori_by_id(kategori_id)
    
    if not kategori:
        await event.answer("❌ Kategori tidak ditemukan!", alert=True)
        return
    
    kategori_nama = kategori['nama']
    akun_list = get_akun_by_kategori(kategori_id)
    
    if not akun_list:
        buttons = [[Button.inline("🔙 Kembali", "clear_kontak")]]
        msg = format_message(f"KATEGORI: {kategori_nama.upper()}", 
                           "Belum ada akun di kategori ini.")
        await event.edit(msg, buttons=buttons)
        return
    
    buttons = []
    for akun_id, nomor, nama_akun in akun_list:
        display_name = f"{nomor}"
        if nama_akun:
            display_name += f" ({nama_akun})"
        buttons.append([Button.inline(f"🧹 {display_name}", f"confirm_clear_{akun_id}")])
    
    buttons.append([Button.inline("🔙 Kembali", "clear_kontak")])
    
    msg = format_message(f"CLEAR KONTAK - {kategori_nama.upper()}", 
                       "Pilih akun yang mau di-clear kontaknya:")
    await event.edit(msg, buttons=buttons)

@bot.on(events.CallbackQuery(pattern=r'confirm_clear_(\d+)'))
async def confirm_clear_handler(event):
    if not is_authorized(event.sender_id):
        return
    
    akun_id = int(event.data.decode().split('_')[-1])
    
    # Get akun info
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
        [Button.inline("✅ Ya, Clear Semua!", f"execute_clear_{akun_id}")],
        [Button.inline("❌ Batal", "clear_kontak")]
    ]
    
    msg = format_message("KONFIRMASI CLEAR KONTAK ⚠️", 
                       f"Lu yakin mau clear SEMUA kontak dari **{display_name}**?\n\n" +
                       "**PERINGATAN:** Semua kontak akan dihapus permanen!")
    
    await event.edit(msg, buttons=buttons)

@bot.on(events.CallbackQuery(pattern=r'execute_clear_(\d+)'))
async def execute_clear_handler(event):
    if not is_authorized(event.sender_id):
        return
    
    akun_id = int(event.data.decode().split('_')[-1])
    
    # Get akun data
    akun = get_akun_by_id(akun_id)
    
    if not akun:
        await event.answer("❌ Akun tidak ditemukan!", alert=True)
        return
    
    nomor = akun['nomor']
    session_string = akun['session_string']
    
    try:
        # Connect with the account
        client = TelegramClient(StringSession(session_string), API_ID, API_HASH)
        await client.connect()
        
        # Get all contacts
        contacts = await client(GetContactsRequest(hash=0))
        
        if not contacts.users:
            await client.disconnect()
            buttons = [[Button.inline("🔙 Kembali ke Menu", "back_to_main")]]
            msg = format_message("TIDAK ADA KONTAK ℹ️", 
                               f"Akun **{nomor}** tidak punya kontak untuk di-clear.")
            await event.edit(msg, buttons=buttons)
            return
        
        # Delete all contacts
        user_ids = [user.id for user in contacts.users]
        await client(DeleteContactsRequest(user_ids))
        
        await client.disconnect()
        
        buttons = [[Button.inline("🔙 Kembali ke Menu", "back_to_main")]]
        msg = format_message("KONTAK BERHASIL DI-CLEAR! ✅", 
                           f"**{len(user_ids)} kontak** berhasil dihapus dari akun **{nomor}**!")
        
        await event.edit(msg, buttons=buttons)
        
    except Exception as e:
        await event.answer(f"❌ Error: {str(e)}", alert=True)

# Invite ke Grup/Channel Handler
@bot.on(events.CallbackQuery(data=b'invite_grup'))
async def invite_grup_handler(event):
    if not is_authorized(event.sender_id):
        return
    
    kategori_list = get_kategori()
    if not kategori_list:
        buttons = [[Button.inline("🔙 Kembali", b"back_to_main")]]
        msg = format_message(
            "BELUM ADA KATEGORI", 
            "Belum ada kategori yang dibuat."
        )
        await event.edit(msg, buttons=buttons)
        return
    
    buttons = []
    for kat_id, kat_nama in kategori_list:
        buttons.append([
            Button.inline(f"📁 {kat_nama}", f"invite_grup_kat_{kat_id}".encode())
        ])
    
    buttons.append([Button.inline("🔙 Kembali", b"back_to_main")])
    
    msg = format_message(
        "INVITE KE GRUP/CHANNEL 👥", 
        "Pilih kategori akun yang mau dipake:"
    )
    await event.edit(msg, buttons=buttons)

@bot.on(events.CallbackQuery(pattern=r'invite_grup_kat_(\d+)'))
async def invite_grup_kategori_handler(event):
    if not is_authorized(event.sender_id):
        return
    
    kategori_id = int(event.data.decode().split('_')[-1])
    
    # Get kategori name and akun list
    kategori = get_kategori_by_id(kategori_id)
    
    if not kategori:
        await event.answer("❌ Kategori tidak ditemukan!", alert=True)
        return
    
    kategori_nama = kategori['nama']
    akun_list = get_akun_by_kategori(kategori_id)
    
    if not akun_list:
        buttons = [[Button.inline("🔙 Kembali", "invite_grup")]]
        msg = format_message(f"KATEGORI: {kategori_nama.upper()}", 
                           "Belum ada akun di kategori ini.")
        await event.edit(msg, buttons=buttons)
        return
    
    buttons = []
    for akun_id, nomor, nama_akun in akun_list:
        display_name = f"{nomor}"
        if nama_akun:
            display_name += f" ({nama_akun})"
        buttons.append([Button.inline(f"👥 {display_name}", f"pilih_akun_invite_{akun_id}")])
    
    buttons.append([Button.inline("🔙 Kembali", "invite_grup")])
    
    msg = format_message(f"PILIH AKUN - {kategori_nama.upper()}", 
                       "Pilih akun yang mau dipake buat invite kontak:")
    await event.edit(msg, buttons=buttons)

@bot.on(events.CallbackQuery(pattern=r'pilih_akun_invite_(\d+)'))
async def pilih_akun_invite_handler(event):
    if not is_authorized(event.sender_id):
        return
    
    akun_id = int(event.data.decode().split('_')[-1])
    
    user_states[event.sender_id] = {
        "action": "invite_input_grup",
        "akun_id": akun_id
    }
    
    msg = format_message("INPUT GRUP/CHANNEL 📝", 
                       "Kirim username grup/channel atau invite link nya:\n\n" +
                       "**Contoh:**\n" +
                       "• @namagrup\n" +
                       "• https://t.me/namagrup\n" +
                       "• https://t.me/+AbCdEfGhIjK")
    
    await event.edit(msg)

# Edit Kategori Handler (Admin Utama Only)
@bot.on(events.CallbackQuery(data=b'edit_kategori'))
async def edit_kategori_handler(event):
    if not is_admin_utama(event.sender_id):
        await event.answer("❌ Akses ditolak!", alert=True)
        return
    
    kategori_list = get_kategori()
    
    if not kategori_list:
        buttons = [[Button.inline("🔙 Kembali", "main_admin_menu")]]
        msg = format_message("BELUM ADA KATEGORI", 
                            "Belum ada kategori yang dibuat.")
        await event.edit(msg, buttons=buttons)
        return
    
    buttons = []
    for kat_id, kat_nama in kategori_list:
        buttons.append([Button.inline(f"📝 {kat_nama}", f"edit_kat_{kat_id}")])
    
    buttons.append([Button.inline("🔙 Kembali", "main_admin_menu")])
    
    msg = format_message("EDIT KATEGORI 📝", 
                        "Pilih kategori yang mau diedit:")
    await event.edit(msg, buttons=buttons)

@bot.on(events.CallbackQuery(pattern=r'edit_kat_(\d+)'))
async def edit_kategori_nama_handler(event):
    if not is_admin_utama(event.sender_id):
        return
    
    kategori_id = int(event.data.decode().split('_')[-1])
    
    # Get current kategori name
    kategori = get_kategori_by_id(kategori_id)
    
    if not kategori:
        await event.answer("❌ Kategori tidak ditemukan!", alert=True)
        return
    
    kategori_nama = kategori['nama']
    
    user_states[event.sender_id] = {
        "action": "edit_nama_kategori",
        "kategori_id": kategori_id,
        "old_name": kategori_nama
    }
    
    msg = format_message("EDIT NAMA KATEGORI ✏️", 
                       f"**Nama saat ini:** {kategori_nama}\n\n" +
                       "Kirim nama baru buat kategori ini:")
    
    await event.edit(msg)

# Pindah Kategori Handler (Admin Utama Only)
@bot.on(events.CallbackQuery(data=b'pindah_kategori'))
async def pindah_kategori_handler(event):
    if not is_admin_utama(event.sender_id):
        await event.answer("❌ Akses ditolak!", alert=True)
        return
    
    kategori_list = get_kategori()
    
    if not kategori_list:
        buttons = [[Button.inline("🔙 Kembali", "main_admin_menu")]]
        msg = format_message("BELUM ADA KATEGORI", 
                            "Belum ada kategori yang dibuat.")
        await event.edit(msg, buttons=buttons)
        return
    
    buttons = []
    for kat_id, kat_nama in kategori_list:
        buttons.append([Button.inline(f"📁 {kat_nama}", f"pindah_dari_kat_{kat_id}")])
    
    buttons.append([Button.inline("🔙 Kembali", "main_admin_menu")])
    
    msg = format_message("PINDAH NOMOR KATEGORI 🔄", 
                        "Pilih kategori ASAL (kategori yang punya nomor yang mau dipindah):")
    await event.edit(msg, buttons=buttons)

# Pindah Nomor Kategori Handlers
@bot.on(events.CallbackQuery(pattern=r'pindah_dari_kat_(\d+)'))
async def pindah_dari_kategori_handler(event):
    if not is_admin_utama(event.sender_id):
        return
    
    kategori_id = int(event.data.decode().split('_')[-1])
    
    # Get kategori name and akun list
    kategori = get_kategori_by_id(kategori_id)
    
    if not kategori:
        await event.answer("❌ Kategori tidak ditemukan!", alert=True)
        return
    
    kategori_nama = kategori['nama']
    akun_list = get_akun_by_kategori(kategori_id)
    
    if not akun_list:
        buttons = [[Button.inline("🔙 Kembali", "pindah_kategori")]]
        msg = format_message(f"KATEGORI: {kategori_nama.upper()}", 
                           "Belum ada akun di kategori ini.")
        await event.edit(msg, buttons=buttons)
        return
    
    buttons = []
    for akun_id, nomor, nama_akun in akun_list:
        display_name = f"{nomor}"
        if nama_akun:
            display_name += f" ({nama_akun})"
        buttons.append([Button.inline(f"📱 {display_name}", f"pilih_nomor_pindah_{akun_id}")])
    
    buttons.append([Button.inline("🔙 Kembali", "pindah_kategori")])
    
    msg = format_message(f"PILIH NOMOR - {kategori_nama.upper()}", 
                       "Pilih nomor yang mau dipindah:")
    await event.edit(msg, buttons=buttons)

@bot.on(events.CallbackQuery(pattern=r'pilih_nomor_pindah_(\d+)'))
async def pilih_nomor_pindah_handler(event):
    if not is_admin_utama(event.sender_id):
        return
    
    akun_id = int(event.data.decode().split('_')[-1])
    
    # Get akun info
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
        buttons = [[Button.inline("🔙 Kembali", "pindah_kategori")]]
        msg = format_message("TIDAK ADA KATEGORI LAIN", 
                           "Tidak ada kategori lain untuk memindahkan nomor ini.")
        await event.edit(msg, buttons=buttons)
        return
    
    display_name = f"{nomor}"
    if nama_akun:
        display_name += f" ({nama_akun})"
    
    buttons = []
    for kat_id, kat_nama in other_kategori:
        buttons.append([Button.inline(f"📁 {kat_nama}", f"pindah_ke_kat_{akun_id}_{kat_id}")])
    
    buttons.append([Button.inline("🔙 Kembali", "pindah_kategori")])
    
    msg = format_message("PILIH KATEGORI TUJUAN 🎯", 
                       f"Mau pindahin **{display_name}** ke kategori mana?")
    await event.edit(msg, buttons=buttons)

@bot.on(events.CallbackQuery(pattern=r'pindah_ke_kat_(\d+)_(\d+)'))
async def pindah_ke_kategori_handler(event):
    if not is_admin_utama(event.sender_id):
        return
    
    data_parts = event.data.decode().split('_')
    akun_id = int(data_parts[-2])
    new_kategori_id = int(data_parts[-1])
    
    # Get akun info
    akun = get_akun_by_id(akun_id)
    
    # Get kategori names
    kategori = get_kategori_by_id(new_kategori_id)
    
    if not akun or not kategori:
        await event.answer("❌ Data tidak ditemukan!", alert=True)
        return
    
    nomor = akun['nomor']
    nama_akun = akun.get('nama_akun', '')
    kategori_nama = kategori['nama']
    
    # Update kategori
    if update_akun_kategori(akun_id, new_kategori_id):
        display_name = f"{nomor}"
        if nama_akun:
            display_name += f" ({nama_akun})"
        
        buttons = [[Button.inline("🔙 Kembali ke Menu Admin", "main_admin_menu")]]
        msg = format_message("NOMOR BERHASIL DIPINDAH! ✅", 
                           f"**Nomor:** {display_name}\n" +
                           f"**Kategori baru:** {kategori_nama}")
        
        await event.edit(msg, buttons=buttons)
    else:
        await event.answer("❌ Gagal memindahkan nomor!", alert=True)

# Error Handler
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
        
        # Handle states that expect text input but not handled by state_message_handler
        expected_text_states = ["buat_kategori", "edit_nama_kategori", "invite_input_grup", 
                               "login_step1", "login_step2", "login_step2_password", 
                               "tambah_admin"]
        
        if state["action"] not in expected_text_states:
            await event.reply("❌ **Perintah tidak dikenali!**\n\n" + 
                            "Gunakan tombol yang tersedia atau ketik /start untuk kembali ke menu utama.")

# Main Function
async def main():
    """Main function untuk menjalankan bot"""
    
    print("🤖 Bot Telegram Manager dimulai...")
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    
    try:
        # Initialize storage
        print("📁 Menginisialisasi JSON storage...")
        storage.ensure_data_dir()
        storage.init_json_files()
        print("✅ JSON storage berhasil diinisialisasi")
        
        # Test JSON operations
        print("🔍 Testing JSON operations...")
        test_data = storage.read_json(KATEGORI_FILE)
        storage.write_json(KATEGORI_FILE, test_data)
        print("✅ JSON operations working properly")
        
        # Initialize bot
        print("🤖 Menginisialisasi bot...")
        await bot.start(bot_token=BOT_TOKEN)
        
        # Get bot info
        me = await bot.get_me()
        print(f"✅ Bot berhasil login sebagai @{me.username}")
        print(f"📊 Bot ID: {me.id}")
        
        # Show statistics
        kategori_count = len(get_kategori())
        akun_count = len(storage.read_json(AKUN_TG_FILE))
        admin_count = len(get_all_admin_bots())
        
        print(f"📈 Statistik saat ini:")
        print(f"   📁 Kategori: {kategori_count}")
        print(f"   📱 Akun TG: {akun_count}")
        print(f"   👨‍💼 Admin Bot: {admin_count}")
        
        print("🚀 Bot siap digunakan!")
        print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        
        # Keep bot running
        await bot.run_until_disconnected()
        
    except Exception as e:
        print(f"❌ Error saat inisialisasi bot: {e}")
        import traceback
        traceback.print_exc()
        
        if bot and bot.is_connected():
            await bot.disconnect()
        return
    
    finally:
        # Cleanup
        if bot and bot.is_connected():
            print("🔌 Memutuskan koneksi bot...")
            await bot.disconnect()
        
        print("💤 Bot telah berhenti")

# Health Check Function
def health_check():
    """Check kesehatan JSON files"""
    try:
        # Check if data directory exists
        if not os.path.exists(DATA_DIR):
            print("❌ Data directory tidak ditemukan!")
            return False
        
        # Check if all JSON files are readable
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

# Backup Function
def create_backup():
    """Buat backup dari semua data JSON"""
    try:
        import shutil
        from datetime import datetime
        
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

# Cleanup Function
def cleanup_old_backups(keep_days=7):
    """Hapus backup lama"""
    try:
        import time
        
        backup_dir = os.path.join(DATA_DIR, "backups")
        if not os.path.exists(backup_dir):
            return
        
        current_time = time.time()
        cutoff_time = current_time - (keep_days * 24 * 60 * 60)  # keep_days dalam detik
        
        removed_count = 0
        for backup_folder in os.listdir(backup_dir):
            backup_path = os.path.join(backup_dir, backup_folder)
            if os.path.isdir(backup_path):
                folder_time = os.path.getctime(backup_path)
                if folder_time < cutoff_time:
                    import shutil
                    shutil.rmtree(backup_path)
                    removed_count += 1
        
        if removed_count > 0:
            print(f"🧹 {removed_count} backup lama berhasil dihapus")
        
    except Exception as e:
        print(f"❌ Cleanup error: {e}")

# Entry Point
if __name__ == '__main__':
    try:
        # Set event loop policy untuk Linux
        if os.name != 'nt':  # Bukan Windows
            asyncio.set_event_loop_policy(asyncio.DefaultEventLoopPolicy())
        
        # Run health check
        print("🏥 Menjalankan health check...")
        if not health_check():
            print("❌ Health check gagal! Memperbaiki struktur data...")
            storage = JSONStorage()  # Reinitialize
        
        # Create backup
        print("💾 Membuat backup...")
        create_backup()
        
        # Cleanup old backups
        print("🧹 Membersihkan backup lama...")
        cleanup_old_backups()
        
        # ✅ Run bot pakai loop dari Telethon, bukan asyncio.run()
        bot.loop.run_until_complete(main())
        
    except KeyboardInterrupt:
        print("\n💤 Bot dihentikan oleh user")
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        print("👋 Terima kasih telah menggunakan Bot Telegram Manager!")
