/**
 * 固定时间窗内按 key 计数，超限返回 429。
 * @param {{
 *   windowMs: number,
 *   max: number,
 *   keyFn?: (req) => string,
 *   countSuccessfulOnly?: boolean,
 * }} opts
 * countSuccessfulOnly: 仅 2xx/3xx 响应计入配额（404 等失败不计）
 */
function getClientIp(req) {
  return req.ip || req.socket?.remoteAddress || 'unknown';
}

function createWindowLimiter(opts) {
  const {
    windowMs,
    max,
    keyFn = (req) => getClientIp(req),
    countSuccessfulOnly = false,
  } = opts;
  const buckets = new Map();

  function getBucket(key, now) {
    let b = buckets.get(key);
    if (!b || now >= b.resetAt) {
      b = { count: 0, resetAt: now + windowMs };
      buckets.set(key, b);
    }
    return b;
  }

  function rejectIfOverLimit(b, res, now) {
    if (b.count >= max) {
      const retrySec = Math.ceil((b.resetAt - now) / 1000);
      res.setHeader('Retry-After', String(Math.max(1, retrySec)));
      res.status(429).json({
        success: false,
        message: '请求过于频繁，请稍后再试',
      });
      return true;
    }
    return false;
  }

  return function rateLimitMiddleware(req, res, next) {
    const key = keyFn(req);
    const now = Date.now();
    const b = getBucket(key, now);

    if (countSuccessfulOnly) {
      if (rejectIfOverLimit(b, res, now)) return;
      res.on('finish', () => {
        const code = res.statusCode;
        if (code >= 200 && code < 400) {
          b.count += 1;
        }
      });
      return next();
    }

    b.count += 1;
    if (b.count > max) {
      const retrySec = Math.ceil((b.resetAt - now) / 1000);
      res.setHeader('Retry-After', String(Math.max(1, retrySec)));
      return res.status(429).json({
        success: false,
        message: '请求过于频繁，请稍后再试',
      });
    }
    next();
  };
}

module.exports = { createWindowLimiter, getClientIp };
