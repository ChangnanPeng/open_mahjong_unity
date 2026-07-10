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
    /// 鸣牌询问：应用「不吃/不碰/不明杠」及「不点和」逐项过滤后，仍可供选择的操作（不含 pass）。
    /// 「不点和」会将荣和纳入 pass 判定；若该牌同时有可用的未过滤鸣牌（如可碰且未开「不碰」），则保留点和等待玩家。
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
        if (ShouldFilterRonForAutoPass(source)) {
            remaining.RemoveAll(IsHuAction);
        }
        return remaining;
    }

    /// <summary>
    /// 「不点和」是否应将荣和从剩余可操作项中剔除（纳入自动 pass 队列）。
    /// 例外：该牌既能鸣牌（吃/碰/明杠且对应过滤未开）又能点和时，不剔除，等待玩家抉择。
    /// </summary>
    private static bool ShouldFilterRonForAutoPass(List<string> allowActions) {
        if (AutoAction.Instance == null || !AutoAction.Instance.IsNoRon) {
            return false;
        }
        if (!allowActions.Any(IsHuAction)) {
            return false;
        }
        return !HasUnblockedMeldOption(allowActions);
    }

    private static bool HasUnblockedMeldOption(List<string> allowActions) {
        if (!AutoAction.Instance.IsPassPeng && allowActions.Contains("peng")) {
            return true;
        }
        if (!AutoAction.Instance.IsPassChi &&
            (allowActions.Contains("chi_left") || allowActions.Contains("chi_mid") || allowActions.Contains("chi_right"))) {
            return true;
        }
        if (!AutoAction.Instance.IsPassMingGang && allowActions.Contains("gang")) {
            return true;
        }
        return false;
    }

    /// <summary>
    /// 鸣牌询问是否应自动 pass：仅当服务器给出的全部可操作项（不含 pass）均被筛除时为 true。
    /// 例：仅点和且开「不点和」→ 自动 pass；可碰可点和且未开「不碰」→ 保留等待玩家。
    /// </summary>
    private static bool ShouldAutoPassMingPaiAsk(List<string> allowActions) {
        bool hasOfferedAction = allowActions.Any(a => a != "pass");
        if (!hasOfferedAction) {
            return false;
        }
        return BuildRemainingActionsAfterMeldFilter(allowActions).Count == 0;
    }

    /// <summary>自家当前摸入牌 id：优先 lastDealTileId，否则回退 2D 摸牌区标记。</summary>
    public int GetCurrentDrawTileId() {
        if (lastDealTileId > 0) {
            return lastDealTileId;
        }
        if (GameCanvas.Instance != null) {
            TileCard drawTile = GameCanvas.Instance.GetDrawTile();
            if (drawTile != null && drawTile.tileId > 0) {
                return drawTile.tileId;
            }
        }
        return 0;
    }

    /// <summary>
    /// 等待并执行自动操作协程。
    /// AutoMingPaiAction（他人切牌/加杠后的鸣牌询问）优先级：
    ///   1. 牌张设置命中 → 直接 pass（含荣和，最高优先级）
    ///   2. 自动和牌（受不点和/不抢杠约束）
    ///   3. 鸣牌过滤 +「不点和」后无任何剩余可操作项 → 自动 pass
    ///   4. 仍有剩余项（含手动和牌或与未过滤鸣牌并存的点和）→ 不自动操作，等待玩家
    /// AutoHandAction（自己回合手牌询问）优先级：
    ///   1. 牌张设置命中摸入牌 → 跳过自动自摸
    ///   2. 自动自摸（受不自摸约束） 3. 自动补花 4. 自动出牌
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

                // 鸣牌过滤 +「不点和」：全部可操作项被筛光才自动 pass
                if (ShouldAutoPassMingPaiAsk(allowActionList)) {
                    yield return new WaitForSeconds(0.2f);
                    GameCanvas.Instance.ChooseAction("pass", 0);
                    yield break;
                }

                yield return null;
            }

            // 手牌操作自动执行
            else if (action == "AutoHandAction"){
                // 起手胡询问：自动胡牌开启时接受，否则等待玩家手动选择
                if (allowActionList.Contains("initial_hu")){
                    if (AutoAction.Instance.IsAutoHepai){
                        yield return new WaitForSeconds(0.2f);
                        GameCanvas.Instance.ChooseAction("initial_hu", 0);
                        yield break;
                    }
                }

                // 如果允许操作列表有hu_self
                if (allowActionList.Contains("hu_self")){
                    // 自动胡牌开启、未勾选「不自摸」、且摸入牌未命中「不询问」列表时执行自动自摸
                    if (AutoAction.Instance.ShouldAutoWinTsumo()
                        && !AutoAction.Instance.ShouldAutoPassForCurrentDraw()){
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

                List<string> allowActionWithoutCut = new List<string>{"buzhang","angang","jiagang","hu_self","initial_hu","sea_bottom","buhua"};
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
