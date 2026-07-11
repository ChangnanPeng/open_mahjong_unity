using System.Collections.Generic;
using Jianzhong;

/// <summary>
/// Client-side Jianzhong calculation entry points. The server remains
/// authoritative; this facade follows the same shape as other rule adapters.
/// </summary>
public static class JianzhongExternal {
    public static HashSet<int> TingpaiCheck(
        List<int> handTileList,
        List<string> combinationList) {
        return new JianzhongTingpaiCheck().TingpaiCheck(
            handTileList,
            combinationList);
    }
}
