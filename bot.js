//
// Import required libraries
const TelegramBot = require('node-telegram-bot-api');
const fs = require('fs');
const path = require('path');
const ExcelJS = require('exceljs');

// TETAPKAN ADMIN IDS DI SINI - GANTI DENGAN ID TELEGRAM ANDA
const ADMIN_IDS = [5522120462]; // Ganti dengan ID Telegram Anda

// Replace with your token
const token = '7631108529:AAHp0Frem726gwnwP-eFseSxB5RSXO9UVX8';

// Create a bot instance
const bot = new TelegramBot(token, { polling: true });

// Log startup information
console.log('Starting bot with admin IDs:', ADMIN_IDS);

// Create data directory if it doesn't exist
const DATA_DIR = path.join(__dirname, 'data');
if (!fs.existsSync(DATA_DIR)) {
  fs.mkdirSync(DATA_DIR);
}

// Files to store data
const USERS_FILE = path.join(DATA_DIR, 'users.json');

// Initialize or load users data
let users = {};
try {
  if (fs.existsSync(USERS_FILE)) {
    users = JSON.parse(fs.readFileSync(USERS_FILE, 'utf8'));
  } else {
    fs.writeFileSync(USERS_FILE, JSON.stringify(users), 'utf8');
  }
} catch (error) {
  console.error('Error loading users data:', error);
}

// Save users data
function saveUsers() {
  fs.writeFileSync(USERS_FILE, JSON.stringify(users), 'utf8');
}

// Helper function to check if user is admin
function isAdmin(userId) {
  return ADMIN_IDS.includes(userId);
}

// User sessions to track state
const userSessions = {};

// Admin sessions for advertisement
const adminSessions = {};

// State constants
const STATE = {
  IDLE: 'IDLE',
  AWAITING_NAME: 'AWAITING_NAME',
  AWAITING_PHONE: 'AWAITING_PHONE',
  AWAITING_RESIDENCE: 'AWAITING_RESIDENCE',
  AWAITING_CONFIRMATION: 'AWAITING_CONFIRMATION',
  ADMIN_MENU: 'ADMIN_MENU',
  ADMIN_VIEW_USERS: 'ADMIN_VIEW_USERS',
  ADMIN_AD_TYPE: 'ADMIN_AD_TYPE',
  ADMIN_AD_TEXT: 'ADMIN_AD_TEXT',
  ADMIN_AD_MEDIA: 'ADMIN_AD_MEDIA',
  ADMIN_AD_CAPTION: 'ADMIN_AD_CAPTION',
  ADMIN_AD_CONFIRM: 'ADMIN_AD_CONFIRM'
};

// Handle /start command
bot.onText(/\/start/, (msg) => {
  const chatId = msg.chat.id;
  const userId = msg.from.id;
  
  console.log(`User ${userId} started the bot`);
  
  // Check if user is admin
  if (isAdmin(userId)) {
    console.log(`Admin ${userId} accessed the bot`);
    
    // Show admin menu immediately
    userSessions[userId] = {
      state: STATE.ADMIN_MENU
    };
    
    showAdminMenu(chatId);
    return;
  }
  
  // For non-admin users, check if already registered
  if (users[userId]) {
    userSessions[userId] = {
      state: STATE.IDLE
    };
    
    bot.sendMessage(
      chatId,
      `⭐ Welcome to our bot! ⭐\n\nYou are already registered, ${users[userId].name}!`,
      {
        reply_markup: {
          keyboard: [
            ['✏️ Update My Information']
          ],
          resize_keyboard: true
        }
      }
    );
  } else {
    // Start registration process for new non-admin users
    userSessions[userId] = {
      state: STATE.AWAITING_NAME,
      data: {
        chatId: chatId
      }
    };
    
    bot.sendMessage(
      chatId,
      '⭐ Welcome to our bot! ⭐\n\nPlease enter your first and last name:',
      { 
        reply_markup: {
          remove_keyboard: true
        }
      }
    );
  }
});

// Handle admin panel access
bot.onText(/\/admin/, (msg) => {
  const userId = msg.from.id;
  const chatId = msg.chat.id;
  
  console.log(`User ${userId} accessed admin panel via command`);
  
  if (!isAdmin(userId)) {
    return bot.sendMessage(chatId, '🚫 You are not authorized to access the admin panel.');
  }
  
  userSessions[userId] = {
    state: STATE.ADMIN_MENU
  };
  
  showAdminMenu(chatId);
});

