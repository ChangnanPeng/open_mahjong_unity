const express = require('express');
const { requireEventAdmin } = require('../../middleware/requireEventAdmin');
const { createWindowLimiter } = require('../../middleware/rateLimit');

const authRoutes = require('./auth');
const eventsRoutes = require('./events');
const eventExtrasRoutes = require('./announcements');

const router = express.Router();

const eventAdminLimiter = createWindowLimiter({
  windowMs: 60_000,
  max: 120,
  keyFn: (req) => `${req.ip || 'unknown'}:event-admin`,
});

router.use(eventAdminLimiter);

// 登录无需 JWT
router.use('/auth', authRoutes);

// 以下均需赛事主/子管理员 JWT
router.use(requireEventAdmin);
router.use('/events', eventsRoutes);
router.use('/events/:eventId', eventExtrasRoutes);

module.exports = router;
