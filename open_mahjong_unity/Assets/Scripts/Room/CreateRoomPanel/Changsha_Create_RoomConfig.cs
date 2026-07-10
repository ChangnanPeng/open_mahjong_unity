public class Changsha_Create_RoomConfig : Qingque_Create_RoomConfig {
    public int OpenKongReplacementCount { get; set; } = 2;
    public bool InitialHuSiXi { get; set; } = true;
    public bool InitialHuBanBanHu { get; set; } = true;
    public bool InitialHuQueYiSe { get; set; } = true;
    public bool InitialHuLiuLiuShun { get; set; } = true;
    public bool InitialHuSanTong { get; set; } = true;
    public int BirdCount { get; set; } = 2;
    public bool DealerBird { get; set; } = true;

    public new bool Validate(out string error, bool passwordToggle, bool setRandomSeedToggle) {
        if (!base.Validate(out error, passwordToggle, setRandomSeedToggle)) {
            return false;
        }
        if (GameRound != 1 && GameRound != 2 && GameRound != 4) {
            error = "长沙麻将对局数量必须是4/8/16";
            return false;
        }
        if (OpenKongReplacementCount < 1 || OpenKongReplacementCount > 4) {
            error = "开杠张数必须在1到4之间";
            return false;
        }
        if (BirdCount != 0 && BirdCount != 1 && BirdCount != 2 && BirdCount != 4) {
            error = "扎鸟张数必须是0/1/2/4";
            return false;
        }
        error = null;
        return true;
    }
}
