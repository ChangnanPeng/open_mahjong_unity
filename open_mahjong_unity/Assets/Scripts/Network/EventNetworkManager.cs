using UnityEngine;
using Newtonsoft.Json;
using NativeWebSocket;
using System;
using System.Collections.Generic;

/// <summary>
/// 赛事相关网络管理器。
/// 与 FriendNetworkManager 同模式：单例 + Handle* 方法 + 主动发送方法。
/// </summary>
public class EventNetworkManager : MonoBehaviour {
    public static EventNetworkManager Instance { get; private set; }

    public List<EventListEntry> ActiveEvents { get; private set; } = new List<EventListEntry>();
    public event Action OnActiveEventsUpdated;

    private void Awake() {
        if (Instance != null && Instance != this) {
            Destroy(gameObject);
            return;
        }
        Instance = this;
    }

    public void HandleEventMessage(Response response) {
        if (response == null || string.IsNullOrEmpty(response.type)) return;
        switch (response.type) {
            case "event/list_my_active":
                ActiveEvents = response.event_list != null
                    ? new List<EventListEntry>(response.event_list)
                    : new List<EventListEntry>();
                OnActiveEventsUpdated?.Invoke();
                break;
        }
    }

    private static WebSocket _GetWs() {
        var ws = NetworkManager.Instance.GetWebSocket();
        return (ws != null && ws.State == WebSocketState.Open) ? ws : null;
    }

    private static async void _Send(object msg) {
        var ws = _GetWs();
        if (ws == null) return;
        try {
            await ws.SendText(JsonConvert.SerializeObject(msg));
        } catch (Exception e) {
            Debug.LogError($"[EventNetworkManager] 发送失败: {e.Message}");
        }
    }

    public void ListMyActiveEvents() {
        _Send(new { type = "event/list_my_active" });
    }
}
