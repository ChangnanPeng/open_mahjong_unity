const pool = require('../config/database');
const { GUOBIAO_FAN_KEYS } = require('../constants/guobiaoFanDict');

const LADDER_TIERS = ['beginner', 'intermediate', 'advanced', 'mcrpl'];
const STAT_DATE_EXPR = "((created_at AT TIME ZONE 'Asia/Shanghai') - interval '4 hours')::date";

const SCENE_METRIC_SUMS = `
  COUNT(*)::int AS total_games,
  SUM(per_game_rounds)::int AS total_rounds,
  SUM(win_count)::int AS win_count,
  SUM(self_draw_count)::int AS self_draw_count,
  SUM(deal_in_count)::int AS deal_in_count,
  SUM(total_fan_score)::int AS total_fan_score,
  SUM(total_win_turn)::int AS total_win_turn,
  SUM(total_fangchong_score)::int AS total_fangchong_score,
  SUM(first_place_count)::int AS first_place_count,
  SUM(second_place_count)::int AS second_place_count,
  SUM(third_place_count)::int AS third_place_count,
  SUM(fourth_place_count)::int AS fourth_place_count,
  SUM(fulu_round_count)::int AS fulu_round_count,
  SUM(cuohe_count)::int AS cuohe_count,
  SUM(total_round_score)::int AS total_round_score
`;

function formatStatDate(val) {
  if (val == null) return null;
  if (typeof val === 'string') return val.slice(0, 10);
  if (val instanceof Date) {
    const y = val.getFullYear();
    const m = String(val.getMonth() + 1).padStart(2, '0');
    const d = String(val.getDate()).padStart(2, '0');
    return `${y}-${m}-${d}`;
  }
  return String(val).slice(0, 10);
}

function mapTotalsRow(row) {
  const out = { match_tier: row.match_tier };
  if (row.rule != null) out.rule = row.rule;
  if (row.game_type != null) out.game_type = row.game_type;
  for (const k of [
    'total_games', 'total_rounds', 'win_count', 'self_draw_count', 'deal_in_count',
    'total_fan_score', 'total_win_turn', 'total_fangchong_score',
    'first_place_count', 'second_place_count', 'third_place_count', 'fourth_place_count',
    'fulu_round_count', 'cuohe_count', 'total_round_score',
  ]) {
    out[k] = Number(row[k]) || 0;
  }
  return out;
}

function buildSceneTotalsQuery(groupByTierOnly, extraWhere, params) {
  const tierPlaceholders = LADDER_TIERS.map((_, i) => `$${i + 1}`).join(', ');
  const innerWhere = [
    "room_type = 'match'",
    `match_tier IN (${tierPlaceholders})`,
    ...extraWhere,
  ];
  const inner = `
    SELECT game_id, room_type, match_tier, event_id, rule, game_type,
           MAX(total_rounds) AS per_game_rounds,
           SUM(win_count) AS win_count,
           SUM(self_draw_count) AS self_draw_count,
           SUM(deal_in_count) AS deal_in_count,
           SUM(total_fan_score) AS total_fan_score,
           SUM(total_win_turn) AS total_win_turn,
           SUM(total_fangchong_score) AS total_fangchong_score,
           SUM(first_place_count) AS first_place_count,
           SUM(second_place_count) AS second_place_count,
           SUM(third_place_count) AS third_place_count,
           SUM(fourth_place_count) AS fourth_place_count,
           SUM(fulu_round_count) AS fulu_round_count,
           SUM(cuohe_count) AS cuohe_count,
           SUM(total_round_score) AS total_round_score
    FROM game_player_metrics
    WHERE ${innerWhere.join(' AND ')}
    GROUP BY game_id, room_type, match_tier, event_id, rule, game_type
  `;
  if (groupByTierOnly) {
    return {
      sql: `
        SELECT match_tier, ${SCENE_METRIC_SUMS}
        FROM (${inner}) g
        GROUP BY match_tier
        ORDER BY array_position(ARRAY['beginner','intermediate','advanced','mcrpl']::varchar[], match_tier)
      `,
      params,
    };
  }
  return {
    sql: `
      SELECT match_tier, rule, game_type, ${SCENE_METRIC_SUMS}
      FROM (${inner}) g
      GROUP BY match_tier, rule, game_type
      ORDER BY match_tier, rule, game_type
    `,
    params,
  };
}

async function getAsOfStatDate() {
  const result = await pool.query('SELECT MAX(stat_date) AS as_of FROM daily_stats');
  return formatStatDate(result.rows[0]?.as_of);
}

