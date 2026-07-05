# New Rule Discard-Win Lockout Notes

## Rule Summary

This rule uses same-tile discard-win lockout.

- Each active player has a lockout set, for example `discard_win_locked_tiles`.
- A player cannot win by discard on a tile that is currently in that player's lockout set.
- Self-draw wins ignore this lockout.
- Robbing a kong is treated like a discard win and is blocked by the same lockout.
- The lockout can accumulate multiple tile types.
- When a player discards any tile, replace that player's whole lockout set with only the just-discarded tile.
- There are no red fives, aka dora, or equivalent special tile ids in this rule.

## State Updates

When a player discards a tile:

- Clear all existing locked tiles for that player.
- Add the just-discarded tile.
- This applies to normal draw-discard, chi/peng follow-up discard, and any post-kong discard.

When another player discards a tile and a player can win but does not choose `hu`:

- Add that discarded tile to the non-winning player's lockout set.
- Timeout counts as not choosing `hu`.
- Choosing a lower-priority action instead of `hu` also counts as not choosing `hu`, if that lower-priority action is allowed to resolve.

When a player self-draws:

- Do not check the lockout.
- If the player wins by self-draw, the player exits the hand.
- If the player does not win and later discards a tile, the discard replacement rule applies.

When a player wins by discard or robbing a kong:

- The winner exits the hand.
- The winner does not need any further lockout updates for this hand.

## Interaction With Blood-Battle Wins

Winning players and non-winning players must be handled separately:

- Players who choose `hu` become accepted winners and exit the hand.
- Players who could win but choose `pass`, time out, or otherwise do not choose `hu` stay in the hand and record the tile as locked.
- Accepted winners should not be added to the lockout list for that winning tile.
- Do not clear every player's lockout state when someone wins.
- Non-winning active players carry their lockout state into continued blood-battle play.
- A winning player's old lockout state can be ignored after `is_hu=True`.

Example:

- B discards 5m.
- A, C, and D can all win.
- A chooses `hu`; C chooses `pass`; D times out.
- A exits the hand.
- C records 5m in `discard_win_locked_tiles`.
- D records 5m in `discard_win_locked_tiles`.
- B's own discard replacement rule has already made B's lockout set `{5m}`.
- Play continues from the next active player after the final accepted winner.

## Interaction With Multi-Ron

This lockout depends on independent multi-ron confirmation.

- Keep `available_hu_results` separate from `accepted_hu_results`.
- `available_hu_results` contains every player who could legally win before confirmation.
- `accepted_hu_results` contains only players who explicitly chose `hu`.
- After the response window closes, add the tile to every available winner who is not in `accepted_hu_results`.
- Then settle only `accepted_hu_results`.

Do not reuse Sichuan's current meaning of `sichuan_hu_results`, because in that implementation all eligible winners are treated as winners once the win is triggered.

## Interaction With Robbing A Kong

Robbing a kong should use the same lockout check as discard wins.

- If the kong tile is in a player's lockout set, do not offer that player `hu`.
- If the player can rob the kong but chooses `pass` or times out, add the kong tile to the lockout set.
- If at least one player robs the kong, settle only the accepted robbing winners.
- If nobody accepts the robbing win, the kong proceeds normally.

## Recommended Check Order

For a discard:

1. Player discards tile `T`.
2. Replace discarder lockout set with `{T}`.
3. Calculate raw discard-win eligibility for other active players.
4. Filter out players whose lockout set contains `T`.
5. Ask remaining eligible players for `hu` / `pass`.
6. After the response window, add `T` to every eligible player who did not choose `hu`.
7. Settle accepted winners, if any.
8. If nobody won, continue lower-priority actions or move to the next draw.

Final-discard exception:

- If the wall is empty after the discard, do not offer chi, peng, or kong.
- The final discard can only be won by discard win.
- If all eligible players pass, time out, or are blocked by lockout, the hand ends by exhausted wall.
- The same lockout update rules still apply to players who had a legal discard-win opportunity on the final discard but did not choose `hu`.

For robbing a kong:

1. Player attempts to add a kong with tile `T`.
2. Calculate raw robbing eligibility for other active players.
3. Filter out players whose lockout set contains `T`.
4. Ask remaining eligible players for `hu` / `pass`.
5. After the response window, add `T` to every eligible player who did not choose `hu`.
6. If accepted winners exist, cancel/revert the kong and settle those winners.
7. If no accepted winners exist, complete the kong flow.

## Implementation Notes

Prefer a small rule helper instead of reusing Sichuan `shunhe`.

Possible helper functions:

- `replace_lockout_on_discard(player, tile)`
- `add_lockout_for_skipped_win(player, tile)`
- `is_discard_win_locked(player, tile)`
- `clear_lockout_for_round_reset(player)`

Reset the lockout at the start of each hand. Also ignore the lockout for players marked `is_hu=True`.
