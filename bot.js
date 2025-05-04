//
// Import required libraries
const TelegramBot = require('node-telegram-bot-api');
const fs = require('fs');
const path = require('path');
const ExcelJS = require('exceljs');

// TETAPKAN ADMIN IDS DI SINI - GANTI DENGAN ID TELEGRAM ANDA
const ADMIN_IDS = [5988451717]; // Ganti dengan ID Telegram Anda

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

// State constants
const STATE = {
  IDLE: 'IDLE',
  AWAITING_NAME: 'AWAITING_NAME',
  AWAITING_PHONE: 'AWAITING_PHONE',
  AWAITING_LOCATION: 'AWAITING_LOCATION',
  AWAITING_MANUAL_LOCATION: 'AWAITING_MANUAL_LOCATION',
  AWAITING_CONFIRMATION: 'AWAITING_CONFIRMATION',
  ADMIN_AWAITING_AD: 'ADMIN_AWAITING_AD',
  EDITING_NAME: 'EDITING_NAME',
  EDITING_PHONE: 'EDITING_PHONE',
  EDITING_LOCATION: 'EDITING_LOCATION'
};

// Handle /start command
bot.onText(/\/start/, (msg) => {
  const chatId = msg.chat.id;
  const userId = msg.from.id;
  
  console.log(`User ${userId} started the bot`);
  
  // Check if user is admin
  if (isAdmin(userId)) {
    console.log(`Admin ${userId} accessed the bot`);
    
    // Show admin panel immediately
    showAdminPanel(chatId);
    return;
  }
  
  // For non-admin users, check if already registered
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
    // Start registration process for new non-admin users
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

// Handle admin panel access
bot.onText(/\/admin/, (msg) => {
  const userId = msg.from.id;
  const chatId = msg.chat.id;
  
  console.log(`User ${userId} accessed admin panel via command`);
  
  if (!isAdmin(userId)) {
    return bot.sendMessage(chatId, '⛔ You are not authorized to access the admin panel.');
  }
  
  showAdminPanel(chatId);
});

// Show admin panel
function showAdminPanel(chatId) {
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
}

// Handle all callback queries
bot.on('callback_query', async (callbackQuery) => {
  const data = callbackQuery.data;
  const userId = callbackQuery.from.id;
  const chatId = callbackQuery.message.chat.id;
  const messageId = callbackQuery.message.message_id;
  
  console.log(`Callback query from user ${userId}: ${data}`);
  
  // Admin panel access via callback
  if (data === 'admin_panel') {
    if (!isAdmin(userId)) {
      bot.answerCallbackQuery(callbackQuery.id, { text: '⛔ You are not authorized to access the admin panel.', show_alert: true });
      return;
    }
    
    showAdminPanel(chatId);
    bot.answerCallbackQuery(callbackQuery.id);
    return;
  }
  
  // Update info
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
    
    bot.answerCallbackQuery(callbackQuery.id);
    return;
  }
  
  // Handle admin view users
  if (data === 'admin_view_users') {
    if (!isAdmin(userId)) {
      bot.answerCallbackQuery(callbackQuery.id, { text: '⛔ You are not authorized to access the admin panel.', show_alert: true });
      return;
    }
    
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
      
      // Format location based on type
      if (user.location && user.location.latitude) {
        userList += `📍 Location: ${user.location.latitude}, ${user.location.longitude}\n`;
        if (user.manualLocation) {
          userList += `🏙️ Description: ${user.manualLocation}\n`;
        }
      } else if (user.manualLocation) {
        userList += `🏙️ Location: ${user.manualLocation}\n`;
      }
      
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
    return;
  }
  
  // Handle admin download excel
  if (data === 'admin_download_excel') {
    if (!isAdmin(userId)) {
      bot.answerCallbackQuery(callbackQuery.id, { text: '⛔ You are not authorized to access the admin panel.', show_alert: true });
      return;
    }
    
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
      { header: 'Latitude', key: 'latitude', width: 15 },
      { header: 'Longitude', key: 'longitude', width: 15 },
      { header: 'Location Description', key: 'locationDesc', width: 25 },
      { header: 'Registration Date', key: 'registeredAt', width: 20 }
    ];
    
    // Add rows
    Object.keys(users).forEach(userId => {
      const user = users[userId];
      const row = {
        userId,
        name: user.name,
        phoneNumber: user.phoneNumber,
        latitude: user.location ? user.location.latitude : '',
        longitude: user.location ? user.location.longitude : '',
        locationDesc: user.manualLocation || '',
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
    return;
  }
  
  // Handle admin send ad
  if (data === 'admin_send_ad') {
    if (!isAdmin(userId)) {
      bot.answerCallbackQuery(callbackQuery.id, { text: '⛔ You are not authorized to access the admin panel.', show_alert: true });
      return;
    }
    
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
    return;
  }
  
  // Handle back to admin
  if (data === 'back_to_admin') {
    if (!isAdmin(userId)) {
      bot.answerCallbackQuery(callbackQuery.id, { text: '⛔ You are not authorized to access the admin panel.', show_alert: true });
      return;
    }
    
    if (userSessions[userId]) {
      userSessions[userId].state = STATE.IDLE;
    }
    
    showAdminPanel(chatId);
    
    bot.answerCallbackQuery(callbackQuery.id);
    return;
  }
  
  // Handle send ad confirmation
  if (data.startsWith('send_ad:')) {
    if (!isAdmin(userId)) {
      bot.answerCallbackQuery(callbackQuery.id, { text: '⛔ You are not authorized to access the admin panel.', show_alert: true });
      return;
    }
    
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
    return;
  }
  
  // Handle manual location entry
  if (data === 'enter_manual_location') {
    userSessions[userId].state = STATE.AWAITING_MANUAL_LOCATION;
    
    bot.sendMessage(
      chatId,
      '🏙️ Please enter your place of residence:',
      {
        reply_markup: {
          remove_keyboard: true
        }
      }
    );
    
    bot.answerCallbackQuery(callbackQuery.id);
    return;
  }
  
  // Handle confirm_data
  if (data === 'confirm_data') {
    const session = userSessions[userId];
    
    if (!session || session.state !== STATE.AWAITING_CONFIRMATION) {
      bot.answerCallbackQuery(callbackQuery.id, { text: '❌ Something went wrong. Please try again.', show_alert: true });
      return;
    }
    
    const userData = session.data;
    userData.registeredAt = new Date().toISOString();
    
    users[userId] = userData;
    saveUsers();
    
    bot.editMessageText(
      `✨ *Thank you!* ✨\n\nYour data has been received and saved successfully.`,
      {
        chat_id: chatId,
        message_id: messageId,
        parse_mode: 'Markdown'
      }
    );
    
    userSessions[userId].state = STATE.IDLE;
    
    bot.answerCallbackQuery(callbackQuery.id);
    return;
  }
  
  // Handle edit_data
  if (data === 'edit_data') {
    bot.sendMessage(
      chatId,
      '🔄 What would you like to edit?',
      {
        reply_markup: {
          inline_keyboard: [
            [{ text: '👤 Name', callback_data: 'edit_name' }],
            [{ text: '📱 Phone Number', callback_data: 'edit_phone' }],
            [{ text: '📍 Location', callback_data: 'edit_location' }]
          ]
        }
      }
    );
    
    bot.answerCallbackQuery(callbackQuery.id);
    return;
  }
  
  // Handle edit_name
  if (data === 'edit_name') {
    userSessions[userId].state = STATE.EDITING_NAME;
    bot.sendMessage(chatId, '👤 Please enter your new name:');
    bot.answerCallbackQuery(callbackQuery.id);
    return;
  }
  
  // Handle edit_phone
  if (data === 'edit_phone') {
    userSessions[userId].state = STATE.EDITING_PHONE;
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
    return;
  }
  
  // Handle edit_location
  if (data === 'edit_location') {
    userSessions[userId].state = STATE.EDITING_LOCATION;
    bot.sendMessage(
      chatId,
      '📍 Please share your location:',
      {
        reply_markup: {
          keyboard: [
            [{ text: '📍 Share my location', request_location: true }],
            [{ text: '🏙️ Enter location manually' }]
          ],
          resize_keyboard: true,
          one_time_keyboard: true
        }
      }
    );
    bot.answerCallbackQuery(callbackQuery.id);
    return;
  }
});

// Handle text messages
bot.on('message', async (msg) => {
  // Skip processing if message doesn't contain useful data
  if (!msg.text && !msg.contact && !msg.location) return;
  
  const chatId = msg.chat.id;
  const userId = msg.from.id;
  const session = userSessions[userId];
  
  // Skip commands
  if (msg.text && msg.text.startsWith('/')) return;
  
  // Manual location entry without going through keyboard
  if (msg.text && msg.text === '🏙️ Enter location manually') {
    userSessions[userId].state = STATE.AWAITING_MANUAL_LOCATION;
    
    bot.sendMessage(
      chatId,
      '🏙️ Please enter your place of residence:',
      {
        reply_markup: {
          remove_keyboard: true
        }
      }
    );
    return;
  }
  
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
  
  // If no active session or admin with no specific task, skip processing
  if (!session) {
    // If admin, show admin panel
    if (isAdmin(userId)) {
      if (msg.text && !msg.text.startsWith('/')) {
        showAdminPanel(chatId);
      }
    } else {
      // For regular users with no session, send help
      bot.sendMessage(
        chatId,
        '❓ *I didn\'t understand that*\n\nPlease use /start to begin registration.',
        { parse_mode: 'Markdown' }
      );
    }
    return;
  }
  
  // Handle location
  if (msg.location) {
    if (session.state === STATE.AWAITING_LOCATION || session.state === STATE.EDITING_LOCATION) {
      session.data.location = {
        latitude: msg.location.latitude,
        longitude: msg.location.longitude
      };
      
      // If editing, update confirmation immediately
      if (session.state === STATE.EDITING_LOCATION) {
        showUpdatedData(chatId, userId);
        return;
      }
      
      // Ask if they want to add a description
      bot.sendMessage(
        chatId,
        '📍 Location received! Would you like to add a description of your location?',
        {
          reply_markup: {
            inline_keyboard: [
              [
                { text: 'Yes', callback_data: 'enter_manual_location' },
                { text: 'No', callback_data: 'skip_description' }
              ]
            ]
          },
          remove_keyboard: true
        }
      );
      
      // Move to confirmation if no description needed
      bot.on('callback_query', (callbackQuery) => {
        if (callbackQuery.data === 'skip_description') {
          session.state = STATE.AWAITING_CONFIRMATION;
          bot.answerCallbackQuery(callbackQuery.id);
          showConfirmationMessage(chatId, userId);
        }
      });
    }
    return;
  }
  
  // Handle contact
  if (msg.contact) {
    if (session.state === STATE.AWAITING_PHONE || session.state === STATE.EDITING_PHONE) {
      session.data.phoneNumber = msg.contact.phone_number;
      
      // If editing, update confirmation
      if (session.state === STATE.EDITING_PHONE) {
        showUpdatedData(chatId, userId);
        return;
      }
      
      // Move to next step if registering
      session.state = STATE.AWAITING_LOCATION;
      
      bot.sendMessage(
        chatId,
        '📍 Please share your location:',
        {
          reply_markup: {
            keyboard: [
              [{ text: '📍 Share my location', request_location: true }],
              [{ text: '🏙️ Enter location manually' }]
            ],
            resize_keyboard: true,
            one_time_keyboard: true
          }
        }
      );
    }
    return;
  }
  
  // Handle text based on state
  if (msg.text) {
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
        
      case STATE.AWAITING_PHONE:
        session.data.phoneNumber = msg.text;
        session.state = STATE.AWAITING_LOCATION;
        
        bot.sendMessage(
          chatId,
          '📍 Please share your location:',
          {
            reply_markup: {
              keyboard: [
                [{ text: '📍 Share my location', request_location: true }],
                [{ text: '🏙️ Enter location manually' }]
              ],
              resize_keyboard: true,
              one_time_keyboard: true
            }
          }
        );
        break;
        
      case STATE.AWAITING_MANUAL_LOCATION:
        session.data.manualLocation = msg.text;
        session.state = STATE.AWAITING_CONFIRMATION;
        
        showConfirmationMessage(chatId, userId);
        break;
        
      case STATE.EDITING_NAME:
        session.data.name = msg.text;
        showUpdatedData(chatId, userId);
        break;
        
      case STATE.EDITING_PHONE:
        session.data.phoneNumber = msg.text;
        showUpdatedData(chatId, userId);
        break;
      
      case STATE.EDITING_LOCATION:
        // Manually entered location during edit
        session.data.manualLocation = msg.text;
        // Remove GPS coordinates if user enters manual location
        delete session.data.location;
        showUpdatedData(chatId, userId);
        break;
        
      default:
        // For admin, show admin panel on any message
        if (isAdmin(userId)) {
          showAdminPanel(chatId);
        } else {
          // Unknown state for non-admin, reset to IDLE
          session.state = STATE.IDLE;
          bot.sendMessage(
            chatId,
            '❓ *I didn\'t understand that*\n\nPlease use /start to begin registration.',
            { 
              parse_mode: 'Markdown',
              reply_markup: {
                remove_keyboard: true
              }
            }
          );
        }
    }
  }
});

// Helper function to show confirmation message
function showConfirmationMessage(chatId, userId) {
  const userData = userSessions[userId].data;
  
  let locationInfo = '';
  if (userData.location) {
    locationInfo = `📍 *Location:* ${userData.location.latitude}, ${userData.location.longitude}\n`;
    if (userData.manualLocation) {
      locationInfo += `🏙️ *Description:* ${userData.manualLocation}\n`;
    }
  } else if (userData.manualLocation) {
    locationInfo = `🏙️ *Location:* ${userData.manualLocation}\n`;
  }
  
  bot.sendMessage(
    chatId,
    `📋 *Your data has been received*\n\n` +
    `👤 *Name:* ${userData.name}\n` +
    `📱 *Phone:* ${userData.phoneNumber}\n` +
    `${locationInfo}\n` +
    `Do you want to confirm?`,
    {
      parse_mode: 'Markdown',
      reply_markup: {
        inline_keyboard: [
          [
            { text: '✅ Confirm', callback_data: 'confirm_data' },
            { text: '✏️ Edit', callback_data: 'edit_data' }
          ]
        ],
        remove_keyboard: true
      }
    }
  );
}

// Helper function to show updated data
function showUpdatedData(chatId, userId) {
  const userData = userSessions[userId].data;
  
  userSessions[userId].state = STATE.AWAITING_CONFIRMATION;
  
  let locationInfo = '';
  if (userData.location) {
    locationInfo = `📍 *Location:* ${userData.location.latitude}, ${userData.location.longitude}\n`;
    if (userData.manualLocation) {
      locationInfo += `🏙️ *Description:* ${userData.manualLocation}\n`;
    }
  } else if (userData.manualLocation) {
    locationInfo = `🏙️ *Location:* ${userData.manualLocation}\n`;
  }
  
  bot.sendMessage(
    chatId,
    `📋 *Updated information*\n\n` +
    `👤 *Name:* ${userData.name}\n` +
    `📱 *Phone:* ${userData.phoneNumber}\n` +
    `${locationInfo}\n` +
    `Do you want to confirm?`,
    {
      parse_mode: 'Markdown',
      reply_markup: {
        inline_keyboard: [
          [
            { text: '✅ Confirm', callback_data: 'confirm_data' },
            { text: '✏️ Edit', callback_data: 'edit_data' }
          ]
        ],
        remove_keyboard: true
      }
    }
  );
}

// Log errors
bot.on('polling_error', (error) => {
  console.error('Polling error:', error);
});

console.log('Bot started successfully!');
