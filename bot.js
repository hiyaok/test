// Import required libraries
const { Telegraf, Scenes, session, Markup } = require('telegraf');
const fs = require('fs');
const path = require('path');
const ExcelJS = require('exceljs');

// Initialize bot with your token
const bot = new Telegraf('7631108529:AAGYAFr7a6eunVchHrO-G7Tl1v4yDRRXNbM');

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
    admins = [5522120462]; // Replace with your Telegram user ID
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

// User registration wizard
const registrationWizard = new Scenes.WizardScene(
  'REGISTRATION_WIZARD',
  // Step 1: Ask for name
  async (ctx) => {
    await ctx.reply('🌟 *Welcome to our bot!* 🌟\n\nPlease enter your first and last name:', {
      parse_mode: 'Markdown'
    });
    return ctx.wizard.next();
  },
  // Step 2: Ask for phone number
  async (ctx) => {
    const name = ctx.message.text;
    ctx.wizard.state.name = name;
    
    await ctx.reply('📱 Please share your phone number:', {
      reply_markup: Markup.keyboard([
        Markup.button.contactRequest('📲 Share my phone number')
      ]).oneTime().resize()
    });
    return ctx.wizard.next();
  },
  // Step 3: Ask for place of residence
  async (ctx) => {
    let phoneNumber;
    
    if (ctx.message.contact) {
      phoneNumber = ctx.message.contact.phone_number;
    } else {
      phoneNumber = ctx.message.text;
    }
    
    ctx.wizard.state.phoneNumber = phoneNumber;
    
    await ctx.reply('🏙️ Please enter your place of residence:', {
      reply_markup: Markup.removeKeyboard()
    });
    return ctx.wizard.next();
  },
  // Step 4: Confirm data
  async (ctx) => {
    const residence = ctx.message.text;
    ctx.wizard.state.residence = residence;
    
    const userData = {
      name: ctx.wizard.state.name,
      phoneNumber: ctx.wizard.state.phoneNumber,
      residence: residence,
      registeredAt: new Date().toISOString(),
      chatId: ctx.chat.id
    };
    
    ctx.wizard.state.userData = userData;
    
    await ctx.reply(
      `📋 *Your data has been received*\n\n` +
      `👤 *Name:* ${userData.name}\n` +
      `📱 *Phone:* ${userData.phoneNumber}\n` +
      `🏙️ *Residence:* ${userData.residence}\n\n` +
      `Do you want to confirm?`,
      {
        parse_mode: 'Markdown',
        reply_markup: Markup.inlineKeyboard([
          Markup.button.callback('✅ Confirm', 'confirm_data'),
          Markup.button.callback('✏️ Edit', 'edit_data')
        ])
      }
    );
    return ctx.wizard.next();
  },
  // Step 5: Handle confirmation or edit
  async (ctx) => {
    // This step is handled by callbacks
    return;
  }
);

// Handle callbacks for data confirmation or editing
registrationWizard.action('confirm_data', async (ctx) => {
  const userId = ctx.from.id.toString();
  users[userId] = ctx.wizard.state.userData;
  saveUsers();
  
  await ctx.editMessageText(
    `✨ *Thank you!* ✨\n\nYour data has been received and saved successfully.`,
    { parse_mode: 'Markdown' }
  );
  return ctx.scene.leave();
});

registrationWizard.action('edit_data', async (ctx) => {
  await ctx.reply('🔄 Let\'s update your information. What would you like to edit?', {
    reply_markup: Markup.inlineKeyboard([
      [Markup.button.callback('👤 Name', 'edit_name')],
      [Markup.button.callback('📱 Phone Number', 'edit_phone')],
      [Markup.button.callback('🏙️ Residence', 'edit_residence')]
    ])
  });
});

// Handle edit callbacks
registrationWizard.action('edit_name', async (ctx) => {
  ctx.wizard.state.editing = 'name';
  await ctx.reply('👤 Please enter your new name:');
});

registrationWizard.action('edit_phone', async (ctx) => {
  ctx.wizard.state.editing = 'phone';
  await ctx.reply('📱 Please enter your new phone number:', {
    reply_markup: Markup.keyboard([
      Markup.button.contactRequest('📲 Share my phone number')
    ]).oneTime().resize()
  });
});

registrationWizard.action('edit_residence', async (ctx) => {
  ctx.wizard.state.editing = 'residence';
  await ctx.reply('🏙️ Please enter your new place of residence:');
});

