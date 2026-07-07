const express = require('express');
const {
  handlePlayerInfo,
  handlePlayerRecords,
  handlePlayerRankStats,
  handlePlayerRank,
} = require('../../services/playerQueryHandlers');

const router = express.Router();

router.get('/info/:key', handlePlayerInfo);
router.get('/records/:key', handlePlayerRecords);
router.get('/rank-stats/:key', handlePlayerRankStats);
router.get('/rank/:key', handlePlayerRank);

module.exports = router;
