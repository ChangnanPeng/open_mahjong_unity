using System.Collections.Generic;

/// <summary>
/// 多家和牌终局的共享计分板聚合：四川和简单均可复用，规则差异只体现在最终行标签。
/// </summary>
public partial class NormalGameStateManager {
    private Dictionary<int, int> _winnerSequenceScoreAccum;
    private int _winnerSequenceHuCount;
    private bool _winnerSequenceHadChajiao;

    public void ResetWinnerSequenceScoreAccum() {
        _winnerSequenceScoreAccum = null;
        _winnerSequenceHuCount = 0;
        _winnerSequenceHadChajiao = false;
    }

    public void BeginWinnerSequenceScoreAccum() {
        _winnerSequenceScoreAccum = new Dictionary<int, int>();
        _winnerSequenceHuCount = 0;
        _winnerSequenceHadChajiao = false;
    }

    public void AccumulateWinnerSequenceScore(Dictionary<int, int> deltas) {
        if (deltas == null || deltas.Count == 0) return;
        _winnerSequenceScoreAccum ??= new Dictionary<int, int>();
        foreach (var kvp in deltas) {
            if (!_winnerSequenceScoreAccum.ContainsKey(kvp.Key)) {
                _winnerSequenceScoreAccum[kvp.Key] = 0;
            }
            _winnerSequenceScoreAccum[kvp.Key] += kvp.Value;
        }
    }

    public void RecordWinnerSequenceHu() {
        _winnerSequenceScoreAccum ??= new Dictionary<int, int>();
        _winnerSequenceHuCount++;
    }

    public void MarkWinnerSequenceChajiaoStep() {
        _winnerSequenceHadChajiao = true;
    }

    /// <summary>终局末步：将累积的分差写入计分板；简单主番显示实际和牌人数。</summary>
    public bool TryFlushWinnerSequenceScoreToHistory() {
        if (_winnerSequenceScoreAccum == null) return false;
        var merged = new Dictionary<int, int>(_winnerSequenceScoreAccum);
        RoundSettlementSnapshot snapshot;
        if (IsJiandan()) {
            snapshot = ScoreHistorySettlementHelper.CreateJiandanScoreboardSnapshot(
                ScoreHistorySettlementHelper.ResolveSubRule(roomRule, subRule),
                _winnerSequenceHuCount);
        } else {
            string roundLabel = ScoreHistorySettlementHelper.ResolveSichuanEndgameRoundLabel(
                _winnerSequenceHuCount, _winnerSequenceHadChajiao);
            snapshot = ScoreHistorySettlementHelper.CreateSichuanScoreboardSnapshot(subRule, roundLabel);
        }
        roundSettlementHistory.Add(snapshot);
        ApplyLocalScoreHistoryFromSettlement(snapshot, merged);
        ResetWinnerSequenceScoreAccum();
        return true;
    }

    public bool IsWinnerSequenceScoreStep(string liujuStep) {
        return liujuStep == "reveal_hu" || liujuStep == "settle_hu" || liujuStep == "chajiao";
    }
}