// Show admin menu with keyboard buttons
function showAdminMenu(chatId) {
  bot.sendMessage(
    chatId,
    '👑 *Admin Panel*\n\nSelect an option:',
    {
      parse_mode: 'Markdown',
      reply_markup: {
        keyboard: [
          ['👥 View Users'],
          ['📊 Download Users as Excel'],
          ['📣 Send Advertisement'],
          ['🏠 Main Menu']
        ],
        resize_keyboard: true
      }
    }
  );
}

// Handle regular text messages
bot.on('message', async (msg) => {
  // Skip if not a text message or is a command
  if (!msg.text || msg.text.startsWith('/')) return;
  
  const chatId = msg.chat.id;
  const userId = msg.from.id;
  const session = userSessions[userId];
  
  // If no session exists, create one
  if (!session) {
    userSessions[userId] = {
      state: STATE.IDLE
    };
    
    // For admin, show admin menu
    if (isAdmin(userId)) {
      userSessions[userId].state = STATE.ADMIN_MENU;
      showAdminMenu(chatId);
    } else {
      bot.sendMessage(
        chatId,
        '❓ I didn\'t understand that. Please use /start to begin.',
        {
          reply_markup: {
            remove_keyboard: true
          }
        }
      );
    }
    return;
  }
  
  // ADMIN MENU OPTIONS
  if (isAdmin(userId)) {
    // Handle admin menu options
    if (msg.text === '👥 View Users') {
      handleViewUsers(chatId, userId);
      return;
    }
    
    if (msg.text === '📊 Download Users as Excel') {
      handleDownloadExcel(chatId, userId);
      return;
    }
    
    if (msg.text === '📣 Send Advertisement') {
      userSessions[userId].state = STATE.ADMIN_AD_TYPE;
      
      bot.sendMessage(
        chatId,
        '📣 *Create Advertisement*\n\nWhat type of advertisement would you like to send?',
        {
          parse_mode: 'Markdown',
          reply_markup: {
            keyboard: [
              ['📝 Text Message'],
              ['🖼️ Photo'],
              ['🎬 Video'],
              ['📄 Document'],
              ['⬅️ Back to Admin Menu']
            ],
            resize_keyboard: true
          }
        }
      );
      return;
    }
    
    if (msg.text === '🏠 Main Menu' || msg.text === '⬅️ Back to Admin Menu') {
      userSessions[userId].state = STATE.ADMIN_MENU;
      showAdminMenu(chatId);
      return;
    }
    
    // AD TYPE SELECTION
    if (session.state === STATE.ADMIN_AD_TYPE) {
      if (msg.text === '📝 Text Message') {
        userSessions[userId].state = STATE.ADMIN_AD_TEXT;
        adminSessions[userId] = {
          type: 'text'
        };
        
        bot.sendMessage(
          chatId,
          '📝 *Enter Text Message*\n\n' +
          'Please enter the text for your advertisement.\n\n' +
          '*Formatting options:*\n' +
          '- Use *bold text* for bold\n' +
          '- Use _italic text_ for italics\n' +
          '- Use `code` for monospace\n' +
          '- Use ```pre-formatted``` for pre-formatted text\n' +
          '- Use [text](URL) for links',
          {
            parse_mode: 'Markdown',
            reply_markup: {
              keyboard: [
                ['⬅️ Back to Admin Menu']
              ],
              resize_keyboard: true
            }
          }
        );
        return;
      } else if (['🖼️ Photo', '🎬 Video', '📄 Document'].includes(msg.text)) {
        // Set state for media upload
        userSessions[userId].state = STATE.ADMIN_AD_MEDIA;
        
        // Determine media type
        let mediaType = '';
        if (msg.text === '🖼️ Photo') mediaType = 'photo';
        else if (msg.text === '🎬 Video') mediaType = 'video';
        else if (msg.text === '📄 Document') mediaType = 'document';
        
        adminSessions[userId] = {
          type: mediaType
        };
        
        bot.sendMessage(
          chatId,
          `Please upload the ${mediaType} you want to send as an advertisement.`,
          {
            reply_markup: {
              keyboard: [
                ['⬅️ Back to Admin Menu']
              ],
              resize_keyboard: true
            }
          }
        );
        return;
      }
    }
    
    // ADVERTISEMENT TEXT
    if (session.state === STATE.ADMIN_AD_TEXT && adminSessions[userId] && adminSessions[userId].type === 'text') {
      // Store the text advertisement
      adminSessions[userId].text = msg.text;
      userSessions[userId].state = STATE.ADMIN_AD_CONFIRM;
      
      // Show preview and confirmation
      bot.sendMessage(
        chatId,
        `📣 *Advertisement Preview*\n\n${msg.text}`,
        {
          parse_mode: 'Markdown',
          reply_markup: {
            keyboard: [
              ['✅ Send Now'],
              ['⬅️ Back to Admin Menu']
            ],
            resize_keyboard: true
          }
        }
      );
      return;
    }
    
    // ADVERTISEMENT CAPTION
    if (session.state === STATE.ADMIN_AD_CAPTION && adminSessions[userId]) {
      adminSessions[userId].caption = msg.text;
      userSessions[userId].state = STATE.ADMIN_AD_CONFIRM;
      
      // Show confirmation for media advertisement
      bot.sendMessage(
        chatId,
        `📣 *Advertisement with Caption*\n\nCaption: ${msg.text}\n\nReady to send?`,
        {
          parse_mode: 'Markdown',
          reply_markup: {
            keyboard: [
              ['✅ Send Now'],
              ['⬅️ Back to Admin Menu']
            ],
            resize_keyboard: true
          }
        }
      );
      return;
    }
    
    // SEND ADVERTISEMENT CONFIRMATION
    if (session.state === STATE.ADMIN_AD_CONFIRM && msg.text === '✅ Send Now' && adminSessions[userId]) {
      // Handle based on type
      if (adminSessions[userId].type === 'text') {
        sendTextAdvertisement(chatId, userId);
      } else {
        sendMediaAdvertisement(chatId, userId);
      }
      return;
    }
  }
  
  // USER REGISTRATION PROCESS
  
  // Handle "Update My Information" button
  if (msg.text === '✏️ Update My Information') {
    // Start registration process again
    userSessions[userId] = {
      state: STATE.AWAITING_NAME,
      data: {
        chatId: chatId
      }
    };
    
    bot.sendMessage(
      chatId,
      '🔄 *Update Your Information*\n\nPlease enter your first and last name:',
      { 
        parse_mode: 'Markdown',
        reply_markup: {
          remove_keyboard: true
        }
      }
    );
    return;
  }
  
  // Handle state-specific user inputs
  switch (session.state) {
    case STATE.AWAITING_NAME:
      session.data.name = msg.text;
      session.state = STATE.AWAITING_PHONE;
      
      bot.sendMessage(
        chatId,
        '📱 Please share your phone number:',
        {
          reply_markup: {
            keyboard: [
              [{ text: '📲 Share my phone number', request_contact: true }]
            ],
            resize_keyboard: true,
            one_time_keyboard: true
          }
        }
      );
      break;
      
    case STATE.AWAITING_RESIDENCE:
      session.data.residence = msg.text;
      session.state = STATE.AWAITING_CONFIRMATION;
      
      // Show confirmation with keyboard buttons
      showConfirmation(chatId, userId);
      break;
      
    case STATE.AWAITING_CONFIRMATION:
      if (msg.text === '✅ Confirm') {
        // Save user data
        const userData = session.data;
        userData.registeredAt = new Date().toISOString();
        
        users[userId] = userData;
        saveUsers();
        
        bot.sendMessage(
          chatId,
          '✨ *Thank you!* ✨\n\nYour data has been received and saved successfully.',
          {
            parse_mode: 'Markdown',
            reply_markup: {
              keyboard: [
                ['✏️ Update My Information']
              ],
              resize_keyboard: true
            }
          }
        );
        
        // Reset session
        userSessions[userId].state = STATE.IDLE;
      } else if (msg.text === '✏️ Edit Information') {
        // Start registration process again
        userSessions[userId] = {
          state: STATE.AWAITING_NAME,
          data: {
            chatId: chatId
          }
        };
        
        bot.sendMessage(
          chatId,
          '🔄 *Update Your Information*\n\nPlease enter your first and last name:',
          { 
            parse_mode: 'Markdown',
            reply_markup: {
              remove_keyboard: true
            }
          }
        );
      }
      break;
  }
});

