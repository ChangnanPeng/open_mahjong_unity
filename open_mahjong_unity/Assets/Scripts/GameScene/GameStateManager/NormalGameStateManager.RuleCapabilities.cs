public partial class NormalGameStateManager {
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
