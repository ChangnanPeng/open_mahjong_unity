const express = require('express');
const router = express.Router();
const pool = require('../../config/database');
const {
  LADDER_TIERS,
  formatStatDate,
  mapTotalsRow,
  querySceneTotals,
  querySceneTotalsFans,
  querySceneDailyGames,
  fillFanByTier,
} = require('../../services/platformStats');

function mapDailyRow(row) {
  return {
    stat_date: formatStatDate(row.stat_date),
    game_count: Number(row.game_count) || 0,
    dau: Number(row.dau) || 0,
    active_users: Number(row.active_users) || 0,
    max_online: Number(row.max_online) || 0,
  };
}

function parseDateParam(val) {
  if (!val || typeof val !== 'string') return null;
  return /^\d{4}-\d{2}-\d{2}$/.test(val) ? val : null;
}

function defaultDateRange(days) {
  const to = new Date();
  const from = new Date();
  from.setDate(from.getDate() - (days - 1));
  return {
    date_from: formatStatDate(from),
    date_to: formatStatDate(to),
  };
}

router.get('/daily', async (req, res) => {
  try {
    const granularity = ['day', 'week', 'month'].includes(req.query.granularity)
      ? req.query.granularity
      : 'day';
    const days = Math.min(365, Math.max(1, parseInt(req.query.days, 10) || 30));
    let dateFrom = parseDateParam(req.query.date_from);
    let dateTo = parseDateParam(req.query.date_to);
    if (!dateFrom || !dateTo) {
      const defaults = defaultDateRange(days);
      dateFrom = dateFrom || defaults.date_from;
      dateTo = dateTo || defaults.date_to;
    }

    let sql;
    const params = [dateFrom, dateTo];
    if (granularity === 'day') {
      sql = `
        SELECT stat_date, game_count, dau, active_users, max_online
        FROM daily_stats
        WHERE stat_date >= $1::date AND stat_date <= $2::date
        ORDER BY stat_date ASC
      `;
    } else {
      const trunc = granularity === 'week' ? 'week' : 'month';
      sql = `
        SELECT
          date_trunc('${trunc}', stat_date)::date AS stat_date,
          SUM(game_count)::int AS game_count,
          SUM(dau)::int AS dau,
          SUM(active_users)::int AS active_users,
          MAX(max_online)::int AS max_online
        FROM daily_stats
        WHERE stat_date >= $1::date AND stat_date <= $2::date
        GROUP BY 1
        ORDER BY stat_date ASC
      `;
    }

    const result = await pool.query(sql, params);
    res.json({
      success: true,
      data: result.rows.map(mapDailyRow),
      meta: { date_from: dateFrom, date_to: dateTo, granularity },
    });
  } catch (error) {
    console.error('admin stats daily error:', error);
    res.status(500).json({ success: false, message: '服务器内部错误' });
  }
});

router.get('/scene/daily', async (req, res) => {
  try {
    const days = Math.min(365, Math.max(1, parseInt(req.query.days, 10) || 30));
    let dateFrom = parseDateParam(req.query.date_from);
    let dateTo = parseDateParam(req.query.date_to);
    if (!dateFrom || !dateTo) {
      const defaults = defaultDateRange(days);
      dateFrom = dateFrom || defaults.date_from;
      dateTo = dateTo || defaults.date_to;
    }
    const data = await querySceneDailyGames({
      dateFrom,
      dateTo,
      tier: req.query.tier,
      gameType: req.query.game_type,
      rule: req.query.rule,
    });
    res.json({
      success: true,
      data,
      meta: { date_from: dateFrom, date_to: dateTo },
    });
  } catch (error) {
    console.error('admin stats scene daily error:', error);
    res.status(500).json({ success: false, message: '服务器内部错误' });
  }
});

router.get('/scene/totals', async (req, res) => {
  try {
    const data = await querySceneTotals({
      tier: req.query.tier,
      gameType: req.query.game_type,
      rule: req.query.rule,
      detail: req.query.detail,
    });
    res.json({ success: true, data });
  } catch (error) {
    console.error('admin stats scene totals error:', error);
    res.status(500).json({ success: false, message: '服务器内部错误' });
  }
});

router.get('/scene/totals/fans', async (req, res) => {
  try {
    const data = await querySceneTotalsFans({
      tier: req.query.tier,
      rule: req.query.rule,
    });
    res.json({ success: true, data });
  } catch (error) {
    console.error('admin stats scene totals fans error:', error);
    res.status(500).json({ success: false, message: '服务器内部错误' });
  }
});

module.exports = router;
