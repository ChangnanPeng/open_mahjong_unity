public partial class NormalGameStateManager {
    private const int LegacyJiandanScoreDisplayMultiplier = 6;

    /// <summary>
    /// Clear server-provided rule capabilities when leaving a game session so
    /// the persistent manager cannot leak them into a later rule or record.
    /// </summary>
    public void ResetRuleCapabilities() {
        handEndMode = "first_win";
        winnerTarget = 1;
        handFlow = null;
        presentationProfile = null;
    }

    /// <summary>
    /// Whether a winner leaves an otherwise continuing hand. The server profile
    /// is authoritative; the Sichuan fallback keeps older servers compatible.
    /// </summary>
    public bool UsesWinnerExitFlow() {
        if (handFlow != null) return handFlow.winners_exit_hand;
        return IsSichuanRule() && winnerTarget > 1;
    }

    public bool DefersWinDetails() {
        if (presentationProfile != null) return presentationProfile.defer_win_details;
        return UsesWinnerExitFlow();
    }

    public bool UsesWinnerResultSequence() {
        if (presentationProfile != null) return presentationProfile.result_sequence == "winner_sequence";
        return false;
    }

    public bool UsesBuhuaWinTilePresentation() {
        return presentationProfile != null && presentationProfile.win_tile_to_buhua;
    }

    public int ScoreDisplayMultiplier() {
        if (presentationProfile != null && presentationProfile.score_display_multiplier > 0) {
            return presentationProfile.score_display_multiplier;
        }
        return 1;
    }

    /// <summary>
    /// Resolve a result-panel multiplier from the rule being displayed. This
    /// prevents a profile retained by the live-game manager from affecting a
    /// record that belongs to another rule.
    /// </summary>
    public int ScoreDisplayMultiplierForRule(string rule) {
        bool isJiandan = rule == "jiandan"
            || (!string.IsNullOrEmpty(rule) && rule.StartsWith("jiandan/"));
        if (!isJiandan) return 1;
        if (presentationProfile != null && presentationProfile.score_display_multiplier > 0) {
            return presentationProfile.score_display_multiplier;
        }
        return LegacyJiandanScoreDisplayMultiplier;
    }

    public bool UsesDrawSlotWinTile() {
        return presentationProfile != null && presentationProfile.draw_slot_win_tile;
    }

    public bool CompletesDiscardBeforeRon() {
        return presentationProfile != null && presentationProfile.complete_discard_before_ron;
    }

    public bool UsesConcealedWinTile() {
        return presentationProfile != null && presentationProfile.concealed_win_tile;
    }

    public bool PreservesWinAnimationOnResume() {
        return presentationProfile != null && presentationProfile.preserve_win_animation_on_resume;
    }
}
