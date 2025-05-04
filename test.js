// Versi bot sederhana untuk testing
const { Telegraf } = require('telegraf');
const bot = new Telegraf('7631108529:AAGYAFr7a6eunVchHrO-G7Tl1v4yDRRXNbM'); // Ganti dengan token asli

bot.start((ctx) => {
  console.log('Menerima perintah start');
  ctx.reply('Bot berjalan dengan baik! Ini pesan test.');
});

bot.launch().then(() => {
  console.log('Bot started successfully!');
}).catch(err => {
  console.error('Failed to start bot:', err);
});
