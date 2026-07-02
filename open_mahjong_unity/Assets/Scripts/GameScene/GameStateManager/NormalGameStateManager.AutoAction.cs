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

    private static bool IsMeldAction(string action) {
        return action == "chi_left" || action == "chi_mid" || action == "chi_right"
            || action == "peng" || action == "gang";
    }

    private static bool HasMeldAction(IEnumerable<string> actions) {
        return actions.Any(IsMeldAction);
    }

    /// <summary>
    /// 从允许操作列表中剔除已勾选「不吃/不碰/不明杠/自动过牌」对应的鸣牌项。
    /// 和牌 action 不参与此过滤；有和牌时由调用方单独处理，不自动 pass。
    /// </summary>
    private static List<string> BuildRemainingMeldActions(List<string> source) {
        List<string> remaining = new List<string>(source);
        if (AutoAction.Instance.IsPassChi) {
            remaining.RemoveAll(a => a == "chi_left" || a == "chi_mid" || a == "chi_right");
        }
        if (AutoAction.Instance.IsPassPeng) {
            remaining.RemoveAll(a => a == "peng");
        }
        if (AutoAction.Instance.IsPassMingGang) {
            remaining.RemoveAll(a => a == "gang");
        }
        remaining.RemoveAll(a => a == "pass" || IsHuAction(a));
        return remaining;
    }

    /// <summary>
    /// 等待并执行自动操作协程。
    /// AutoMingPaiAction（他人切牌/加杠后的鸣牌询问）优先级：
    ///   1. 牌张设置命中 → 直接 pass（含荣和，最高优先级）
    ///   2. 自动和牌（受不点和/不抢杠约束）
    ///   3. 有和牌但未自动和：仍有鸣牌 → 不跳过；鸣牌已全部过滤 → 跳过
    ///   4. 无和牌：鸣牌过滤光 / 自动过牌 → 跳过
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

                List<string> remainingMelds = BuildRemainingMeldActions(allowActionList);
                bool hadMeldOptions = HasMeldAction(allowActionList);
                bool allMeldsFiltered = hadMeldOptions && remainingMelds.Count == 0;

                // 有和牌但未自动和：仍有未过滤鸣牌 → 不跳过；鸣牌已全部过滤 → 跳过
                if (hasHuAction) {
                    if (remainingMelds.Count > 0) {
                        yield return null;
                        yield break;
                    }
                    if (allMeldsFiltered) {
                        yield return new WaitForSeconds(0.2f);
                        GameCanvas.Instance.ChooseAction("pass", 0);
                        yield break;
                    }
                    // 仅有和牌、无鸣牌选项（如不点和但可手动荣和）→ 不跳过
                    yield return null;
                    yield break;
                }

                // 无和牌选项时：鸣牌已全部过滤 或 开启自动过牌（= 不吃碰杠）→ pass
                if (remainingMelds.Count == 0 || AutoAction.Instance.IsAutoPass){
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
