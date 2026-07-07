/**
 * 管理后台等复用的玩家统计查询（实现见 playerPublicApi）
 */
const { fetchPlayerInfo } = require('./playerPublicApi');

async function fetchUserStatsBundle(userId) {
  const data = await fetchPlayerInfo(userId);
  if (!data) return null;
  return {
    guobiao_stats: data.guobiao_stats,
    riichi_stats: data.riichi_stats,
    qingque_stats: data.qingque_stats,
    classical_stats: data.classical_stats,
  };
}

module.exports = { fetchUserStatsBundle };