// Handle text and contact messages for editing
registrationWizard.on('text', async (ctx) => {
  const editing = ctx.wizard.state.editing;
  
  if (!editing) return;
  
  if (editing === 'name') {
    ctx.wizard.state.userData.name = ctx.message.text;
  } else if (editing === 'residence') {
    ctx.wizard.state.userData.residence = ctx.message.text;
  } else if (editing === 'phone') {
    ctx.wizard.state.userData.phoneNumber = ctx.message.text;
  }
  
  // Show updated data
  await showUpdatedData(ctx);
});

registrationWizard.on('contact', async (ctx) => {
  if (ctx.wizard.state.editing === 'phone') {
    ctx.wizard.state.userData.phoneNumber = ctx.message.contact.phone_number;
    await showUpdatedData(ctx);
  }
});

// Helper function to show updated data
async function showUpdatedData(ctx) {
  const userData = ctx.wizard.state.userData;
  
  await ctx.reply(
    `📋 *Updated information*\n\n` +
    `👤 *Name:* ${userData.name}\n` +
    `📱 *Phone:* ${userData.phoneNumber}\n` +
    `🏙️ *Residence:* ${userData.residence}\n\n` +
    `Do you want to confirm?`,
    {
      parse_mode: 'Markdown',
      reply_markup: Markup.inlineKeyboard([
        Markup.button.callback('✅ Confirm', 'confirm_data'),
        Markup.button.callback('✏️ Edit', 'edit_data')
      ])
    }
  );
  
  ctx.wizard.state.editing = null;
}

// Create scene manager
const stage = new Scenes.Stage([registrationWizard]);

// Register middleware
bot.use(session());
bot.use(stage.middleware());

// Start command
bot.start(async (ctx) => {
  const userId = ctx.from.id.toString();
  
  // Check if user is already registered
  if (users[userId]) {
    await ctx.reply(
      `👋 *Welcome back, ${users[userId].name}!*\n\nYour information is already registered with us.`,
      { 
        parse_mode: 'Markdown',
        reply_markup: Markup.inlineKeyboard([
          Markup.button.callback('✏️ Update My Information', 'update_info')
        ])
      }
    );
  } else {
    // Start registration wizard
    await ctx.scene.enter('REGISTRATION_WIZARD');
  }
});

// Handle update info button
bot.action('update_info', async (ctx) => {
  await ctx.scene.enter('REGISTRATION_WIZARD');
});

// Admin Commands
bot.command('admin', async (ctx) => {
  const userId = ctx.from.id;
  
  if (!isAdmin(userId)) {
    return ctx.reply('⛔ You are not authorized to access the admin panel.');
  }
  
  await ctx.reply(
    '👑 *Admin Panel*\n\nSelect an option:',
    {
      parse_mode: 'Markdown',
      reply_markup: Markup.inlineKeyboard([
        [Markup.button.callback('👥 View Users', 'admin_view_users')],
        [Markup.button.callback('📊 View Users as Excel', 'admin_download_excel')],
        [Markup.button.callback('📣 Send Advertisement', 'admin_send_ad')]
      ])
    }
  );
});

