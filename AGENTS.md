# AGENTS.md - Changsha Mahjong Salasasa Integration

## Project Goal

- Fully integrate Changsha Mahjong rules into the Salasasa website and client/server flow.
- Keep work scoped to `D:\Codex\open_mahjong_unity` unless the user explicitly says otherwise.

## Development Order

- First copy and stabilize the gamestate implementation.
- Then complete edge-case rule paths.
- Then complete the scoring scripts.
- Finally connect and harden the main program and user-facing flow.

## Rule Confirmation

- Confirm Changsha Mahjong rule details with the user before implementing new rule behavior.
- For rules already confirmed by the user, encode them in focused tests before or alongside the fix.

## Current Rule Priority

- Prioritize the pass-hu lifecycle:
  - Passing on a discard blocks same-or-lower base discard wins until that player's next self draw/discard refresh.
  - The block remains across immediate discards from other players before that refresh.
  - The block clears after that player completes their own discard.
  - Self draw wins are never blocked by pass-hu state.

## Future UI Work

- Add a separate Changsha bird-draw animation later. Current rule work should only preserve/send the result data unless the user explicitly asks to implement the animation.

## Repository Safety

- Do not commit or push unless the user explicitly asks.
- Do not touch unrelated dirty files, especially:
  - `open_mahjong_server/server/chat_server/secret_key.txt`
  - `open_mahjong_unity/Assets/Plugins/TextMesh Pro/Resources/Fonts & Materials/LiberationSans SDF - Fallback.asset`
  - `open_mahjong_unity/Assets/Scripts/Config/ConfigManager.cs`
  - `open_mahjong_unity/ProjectSettings/EntitiesClientSettings.asset`
