#!/usr/bin/env python3
"""
Telegram Bot Manager - Enhanced Version
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
from dataclasses import dataclass, asdict
from contextlib import asynccontextmanager

from telethon import TelegramClient, events, Button
from telethon.sessions import StringSession
from telethon.tl.types import InputPhoneContact, User, Chat, Channel
from telethon.errors import (
    SessionPasswordNeededError, PhoneCodeInvalidError, 
    PasswordHashInvalidError, FloodWaitError, PhoneNumberInvalidError
)
from telethon.tl.functions.contacts import (
    ImportContactsRequest, DeleteContactsRequest, GetContactsRequest
)
from telethon.tl.functions.channels import InviteToChannelRequest
from telethon.tl.functions.messages import AddChatUserRequest

# ==================== CONFIGURATION ====================
@dataclass
class BotConfig:
    """Konfigurasi Bot"""
    API_ID: str = "20755791"
    API_HASH: str = "3d09356fe14a31a5baaad296a1abef80"
    BOT_TOKEN: str = "8426128734:AAHYVpJCy7LrofTI3AzyUNhB_42hQnVNwiA"
    ADMIN_UTAMA: int = 5988451717
    DATA_DIR: str = "bot_data"
    BACKUP_RETENTION_DAYS: int = 7
    MAX_RETRY_ATTEMPTS: int = 3
    FLOOD_WAIT_TIMEOUT: int = 60

config = BotConfig()

# ==================== LOGGING SETUP ====================
def setup_logging():
    """Setup logging configuration"""
    log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    logging.basicConfig(
        level=logging.INFO,
        format=log_format,
        handlers=[
            logging.FileHandler(os.path.join(config.DATA_DIR, 'bot.log')),
            logging.StreamHandler()
        ]
    )
    
    # Suppress telethon debug logs
    logging.getLogger('telethon').setLevel(logging.WARNING)
    
    return logging.getLogger(__name__)

# ==================== DATA MODELS ====================
@dataclass
class Kategori:
    id: int
    nama: str
    created_at: str

@dataclass
class AkunTG:
    id: int
    nomor: str
    session_string: str
    kategori_id: int
    nama_akun: str = ""
    created_at: str = ""
    is_active: bool = True

@dataclass
class AdminBot:
    user_id: int
    added_by: int
    added_at: str

@dataclass
class TempContact:
    user_id: int
    contact_data: Dict
    created_at: str

# ==================== STORAGE MANAGER ====================
class StorageManager:
    """Thread-safe JSON storage manager dengan error handling yang lebih baik"""
    
    def __init__(self, data_dir: str):
        self.data_dir = data_dir
        self.file_lock = threading.RLock()  # Reentrant lock
        self.logger = logging.getLogger(self.__class__.__name__)
        
        # File paths
        self.files = {
            'kategori': os.path.join(data_dir, 'kategori.json'),
            'akun_tg': os.path.join(data_dir, 'akun_tg.json'),
            'temp_contacts': os.path.join(data_dir, 'temp_contacts.json'),
            'admin_bots': os.path.join(data_dir, 'admin_bots.json')
        }
        
        self._ensure_setup()
    
    def _ensure_setup(self):
        """Pastikan direktori dan file ada"""
        try:
            if not os.path.exists(self.data_dir):
                os.makedirs(self.data_dir)
                self.logger.info(f"Created data directory: {self.data_dir}")
            
            # Initialize files with empty lists
            for file_type, file_path in self.files.items():
                if not os.path.exists(file_path):
                    self._write_json(file_path, [])
                    self.logger.info(f"Initialized {file_type} file")
                    
        except Exception as e:
            self.logger.error(f"Error during setup: {e}")
            raise
    
    def _read_json(self, file_path: str) -> List[Dict]:
        """Internal method untuk membaca JSON dengan error handling"""
        try:
            if not os.path.exists(file_path):
                return []
            
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read().strip()
                if not content:
                    return []
                    
                data = json.loads(content)
                return data if isinstance(data, list) else []
                
        except json.JSONDecodeError as e:
            self.logger.error(f"JSON decode error in {file_path}: {e}")
            # Try to restore from backup
            backup_path = file_path + '.backup'
            if os.path.exists(backup_path):
                self.logger.info(f"Restoring from backup: {backup_path}")
                shutil.copy2(backup_path, file_path)
                return self._read_json(file_path)
            return []
            
        except Exception as e:
            self.logger.error(f"Error reading {file_path}: {e}")
            return []
    
    def _write_json(self, file_path: str, data: List[Dict]) -> bool:
        """Internal method untuk menulis JSON dengan backup"""
        try:
            # Create backup
            if os.path.exists(file_path):
                shutil.copy2(file_path, file_path + '.backup')
            
            # Write data
            temp_path = file_path + '.tmp'
            with open(temp_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            
            # Atomic rename
            if os.name == 'nt':  # Windows
                if os.path.exists(file_path):
                    os.remove(file_path)
            os.rename(temp_path, file_path)
            
            # Remove backup if write successful
            backup_path = file_path + '.backup'
            if os.path.exists(backup_path):
                os.remove(backup_path)
                
            return True
            
        except Exception as e:
            self.logger.error(f"Error writing {file_path}: {e}")
            # Restore from backup if exists
            backup_path = file_path + '.backup'
            if os.path.exists(backup_path):
                shutil.copy2(backup_path, file_path)
                if os.path.exists(backup_path):
                    os.remove(backup_path)
            return False
    
    def read_json(self, file_type: str) -> List[Dict]:
        """Public method untuk membaca data dengan thread safety"""
        with self.file_lock:
            file_path = self.files.get(file_type)
            if not file_path:
                raise ValueError(f"Unknown file type: {file_type}")
            return self._read_json(file_path)
    
    def write_json(self, file_type: str, data: List[Dict]) -> bool:
        """Public method untuk menulis data dengan thread safety"""
        with self.file_lock:
            file_path = self.files.get(file_type)
            if not file_path:
                raise ValueError(f"Unknown file type: {file_type}")
            return self._write_json(file_path, data)
    
    def get_next_id(self, file_type: str) -> int:
        """Generate ID berikutnya"""
        data = self.read_json(file_type)
        if not data:
            return 1
        max_id = max([item.get('id', 0) for item in data], default=0)
        return max_id + 1
    
    def create_backup(self) -> Optional[str]:
        """Buat backup semua file"""
        try:
            backup_dir = os.path.join(self.data_dir, "backups")
            if not os.path.exists(backup_dir):
                os.makedirs(backup_dir)
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_subdir = os.path.join(backup_dir, f"backup_{timestamp}")
            os.makedirs(backup_subdir)
            
            for file_type, file_path in self.files.items():
                if os.path.exists(file_path):
                    filename = os.path.basename(file_path)
                    backup_path = os.path.join(backup_subdir, filename)
                    shutil.copy2(file_path, backup_path)
            
            self.logger.info(f"Backup created: {backup_subdir}")
            return backup_subdir
            
        except Exception as e:
            self.logger.error(f"Backup error: {e}")
            return None
    
    def cleanup_old_backups(self, keep_days: int = 7):
        """Hapus backup lama"""
        try:
            backup_dir = os.path.join(self.data_dir, "backups")
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
                self.logger.info(f"Cleaned up {removed_count} old backups")
                
        except Exception as e:
            self.logger.error(f"Cleanup error: {e}")

# ==================== DATABASE OPERATIONS ====================
class DatabaseManager:
    """Manager untuk operasi database/JSON"""
    
    def __init__(self, storage: StorageManager):
        self.storage = storage
        self.logger = logging.getLogger(self.__class__.__name__)
    
    # Kategori operations
    def get_all_kategori(self) -> List[Kategori]:
        """Get semua kategori"""
        data = self.storage.read_json('kategori')
        return [Kategori(**item) for item in data]
    
    def add_kategori(self, nama: str) -> bool:
        """Tambah kategori baru"""
        data = self.storage.read_json('kategori')
        
        # Check duplicate (case insensitive)
        if any(item['nama'].lower() == nama.lower() for item in data):
            return False
        
        new_kategori = {
            'id': self.storage.get_next_id('kategori'),
            'nama': nama.strip(),
            'created_at': datetime.now().isoformat()
        }
        
        data.append(new_kategori)
        return self.storage.write_json('kategori', data)
    
    def update_kategori(self, kategori_id: int, nama_baru: str) -> bool:
        """Update nama kategori"""
        data = self.storage.read_json('kategori')
        
        # Check duplicate (exclude current)
        nama_baru = nama_baru.strip()
        if any(item['nama'].lower() == nama_baru.lower() and item['id'] != kategori_id 
               for item in data):
            return False
        
        for item in data:
            if item['id'] == kategori_id:
                item['nama'] = nama_baru
                return self.storage.write_json('kategori', data)
        
        return False
    
    def get_kategori_by_id(self, kategori_id: int) -> Optional[Kategori]:
        """Get kategori by ID"""
        data = self.storage.read_json('kategori')
        item = next((item for item in data if item['id'] == kategori_id), None)
        return Kategori(**item) if item else None
    
    # Akun TG operations
    def get_akun_by_kategori(self, kategori_id: int) -> List[AkunTG]:
        """Get akun berdasarkan kategori"""
        data = self.storage.read_json('akun_tg')
        filtered_data = [item for item in data if item['kategori_id'] == kategori_id]
        return [AkunTG(**item) for item in filtered_data]
    
    def add_akun_tg(self, nomor: str, session_string: str, kategori_id: int, nama_akun: str = '') -> bool:
        """Tambah akun TG baru"""
        data = self.storage.read_json('akun_tg')
        
        # Check duplicate
        if any(item['nomor'] == nomor for item in data):
            return False
        
        new_akun = {
            'id': self.storage.get_next_id('akun_tg'),
            'nomor': nomor,
            'session_string': session_string,
            'kategori_id': kategori_id,
            'nama_akun': nama_akun,
            'created_at': datetime.now().isoformat(),
            'is_active': True
        }
        
        data.append(new_akun)
        return self.storage.write_json('akun_tg', data)
    
    def get_akun_by_id(self, akun_id: int) -> Optional[AkunTG]:
        """Get akun by ID"""
        data = self.storage.read_json('akun_tg')
        item = next((item for item in data if item['id'] == akun_id), None)
        return AkunTG(**item) if item else None
    
    def delete_akun_by_id(self, akun_id: int) -> bool:
        """Hapus akun by ID"""
        data = self.storage.read_json('akun_tg')
        original_length = len(data)
        data = [item for item in data if item['id'] != akun_id]
        
        if len(data) < original_length:
            return self.storage.write_json('akun_tg', data)
        return False
    
    def update_akun_kategori(self, akun_id: int, new_kategori_id: int) -> bool:
        """Update kategori akun"""
        data = self.storage.read_json('akun_tg')
        
        for item in data:
            if item['id'] == akun_id:
                item['kategori_id'] = new_kategori_id
                return self.storage.write_json('akun_tg', data)
        
        return False
    
    # Admin Bot operations
    def is_admin_utama(self, user_id: int) -> bool:
        return user_id == config.ADMIN_UTAMA
    
    def is_admin_bot(self, user_id: int) -> bool:
        data = self.storage.read_json('admin_bots')
        return any(item['user_id'] == user_id for item in data)
    
    def is_authorized(self, user_id: int) -> bool:
        return self.is_admin_utama(user_id) or self.is_admin_bot(user_id)
    
    def add_admin_bot(self, user_id: int, added_by: int) -> bool:
        """Tambah admin bot"""
        data = self.storage.read_json('admin_bots')
        
        # Check duplicate
        if any(item['user_id'] == user_id for item in data):
            return False
        
        new_admin = {
            'user_id': user_id,
            'added_by': added_by,
            'added_at': datetime.now().isoformat()
        }
        
        data.append(new_admin)
        return self.storage.write_json('admin_bots', data)
    
    def get_all_admin_bots(self) -> List[AdminBot]:
        """Get semua admin bots"""
        data = self.storage.read_json('admin_bots')
        return [AdminBot(**item) for item in data]
    
    def delete_admin_bot(self, user_id: int) -> bool:
        """Hapus admin bot"""
        data = self.storage.read_json('admin_bots')
        original_length = len(data)
        data = [item for item in data if item['user_id'] != user_id]
        
        if len(data) < original_length:
            return self.storage.write_json('admin_bots', data)
        return False
    
    # Temp Contacts operations  
    def add_temp_contact(self, user_id: int, contact_data: Dict) -> bool:
        """Tambah temporary contact"""
        data = self.storage.read_json('temp_contacts')
        
        new_contact = {
            'user_id': user_id,
            'contact_data': contact_data,
            'created_at': datetime.now().isoformat()
        }
        
        data.append(new_contact)
        return self.storage.write_json('temp_contacts', data)
    
    def get_temp_contacts(self, user_id: int) -> List[Dict]:
        """Get temporary contacts by user ID"""
        data = self.storage.read_json('temp_contacts')
        return [item['contact_data'] for item in data if item['user_id'] == user_id]
    
    def clear_temp_contacts(self, user_id: int) -> bool:
        """Clear temporary contacts by user ID"""
        data = self.storage.read_json('temp_contacts')
        original_length = len(data)
        data = [item for item in data if item['user_id'] != user_id]
        
        if len(data) < original_length:
            return self.storage.write_json('temp_contacts', data)
        return True

# ==================== UTILITIES ====================
class MessageFormatter:
    """Utility untuk format pesan"""
    
    @staticmethod
    def format_message(title: str, content: str = "", success: bool = None) -> str:
        """Format pesan dengan style yang konsisten"""
        
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

class SessionManager:
    """Manager untuk Telethon sessions"""
    
    @staticmethod
    @asynccontextmanager
    async def get_client(session_string: str):
        """Context manager untuk Telethon client"""
        client = TelegramClient(StringSession(session_string), config.API_ID, config.API_HASH)
        try:
            await client.connect()
            yield client
        finally:
            if client.is_connected():
                await client.disconnect()

# ==================== STATE MANAGER ====================
class StateManager:
    """Manager untuk user states"""
    
    def __init__(self):
        self._states: Dict[int, Dict] = {}
        self._lock = threading.RLock()
    
    def set_state(self, user_id: int, state: Dict):
        with self._lock:
            self._states[user_id] = state
    
    def get_state(self, user_id: int) -> Optional[Dict]:
        with self._lock:
            return self._states.get(user_id)
    
    def clear_state(self, user_id: int):
        with self._lock:
            self._states.pop(user_id, None)
    
    def has_state(self, user_id: int) -> bool:
        with self._lock:
            return user_id in self._states

# ==================== BOT CLASS ====================
class TelegramBotManager:
    """Main bot class"""
    
    def __init__(self):
        self.logger = setup_logging()
        self.storage = StorageManager(config.DATA_DIR)
        self.db = DatabaseManager(self.storage)
        self.state_manager = StateManager()
        self.formatter = MessageFormatter()
        
        # Initialize bot client
        self.bot = TelegramClient('bot_session', config.API_ID, config.API_HASH)
        
        # Setup event handlers
        self._setup_handlers()
    
    def _setup_handlers(self):
        """Setup semua event handlers"""
        
        @self.bot.on(events.NewMessage(pattern='/start'))
        async def start_handler(event):
            await self.handle_start(event)
        
        @self.bot.on(events.NewMessage(pattern='/done'))
        async def done_handler(event):
            await self.handle_done(event)
        
        @self.bot.on(events.CallbackQuery)
        async def callback_handler(event):
            await self.handle_callback(event)
        
        @self.bot.on(events.NewMessage)
        async def message_handler(event):
            await self.handle_message(event)
    
    async def handle_start(self, event):
        """Handle /start command"""
        user_id = event.sender_id
        
        if not self.db.is_authorized(user_id):
            await event.reply(self.formatter.format_message(
                "AKSES DITOLAK", 
                "Anda tidak memiliki izin untuk menggunakan bot ini.",
                success=False
            ))
            return
        
        # Clear any existing state
        self.state_manager.clear_state(user_id)
        
        # Build menu buttons
        buttons = self._build_main_menu(user_id)
        
        msg = self.formatter.format_message(
            "SELAMAT DATANG", 
            "Pilih menu yang ingin Anda gunakan:"
        )
        
        await event.reply(msg, buttons=buttons)
    
    def _build_main_menu(self, user_id: int) -> List[List[Button]]:
        """Build main menu buttons based on user permissions"""
        buttons = []
        
        if self.db.is_admin_utama(user_id):
            buttons.append([Button.inline("👑 Menu Admin Utama", b"main_admin_menu")])
        
        buttons.extend([
            [Button.inline("📱 Login Nomor Baru", b"login_nomor")],
            [Button.inline("📋 List Semua Akun", b"list_akun")],
            [Button.inline("➕ Tambah Kontak", b"tambah_kontak")],
            [Button.inline("🗑️ Hapus Nomor", b"hapus_nomor")],
            [Button.inline("🧹 Clear Kontak", b"clear_kontak")],
            [Button.inline("👥 Invite ke Grup/Channel", b"invite_grup")]
        ])
        
        return buttons
    
    async def handle_callback(self, event):
        """Handle callback queries dari inline buttons"""
        try:
            user_id = event.sender_id
            data = event.data
            
            if not self.db.is_authorized(user_id):
                await event.answer("❌ Akses ditolak!", alert=True)
                return
            
            # Route callbacks
            if data == b"back_to_main":
                await self._show_main_menu(event)
            elif data == b"main_admin_menu":
                await self._show_admin_menu(event)
            elif data == b"login_nomor":
                await self._start_login_process(event)
            elif data == b"list_akun":
                await self._show_kategori_list_akun(event)
            elif data == b"tambah_kontak":
                await self._start_tambah_kontak(event)
            elif data.startswith(b"pilih_kategori_"):
                await self._handle_kategori_selection(event)
            # Add more callback handlers as needed...
            
        except Exception as e:
            self.logger.error(f"Error in callback handler: {e}")
            await event.answer("❌ Terjadi kesalahan internal!", alert=True)
    
    async def handle_message(self, event):
        """Handle text messages based on user state"""
        try:
            user_id = event.sender_id
            
            if not self.db.is_authorized(user_id):
                return
            
            # Skip if it's a command or not text
            if event.message.text and event.message.text.startswith('/'):
                return
            
            state = self.state_manager.get_state(user_id)
            if not state:
                return
            
            action = state.get("action")
            
            if action == "login_step1":
                await self._process_login_phone(event)
            elif action == "login_step2":
                await self._process_login_code(event)
            elif action == "login_step2_password":
                await self._process_login_password(event)
            elif action == "tambah_kontak_step1":
                await self._process_contact_input(event)
            elif action == "buat_kategori":
                await self._process_new_kategori(event)
            # Add more state handlers...
            
        except Exception as e:
            self.logger.error(f"Error in message handler: {e}")
            await event.reply("❌ Terjadi kesalahan saat memproses pesan!")
    
    async def handle_done(self, event):
        """Handle /done command"""
        user_id = event.sender_id
        
        if not self.db.is_authorized(user_id):
            return
        
        state = self.state_manager.get_state(user_id)
        if not state:
            return
        
        if state.get("action") == "tambah_kontak_step1":
            await self._finish_contact_input(event)
    
    # ==================== MENU HANDLERS ====================
    async def _show_main_menu(self, event):
        """Show main menu"""
        user_id = event.sender_id
        self.state_manager.clear_state(user_id)
        
        buttons = self._build_main_menu(user_id)
        msg = self.formatter.format_message("MENU UTAMA", "Pilih menu yang ingin Anda gunakan:")
        
        await event.edit(msg, buttons=buttons)
    
    async def _show_admin_menu(self, event):
        """Show admin menu (admin utama only)"""
        if not self.db.is_admin_utama(event.sender_id):
            await event.answer("❌ Akses ditolak!", alert=True)
            return
        
        buttons = [
            [Button.inline("👨‍💼 Kelola Admin Bot", b"kelola_admin")],
            [Button.inline("📝 Edit Kategori", b"edit_kategori")],
            [Button.inline("🔄 Pindah Nomor Kategori", b"pindah_kategori")],
            [Button.inline("🔙 Kembali", b"back_to_main")]
        ]
        
        msg = self.formatter.format_message("MENU ADMIN UTAMA", "Fitur khusus untuk admin utama:")
        await event.edit(msg, buttons=buttons)
    
    # ==================== LOGIN HANDLERS ====================
    async def _start_login_process(self, event):
        """Start login process"""
        user_id = event.sender_id
        self.state_manager.set_state(user_id, {"action": "login_step1"})
        
        msg = self.formatter.format_message(
            "LOGIN NOMOR BARU", 
            "Kirim nomor HP yang ingin di-login (format: +628123456789):"
        )
        await event.edit(msg)
    
    async def _process_login_phone(self, event):
        """Process phone number input"""
        user_id = event.sender_id
        nomor = event.message.text.strip()
        
        if not nomor.startswith('+'):
            await event.reply("❌ Format nomor salah! Harus dimulai dengan + (contoh: +628123456789)")
            return
        
        try:
            # Create temporary client
            client = TelegramClient(StringSession(), config.API_ID, config.API_HASH)
            await client.connect()
            
            result = await client.send_code_request(nomor)
            
            self.state_manager.set_state(user_id, {
                "action": "login_step2",
                "nomor": nomor,
                "client": client,
                "phone_code_hash": result.phone_code_hash
            })
            
            msg = self.formatter.format_message(
                "KODE OTP DIKIRIM", 
                f"Kode OTP telah dikirim ke **{nomor}**\n\nKirim kode OTP yang Anda terima:"
            )
            await event.reply(msg)
            
        except PhoneNumberInvalidError:
            await event.reply("❌ Nomor HP tidak valid!")
            self.state_manager.clear_state(user_id)
        except Exception as e:
            await event.reply(f"❌ Error: {str(e)}")
            self.state_manager.clear_state(user_id)
    
    async def _process_login_code(self, event):
        """Process OTP code input"""
        user_id = event.sender_id
        code = event.message.text.strip()
        state = self.state_manager.get_state(user_id)
        
        if not state:
            return
        
        try:
            client = state["client"]
            nomor = state["nomor"]
            
            await client.sign_in(nomor, code, phone_code_hash=state["phone_code_hash"])
            
            # Get session string and user info
            session_string = client.session.save()
            me = await client.get_me()
            nama_akun = me.first_name + (f" {me.last_name}" if me.last_name else "")
            await client.disconnect()
            
            # Update state for kategori selection
            self.state_manager.set_state(user_id, {
                "action": "login_step3_pilih_kategori",
                "nomor": nomor,
                "session_string": session_string,
                "nama_akun": nama_akun
            })
            
            await self._show_kategori_selection(event, "Pilih kategori untuk nomor ini:")
            
        except SessionPasswordNeededError:
            # Need 2FA password
            state["action"] = "login_step2_password"
            self.state_manager.set_state(user_id, state)
            
            msg = self.formatter.format_message(
                "BUTUH PASSWORD 2FA", 
                "Akun ini menggunakan 2FA. Kirim password 2FA Anda:"
            )
            await event.reply(msg)
            
        except PhoneCodeInvalidError:
            await event.reply("❌ Kode OTP salah! Coba lagi dengan kode yang benar:")
        except Exception as e:
            await event.reply(f"❌ Error: {str(e)}")
            self.state_manager.clear_state(user_id)
    
    async def _process_login_password(self, event):
        """Process 2FA password input"""
        user_id = event.sender_id
        password = event.message.text.strip()
        state = self.state_manager.get_state(user_id)
        
        if not state:
            return
        
        try:
            client = state["client"]
            await client.sign_in(password=password)
            
            # Get session string and user info
            session_string = client.session.save()
            me = await client.get_me()
            nama_akun = me.first_name + (f" {me.last_name}" if me.last_name else "")
            
            await client.disconnect()
            
            # Update state for kategori selection
            self.state_manager.set_state(user_id, {
                "action": "login_step3_pilih_kategori",
                "nomor": state["nomor"],
                "session_string": session_string,
                "nama_akun": nama_akun
            })
            
            await self._show_kategori_selection(event, "Pilih kategori untuk nomor ini:")
            
        except PasswordHashInvalidError:
            await event.reply("❌ Password salah! Coba lagi:")
        except Exception as e:
            await event.reply(f"❌ Error: {str(e)}")
            self.state_manager.clear_state(user_id)
    
    # ==================== KATEGORI HANDLERS ====================
    async def _show_kategori_selection(self, event, message_text: str):
        """Show kategori selection menu"""
        kategori_list = self.db.get_all_kategori()
        
        buttons = []
        for kategori in kategori_list:
            buttons.append([Button.inline(f"📁 {kategori.nama}", f"pilih_kategori_{kategori.id}".encode())])
        
        buttons.append([Button.inline("➕ Buat Kategori Baru", b"buat_kategori_baru")])
        
        if not kategori_list:
            message_text = "Belum ada kategori yang dibuat.\n\nBuat kategori baru dulu:"
            buttons = [[Button.inline("➕ Buat Kategori Baru", b"buat_kategori_baru")]]
        
        msg = self.formatter.format_message("PILIH KATEGORI", message_text)
        
        if hasattr(event, 'edit'):
            await event.edit(msg, buttons=buttons)
        else:
            await event.reply(msg, buttons=buttons)
    
    async def _handle_kategori_selection(self, event):
        """Handle kategori selection"""
        user_id = event.sender_id
        kategori_id = int(event.data.decode().split('_')[-1])
        
        state = self.state_manager.get_state(user_id)
        if not state:
            return
        
        kategori = self.db.get_kategori_by_id(kategori_id)
        if not kategori:
            await event.answer("❌ Kategori tidak ditemukan!", alert=True)
            return
        
        action = state.get("action")
        
        if action == "login_step3_pilih_kategori":
            # Save akun to database
            if self.db.add_akun_tg(state["nomor"], state["session_string"], 
                                   kategori_id, state["nama_akun"]):
                msg = self.formatter.format_message(
                    "LOGIN BERHASIL",
                    f"Akun **{state['nomor']}** berhasil ditambahkan ke kategori **{kategori.nama}**!\n\n"
                    f"👤 **Nama Akun:** {state['nama_akun']}",
                    success=True
                )
                buttons = [[Button.inline("🔙 Kembali ke Menu", b"back_to_main")]]
                await event.edit(msg, buttons=buttons)
            else:
                await event.answer("❌ Nomor ini sudah ada di database!", alert=True)
            
            self.state_manager.clear_state(user_id)
        
        elif action == "tambah_kontak_step2_pilih_kategori":
            await self._show_akun_selection_for_contacts(event, kategori)
    
    async def _process_new_kategori(self, event):
        """Process new kategori creation"""
        user_id = event.sender_id
        nama_kategori = event.message.text.strip()
        
        if not nama_kategori:
            await event.reply("❌ Nama kategori tidak boleh kosong!")
            return
        
        if self.db.add_kategori(nama_kategori):
            msg = self.formatter.format_message(
                "KATEGORI BERHASIL DIBUAT",
                f"Kategori **{nama_kategori}** telah dibuat!",
                success=True
            )
            await event.reply(msg)
            
            # Continue with previous flow if needed
            state = self.state_manager.get_state(user_id)
            if state:
                if "login_step3_pilih_kategori" in str(state.get("action", "")):
                    await self._show_kategori_selection(event, "Pilih kategori untuk nomor ini:")
                    return
                elif "tambah_kontak_step2_pilih_kategori" in str(state.get("action", "")):
                    await self._show_kategori_selection(event, "Pilih kategori akun yang ingin digunakan:")
                    return
        else:
            await event.reply("❌ Nama kategori sudah ada! Gunakan nama yang lain.")
            return
        
        self.state_manager.clear_state(user_id)
    
    # ==================== LIST AKUN HANDLERS ====================
    async def _show_kategori_list_akun(self, event):
        """Show kategori list for viewing akun"""
        kategori_list = self.db.get_all_kategori()
        
        if not kategori_list:
            buttons = [[Button.inline("🔙 Kembali", b"back_to_main")]]
            msg = self.formatter.format_message(
                "BELUM ADA KATEGORI",
                "Belum ada kategori yang dibuat. Buat kategori dulu!",
                success=False
            )
            await event.edit(msg, buttons=buttons)
            return
        
        buttons = []
        for kategori in kategori_list:
            buttons.append([Button.inline(f"📁 {kategori.nama}", f"list_akun_kat_{kategori.id}".encode())])
        
        buttons.append([Button.inline("🔙 Kembali", b"back_to_main")])
        
        msg = self.formatter.format_message(
            "PILIH KATEGORI",
            "Pilih kategori untuk melihat akun-akun di dalamnya:"
        )
        await event.edit(msg, buttons=buttons)
    
    # ==================== CONTACT HANDLERS ====================
    async def _start_tambah_kontak(self, event):
        """Start tambah kontak process"""
        user_id = event.sender_id
        self.state_manager.set_state(user_id, {
            "action": "tambah_kontak_step1", 
            "contacts": []
        })
        
        msg = self.formatter.format_message(
            "TAMBAH KONTAK",
            "Kirim kontak yang ingin ditambahkan satu per satu.\n\n"
            "Setelah selesai kirim semua kontak, ketik `/done` untuk lanjut ke step berikutnya."
        )
        await event.edit(msg)
    
    async def _process_contact_input(self, event):
        """Process contact input"""
        user_id = event.sender_id
        state = self.state_manager.get_state(user_id)
        
        if not state:
            return
        
        if event.message.contact:
            contact_data = {
                "phone": event.message.contact.phone_number,
                "first_name": event.message.contact.first_name,
                "last_name": event.message.contact.last_name
            }
            
            state["contacts"].append(contact_data)
            self.state_manager.set_state(user_id, state)
            
            count = len(state["contacts"])
            msg = f"✅ **Kontak ke-{count} berhasil ditambahkan!**\n\n"
            msg += f"👤 **Nama:** {contact_data['first_name']} {contact_data['last_name'] or ''}\n"
            msg += f"📞 **Nomor:** +{contact_data['phone']}\n\n"
            msg += "Kirim kontak lain atau ketik `/done` jika sudah selesai."
            
            await event.reply(msg)
        else:
            await event.reply("❌ Kirim kontak yang valid! Bukan text biasa.")
    
    async def _finish_contact_input(self, event):
        """Finish contact input process"""
        user_id = event.sender_id
        state = self.state_manager.get_state(user_id)
        
        if not state or not state.get("contacts"):
            await event.reply("❌ Belum ada kontak yang ditambahkan!")
            return
        
        # Save contacts temporarily
        self.db.clear_temp_contacts(user_id)
        
        for contact in state["contacts"]:
            self.db.add_temp_contact(user_id, contact)
        
        self.state_manager.set_state(user_id, {"action": "tambah_kontak_step2_pilih_kategori"})
        
        message_text = f"✅ **{len(state['contacts'])} kontak telah disimpan sementara!**\n\n"
        message_text += "Sekarang pilih kategori akun yang ingin digunakan untuk menyimpan kontak:"
        
        await self._show_kategori_selection(event, message_text)
    
    async def _show_akun_selection_for_contacts(self, event, kategori):
        """Show akun selection for contacts"""
        user_id = event.sender_id
        akun_list = self.db.get_akun_by_kategori(kategori.id)
        
        if not akun_list:
            await event.answer(f"❌ Belum ada akun di kategori {kategori.nama}!", alert=True)
            return
        
        buttons = []
        for akun in akun_list:
            display_name = f"{akun.nomor}"
            if akun.nama_akun:
                display_name += f" ({akun.nama_akun})"
            buttons.append([Button.inline(f"📱 {display_name}", f"pilih_akun_kontak_{akun.id}".encode())])
        
        buttons.append([Button.inline("🔙 Kembali", b"tambah_kontak")])
        
        self.state_manager.set_state(user_id, {
            "action": "tambah_kontak_step2_pilih_kategori",
            "selected_kategori": kategori.id
        })
        
        msg = self.formatter.format_message(
            f"PILIH AKUN - {kategori.nama.upper()}",
            "Pilih akun yang ingin digunakan untuk menyimpan kontak:"
        )
        await event.edit(msg, buttons=buttons)
    
    # ==================== INVITE HANDLERS ====================
    async def _start_invite_process(self, event):
        """Start invite process"""
        kategori_list = self.db.get_all_kategori()
        
        if not kategori_list:
            buttons = [[Button.inline("🔙 Kembali", b"back_to_main")]]
            msg = self.formatter.format_message(
                "BELUM ADA KATEGORI",
                "Belum ada kategori yang dibuat.",
                success=False
            )
            await event.edit(msg, buttons=buttons)
            return
        
        buttons = []
        for kategori in kategori_list:
            buttons.append([Button.inline(f"📁 {kategori.nama}", f"invite_grup_kat_{kategori.id}".encode())])
        
        buttons.append([Button.inline("🔙 Kembali", b"back_to_main")])
        
        msg = self.formatter.format_message(
            "INVITE KE GRUP/CHANNEL",
            "Pilih kategori akun yang ingin digunakan:"
        )
        await event.edit(msg, buttons=buttons)
    
    # ==================== UTILITY METHODS ====================
    async def _safe_disconnect_client(self, client):
        """Safely disconnect Telethon client"""
        try:
            if client and client.is_connected():
                await client.disconnect()
        except Exception as e:
            self.logger.error(f"Error disconnecting client: {e}")
    
    def _validate_phone_number(self, phone: str) -> bool:
        """Validate phone number format"""
        if not phone.startswith('+'):
            return False
        
        # Remove + and check if remaining chars are digits
        digits = phone[1:]
        if not digits.isdigit():
            return False
        
        # Basic length validation (7-15 digits)
        return 7 <= len(digits) <= 15
    
    async def _get_user_display_name(self, user_id: int) -> str:
        """Get user display name"""
        try:
            user = await self.bot.get_entity(user_id)
            name = user.first_name
            if user.last_name:
                name += f" {user.last_name}"
            if user.username:
                name += f" (@{user.username})"
            return name
        except Exception:
            return f"User ID: {user_id}"
    
    # ==================== BOT LIFECYCLE ====================
    async def start(self):
        """Start the bot"""
        try:
            self.logger.info("🤖 Starting Telegram Bot Manager...")
            
            # Create backup
            self.logger.info("💾 Creating backup...")
            self.storage.create_backup()
            
            # Cleanup old backups
            self.logger.info("🧹 Cleaning up old backups...")
            self.storage.cleanup_old_backups(config.BACKUP_RETENTION_DAYS)
            
            # Start bot
            await self.bot.start(bot_token=config.BOT_TOKEN)
            
            # Get bot info
            me = await self.bot.get_me()
            self.logger.info(f"✅ Bot successfully logged in as @{me.username}")
            self.logger.info(f"📊 Bot ID: {me.id}")
            
            # Show statistics
            kategori_count = len(self.db.get_all_kategori())
            akun_count = len(self.storage.read_json('akun_tg'))
            admin_count = len(self.db.get_all_admin_bots())
            
            self.logger.info(f"📈 Current statistics:")
            self.logger.info(f"   📁 Categories: {kategori_count}")
            self.logger.info(f"   📱 TG Accounts: {akun_count}")
            self.logger.info(f"   👨‍💼 Bot Admins: {admin_count}")
            
            self.logger.info("🚀 Bot is ready to use!")
            
            # Keep bot running
            await self.bot.run_until_disconnected()
            
        except Exception as e:
            self.logger.error(f"❌ Error starting bot: {e}")
            raise
        finally:
            if self.bot.is_connected():
                await self.bot.disconnect()
    
    async def stop(self):
        """Stop the bot gracefully"""
        self.logger.info("💤 Stopping bot...")
        if self.bot.is_connected():
            await self.bot.disconnect()
        self.logger.info("👋 Bot stopped successfully!")

# ==================== ADDITIONAL HANDLERS ====================
# Additional callback and message handlers can be added here
# This includes handlers for:
# - Admin management (add/remove admins)
# - Category editing
# - Account deletion
# - Contact clearing
# - Group/channel inviting
# - Account migration between categories

# ==================== MAIN FUNCTION ====================
async def main():
    """Main function to run the bot"""
    bot_manager = None
    
    try:
        # Initialize bot manager
        bot_manager = TelegramBotManager()
        
        # Start bot
        await bot_manager.start()
        
    except KeyboardInterrupt:
        print("\n💤 Bot stopped by user")
    except Exception as e:
        print(f"❌ Fatal error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        if bot_manager:
            await bot_manager.stop()
        print("👋 Thank you for using Telegram Bot Manager!")

# ==================== HEALTH CHECK ====================
def health_check() -> bool:
    """Check the health of JSON files"""
    try:
        storage = StorageManager(config.DATA_DIR)
        
        # Check if all files are readable
        for file_type in ['kategori', 'akun_tg', 'temp_contacts', 'admin_bots']:
            data = storage.read_json(file_type)
            if not isinstance(data, list):
                print(f"❌ File {file_type} has invalid format!")
                return False
        
        print("✅ All JSON files are healthy")
        return True
        
    except Exception as e:
        print(f"❌ Health check error: {e}")
        return False

# ==================== CLI UTILITIES ====================
def create_manual_backup():
    """Create manual backup"""
    try:
        storage = StorageManager(config.DATA_DIR)
        backup_path = storage.create_backup()
        if backup_path:
            print(f"✅ Manual backup created: {backup_path}")
        else:
            print("❌ Failed to create backup")
    except Exception as e:
        print(f"❌ Backup error: {e}")

def show_statistics():
    """Show current statistics"""
    try:
        db = DatabaseManager(StorageManager(config.DATA_DIR))
        
        kategori_count = len(db.get_all_kategori())
        akun_count = len(db.storage.read_json('akun_tg'))
        admin_count = len(db.get_all_admin_bots())
        
        print("📈 Current Statistics:")
        print(f"   📁 Categories: {kategori_count}")
        print(f"   📱 TG Accounts: {akun_count}")
        print(f"   👨‍💼 Bot Admins: {admin_count}")
        
    except Exception as e:
        print(f"❌ Error showing statistics: {e}")

# ==================== ENTRY POINT ====================
if __name__ == '__main__':
    import sys
    
    # Handle CLI arguments
    if len(sys.argv) > 1:
        command = sys.argv[1].lower()
        
        if command == 'health':
            health_check()
            sys.exit(0)
        elif command == 'backup':
            create_manual_backup()
            sys.exit(0)
        elif command == 'stats':
            show_statistics()
            sys.exit(0)
        elif command == 'help':
            print("Available commands:")
            print("  python bot.py health  - Check JSON files health")
            print("  python bot.py backup  - Create manual backup")
            print("  python bot.py stats   - Show statistics")
            print("  python bot.py         - Start bot (default)")
            sys.exit(0)
    
    try:
        # Run health check before starting
        print("🏥 Running health check...")
        if not health_check():
            print("❌ Health check failed! Attempting to fix...")
            # Try to reinitialize storage
            try:
                StorageManager(config.DATA_DIR)
                print("✅ Storage reinitialized")
            except Exception as e:
                print(f"❌ Failed to reinitialize storage: {e}")
                sys.exit(1)
        
        # Run bot
        asyncio.run(main())
        
    except KeyboardInterrupt:
        print("\n💤 Bot stopped by user")
    except Exception as e:
        print(f"❌ Fatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