async function querySceneTotals({ asOfDate, tier, gameType, rule, detail } = {}) {
  const extraWhere = [];
  const params = [...LADDER_TIERS];
  if (asOfDate) {
    params.push(asOfDate);
    extraWhere.push(`${STAT_DATE_EXPR} <= $${params.length}::date`);
  }
  if (tier && LADDER_TIERS.includes(tier)) {
    params.push(tier);
    extraWhere.push(`match_tier = $${params.length}`);
  }
  if (gameType) {
    params.push(gameType);
    extraWhere.push(`game_type = $${params.length}`);
  }
  if (rule) {
    params.push(rule);
    extraWhere.push(`rule = $${params.length}`);
  }
  const groupByTierOnly = detail !== '1';
  const { sql, params: queryParams } = buildSceneTotalsQuery(groupByTierOnly, extraWhere, params);
  const result = await pool.query(sql, queryParams);
  return result.rows.map(mapTotalsRow);
}

function fillFanByTier(rawByTier) {
  const byTier = {};
  for (const tier of LADDER_TIERS) {
    byTier[tier] = {};
    for (const key of GUOBIAO_FAN_KEYS) {
      byTier[tier][key] = Number(rawByTier[tier]?.[key]) || 0;
    }
  }
  return byTier;
}

async function querySceneTotalsFans({ asOfDate, tier, rule } = {}) {
  const where = [`match_tier IN (${LADDER_TIERS.map((_, i) => `$${i + 1}`).join(', ')})`];
  const params = [...LADDER_TIERS];
  if (asOfDate) {
    params.push(asOfDate);
    where.push(`stat_date <= $${params.length}::date`);
  }
  if (tier && LADDER_TIERS.includes(tier)) {
    params.push(tier);
    where.push(`match_tier = $${params.length}`);
  }
  if (rule) {
    params.push(rule);
    where.push(`rule = $${params.length}`);
  } else {
    where.push("rule = 'guobiao'");
  }
  const result = await pool.query(
    `SELECT match_tier, fan_field, SUM(fan_count)::int AS fan_count
     FROM scene_tier_fan_daily
     WHERE ${where.join(' AND ')}
     GROUP BY match_tier, fan_field
     ORDER BY match_tier, fan_count DESC`,
    params
  );
  const rawByTier = {};
  for (const row of result.rows) {
    if (!rawByTier[row.match_tier]) rawByTier[row.match_tier] = {};
    rawByTier[row.match_tier][row.fan_field] = Number(row.fan_count) || 0;
  }
  return fillFanByTier(rawByTier);
}

async function querySceneDailyGames({ dateFrom, dateTo, asOfDate, tier, gameType, rule } = {}) {
  const where = [
    "room_type = 'match'",
    `match_tier IN (${LADDER_TIERS.map((_, i) => `$${i + 1}`).join(', ')})`,
  ];
  const params = [...LADDER_TIERS];
  if (dateFrom) {
    params.push(dateFrom);
    where.push(`stat_date >= $${params.length}::date`);
  }
  if (dateTo) {
    params.push(dateTo);
    where.push(`stat_date <= $${params.length}::date`);
  } else if (asOfDate) {
    params.push(asOfDate);
    where.push(`stat_date <= $${params.length}::date`);
  }
  if (tier && LADDER_TIERS.includes(tier)) {
    params.push(tier);
    where.push(`match_tier = $${params.length}`);
  }
  if (gameType) {
    params.push(gameType);
    where.push(`game_type = $${params.length}`);
  }
  if (rule) {
    params.push(rule);
    where.push(`rule = $${params.length}`);
  }
  const result = await pool.query(
    `SELECT stat_date, match_tier, SUM(total_games)::int AS total_games
     FROM scene_daily_stats
     WHERE ${where.join(' AND ')}
     GROUP BY stat_date, match_tier
     ORDER BY stat_date ASC, match_tier`,
    params
  );
  return result.rows.map((row) => ({
    stat_date: formatStatDate(row.stat_date),
    match_tier: row.match_tier,
    total_games: Number(row.total_games) || 0,
  }));
}

module.exports = {
  LADDER_TIERS,
  formatStatDate,
  mapTotalsRow,
  buildSceneTotalsQuery,
  getAsOfStatDate,
  querySceneTotals,
  querySceneTotalsFans,
  querySceneDailyGames,
  fillFanByTier,
  GUOBIAO_FAN_KEYS,
};
