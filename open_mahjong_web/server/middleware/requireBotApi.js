const config = require('../config/config');
const { verifyToken } = require('../utils/jwt');

function requireBotApi(req, res, next) {
  const header = req.headers.authorization || '';
  const token = header.startsWith('Bearer ') ? header.slice(7) : null;
  if (!token) {
    return res.status(401).json({ success: false, message: '缺少 Bot API 令牌' });
  }

  const payload = verifyToken(token, config.botApi.jwtSecret);
  if (!payload || payload.aud !== 'botapi') {
    return res.status(401).json({ success: false, message: 'Bot API 令牌无效或已过期' });
  }

  req.botApi = {
    botName: payload.bot_name || 'unknown',
    issuedAt: payload.iat || null,
  };
  return next();
}

module.exports = { requireBotApi };