// Handle contact sharing for phone number
bot.on('contact', (msg) => {
  const chatId = msg.chat.id;
  const userId = msg.from.id;
  const session = userSessions[userId];
  
  if (!session) return;
  
  if (session.state === STATE.AWAITING_PHONE) {
    session.data.phoneNumber = msg.contact.phone_number;
    session.state = STATE.AWAITING_RESIDENCE;
    
    bot.sendMessage(
      chatId,
      '🏙️ Please enter your place of residence:',
      {
        reply_markup: {
          remove_keyboard: true
        }
      }
    );
  }
});

// Handle photo uploads (for admin advertisements)
bot.on('photo', (msg) => {
  const chatId = msg.chat.id;
  const userId = msg.from.id;
  
  if (!isAdmin(userId)) return;
  
  const session = userSessions[userId];
  if (!session || session.state !== STATE.ADMIN_AD_MEDIA || !adminSessions[userId] || adminSessions[userId].type !== 'photo') return;
  
  // Get the highest quality photo
  const photo = msg.photo[msg.photo.length - 1];
  adminSessions[userId].fileId = photo.file_id;
  
  userSessions[userId].state = STATE.ADMIN_AD_CAPTION;
  
  bot.sendMessage(
    chatId,
    '📝 Please enter a caption for your photo (or click Skip Caption):',
    {
      reply_markup: {
        keyboard: [
          ['⏩ Skip Caption'],
          ['⬅️ Back to Admin Menu']
        ],
        resize_keyboard: true
      }
    }
  );
});

