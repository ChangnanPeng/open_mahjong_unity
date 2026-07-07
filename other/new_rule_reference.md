# New Rule Reference

## Target Rule Shape

The new rule should use:

- `game_sichuan` as the game-flow skeleton for blood-battle style play.
- Qingque-like no-flower wall shape.
- Guobiao/Qingque-like meld/action structure.
- A 136-tile wall:
  - Characters, dots, bamboo: 108 tiles.
  - Winds: east, south, west, north: 16 tiles.
  - Dragons: red, white, green: 12 tiles.
- No flower tiles.
- No dead wall / 14-tile reserve.
- Draw until the wall is empty.
- After the wall is empty, the final discard response window only allows discard wins. Do not allow chi, peng, or kong on the final discard.
- No minimum fan / starting-score requirement for winning.
- A completed standard hand can win with 0 points if it matches no scoring fan.
- "0-point minimum" means shape legality and scoring are separate:
  - legal standard shape `4 sets + 1 pair` may win even if the fan list is empty;
  - special hands such as seven pairs and thirteen orphans remain legal by their own shape rules;
  - invalid/incomplete shapes are still not wins.
- No false-win (`cuohe`) flow.
- One player winning does not end the hand.
- A winning player exits the hand.
- Continue until 3 players have won or the wall is exhausted.
- Use Guobiao/Qingque-style fixed dealer rotation between hands.
- Do not use Sichuan winner-based dealer selection or draw-based dealer repeat.
- Multiple players may win from the same discard, but each eligible player must independently choose `hu` or `pass`.
- Do not automatically count all eligible winners as accepted winners just because one player clicked `hu`.
- A player who chooses `pass` on a discard remains in the hand and continues playing.
- Use same-tile discard-win lockout: a player who skips a win or discards a tile cannot later win by discard on the same tile until that player discards again.
- After chi or peng, the player must discard and cannot immediately perform concealed kong or added kong.
- After exposed kong, concealed kong, or added kong, draw a supplement tile and then enter normal hand-action checks.
- During mid-hand blood-battle wins, hide the winner's hand, fan list, score, score changes, and non-public self-draw tile from other players.
- Reveal hand, fan list, score, and score changes only during the final end-of-hand settlement.
- During mid-hand concealed kongs, hide the concealed kong tile identity from other players.
- Reveal concealed kong tile identities only during the final end-of-hand settlement.

## Best Composition

Use this mix as the default implementation plan:

- Blood-battle state machine from `game_sichuan`.
- No-flower 136-tile wall from `game_mmcr` / Qingque.
- Chi/peng/gang action style from Guobiao or Qingque.
- New rule-specific win, fan, and scoring calculation.

In short: Sichuan flow + Qingque wall + Guobiao/Qingque actions + custom scoring.

Fan and scoring reference: [new_rule_fan_scoring/new_rule_fan_scoring.md](new_rule_fan_scoring/new_rule_fan_scoring.md)

## Settlement Scoring

Use the fan-scoring document's point-transfer formula for each accepted win:

- 0-point legal wins produce no point transfer.
- Discard win: the discarder pays `6X` to the winner.
- Robbing kong: treat as a discard win; the added-kong player pays `6X` to the winner.
- Self-draw:
  - if 3 other non-winning players remain, each pays `2X`;
  - if 2 other non-winning players remain, each pays `3X`;
  - if 1 other non-winning player remains, that player pays `6X`.
- In live blood-battle flow, store these transfers in deferred settlement `score_changes`; do not reveal them during mid-hand win presentation.

## Hidden Backend Test Entry

Use a hidden backend-only room creation route for local smoke testing:

- WebSocket message type: `room/create_NewRule_room`
- Server room rule id: `new_rule`
- Sub-rule id: `new_rule/standard`
- Fixed room fields:
  - `hepai_limit = 0`
  - `open_cuohe = False`
- `hepai_limit` is a compatibility room field only for this route. New-rule win eligibility must be based on `is_win` / completed shape, not on `points > 0`.
- This route is for backend tests only for now.
- Do not add it to normal Unity/client room creation UI until the live loop, reconnect/spectator handling, and final settlement behavior are stable.

## Mid-Hand Win Visibility

Use delayed public information for blood-battle wins:

- Mid-hand win broadcast should only indicate that a player won.
- Do not send the real fan list during mid-hand win presentation. Prefer sending an empty list over `None` if the Unity UI expects a list.
- Do not send the score or score changes during mid-hand win presentation.
- Do not reveal the winner's full hand or combination mask during mid-hand win presentation.
- For self-draw wins, non-winning players should not see the real self-drawn winning tile.
- Store the true fan list, score data, win tile, and hand data server-side for deferred settlement.
- Final settlement should reveal the stored hand, fan list, score, and score changes.

## Multi-Ron Confirmation

Use independent win confirmation for multiple wins from the same discard:

- All players who can win from a discard should see their own `hu` / `pass` choice.
- Each eligible player chooses independently.
- Eligible players respond during the same response window. Do not ask them sequentially one-by-one.
- Click timing must not affect settlement order. After the window closes, accepted winners are sorted by fixed seat order from the discarder: next seat, opposite seat, previous seat.
- Only players who explicitly choose `hu` should enter the accepted winner list.
- Players who choose `pass` should not be included in the win settlement for that discard.
- If at least one eligible player chooses `hu`, settle only those accepted winners.
- If accepted winners do not end the hand, the next draw starts from the seat after the last accepted winner in that fixed seat-sorted list, skipping players who have already won.
- If every eligible player chooses `pass` or times out, continue resolving lower-priority actions such as peng/gang/chi, or continue to the next draw if none exist.
- Exception: if the wall is empty after the discard, do not resolve lower-priority chi/peng/gang. The final discard can only be won; if nobody wins, the hand ends as exhausted wall.
- Chi is seat-relative, not active-player-relative. Only the fixed next seat after the discarder may chi. If that player has already won and exited, the chi opportunity disappears; it does not pass to the next active player.
- Do not reuse Sichuan's current behavior where `sichuan_hu_results` means "all eligible winners are winners".
- Prefer splitting the data into:
  - `available_hu_results`: all eligible win results for this discard, used for buttons and validation.
  - `accepted_hu_results`: only players who actually chose `hu`, used by settlement.
