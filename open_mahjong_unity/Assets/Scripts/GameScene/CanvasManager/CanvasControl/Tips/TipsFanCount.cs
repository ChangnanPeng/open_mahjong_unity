using UnityEngine;
using UnityEngine.UI;
using TMPro;
public class TipsFanCount : MonoBehaviour
{
    [SerializeField] private TMP_Text tipsFanCountText; // 提示番数文本
    [SerializeField] private Image backgroundImage; // 背景图片组件

    [Header("颜色设置")]
    public Color dianheColor = Color.green; // 点和颜色（绿色，可和牌）
    public Color zimoColor = Color.yellow; // 自摸颜色（黄色，仅自摸）
    public Color wuyiColor = new Color(1f, 0.647f, 0f); // 无役颜色（橙色，未起和）
    public Color exhaustedColor = new Color(0.55f, 0.55f, 0.55f, 1f); // 听牌张已用尽（灰色）

    private void Awake() {
        ConfigureText();
    }

    public void SetTipsFanCount(string fanCount, string colorType) {
        ConfigureText();
        tipsFanCountText.text = fanCount;

        if (colorType == "exhausted")
        {
            backgroundImage.color = exhaustedColor;
        }
        else if (colorType == "dianhe")
        {
            backgroundImage.color = dianheColor;
        }
        else if (colorType == "zimo")
        {
            backgroundImage.color = zimoColor;
        }
        else if (colorType == "wuyi")
        {
            backgroundImage.color = wuyiColor;
        }
    }

    private void ConfigureText() {
        if (tipsFanCountText == null) return;
        tipsFanCountText.enableAutoSizing = true;
        tipsFanCountText.fontSizeMax = Mathf.Max(tipsFanCountText.fontSize, 28f);
        tipsFanCountText.fontSizeMin = 12f;
        tipsFanCountText.enableWordWrapping = false;
        tipsFanCountText.overflowMode = TextOverflowModes.Truncate;
        tipsFanCountText.alignment = TextAlignmentOptions.Center;
    }
}