// Handle video uploads
bot.on('video', (msg) => {
  const chatId = msg.chat.id;
  const userId = msg.from.id;
  
  if (!isAdmin(userId)) return;
  
  const session = userSessions[userId];
  if (!session || session.state !== STATE.ADMIN_AD_MEDIA || !adminSessions[userId] || adminSessions[userId].type !== 'video') return;
  
  adminSessions[userId].fileId = msg.video.file_id;
  
  userSessions[userId].state = STATE.ADMIN_AD_CAPTION;
  
  bot.sendMessage(
    chatId,
    '📝 Please enter a caption for your video (or click Skip Caption):',
    {
      reply_markup: {
        keyboard: [
          ['⏩ Skip Caption'],
          ['⬅️ Back to Admin Menu']
        ],
        resize_keyboard: true
      }
    }
  );
});

// Handle document uploads
bot.on('document', (msg) => {
  const chatId = msg.chat.id;
  const userId = msg.from.id;
  
  if (!isAdmin(userId)) return;
  
  const session = userSessions[userId];
  if (!session || session.state !== STATE.ADMIN_AD_MEDIA || !adminSessions[userId] || adminSessions[userId].type !== 'document') return;
  
  adminSessions[userId].fileId = msg.document.file_id;
  
  userSessions[userId].state = STATE.ADMIN_AD_CAPTION;
  
  bot.sendMessage(
    chatId,
    '📝 Please enter a caption for your document (or click Skip Caption):',
    {
      reply_markup: {
        keyboard: [
          ['⏩ Skip Caption'],
          ['⬅️ Back to Admin Menu']
        ],
        resize_keyboard: true
      }
    }
  );
});

// Handle skip caption
bot.onText(/⏩ Skip Caption/, (msg) => {
  const chatId = msg.chat.id;
  const userId = msg.from.id;
  
  if (!isAdmin(userId)) return;
  
  const session = userSessions[userId];
  if (!session || session.state !== STATE.ADMIN_AD_CAPTION || !adminSessions[userId]) return;
  
  adminSessions[userId].caption = '';
  userSessions[userId].state = STATE.ADMIN_AD_CONFIRM;
  
  // Show preview for media
  showMediaPreview(chatId, userId);
});

// Function to show confirmation with keyboard buttons
function showConfirmation(chatId, userId) {
  const userData = userSessions[userId].data;
  
  bot.sendMessage(
    chatId,
    `📋 *Your data:*\n\n` +
    `👤 *Name:* ${userData.name}\n` +
    `📱 *Phone:* ${userData.phoneNumber}\n` +
    `🏙️ *Residence:* ${userData.residence}\n\n` +
    `Is this information correct?`,
    {
      parse_mode: 'Markdown',
      reply_markup: {
        keyboard: [
          ['✅ Confirm'],
          ['✏️ Edit Information']
        ],
        resize_keyboard: true,
        one_time_keyboard: true
      }
    }
  );
}

