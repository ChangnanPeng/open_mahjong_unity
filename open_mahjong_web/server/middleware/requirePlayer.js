const config = require('../config/config');
const { verifyToken } = require('../utils/jwt');

function requirePlayer(req, res, next) {
  const header = req.headers.authorization || '';
  const token = header.startsWith('Bearer ') ? header.slice(7) : null;
  if (!token) {
    return res.status(401).json({ success: false, message: '未登录或令牌无效' });
  }

  const payload = verifyToken(token, config.playerAuth.jwtSecret);
  if (!payload || !payload.user_id) {
    return res.status(401).json({ success: false, message: '登录已过期，请重新登录' });
  }
  if (payload.aud !== config.playerAuth.audience) {
    return res.status(401).json({ success: false, message: '令牌类型无效' });
  }

  req.player = {
    userId: Number(payload.user_id),
    username: payload.username || '',
  };
  return next();
}

module.exports = { requirePlayer };
