#!/usr/bin/env node
/**
 * 签发 Bot API JWT，供站点管理员分发给 QQ 机器人开发者。
 *
 * 用法（在 open_mahjong_web 目录下）：
 *   node scripts/issue-bot-token.js [bot_name] [expires_sec]
 *
 * expires_sec 可选；省略则签发永不过期令牌。
 */
require('dotenv').config({ path: require('path').join(__dirname, '..', '.env') });

const { signToken } = require('../server/utils/jwt');

const secret = process.env.BOT_API_JWT_SECRET;
if (!secret || !String(secret).trim()) {
  console.error('错误: 未设置 BOT_API_JWT_SECRET');
  process.exit(1);
}

const botName = process.argv[2] || 'qq-bot';
const expiresArg = process.argv[3];
let expiresSec = null;
if (expiresArg != null && String(expiresArg).trim() !== '') {
  expiresSec = parseInt(expiresArg, 10);
  if (Number.isNaN(expiresSec) || expiresSec <= 0) {
    console.error('错误: expires_sec 必须是正整数');
    process.exit(1);
  }
}

const token = signToken(
  {
    aud: 'botapi',
    bot_name: botName,
    iat: Math.floor(Date.now() / 1000),
  },
  String(secret).trim(),
  expiresSec
);

console.log(`Bot 名称: ${botName}`);
console.log(expiresSec ? `有效期: ${expiresSec} 秒` : '有效期: 无（永不过期）');
console.log('');
console.log(token);