// Function to handle View Users
async function handleViewUsers(chatId, userId) {
  if (!isAdmin(userId)) return;
  
  userSessions[userId].state = STATE.ADMIN_VIEW_USERS;
  
  const userCount = Object.keys(users).length;
  
  if (userCount === 0) {
    bot.sendMessage(
      chatId,
      '📊 *User Statistics*\n\nNo users have registered yet.',
      {
        parse_mode: 'Markdown',
        reply_markup: {
          keyboard: [
            ['⬅️ Back to Admin Menu']
          ],
          resize_keyboard: true
        }
      }
    );
    return;
  }
  
  let userList = `📊 *User Statistics*\n\nTotal Users: ${userCount}\n\n`;
  
  // Get first 10 users for display
  const userIds = Object.keys(users).slice(0, 10);
  
  userIds.forEach((id, index) => {
    const user = users[id];
    userList += `*User ${index + 1}:*\n`;
    userList += `👤 Name: ${user.name}\n`;
    userList += `📱 Phone: ${user.phoneNumber}\n`;
    userList += `🏙️ Residence: ${user.residence}\n`;
    userList += `📅 Registered: ${new Date(user.registeredAt).toLocaleDateString()}\n\n`;
  });
  
  if (userCount > 10) {
    userList += `_...and ${userCount - 10} more users_`;
  }
  
  bot.sendMessage(
    chatId,
    userList,
    {
      parse_mode: 'Markdown',
      reply_markup: {
        keyboard: [
          ['⬅️ Back to Admin Menu']
        ],
        resize_keyboard: true
      }
    }
  );
}

// Function to handle Download Excel
async function handleDownloadExcel(chatId, userId) {
  if (!isAdmin(userId)) return;
  
  const userCount = Object.keys(users).length;
  
  if (userCount === 0) {
    bot.sendMessage(
      chatId,
      '📊 *User Statistics*\n\nNo users have registered yet.',
      {
        parse_mode: 'Markdown',
        reply_markup: {
          keyboard: [
            ['⬅️ Back to Admin Menu']
          ],
          resize_keyboard: true
        }
      }
    );
    return;
  }
  
  const workbook = new ExcelJS.Workbook();
  const worksheet = workbook.addWorksheet('Users');
  
  // Add header row
  worksheet.columns = [
    { header: 'User ID', key: 'userId', width: 15 },
    { header: 'Name', key: 'name', width: 20 },
    { header: 'Phone Number', key: 'phoneNumber', width: 15 },
    { header: 'Residence', key: 'residence', width: 25 },
    { header: 'Registration Date', key: 'registeredAt', width: 20 }
  ];
  
  // Add rows
  Object.keys(users).forEach(userId => {
    const user = users[userId];
    const row = {
      userId,
      name: user.name,
      phoneNumber: user.phoneNumber,
      residence: user.residence,
      registeredAt: user.registeredAt
    };
    
    worksheet.addRow(row);
  });
  
  // Style header row
  worksheet.getRow(1).font = { bold: true };
  
  // Write to file
  const excelFileName = path.join(DATA_DIR, 'users.xlsx');
  await workbook.xlsx.writeFile(excelFileName);
  
  // Send file to admin
  bot.sendDocument(chatId, excelFileName, {
    caption: '📊 Here is the user data in Excel format.',
    reply_markup: {
      keyboard: [
        ['⬅️ Back to Admin Menu']
      ],
      resize_keyboard: true
    }
  });
  
  // Remove file after sending
  setTimeout(() => {
    try {
      fs.unlinkSync(excelFileName);
    } catch (error) {
      console.error('Error removing Excel file:', error);
    }
  }, 5000);
}

// Function to show media preview
function showMediaPreview(chatId, userId) {
  const adData = adminSessions[userId];
  
  if (!adData) return;
  
  // Send preview based on media type
  const replyMarkup = {
    keyboard: [
      ['✅ Send Now'],
      ['⬅️ Back to Admin Menu']
    ],
    resize_keyboard: true
  };
  
  const options = {
    caption: adData.caption || undefined,
    parse_mode: 'Markdown',
    reply_markup: replyMarkup
  };
  
  switch (adData.type) {
    case 'photo':
      bot.sendPhoto(chatId, adData.fileId, options);
      break;
    case 'video':
      bot.sendVideo(chatId, adData.fileId, options);
      break;
    case 'document':
      bot.sendDocument(chatId, adData.fileId, options);
      break;
  }
}

