const express = require('express');
const router = express.Router();
const { requirePlayer } = require('../../middleware/requirePlayer');
const { listUserEvents } = require('../../utils/eventAdminHelpers');

router.get('/my-events', requirePlayer, async (req, res) => {
  try {
    const items = await listUserEvents(req.player.userId);
    res.json({ success: true, data: { items } });
  } catch (err) {
    console.error('player my-events:', err);
    res.status(500).json({ success: false, message: '服务器内部错误' });
  }
});

module.exports = router;
