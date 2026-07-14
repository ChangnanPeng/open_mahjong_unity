using UnityEngine;

public class PlayerConfigPanel : MonoBehaviour {
    public static PlayerConfigPanel Instance;
    private void Awake() {
        Instance = this;
    }
}