- Implementation notes: [new_rule_multi_ron_implementation.md](new_rule_multi_ron_implementation.md)

## Dealer Rotation

Use fixed dealer rotation like Guobiao/Qingque:

- Advance the dealer every hand.
- Do not repeat dealer on draw.
- Do not set the next dealer to the first winner.
- Do not set the next dealer to the discarder when the first win is a multi-ron.
- Reuse or mirror the Guobiao/Qingque round-advance helpers instead of Sichuan's `_decide_next_dealer`.

## Post-Claim Action Flow

Use forced discard after chi or peng:

- After chi, the claiming player must discard.
- After peng, the claiming player must discard.
- Chi is available only to the fixed next seat after the discarder. It is not reassigned when that seat has already won.
- Do not allow concealed kong immediately after chi or peng.
- Do not allow added kong immediately after chi or peng.
- The forced discard after chi or peng applies the same-tile discard-win lockout replacement rule.
- Chi and peng are not allowed on the final discard after the wall is empty.

Kong flows are different:

- After exposed kong from another player's discard, draw a supplement tile.
- After concealed kong, draw a supplement tile.
- After added kong, allow robbing-kong responses first; if nobody wins, draw a supplement tile.
- After a supplement draw, enter normal hand-action checks, including self-draw win, concealed kong, added kong, and discard.
- Kongs are not allowed on the final discard after the wall is empty.

## Same-Tile Discard-Win Lockout

Use a same-tile lockout for discard wins:

- Track a per-player lockout set, for example `discard_win_locked_tiles`.
- If a player can win from another player's discard but does not choose `hu`, add that discarded tile to the player's lockout set.
- If a player times out on a discard-win opportunity, treat it as not choosing `hu` and add that discarded tile to the lockout set.
- While a tile is in a player's lockout set, that player cannot win by discard on the same tile.
- Self-draw wins are never blocked by this lockout.
- Robbing a kong is treated like a discard win for this rule, so it is blocked if the kong tile is in the player's lockout set.
- The lockout can accumulate multiple tile types before the player's next discard.
- When the player discards any tile, replace the whole lockout set with only that just-discarded tile.
- This means discarding does two things at once:
  - clears all previous lockout tiles;
  - adds the newly discarded tile as the next lockout tile.
- There are no red fives, aka dora, or equivalent special tile ids in this rule, so no tile normalization exception is needed for those cases.
- Do not reuse Sichuan's `shunhe` behavior, because that blocks by skipped fan value and has different activation timing.
- Implementation notes: [new_rule_discard_win_lockout.md](new_rule_discard_win_lockout.md)

## Concealed Kong Visibility

Use the Guobiao/Qingque information-hiding style for concealed kongs:

- The concealed kong owner sees the real kong tile.
- Other players only see that a concealed kong happened.
- Other players should receive a sanitized target such as `G0`, not `G{tile}`.
- Other players should receive sanitized concealed-kong masks where hidden tile ids are replaced with `0`.
- Store the true concealed-kong mask server-side.
- Final settlement should reveal the true concealed-kong tiles.

## Explicitly Excluded

- No Sichuan dingque phase.
- No Sichuan winner-based dealer selection.
- No Sichuan draw-based dealer repeat.
- No Sichuan immediate gang scoring.
- No Sichuan chajiao / tingpai settlement on draw.
- No flower replacement flow.
- No riichi-style dead wall.
- No Guobiao-style configurable `hepai_limit`.
- No `open_cuohe` / false-win penalty path.

## Existing Code To Reuse Or Compare

- Blood-battle flow:
  - `open_mahjong_server/server/gamestate/game_sichuan/SichuanGameState.py`
  - `SichuanPlayer.is_hu`
  - `SichuanPlayer.hu_order`
  - `SichuanGameState._next_active_index`
  - `SichuanGameState._settle_win`
  - `SichuanGameState._settle_liuju`
- Guobiao-like tile/action structure:
  - `open_mahjong_server/server/gamestate/game_guobiao/init_tiles.py`
  - `open_mahjong_server/server/gamestate/game_guobiao/action_check.py`
  - `open_mahjong_server/server/gamestate/game_guobiao/wait_action.py`
- Concealed-kong information hiding:
  - `open_mahjong_server/server/gamestate/game_guobiao/combination_mask_view.py`
  - `open_mahjong_server/server/gamestate/game_guobiao/boardcast.py`
  - `open_mahjong_server/server/gamestate/game_mmcr/boardcast.py`
- Qingque no-flower wall:
  - `open_mahjong_server/server/gamestate/game_mmcr/init_tiles.py`
- Calculation entry points:
  - `open_mahjong_server/server/game_calculation/game_calculation_service.py`

## Implementation Direction

Start from the Sichuan round loop, remove Sichuan-only phases and scoring, then plug in Guobiao/Qingque-like action checks and a no-flower 136-tile initializer.

If the rule's win/fan/scoring logic differs from Guobiao, add new calculation methods rather than overloading `GB_hepai_check`.
