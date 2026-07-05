# Multi-Ron Independent Confirmation Implementation Notes

These notes describe how to implement independent `hu` / `pass` confirmation for multiple wins from the same discard in the new rule.

## Goal

The new rule should allow multiple players to win from the same discard, but only players who explicitly choose `hu` should be settled as winners.

This differs from the current Sichuan flow, where all eligible winners are cached and can all be treated as winners once any one player triggers the win settlement.

## Desired Behavior

- A discard may make multiple players eligible to win.
- Every eligible player should receive their own `hu` / `pass` choice.
- Each eligible player decides independently.
- Choosing `hu` means the player joins the accepted winner list and exits the hand after settlement.
- Choosing `pass` means the player gives up this discard and continues playing.
- Timing out should be treated as `pass`.
- If at least one eligible player chooses `hu`, settle only those accepted winners.
- If no eligible player chooses `hu`, continue resolving lower-priority actions such as peng/gang/chi, then continue play if none apply.
- Exception: if the wall is empty after the discard, do not resolve lower-priority chi/peng/gang. The final discard can only be won; if nobody wins, the hand ends by exhausted wall.

## Current Sichuan Behavior To Avoid

In `game_sichuan`, `check_action_after_cut()` collects all eligible ron results into `self.sichuan_hu_results`.

Then `_settle_win()` derives winners from:

```python
winners = sorted(self.sichuan_hu_results.keys(), key=lambda x: self._distance_from(discarder, x))
```

That means `sichuan_hu_results` currently acts like "all eligible winners are winners", not "all eligible winners may choose whether to win".

For the new rule, do not let the eligibility cache become the accepted winner list.

## Proposed State Split

Use two separate data structures:

```python
available_hu_results = {}
accepted_hu_results = {}
```

`available_hu_results`:

- Contains every player who can win from the current discard.
- Stores the precomputed fan/result data needed if that player chooses `hu`.
- Is used for button display, validation, and timeout/pass handling.

`accepted_hu_results`:

- Contains only players who explicitly chose `hu`.
- Is the only source of winners for settlement.
- Should be cleared after the discard response is resolved.

## Action Check Direction

When checking actions after a discard:

1. Compute win eligibility for every non-discarding active player.
2. For each eligible player, add `hu` to that player's action list.
3. Store that player's result in `available_hu_results[player_index]`.
4. Do not store the result in the settlement winner list yet.

This lets the UI show `hu`, while keeping settlement opt-in.

## Wait Action Direction

The most important change is in the `waiting_action_after_cut` branch.

Before resolving lower-priority actions, run a special collection phase for all players who have `hu` available:

```python
hu_waiters = [i for i, acts in action_dict.items() if "hu" in acts]
accepted = {}
answered = set()

while hu_waiters still have unanswered players and timer remains:
    action = wait_for_next_action()

    if action.player_index not in hu_waiters:
        keep or defer lower-priority action
        continue

    if action.type == "hu":
        accepted[action.player_index] = available_hu_results[action.player_index]

    if action.type in ("hu", "pass"):
        answered.add(action.player_index)

for timed_out_player in hu_waiters not in answered:
    treat as pass

if accepted:
    accepted_hu_results = accepted
    pending_win = {"type": "ron", "discarder": current_player_index, "hepai_tile": tile_id}
    remove the discard from the discarder display pile
    game_status = "settle_win"
else:
    if wall is empty:
        end hand as exhausted wall
    else:
        continue resolving peng/gang/chi/pass as normal
```

## Lower-Priority Action Interaction

Winning has priority over peng/gang/chi. However, independent confirmation means lower-priority actions should not execute until all eligible win players have either chosen `hu`, chosen `pass`, or timed out.

Implementation options:

- Simpler option: during the win-confirmation phase, ignore or defer non-win actions. After every win player has passed/timed out, run the usual action-resolution logic for the remaining actions.
- More complete option: collect lower-priority actions while waiting for win responses, but only execute the best one if no accepted winners exist.
- Final-discard exception: when the wall is empty after the discard, do not collect or execute lower-priority chi/peng/gang actions.

The simpler option is safer for a first implementation.

## Settlement Direction

Modify the new rule's `_settle_win()` so ron winners come from `accepted_hu_results`, not from all eligible players.

For example:

```python
if pending_win["type"] == "zimo":
    winners = [current_player_index]
else:
    discarder = pending_win["discarder"]
    winners = sorted(accepted_hu_results.keys(), key=lambda x: distance_from(discarder, x))
```

Then reuse the Sichuan-style multi-winner settlement loop, including:

- respecting the maximum of 3 total winners in blood-battle play;
- marking each accepted winner as `is_hu`;
- assigning `hu_order`;
- skipping accepted winners in future turns;
- storing deferred final-settlement data.

## Mid-Hand Visibility Interaction

This feature must combine with delayed public information:

- During the mid-hand win event, reveal only that accepted player(s) won.
- Do not reveal fan lists, score changes, or full hands.
- Do not reveal which players passed unless the UI already treats pass as public action feedback.
- At final settlement, reveal accepted winners' true hands, fan lists, and score changes.

## Edge Cases

- If only one player can win, they still choose `hu` or `pass`.
- If a player passes, they remain active and can win later.
- If all eligible players pass, the discard remains available for peng/gang/chi resolution, unless the wall is empty.
- If the wall is empty and all eligible players pass or time out, the hand ends by exhausted wall; chi/peng/gang are not offered on the final discard.
- If an accepted win fills the third winner slot, stop the hand after settlement.
- If more players choose `hu` than remaining blood-battle winner slots, apply a deterministic rule. The recommended rule is distance from the discarder, matching the current Sichuan ordering.
- If a player disconnects or times out during win confirmation, treat as `pass` unless a stronger reconnect policy is added later.
- If a rob-kong win can involve multiple winners, apply the same independent confirmation model.

## Main Implementation Risk

The hard part is not the settlement loop. The hard part is changing the waiting/action-resolution logic without breaking priority ordering.

Current wait loops are designed to pick one highest-priority action and then proceed. Independent multi-ron needs an exception:

- collect all same-priority win decisions first;
- only then decide whether to settle wins or continue to lower-priority actions.

This should be isolated in a helper rather than scattered through the whole `wait_action()` function.

## Suggested Helper Shape

A helper such as this would keep the new rule easier to reason about:

```python
async def collect_ron_confirmations(self, tile_id: int) -> dict:
    """Return accepted_hu_results for this discard. Timeout/pass means not accepted."""
```

The `waiting_action_after_cut` branch can call this helper before normal meld resolution.

## Files To Compare

- `open_mahjong_server/server/gamestate/game_sichuan/action_check.py`
- `open_mahjong_server/server/gamestate/game_sichuan/wait_action.py`
- `open_mahjong_server/server/gamestate/game_sichuan/SichuanGameState.py`
- `open_mahjong_server/server/gamestate/game_guobiao/wait_action.py`
- `open_mahjong_server/server/gamestate/game_mmcr/wait_action.py`
