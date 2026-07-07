using TMPro;
using UnityEngine;
using UnityEngine.EventSystems;
using UnityEngine.UI;

public class NewRuleDebugScenarioPanel : MonoBehaviour
{
    private static readonly string[] ScenarioNames = {
        "multi_ron_2",
        "multi_ron_3",
        "rob_kong",
        "rob_kong_multi_ron_2",
        "same_tile_lockout",
        "haitei",
        "houtei",
        "rinshan",
        "heavenly_win",
        "earthly_win",
        "nine_gates",
    };

    private const float ButtonWidth = 170f;
    private const float ButtonHeight = 28f;
    private const float Gap = 4f;

    private static NewRuleDebugScenarioPanel instance;
    private RectTransform rootRect;
    private GameObject listRoot;
    private TMP_Text toggleText;
    private bool expanded;

    public static void EnsureForCurrentGame()
    {
        NormalGameStateManager manager = NormalGameStateManager.Instance;
        bool isNewRule = manager != null
            && (manager.roomRule == "new_rule" || (!string.IsNullOrEmpty(manager.subRule) && manager.subRule.StartsWith("new_rule")))
            && !manager.IsRealtimeSpectator;

        if (!isNewRule)
        {
            Hide();
            return;
        }

        if (instance == null)
        {
            EnsureEventSystem();
            GameObject canvasRoot = new GameObject(
                "NewRuleDebugScenarioCanvas",
                typeof(RectTransform),
                typeof(Canvas),
                typeof(CanvasScaler),
                typeof(GraphicRaycaster)
            );
            Canvas canvas = canvasRoot.GetComponent<Canvas>();
            canvas.renderMode = RenderMode.ScreenSpaceOverlay;
            canvas.overrideSorting = true;
            canvas.sortingOrder = 32000;
            CanvasScaler scaler = canvasRoot.GetComponent<CanvasScaler>();
            scaler.uiScaleMode = CanvasScaler.ScaleMode.ScaleWithScreenSize;
            scaler.referenceResolution = new Vector2(1920f, 1080f);
            scaler.matchWidthOrHeight = 0.5f;

            GameObject root = new GameObject("NewRuleDebugScenarioPanel", typeof(RectTransform), typeof(CanvasGroup), typeof(NewRuleDebugScenarioPanel));
            root.transform.SetParent(canvasRoot.transform, false);
            instance = root.GetComponent<NewRuleDebugScenarioPanel>();
            instance.Build();
        }
        else
        {
            Canvas canvas = instance.GetComponentInParent<Canvas>();
            if (canvas != null)
            {
                canvas.gameObject.SetActive(true);
                canvas.transform.SetAsLastSibling();
            }
        }

        instance.gameObject.SetActive(true);
        instance.Collapse();
    }

    public static void Hide()
    {
        if (instance != null)
        {
            instance.gameObject.SetActive(false);
            Canvas canvas = instance.GetComponentInParent<Canvas>();
            if (canvas != null)
            {
                canvas.gameObject.SetActive(false);
            }
        }
    }

