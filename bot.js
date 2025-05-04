//
// Import required libraries
const TelegramBot = require('node-telegram-bot-api');
const fs = require('fs');
const path = require('path');
const ExcelJS = require('exceljs');

// Replace with your token
const token = '8138702651:AAGQFucl1jGqPBrij1UPuh2vwB5VB1UnyqQ';

// Create a bot instance
const bot = new TelegramBot(token, { polling: true });

// Create data directory if it doesn't exist
const DATA_DIR = path.join(__dirname, 'data');
if (!fs.existsSync(DATA_DIR)) {
  fs.mkdirSync(DATA_DIR);
}

// Files to store data
const USERS_FILE = path.join(DATA_DIR, 'users.json');
const ADMINS_FILE = path.join(DATA_DIR, 'admins.json');

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

// Initialize or load admins data
let admins = [];
try {
  if (fs.existsSync(ADMINS_FILE)) {
    admins = JSON.parse(fs.readFileSync(ADMINS_FILE, 'utf8'));
  } else {
    // Add your admin user IDs here
    admins = [5988451717]; // Replace with your Telegram user ID
    fs.writeFileSync(ADMINS_FILE, JSON.stringify(admins), 'utf8');
  }
} catch (error) {
  console.error('Error loading admins data:', error);
}

// Save users data
function saveUsers() {
  fs.writeFileSync(USERS_FILE, JSON.stringify(users), 'utf8');
}

// Helper function to check if user is admin
function isAdmin(userId) {
  return admins.includes(userId);
}

// User sessions to track state
const userSessions = {};

// State constants
const STATE = {
  IDLE: 'IDLE',
  AWAITING_NAME: 'AWAITING_NAME',
  AWAITING_PHONE: 'AWAITING_PHONE',
  AWAITING_RESIDENCE: 'AWAITING_RESIDENCE',
  AWAITING_CONFIRMATION: 'AWAITING_CONFIRMATION',
  ADMIN_AWAITING_AD: 'ADMIN_AWAITING_AD'
};

// Handle /start command
bot.onText(/\/start/, (msg) => {
  const chatId = msg.chat.id;
  const userId = msg.from.id.toString();
  
  console.log(`User ${userId} started the bot`);
  
  // Check if user is already registered
  if (users[userId]) {
    bot.sendMessage(
      chatId,
      `👋 *Welcome back, ${users[userId].name}!*\n\nYour information is already registered with us.`,
      {
        parse_mode: 'Markdown',
        reply_markup: {
          inline_keyboard: [
            [{ text: '✏️ Update My Information', callback_data: 'update_info' }]
          ]
        }
      }
    );
  } else {
    // Start registration process
    userSessions[userId] = {
      state: STATE.AWAITING_NAME,
      data: {
        chatId: chatId
      }
    };
    
    bot.sendMessage(
      chatId,
      '🌟 *Welcome to our bot!* 🌟\n\nPlease enter your first and last name:',
      { parse_mode: 'Markdown' }
    );
  }
});

// Handle update_info button
bot.on('callback_query', (callbackQuery) => {
  const data = callbackQuery.data;
  const userId = callbackQuery.from.id.toString();
  const chatId = callbackQuery.message.chat.id;
  
  if (data === 'update_info') {
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
      { parse_mode: 'Markdown' }
    );
    
    // Answer callback query
    bot.answerCallbackQuery(callbackQuery.id);
  }
});

// Handle admin panel
bot.onText(/\/admin/, (msg) => {
  const userId = msg.from.id;
  const chatId = msg.chat.id;
  
  console.log(`User ${userId} accessed admin panel`);
  
  if (!isAdmin(userId)) {
    return bot.sendMessage(chatId, '⛔ You are not authorized to access the admin panel.');
  }
  
  bot.sendMessage(
    chatId,
    '👑 *Admin Panel*\n\nSelect an option:',
    {
      parse_mode: 'Markdown',
      reply_markup: {
        inline_keyboard: [
          [{ text: '👥 View Users', callback_data: 'admin_view_users' }],
          [{ text: '📊 View Users as Excel', callback_data: 'admin_download_excel' }],
          [{ text: '📣 Send Advertisement', callback_data: 'admin_send_ad' }]
        ]
      }
    }
  );
});