// Function to send text advertisement
async function sendTextAdvertisement(chatId, userId) {
  if (!isAdmin(userId) || !adminSessions[userId]) return;
  
  const adText = adminSessions[userId].text;
  
  // Send status message
  const statusMsg = await bot.sendMessage(
    chatId,
    '📣 *Sending advertisement...*',
    { 
      parse_mode: 'Markdown',
      reply_markup: {
        remove_keyboard: true
      }
    }
  );
  
  let sentCount = 0;
  let failedCount = 0;
  const userIds = Object.keys(users);
  const totalUsers = userIds.length;
  
  // Send to each user
  for (const receiverId of userIds) {
    try {
      await bot.sendMessage(
        users[receiverId].chatId,
        `📢 *ANNOUNCEMENT*\n\n${adText}`,
        { parse_mode: 'Markdown' }
      );
      sentCount++;
      
      // Update status every 10 users
      if (sentCount % 10 === 0 || sentCount + failedCount === totalUsers) {
        await bot.editMessageText(
          `📣 *Sending advertisement...*\n\nProgress: ${sentCount + failedCount}/${totalUsers}`,
          {
            chat_id: chatId,
            message_id: statusMsg.message_id,
            parse_mode: 'Markdown'
          }
        );
      }
      
      // Add a small delay to avoid hitting Telegram's rate limits
      await new Promise(resolve => setTimeout(resolve, 100));
    } catch (error) {
      console.error(`Failed to send message to user ${receiverId}:`, error);
      failedCount++;
    }
  }
  
  // Final status
  await bot.editMessageText(
    `📣 *Advertisement Status*\n\n` +
    `✅ Successfully sent to: ${sentCount} users\n` +
    `❌ Failed to send to: ${failedCount} users\n\n` +
    `Total Users: ${totalUsers}`,
    {
      chat_id: chatId,
      message_id: statusMsg.message_id,
      parse_mode: 'Markdown'
    }
  );
  
  // Show admin menu again
  showAdminMenu(chatId);
  
  // Clear admin session
  delete adminSessions[userId];
  userSessions[userId].state = STATE.ADMIN_MENU;
}

// Function to send media advertisement
async function sendMediaAdvertisement(chatId, userId) {
  if (!isAdmin(userId) || !adminSessions[userId]) return;
  
  const adData = adminSessions[userId];
  
  // Send status message
  const statusMsg = await bot.sendMessage(
    chatId,
    '📣 *Sending advertisement...*',
    { 
      parse_mode: 'Markdown',
      reply_markup: {
        remove_keyboard: true
      }
    }
  );
  
  let sentCount = 0;
  let failedCount = 0;
  const userIds = Object.keys(users);
  const totalUsers = userIds.length;
  
  // Send to each user
  for (const receiverId of userIds) {
    try {
      const options = {
        caption: adData.caption || undefined,
        parse_mode: 'Markdown'
      };
      
      // Send based on media type
      switch (adData.type) {
        case 'photo':
          await bot.sendPhoto(users[receiverId].chatId, adData.fileId, options);
          break;
        case 'video':
          await bot.sendVideo(users[receiverId].chatId, adData.fileId, options);
          break;
        case 'document':
          await bot.sendDocument(users[receiverId].chatId, adData.fileId, options);
          break;
      }
      
      sentCount++;
      
      // Update status every 10 users
      if (sentCount % 10 === 0 || sentCount + failedCount === totalUsers) {
        await bot.editMessageText(
          `📣 *Sending advertisement...*\n\nProgress: ${sentCount + failedCount}/${totalUsers}`,
          {
            chat_id: chatId,
            message_id: statusMsg.message_id,
            parse_mode: 'Markdown'
          }
        );
      }
      
      // Add a small delay to avoid hitting Telegram's rate limits
      await new Promise(resolve => setTimeout(resolve, 100));
    } catch (error) {
      console.error(`Failed to send message to user ${receiverId}:`, error);
      failedCount++;
    }
  }
  
  // Final status
  await bot.editMessageText(
    `📣 *Advertisement Status*\n\n` +
    `✅ Successfully sent to: ${sentCount} users\n` +
    `❌ Failed to send to: ${failedCount} users\n\n` +
    `Total Users: ${totalUsers}`,
    {
      chat_id: chatId,
      message_id: statusMsg.message_id,
      parse_mode: 'Markdown'
    }
  );
  
  // Show admin menu again
  showAdminMenu(chatId);
  
  // Clear admin session
  delete adminSessions[userId];
  userSessions[userId].state = STATE.ADMIN_MENU;
}

// Log errors
bot.on('polling_error', (error) => {
  console.error('Polling error:', error);
});

console.log('Bot started successfully!');
