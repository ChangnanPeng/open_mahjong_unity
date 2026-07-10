const express = require('express');
const { requireBotApi } = require('../../middleware/requireBotApi');
const { createWindowLimiter, getClientIp } = require('../../middleware/rateLimit');
const playerRoutes = require('./player');

const router = express.Router();

const botApiLimiter = createWindowLimiter({
  windowMs: 60_000,
  max: 120,
  keyFn: (req) => {
    const botName = req.botApi?.botName;
    return botName ? `botapi:${botName}` : `${getClientIp(req)}:botapi`;
  },
  countSuccessfulOnly: true,
});

router.use(requireBotApi);
router.use(botApiLimiter);
router.use('/player', playerRoutes);

module.exports = router;