    private void Build()
    {
        CanvasGroup canvasGroup = GetComponent<CanvasGroup>();
        if (canvasGroup != null)
        {
            canvasGroup.interactable = true;
            canvasGroup.blocksRaycasts = true;
        }

        rootRect = GetComponent<RectTransform>();
        rootRect.anchorMin = new Vector2(0f, 0f);
        rootRect.anchorMax = new Vector2(0f, 0f);
        rootRect.pivot = new Vector2(0f, 0f);
        rootRect.anchoredPosition = new Vector2(14f, 14f);
        rootRect.sizeDelta = new Vector2(ButtonWidth, ButtonHeight);

        Button toggle = CreateButton(transform, "Toggle", "NR Debug", new Vector2(0f, 0f), ButtonWidth, ButtonHeight);
        toggle.onClick.AddListener(ToggleExpanded);
        toggleText = toggle.GetComponentInChildren<TMP_Text>();

        listRoot = new GameObject("ScenarioList", typeof(RectTransform), typeof(Image));
        listRoot.transform.SetParent(transform, false);
        RectTransform listRect = listRoot.GetComponent<RectTransform>();
        listRect.anchorMin = new Vector2(0f, 0f);
        listRect.anchorMax = new Vector2(0f, 0f);
        listRect.pivot = new Vector2(0f, 0f);
        listRect.anchoredPosition = new Vector2(0f, ButtonHeight + Gap);
        listRect.sizeDelta = new Vector2(ButtonWidth, ScenarioNames.Length * (ButtonHeight + Gap) + Gap);
        Image listImage = listRoot.GetComponent<Image>();
        listImage.color = new Color(0f, 0f, 0f, 0.62f);

        for (int i = 0; i < ScenarioNames.Length; i++)
        {
            string scenario = ScenarioNames[i];
            Button button = CreateButton(
                listRoot.transform,
                "Scenario_" + scenario,
                scenario,
                new Vector2(0f, Gap + i * (ButtonHeight + Gap)),
                ButtonWidth,
                ButtonHeight
            );
            button.onClick.AddListener(() => TriggerScenario(scenario));
        }

        Collapse();
    }

    private static void EnsureEventSystem()
    {
        if (EventSystem.current != null)
        {
            return;
        }
        new GameObject("EventSystem", typeof(EventSystem), typeof(StandaloneInputModule));
    }

    private Button CreateButton(Transform parent, string name, string label, Vector2 anchoredPosition, float width, float height)
    {
        GameObject buttonObject = new GameObject(name, typeof(RectTransform), typeof(Image), typeof(Button));
        buttonObject.transform.SetParent(parent, false);
        RectTransform rect = buttonObject.GetComponent<RectTransform>();
        rect.anchorMin = new Vector2(0f, 0f);
        rect.anchorMax = new Vector2(0f, 0f);
        rect.pivot = new Vector2(0f, 0f);
        rect.anchoredPosition = anchoredPosition;
        rect.sizeDelta = new Vector2(width, height);

        Image image = buttonObject.GetComponent<Image>();
        image.color = new Color(0.12f, 0.16f, 0.20f, 0.88f);

        Button button = buttonObject.GetComponent<Button>();
        ColorBlock colors = button.colors;
        colors.highlightedColor = new Color(0.20f, 0.28f, 0.36f, 0.95f);
        colors.pressedColor = new Color(0.08f, 0.12f, 0.16f, 0.95f);
        button.colors = colors;

        GameObject textObject = new GameObject("Text", typeof(RectTransform), typeof(TextMeshProUGUI));
        textObject.transform.SetParent(buttonObject.transform, false);
        RectTransform textRect = textObject.GetComponent<RectTransform>();
        textRect.anchorMin = Vector2.zero;
        textRect.anchorMax = Vector2.one;
        textRect.offsetMin = new Vector2(8f, 0f);
        textRect.offsetMax = new Vector2(-8f, 0f);

        TextMeshProUGUI text = textObject.GetComponent<TextMeshProUGUI>();
        text.text = label;
        text.fontSize = 16f;
        text.color = Color.white;
        text.alignment = TextAlignmentOptions.MidlineLeft;
        text.raycastTarget = false;
        return button;
    }

    private void ToggleExpanded()
    {
        SetExpanded(!expanded);
    }

    private void Collapse()
    {
        SetExpanded(false);
    }

    private void SetExpanded(bool value)
    {
        expanded = value;
        if (listRoot != null)
        {
            listRoot.SetActive(expanded);
        }
        if (toggleText != null)
        {
            toggleText.text = expanded ? "NR Debug x" : "NR Debug";
        }
    }

    private void TriggerScenario(string scenario)
    {
        GameStateNetworkManager.Instance.SendNewRuleDebugScenario(scenario);
        Collapse();
    }
}
