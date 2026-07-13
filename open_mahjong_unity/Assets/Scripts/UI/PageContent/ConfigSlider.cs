using UnityEngine;
using UnityEngine.UI;
using TMPro;

public enum VolumeType {
    Master,
    Music,
    SoundEffect,
    Voice
}

public class ConfigSlider : MonoBehaviour {
    [SerializeField] private Slider slider;
    [SerializeField] private TMP_Text valueText;
    [SerializeField] private VolumeType volumeType;

    // 初始化滑动条
    public void Init() {
        slider.minValue = 0;
        slider.maxValue = 100;
        slider.wholeNumbers = true;
        SyncFromConfig();
        slider.onValueChanged.RemoveListener(OnValueChanged);
        slider.onValueChanged.AddListener(OnValueChanged);
    }

    /// <summary>
    /// 从 ConfigManager 刷新滑动条显示，不触发写回。
    /// </summary>
    public void SyncFromConfig() {
        if (slider == null) return;
        int currentVolume = GetVolume();
        slider.SetValueWithoutNotify(currentVolume);
        if (valueText != null) {
            valueText.text = $"{currentVolume}%";
        }
    }

    // 获取当前音量
    private int GetVolume() {
        switch (volumeType) {
            case VolumeType.Master:
                return ConfigManager.Instance.MasterVolume;
            case VolumeType.Music:
                return ConfigManager.Instance.MusicVolume;
            case VolumeType.SoundEffect:
                return ConfigManager.Instance.SoundEffectVolume;
            case VolumeType.Voice:
                return ConfigManager.Instance.VoiceVolume;
            default:
                return 100;
        }
    }

    private void SetVolume(int value){
        switch (volumeType) {
            case VolumeType.Master:
                ConfigManager.Instance.SetMasterVolume(value);
                break;
            case VolumeType.Music:
                ConfigManager.Instance.SetMusicVolume(value);
                break;
            case VolumeType.SoundEffect:
                ConfigManager.Instance.SetSoundEffectVolume(value);
                break;
            case VolumeType.Voice:
                ConfigManager.Instance.SetVoiceVolume(value);
                break;
        }
    }

    // 当滑动条值改变时更新音量值显示和音量
    private void OnValueChanged(float value){
        int intValue = Mathf.RoundToInt(value);
        valueText.text = $"{intValue}%";
        SetVolume(intValue);
    }

}