// Handle admin callbacks
bot.on('callback_query', async (callbackQuery) => {
  const data = callbackQuery.data;
  const userId = callbackQuery.from.id;
  const chatId = callbackQuery.message.chat.id;
  
  // Handle admin view users
  if (data === 'admin_view_users') {
    if (!isAdmin(userId)) return;
    
    const userCount = Object.keys(users).length;
    
    if (userCount === 0) {
      bot.sendMessage(
        chatId,
        '📊 *User Statistics*\n\nNo users have registered yet.',
        { parse_mode: 'Markdown' }
      );
      
      bot.answerCallbackQuery(callbackQuery.id);
      return;
    }
    
    let userList = `📊 *User Statistics*\n\nTotal Users: ${userCount}\n\n`;
    
    // Get first 10 users for display
    const userIds = Object.keys(users).slice(0, 10);
    
    userIds.forEach((userId, index) => {
      const user = users[userId];
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
          inline_keyboard: [
            [{ text: '⬅️ Back to Admin Panel', callback_data: 'back_to_admin' }]
          ]
        }
      }
    );
    
    bot.answerCallbackQuery(callbackQuery.id);
  }
  
  // Handle admin download excel
  else if (data === 'admin_download_excel') {
    if (!isAdmin(userId)) return;
    
    const userCount = Object.keys(users).length;
    
    if (userCount === 0) {
      bot.sendMessage(
        chatId,
        '📊 *User Statistics*\n\nNo users have registered yet.',
        { parse_mode: 'Markdown' }
      );
      
      bot.answerCallbackQuery(callbackQuery.id);
      return;
    }
    
    const workbook = new ExcelJS.Workbook();
    const worksheet = workbook.addWorksheet('Users');
    
    // Add header row
    worksheet.columns = [
      { header: 'User ID', key: 'userId', width: 15 },
      { header: 'Name', key: 'name', width: 20 },
      { header: 'Phone Number', key: 'phoneNumber', width: 15 },
      { header: 'Residence', key: 'residence', width: 20 },
      { header: 'Registration Date', key: 'registeredAt', width: 20 }
    ];
    
    // Add rows
    Object.keys(users).forEach(userId => {
      const user = users[userId];
      worksheet.addRow({
        userId,
        name: user.name,
        phoneNumber: user.phoneNumber,
        residence: user.residence,
        registeredAt: user.registeredAt
      });
    });
    
    // Style header row
    worksheet.getRow(1).font = { bold: true };
    
    // Write to file
    const excelFileName = path.join(DATA_DIR, 'users.xlsx');
    await workbook.xlsx.writeFile(excelFileName);
    
    // Send file to admin
    bot.sendDocument(chatId, excelFileName);
    
    // Remove file after sending
    setTimeout(() => {
      try {
        fs.unlinkSync(excelFileName);
      } catch (error) {
        console.error('Error removing Excel file:', error);
      }
    }, 5000);
    
    bot.answerCallbackQuery(callbackQuery.id);
  }
  
  // Handle admin send ad
  else if (data === 'admin_send_ad') {
    if (!isAdmin(userId)) return;
    
    userSessions[userId] = {
      state: STATE.ADMIN_AWAITING_AD
    };
    
    bot.sendMessage(
      chatId,
      '📣 *Send Advertisement*\n\nPlease enter the advertisement text you want to send to all users:',
      {
        parse_mode: 'Markdown',
        reply_markup: {
          inline_keyboard: [
            [{ text: '⬅️ Cancel', callback_data: 'back_to_admin' }]
          ]
        }
      }
    );
    
    bot.answerCallbackQuery(callbackQuery.id);
  }
  
  // Handle back to admin
  else if (data === 'back_to_admin') {
    if (!isAdmin(userId)) return;
    
    if (userSessions[userId]) {
      userSessions[userId].state = STATE.IDLE;
    }
    
    bot.sendMessage(
      chatId,
      '👑 *Admin Panel*\n\nSelect an option:',
      {
        parse_mode: 'Markdown',
        reply_markup: {
          inline_keyboard: [
            [{ text: '👥 View Users', callback_data: 'admin_view_users' }],
            [{ text: '📊 View Users as Excel', callback_data: 'admin_download_excel' }],
            [{ text: '📣 Send Advertisement', callback_data: 'admin_send_ad' }]
          ]
        }
      }
    );
    
    bot.answerCallbackQuery(callbackQuery.id);
  }
  
  // Handle send ad confirmation
  else if (data.startsWith('send_ad:')) {
    if (!isAdmin(userId)) return;
    
    const adText = Buffer.from(data.split(':')[1], 'base64').toString();
    
    bot.sendMessage(
      chatId,
      '📣 *Sending advertisement...*',
      { parse_mode: 'Markdown' }
    ).then(statusMessage => {
      let sentCount = 0;
      let failedCount = 0;
      const userIds = Object.keys(users);
      const totalUsers = userIds.length;
      
      const sendAds = async () => {
        for (const userId of userIds) {
          try {
            await bot.sendMessage(
              users[userId].chatId,
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
                  message_id: statusMessage.message_id,
                  parse_mode: 'Markdown'
                }
              );
            }
            
            // Add a small delay to avoid hitting Telegram's rate limits
            await new Promise(resolve => setTimeout(resolve, 100));
          } catch (error) {
            console.error(`Failed to send message to user ${userId}:`, error);
            failedCount++;
          }
        }
        
        // Final status
        bot.editMessageText(
          `📣 *Advertisement Status*\n\n` +
          `✅ Successfully sent to: ${sentCount} users\n` +
          `❌ Failed to send to: ${failedCount} users\n\n` +
          `Total Users: ${totalUsers}`,
          {
            chat_id: chatId,
            message_id: statusMessage.message_id,
            parse_mode: 'Markdown',
            reply_markup: {
              inline_keyboard: [
                [{ text: '⬅️ Back to Admin Panel', callback_data: 'back_to_admin' }]
              ]
            }
          }
        );
      };
      
      sendAds();
    });
    
    bot.answerCallbackQuery(callbackQuery.id);
  }
  
  // Handle confirm_data
  else if (data === 'confirm_data') {
    const session = userSessions[userId];
    
    if (session && session.state === STATE.AWAITING_CONFIRMATION) {
      const userData = session.data;
      userData.registeredAt = new Date().toISOString();
      
      users[userId] = userData;
      saveUsers();
      
      bot.editMessageText(
        `✨ *Thank you!* ✨\n\nYour data has been received and saved successfully.`,
        {
          chat_id: chatId,
          message_id: callbackQuery.message.message_id,
          parse_mode: 'Markdown'
        }
      );
      
      userSessions[userId].state = STATE.IDLE;
    }
    
    bot.answerCallbackQuery(callbackQuery.id);
  }
  
  // Handle edit_data
  else if (data === 'edit_data') {
    bot.sendMessage(
      chatId,
      '🔄 Let\'s update your information. What would you like to edit?',
      {
        reply_markup: {
          inline_keyboard: [
            [{ text: '👤 Name', callback_data: 'edit_name' }],
            [{ text: '📱 Phone Number', callback_data: 'edit_phone' }],
            [{ text: '🏙️ Residence', callback_data: 'edit_residence' }]
          ]
        }
      }
    );
    
    bot.answerCallbackQuery(callbackQuery.id);
  }
  
  // Handle edit_name
  else if (data === 'edit_name') {
    userSessions[userId].state = STATE.AWAITING_NAME;
    bot.sendMessage(chatId, '👤 Please enter your new name:');
    bot.answerCallbackQuery(callbackQuery.id);
  }
  
  // Handle edit_phone
  else if (data === 'edit_phone') {
    userSessions[userId].state = STATE.AWAITING_PHONE;
    bot.sendMessage(
      chatId,
      '📱 Please enter your new phone number:',
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
    bot.answerCallbackQuery(callbackQuery.id);
  }
  
  // Handle edit_residence
  else if (data === 'edit_residence') {
    userSessions[userId].state = STATE.AWAITING_RESIDENCE;
    bot.sendMessage(chatId, '🏙️ Please enter your new place of residence:');
    bot.answerCallbackQuery(callbackQuery.id);
  }
});

