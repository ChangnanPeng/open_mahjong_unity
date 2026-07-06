using UnityEngine;
using UnityEngine.UI;
using TMPro;

public class FanCount : MonoBehaviour {
    [SerializeField] private TextMeshProUGUI FanName;
    [SerializeField] private TextMeshProUGUI FanValue;
    [SerializeField] private Image BackgroundImage;

    [Header("副数颜色")]
    [SerializeField] private Color fuColor = new Color(0.55f, 0.82f, 0.49f);
    [Header("番数颜色")]
    [SerializeField] private Color fanColor = new Color(0.55f, 0.70f, 1f);

    private void Awake() {
        ConfigureText(FanName, 18f);
        ConfigureText(FanValue, 16f);
    }

    public void SetFanCount(string name, string valueDisplay) {
        ConfigureText(FanName, 18f);
        ConfigureText(FanValue, 16f);
        FanName.text = name;
        FanValue.text = valueDisplay;
    }

    private static void ConfigureText(TMP_Text text, float minSize) {
        if (text == null) return;
        text.enableAutoSizing = true;
        text.fontSizeMax = Mathf.Max(text.fontSize, 40f);
        text.fontSizeMin = minSize;
        text.enableWordWrapping = false;
        text.overflowMode = TextOverflowModes.Truncate;
        text.alignment = TextAlignmentOptions.Center;
    }

    public void ApplyFuColor() {
        BackgroundImage.color = fuColor;
    }

    public void ApplyFanColor() {
        BackgroundImage.color = fanColor;
    }
}