// Handle admin view users
bot.action('admin_view_users', async (ctx) => {
  if (!isAdmin(ctx.from.id)) return;
  
  const userCount = Object.keys(users).length;
  
  if (userCount === 0) {
    return ctx.reply('📊 *User Statistics*\n\nNo users have registered yet.', {
      parse_mode: 'Markdown'
    });
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
  
  await ctx.reply(userList, {
    parse_mode: 'Markdown',
    reply_markup: Markup.inlineKeyboard([
      Markup.button.callback('⬅️ Back to Admin Panel', 'back_to_admin')
    ])
  });
});

// Generate Excel file with users
bot.action('admin_download_excel', async (ctx) => {
  if (!isAdmin(ctx.from.id)) return;
  
  const userCount = Object.keys(users).length;
  
  if (userCount === 0) {
    return ctx.reply('📊 *User Statistics*\n\nNo users have registered yet.', {
      parse_mode: 'Markdown'
    });
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
  await ctx.replyWithDocument({ source: excelFileName, filename: 'users.xlsx' });
  
  // Remove file after sending
  setTimeout(() => {
    try {
      fs.unlinkSync(excelFileName);
    } catch (error) {
      console.error('Error removing Excel file:', error);
    }
  }, 5000);
});

// Handle admin send ad
bot.action('admin_send_ad', async (ctx) => {
  if (!isAdmin(ctx.from.id)) return;
  
  await ctx.reply(
    '📣 *Send Advertisement*\n\nPlease enter the advertisement text you want to send to all users:',
    {
      parse_mode: 'Markdown',
      reply_markup: Markup.inlineKeyboard([
        Markup.button.callback('⬅️ Cancel', 'back_to_admin')
      ])
    }
  );
  
  // Set state for next message
  bot.context.adminSendingAd = true;
});

// Handle back to admin
bot.action('back_to_admin', async (ctx) => {
  if (!isAdmin(ctx.from.id)) return;
  
  bot.context.adminSendingAd = false;
  
  await ctx.reply(
    '👑 *Admin Panel*\n\nSelect an option:',
    {
      parse_mode: 'Markdown',
      reply_markup: Markup.inlineKeyboard([
        [Markup.button.callback('👥 View Users', 'admin_view_users')],
        [Markup.button.callback('📊 View Users as Excel', 'admin_download_excel')],
        [Markup.button.callback('📣 Send Advertisement', 'admin_send_ad')]
      ])
    }
  );
});

// Handle ad text
bot.on('text', async (ctx) => {
  // Skip if it's a command
  if (ctx.message.text.startsWith('/')) return;
  
  // If admin is sending an ad
  if (isAdmin(ctx.from.id) && bot.context.adminSendingAd) {
    bot.context.adminSendingAd = false;
    const adText = ctx.message.text;
    
    // Confirmation before sending
    await ctx.reply(
      `📣 *Advertisement Preview*\n\n${adText}\n\nDo you want to send this advertisement to all users?`,
      {
        parse_mode: 'Markdown',
        reply_markup: Markup.inlineKeyboard([
          Markup.button.callback('✅ Send Now', `send_ad:${Buffer.from(adText).toString('base64')}`),
          Markup.button.callback('⬅️ Cancel', 'back_to_admin')
        ])
      }
    );
  }
});

// Handle send ad confirmation
bot.action(/send_ad:(.+)/, async (ctx) => {
  if (!isAdmin(ctx.from.id)) return;
  
  const adText = Buffer.from(ctx.match[1], 'base64').toString();
  const statusMessage = await ctx.reply('📣 *Sending advertisement...*', {
    parse_mode: 'Markdown'
  });
  
  let sentCount = 0;
  let failedCount = 0;
  const userIds = Object.keys(users);
  
  for (const userId of userIds) {
    try {
      await bot.telegram.sendMessage(
        users[userId].chatId,
        `📢 *ANNOUNCEMENT*\n\n${adText}`,
        { parse_mode: 'Markdown' }
      );
      sentCount++;
      
      // Update status every 10 users
      if (sentCount % 10 === 0 || sentCount + failedCount === userIds.length) {
        await bot.telegram.editMessageText(
          ctx.chat.id,
          statusMessage.message_id,
          null,
          `📣 *Sending advertisement...*\n\nProgress: ${sentCount + failedCount}/${userIds.length}`,
          { parse_mode: 'Markdown' }
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
  await bot.telegram.editMessageText(
    ctx.chat.id,
    statusMessage.message_id,
    null,
    `📣 *Advertisement Status*\n\n` +
    `✅ Successfully sent to: ${sentCount} users\n` +
    `❌ Failed to send to: ${failedCount} users\n\n` +
    `Total Users: ${userIds.length}`,
    {
      parse_mode: 'Markdown',
      reply_markup: Markup.inlineKeyboard([
        Markup.button.callback('⬅️ Back to Admin Panel', 'back_to_admin')
      ])
    }
  );
});

// Handle unknown commands
bot.on('text', (ctx) => {
  // If message doesn't start with a command and user isn't in a scene
  if (!ctx.message.text.startsWith('/') && !ctx.session.__scenes.current) {
    ctx.reply(
      '❓ *I didn\'t understand that command*\n\nPlease use /start to begin or /admin for admin panel.',
      { parse_mode: 'Markdown' }
    );
  }
});

// Error handler
bot.catch((err, ctx) => {
  console.error(`Error for ${ctx.updateType}:`, err);
  ctx.reply('❌ An error occurred while processing your request. Please try again later.');
});

// Start bot
bot.launch().then(() => {
  console.log('Bot started successfully!');
}).catch(err => {
  console.error('Failed to start bot:', err);
});

// Tambahkan setelah bot.use(stage.middleware())
bot.use((ctx, next) => {
  console.log('Bot menerima pesan/aksi:', ctx.update);
  return next();
});

// Enable graceful stop
process.once('SIGINT', () => bot.stop('SIGINT'));
process.once('SIGTERM', () => bot.stop('SIGTERM'));
