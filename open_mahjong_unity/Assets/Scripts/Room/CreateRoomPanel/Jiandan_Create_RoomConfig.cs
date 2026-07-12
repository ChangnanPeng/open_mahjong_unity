/// <summary>
/// Jiandan composition root. Action/scoring identity stays in Rule/SubRule;
/// hand continuation is a reusable, independent policy.
/// </summary>
public class Jiandan_Create_RoomConfig : Qingque_Create_RoomConfig {
    public string HandEndMode { get; set; } = "third_win";
}
