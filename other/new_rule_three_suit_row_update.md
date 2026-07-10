# New Rule: Three-Suit-Number Row Update

## Change

The `二色同刻` / `小三色同刻` / `三色同顺` / `三色同刻` row no longer keeps only one matching pattern for the entire row. It now scores the highest total of patterns that use non-overlapping resolved winning-structure units.

A unit is one resolved sequence, triplet, declared kong, or the resolved pair. A unit may participate in at most one pattern in this row.

All other fan rows retain the existing rule: only the highest matching pattern in that row scores.

## Example

`222万 222饼 22条 333万 333饼` has two disjoint groups:

- `222万 + 222饼 + 22条`: `小三色同刻`, 3 points.
- `333万 + 333饼`: `二色同刻`, 1 point.

The row therefore contributes 4 points.

This hand can still reach the 20-point cap through other fans, so the change may affect its displayed fan list without changing its final payment. It changes payment whenever the hand is below the cap.

## Constraints

- Do not reuse a triplet, kong, sequence, or pair in two patterns from this row.
- Do not greedily select the highest single pattern; select the valid non-overlapping set with the highest total.
- Evaluate unit assignment inside each resolved decomposition, then choose the highest-scoring decomposition for the hand.
- An undeclared four-of-a-kind is not a triplet/kong unit for this purpose.

## Implementation and tests

The current detector produces same-number patterns from the resolved structure, so a high and low pattern for the same number are not emitted together. Row scoring preserves multiple occurrences in this row when they are therefore disjoint; this covers `小三色同刻 + 二色同刻` and repeated `二色同刻`.

Regression coverage is in `open_mahjong_server/server/game_calculation/new_rule/test_new_rule_scoring.py` and the service-level smoke test.
