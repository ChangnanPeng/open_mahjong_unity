export const ratio = (n, d, suffix = '%') =>
  (!d || d <= 0 ? '0.00' + suffix : ((n / d) * 100).toFixed(2) + suffix);

/** 最大余数法：将 counts 分配为总和恰好 100 的整数百分比 */
export function distributeIntegerPercents(counts, total) {
  if (!total || total <= 0) return counts.map(() => 0);
  const exact = counts.map((c) => (c / total) * 100);
  const floors = exact.map((v) => Math.floor(v));
  let remainder = 100 - floors.reduce((a, b) => a + b, 0);
  const order = exact
    .map((v, i) => ({ i, rem: v - floors[i] }))
    .sort((a, b) => b.rem - a.rem || a.i - b.i);
  const result = [...floors];
  for (let k = 0; k < remainder; k++) {
    result[order[k].i] += 1;
  }
  return result;
}

/** 玩家个人副露率：副露小局数 / 该玩家总小局数 */
export const playerFuluRate = (fuluCount, totalRounds) =>
  ratio(fuluCount, totalRounds);

/** 平台全站副露率：四人席累加后除以总小局数×4 */
export const platformFuluRate = (fuluCount, totalRounds) =>
  ratio(fuluCount, (Number(totalRounds) || 0) * 4);

export const avg = (n, d) =>
  (d === undefined || !d || d <= 0 ? '0.00' : (n / d).toFixed(2));

export const avgRank = (s) => {
  const games = s.total_games || 0;
  if (!games) return '0.00';
  const weighted = (s.first_place_count || 0) * 1
    + (s.second_place_count || 0) * 2
    + (s.third_place_count || 0) * 3
    + (s.fourth_place_count || 0) * 4;
  return (weighted / games).toFixed(2);
};

function buildStatsRowsBase(s, fuluRateFn) {
  return [
    { label: '总对局', value: String(s.total_games || 0) },
    { label: '总回合', value: String(s.total_rounds || 0) },
    { label: '平均顺位', value: avgRank(s) },
    { label: '局均点', value: avg(s.total_round_score, s.total_games) },
    { label: '一位率', value: ratio(s.first_place_count, s.total_games) },
    { label: '二位率', value: ratio(s.second_place_count, s.total_games) },
    { label: '三位率', value: ratio(s.third_place_count, s.total_games) },
    { label: '四位率', value: ratio(s.fourth_place_count, s.total_games) },
    { label: '和牌率', value: ratio(s.win_count, s.total_rounds) },
    { label: '自摸率', value: ratio(s.self_draw_count, s.win_count) },
    { label: '放铳率', value: ratio(s.deal_in_count, s.total_rounds) },
    { label: '错和率', value: ratio(s.cuohe_count, s.total_rounds) },
    { label: '副露率', value: fuluRateFn(s.fulu_round_count, s.total_rounds) },
    { label: '平均和番', value: avg(s.total_fan_score, s.win_count) },
    { label: '平均和巡', value: avg(s.total_win_turn, s.win_count) },
    { label: '平均铳番', value: avg(s.total_fangchong_score, s.deal_in_count) },
  ];
}

/** 玩家个人统计（PlayerData） */
export const buildPlayerStatsRows = (s) => buildStatsRowsBase(s, playerFuluRate);

/** 平台全站聚合统计（管理后台 / 平台数据页） */
export const buildPlatformStatsRows = (s) => buildStatsRowsBase(s, platformFuluRate);

export function buildAllFanEntries(fans, fanDict) {
  const dict = fanDict || {};
  return Object.keys(dict)
    .map((key) => ({
      key,
      label: dict[key] || key,
      count: Number(fans?.[key]) || 0,
    }))
    .sort((a, b) => b.count - a.count || a.label.localeCompare(b.label, 'zh-CN'));
}

export const TIER_CHART_COLORS = {
  beginner: '#409eff',
  intermediate: '#67c23a',
  advanced: '#e6a23c',
  mcrpl: '#f56c6c',
};

export function buildSceneDailyChartOption(rows, { tierOptions, tierLabel, selectedTier = null }) {
  const byDate = {};
  for (const row of rows) {
    const d = row.stat_date;
    const t = row.match_tier;
    if (!byDate[d]) byDate[d] = {};
    byDate[d][t] = (byDate[d][t] || 0) + (Number(row.total_games) || 0);
  }
  const dates = Object.keys(byDate).sort();
  const tiers = selectedTier ? [selectedTier] : tierOptions.map((t) => t.value);
  const chartBottom = dates.length > 14 ? 88 : 72;
  return {
    tooltip: { trigger: 'axis' },
    legend: {
      data: tiers.map((t) => tierLabel[t] || t),
      bottom: 4,
      itemGap: 16,
    },
    grid: { left: 48, right: 24, top: 28, bottom: chartBottom, containLabel: true },
    xAxis: {
      type: 'category',
      data: dates,
      axisLabel: { rotate: dates.length > 14 ? 35 : 0, margin: 16 },
      axisTick: { alignWithLabel: true },
    },
    yAxis: { type: 'value', minInterval: 1 },
    series: tiers.map((t) => ({
      name: tierLabel[t] || t,
      type: 'line',
      smooth: true,
      data: dates.map((d) => byDate[d]?.[t] || 0),
      itemStyle: { color: TIER_CHART_COLORS[t] },
    })),
  };
}

export function buildSceneDailyTable(rows, tierOptions, tierLabel) {
  const byDate = {};
  for (const row of rows) {
    const d = row.stat_date;
    if (!byDate[d]) {
      byDate[d] = { stat_date: d };
      for (const t of tierOptions) byDate[d][t.value] = 0;
    }
    byDate[d][row.match_tier] = (byDate[d][row.match_tier] || 0) + (Number(row.total_games) || 0);
  }
  return Object.values(byDate).sort((a, b) => (a.stat_date < b.stat_date ? 1 : -1));
}
