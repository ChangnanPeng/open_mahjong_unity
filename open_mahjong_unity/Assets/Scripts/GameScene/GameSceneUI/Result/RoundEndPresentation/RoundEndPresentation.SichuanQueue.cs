using System.Collections;
using System.Collections.Generic;
using UnityEngine;

/// <summary>
/// 四川血战终局演出（与服务端 _settle_liuju 顶部 ABCD 注释一致，禁止跳过任一步）：
/// reveal_hu → settle_hu×N（按和牌先后 hu_order）→ chajiao×M（末家和牌者下家起逆时针，每家 1 面板）→ 末步 8s。
/// 退税并入查叫面板（不再有独立 cha_refund 步）。每条 show_result 驱动一步；
/// 新数据到达时中断当前步、重置面板并渐显（步间 sleep 由服务端控制）。
/// </summary>
public partial class RoundEndPresentation {
    private Coroutine _sichuanEndgameRunner;
    private bool _sichuanEndgameSessionStarted;
    private readonly Queue<IEnumerator> _sichuanEndgameStepQueue = new Queue<IEnumerator>();

    public void ResetSichuanEndgameQueue() {
        if (_sichuanEndgameRunner != null) {
            StopCoroutine(_sichuanEndgameRunner);
            _sichuanEndgameRunner = null;
        }
        _sichuanEndgameStepQueue.Clear();
        _sichuanEndgameSessionStarted = false;
        _sichuanEndgamePanelStarted = false;
        if (EndResultPanel.Instance != null) {
            EndResultPanel.Instance.StopActivePresentation();
        }
    }

    public void EnqueueSichuanEndgameStep(IEnumerator step) {
        if (step == null) return;
        if (NormalGameStateManager.Instance != null && NormalGameStateManager.Instance.UsesWinnerResultSequence()) {
            _sichuanEndgameStepQueue.Enqueue(step);
            Debug.Log($"[NewRuleEndgameQueue] enqueue step, queued={_sichuanEndgameStepQueue.Count}, running={_sichuanEndgameRunner != null}");
            if (_sichuanEndgameRunner == null) {
                _sichuanEndgameRunner = StartCoroutine(RunNewRuleEndgameQueue());
            }
            return;
        }

        if (_sichuanEndgameRunner != null) {
            StopCoroutine(_sichuanEndgameRunner);
            _sichuanEndgameRunner = null;
            if (EndResultPanel.Instance != null) {
                EndResultPanel.Instance.StopActivePresentation();
            }
        }
        _sichuanEndgameRunner = StartCoroutine(RunSichuanEndgameStep(step));
    }

    private IEnumerator RunNewRuleEndgameQueue() {
        if (!_sichuanEndgameSessionStarted) {
            StopActiveSequence();
            HideSelfGameplayControl(false);
            gameObject.SetActive(true);
            _sichuanEndgameSessionStarted = true;
            Debug.Log("[NewRuleEndgameQueue] start session");
        }

        while (_sichuanEndgameStepQueue.Count > 0) {
            Debug.Log($"[NewRuleEndgameQueue] run step, remaining_before={_sichuanEndgameStepQueue.Count}");
            yield return _sichuanEndgameStepQueue.Dequeue();
        }

        _sichuanEndgameRunner = null;
        Debug.Log("[NewRuleEndgameQueue] queue drained");
    }

    private IEnumerator RunSichuanEndgameStep(IEnumerator step) {
        if (!_sichuanEndgameSessionStarted) {
            StopActiveSequence();
            HideSelfGameplayControl(false);
            gameObject.SetActive(true);
            _sichuanEndgameSessionStarted = true;
        }
        yield return step;
        _sichuanEndgameRunner = null;
    }

    /// <summary>准备下一步面板内容（alpha=0），若已有面板则先中断当前演出。</summary>
    private void BeginSichuanEndgamePanel() {
        if (EndResultPanel.Instance != null) {
            EndResultPanel.Instance.StopActivePresentation();
            if (_sichuanEndgamePanelStarted) {
                EndResultPanel.Instance.gameObject.SetActive(false);
            }
        }
        _sichuanEndgamePanelStarted = true;
        PreparePresentationRoot(true);
    }

    private bool _sichuanEndgamePanelStarted;

    private IEnumerator CoFadeInSichuanEndgamePanel() {
        yield return PlayPresentationFade(true);
    }
}
