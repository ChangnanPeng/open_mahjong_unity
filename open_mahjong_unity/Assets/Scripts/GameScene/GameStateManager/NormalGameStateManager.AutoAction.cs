using System.Collections;
using System.Collections.Generic;
using System.Linq;
using UnityEngine;

public partial class NormalGameStateManager {
    private Coroutine waitAutoActionCoroutine;

    private static readonly HashSet<string> HuActionNames = new HashSet<string> {
        "hu", "hu_first", "hu_second", "hu_third"
    };

    /// <summary>取消未完成的自动操作协程，避免手动/自动 ChooseAction 后过期协程再次 ClearAction。</summary>
    public void CancelWaitAutoAction(string reason) {
        if (waitAutoActionCoroutine == null) {
            return;
        }
        StopCoroutine(waitAutoActionCoroutine);
        waitAutoActionCoroutine = null;
        Debug.Log($"[AutoAction] 取消 WaitAutoAction | 原因={reason}");
    }

    private void StartWaitAutoAction(string action) {
        CancelWaitAutoAction("新协程启动");
        waitAutoActionCoroutine = StartCoroutine(WaitAutoAction(action));
    }

    private void ClearWaitAutoActionCoroutineRef() {
        waitAutoActionCoroutine = null;
    }

    private static bool IsHuAction(string action) {
        return HuActionNames.Contains(action);
    }

    private static string GetFirstHuAction(IEnumerable<string> actions) {
        return actions.FirstOrDefault(IsHuAction);
    }

    /// <summary>
    /// 鸣牌询问：应用「不吃/不碰/不明杠」逐项过滤后，仍可供选择的操作（不含 pass）。
    /// 和牌 action 不参与鸣牌过滤，始终保留在结果中。
    /// </summary>
    private static List<string> BuildRemainingActionsAfterMeldFilter(List<string> source) {
        List<string> remaining = new List<string>(source);
        remaining.RemoveAll(a => a == "pass");
        if (AutoAction.Instance.IsPassChi) {
            remaining.RemoveAll(a => a == "chi_left" || a == "chi_mid" || a == "chi_right");
        }
        if (AutoAction.Instance.IsPassPeng) {
            remaining.RemoveAll(a => a == "peng");
        }
        if (AutoAction.Instance.IsPassMingGang) {
            remaining.RemoveAll(a => a == "gang");
        }
        return remaining;
    }

    /// <summary>
    /// 鸣牌询问是否应自动 pass：仅当服务器给出的全部可操作项（不含 pass）均被筛除时为 true。
    /// 例：可吃可碰可和且只开「不吃/不碰」→ 和牌仍在，返回 false，等待玩家或「自动胡牌」。
    /// 「不吃+不碰+不明杠」全开启等效于主面板「自动过牌」，但仍不因和牌选项而自动 pass。
    /// </summary>
    private static bool ShouldAutoPassMingPaiAsk(List<string> allowActions) {
        bool hasOfferedAction = allowActions.Any(a => a != "pass");
        if (!hasOfferedAction) {
            return false;
        }
        return BuildRemainingActionsAfterMeldFilter(allowActions).Count == 0;
    }

    /// <summary>
    /// 等待并执行自动操作协程。
    /// AutoMingPaiAction（他人切牌/加杠后的鸣牌询问）优先级：
    ///   1. 牌张设置命中 → 直接 pass（含荣和，最高优先级）
    ///   2. 自动和牌（受不点和/不抢杠约束）
    ///   3. 鸣牌过滤后无任何剩余可操作项 → 自动 pass
    ///   4. 仍有剩余项（含手动和牌）→ 不自动操作，等待玩家
    /// AutoHandAction（自己回合手牌询问）优先级：
    ///   1. 自动自摸（受不自摸约束） 2. 自动补花 3. 自动出牌
    /// </summary>
    private IEnumerator WaitAutoAction(string action){
        if (IsRealtimeSpectator) {
            yield break;
        }

        try {
            // 鸣牌操作自动执行
            if (action == "AutoMingPaiAction"){
                string actualHupaiAction = GetFirstHuAction(allowActionList);
                bool hasHuAction = !string.IsNullOrEmpty(actualHupaiAction);

                // 牌张设置最优先：命中牌张时不询问任何操作（含荣和）
                if (AutoAction.Instance.ShouldAutoPassForCurrentDiscard()){
                    yield return new WaitForSeconds(0.2f);
                    GameCanvas.Instance.ChooseAction("pass", 0);
                    yield break;
                }

                // 自动和牌
                if (hasHuAction){
                    bool isQiangGangAsk = Instance != null && IsQiangGangAsk;
                    bool shouldAutoWin = isQiangGangAsk
                        ? AutoAction.Instance.ShouldAutoWinRobKong()
                        : AutoAction.Instance.ShouldAutoWinRon();
                    if (shouldAutoWin){
                        yield return new WaitForSeconds(0.2f);
                        GameCanvas.Instance.ChooseAction(actualHupaiAction, 0);
                        yield break;
                    }
                }

                // 不吃/不碰/不明杠 只逐项剔除对应鸣牌；全部可操作项被筛光才自动 pass（和牌不会被剔除）
                if (ShouldAutoPassMingPaiAsk(allowActionList)) {
                    yield return new WaitForSeconds(0.2f);
                    GameCanvas.Instance.ChooseAction("pass", 0);
                    yield break;
                }

                yield return null;
            }

            // 手牌操作自动执行
            else if (action == "AutoHandAction"){
                // 如果允许操作列表有hu_self
                if (allowActionList.Contains("hu_self")){
                    // 自动胡牌开启且未勾选「不自摸」时执行自动自摸
                    if (AutoAction.Instance.ShouldAutoWinTsumo()){
                        yield return new WaitForSeconds(0.2f);
                        GameCanvas.Instance.ChooseAction("hu_self", 0);
                        yield break;
                    }
                }

                // 如果允许操作列表有buhua
                if (allowActionList.Contains("buhua")){
                    // 如果开启自动补花，则执行自动补花
                    if (AutoAction.Instance.IsAutoBuhua){
                        yield return new WaitForSeconds(0.3f);
                        GameCanvas.Instance.ChooseAction("buhua", 0);
                        yield break;
                    }
                }

                List<string> allowActionWithoutCut = new List<string>{"angang","jiagang","hu_self","buhua"};
                // 如果允许操作列表有除去cut的其他操作 则转到玩家操作
                if (allowActionWithoutCut.Any(allowActionList.Contains)){
                    yield return null;
                }
                // 如果上次摸牌类型是杠牌，不执行自动出牌
                else if (lastDealTileType == "deal_gang_tile"){
                    yield return null;
                }
                // 如果没有，则执行自动出牌
                else{
                    if (AutoAction.Instance.IsAutoCut){
                        float autoCutDelay = AutoAction.Instance.IsAutoCutLocked ? 0.3f : 0.5f;
                        yield return new WaitForSeconds(autoCutDelay);
                        if (!GameCanvas.Instance.TriggerMoqieHandCardClick()) {
                            Debug.LogWarning("自动出牌失败：手牌容器中没有可出的牌");
                        }
                    }
                    else{
                        yield return null;
                    }
                }
            }

            else{
                Debug.LogWarning($"未知操作: {action}");
            }
        }
        finally {
            ClearWaitAutoActionCoroutineRef();
        }
    }
}