// Handle text messages
bot.on('message', (msg) => {
  if (!msg.text && !msg.contact) return;
  
  const chatId = msg.chat.id;
  const userId = msg.from.id.toString();
  const session = userSessions[userId];
  
  // Skip commands
  if (msg.text && msg.text.startsWith('/')) return;
  
  // If admin is sending an ad
  if (session && session.state === STATE.ADMIN_AWAITING_AD && isAdmin(userId)) {
    const adText = msg.text;
    
    bot.sendMessage(
      chatId,
      `📣 *Advertisement Preview*\n\n${adText}\n\nDo you want to send this advertisement to all users?`,
      {
        parse_mode: 'Markdown',
        reply_markup: {
          inline_keyboard: [
            [{ text: '✅ Send Now', callback_data: `send_ad:${Buffer.from(adText).toString('base64')}` }],
            [{ text: '⬅️ Cancel', callback_data: 'back_to_admin' }]
          ]
        }
      }
    );
    
    userSessions[userId].state = STATE.IDLE;
    return;
  }
  
  // If no active session, send help
  if (!session) {
    bot.sendMessage(
      chatId,
      '❓ *I didn\'t understand that command*\n\nPlease use /start to begin or /admin for admin panel.',
      { parse_mode: 'Markdown' }
    );
    return;
  }
  
  // Handle based on state
  switch (session.state) {
    case STATE.AWAITING_NAME:
      if (!msg.text) {
        bot.sendMessage(chatId, '❌ Please send a valid name as text.');
        return;
      }
      
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
      
    case STATE.AWAITING_PHONE:
      let phoneNumber;
      
      if (msg.contact) {
        phoneNumber = msg.contact.phone_number;
      } else if (msg.text) {
        phoneNumber = msg.text;
      } else {
        bot.sendMessage(chatId, '❌ Please send a valid phone number.');
        return;
      }
      
      session.data.phoneNumber = phoneNumber;
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
      break;
      
    case STATE.AWAITING_RESIDENCE:
      if (!msg.text) {
        bot.sendMessage(chatId, '❌ Please send a valid residence as text.');
        return;
      }
      
      session.data.residence = msg.text;
      session.state = STATE.AWAITING_CONFIRMATION;
      
      bot.sendMessage(
        chatId,
        `📋 *Your data has been received*\n\n` +
        `👤 *Name:* ${session.data.name}\n` +
        `📱 *Phone:* ${session.data.phoneNumber}\n` +
        `🏙️ *Residence:* ${session.data.residence}\n\n` +
        `Do you want to confirm?`,
        {
          parse_mode: 'Markdown',
          reply_markup: {
            inline_keyboard: [
              [
                { text: '✅ Confirm', callback_data: 'confirm_data' },
                { text: '✏️ Edit', callback_data: 'edit_data' }
              ]
            ]
          }
        }
      );
      break;
      
    default:
      // Unknown state, reset to IDLE
      session.state = STATE.IDLE;
      bot.sendMessage(
        chatId,
        '❓ *I didn\'t understand that command*\n\nPlease use /start to begin or /admin for admin panel.',
        { parse_mode: 'Markdown' }
      );
  }
});

// Log errors
bot.on('polling_error', (error) => {
  console.error('Polling error:', error);
});

console.log('Bot started successfully!');
