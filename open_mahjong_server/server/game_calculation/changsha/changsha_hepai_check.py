"""Changsha Mahjong win check and base-score helpers.

Rules implemented for the first Salasasa integration:
- 108 suited tiles only: wan 11-19, tong 21-29, tiao 31-39.
- Small hu requires a normal 4 sets + pair shape whose pair is 2/5/8.
- Big hu accepts any winning shape and detects pengpenghu, jiangjianghu,
  qingyise, quanqiuren, seven pairs, luxury seven pairs, and context wins.
- Score base: small hu 1, big hu 6 per big pattern, dealer-related big hu 7.
  Birds and payer selection are handled by the gamestate layer.
"""
from typing import Dict, Iterable, List, Tuple


VALID_TILES = tuple(
    list(range(11, 20)) + list(range(21, 30)) + list(range(31, 40))
)
JIANG_RANKS = {2, 5, 8}

BIG_HU_NAMES = {
    "碰碰胡",
    "将将胡",
    "清一色",
    "全求人",
    "七小对",
    "豪华七小对",
    "天胡",
    "地胡",
    "海底",
    "杠上开花",
    "杠上炮",
    "抢杠胡",
}

INITIAL_HU_NAMES = {
    "siXi": "四喜",
    "banBanHu": "板板胡",
    "queYiSe": "缺一色",
    "liuLiuShun": "六六顺",
    "sanTong": "三同",
}


def _rank(tile: int) -> int:
    return tile % 10


def _suit(tile: int) -> int:
    return tile // 10


def _is_jiang(tile: int) -> bool:
    return _rank(tile) in JIANG_RANKS


def _count_tiles(tiles: Iterable[int]) -> Dict[int, int]:
    counts: Dict[int, int] = {}
    for tile in tiles:
        counts[tile] = counts.get(tile, 0) + 1
    return counts


def evaluate_changsha_initial_hu(tiles: List[int]) -> List[str]:
    counts = _count_tiles(tiles)
    if not counts or any(tile not in VALID_TILES for tile in tiles):
        return []

    result: List[str] = []
    if any(count == 4 for count in counts.values()):
        result.append(INITIAL_HU_NAMES["siXi"])
    if all(not _is_jiang(tile) for tile in tiles):
        result.append(INITIAL_HU_NAMES["banBanHu"])
    if len({_suit(tile) for tile in tiles}) < 3:
        result.append(INITIAL_HU_NAMES["queYiSe"])
    if sum(1 for count in counts.values() if count >= 3) >= 2:
        result.append(INITIAL_HU_NAMES["liuLiuShun"])
    if any(
        all(counts.get(suit * 10 + rank, 0) >= 2 for suit in (1, 2, 3))
        for rank in range(1, 10)
    ):
        result.append(INITIAL_HU_NAMES["sanTong"])
    return result


def _expand_meld(comb: str) -> List[int]:
    if not comb:
        return []
    sign = comb[0]
    try:
        tile = int(comb[1:])
    except ValueError:
        return []
    if sign in ("g", "G"):
        return [tile] * 4
    if sign in ("k", "K"):
        return [tile] * 3
    if sign in ("s", "S"):
        return [tile - 1, tile, tile + 1]
    if sign == "q":
        return [tile] * 2
    return []


def _expand_all(hand_list: List[int], tiles_combination: List[str]) -> List[int]:
    tiles = list(hand_list)
    for comb in tiles_combination:
        tiles.extend(_expand_meld(comb))
    return tiles


def _first_remaining(counts: Dict[int, int]):
    for tile in sorted(counts):
        if counts.get(tile, 0) > 0:
            return tile
    return None


def _decrement(counts: Dict[int, int], tile: int, amount: int) -> None:
    next_count = counts.get(tile, 0) - amount
    if next_count <= 0:
        counts.pop(tile, None)
    else:
        counts[tile] = next_count


def _can_form_sets(counts: Dict[int, int], sets_needed: int, triplets_only: bool = False) -> bool:
    if sets_needed == 0:
        return all(v == 0 for v in counts.values())

    tile = _first_remaining(counts)
    if tile is None:
        return False

    if counts.get(tile, 0) >= 3:
        triplet_counts = dict(counts)
        _decrement(triplet_counts, tile, 3)
        if _can_form_sets(triplet_counts, sets_needed - 1, triplets_only):
            return True

    if triplets_only:
        return False

    if tile in VALID_TILES and _rank(tile) <= 7:
        sequence = (tile, tile + 1, tile + 2)
        if all(_suit(t) == _suit(tile) and counts.get(t, 0) > 0 for t in sequence):
            seq_counts = dict(counts)
            for seq_tile in sequence:
                _decrement(seq_counts, seq_tile, 1)
            if _can_form_sets(seq_counts, sets_needed - 1, triplets_only):
                return True

    return False


def _is_standard_shape(hand_list: List[int], tiles_combination: List[str], *, jiang_pair: bool = False) -> bool:
    sets_needed = 4 - len(tiles_combination)
    if sets_needed < 0 or len(hand_list) != sets_needed * 3 + 2:
        return False
    counts = _count_tiles(hand_list)
    for tile, count in list(counts.items()):
        if count < 2:
            continue
        if jiang_pair and not _is_jiang(tile):
            continue
        remaining = dict(counts)
        _decrement(remaining, tile, 2)
        if _can_form_sets(remaining, sets_needed):
            return True
    return False


def _is_all_triplets(hand_list: List[int], tiles_combination: List[str]) -> bool:
    if any(comb and comb[0] in ("s", "S") for comb in tiles_combination):
        return False
    sets_needed = 4 - len(tiles_combination)
    if sets_needed < 0 or len(hand_list) != sets_needed * 3 + 2:
        return False
    counts = _count_tiles(hand_list)
    for tile, count in list(counts.items()):
        if count < 2:
            continue
        remaining = dict(counts)
        _decrement(remaining, tile, 2)
        if _can_form_sets(remaining, sets_needed, triplets_only=True):
            return True
    return False


def _seven_pairs_type(hand_list: List[int], tiles_combination: List[str]) -> str:
    if tiles_combination or len(hand_list) != 14:
        return "none"
    counts = list(_count_tiles(hand_list).values())
    if not counts or any(c not in (2, 4) for c in counts):
        return "none"
    if sum(c // 2 for c in counts) != 7:
        return "none"
    return "luxury" if any(c == 4 for c in counts) else "normal"


def _has_winning_shape(hand_list: List[int], tiles_combination: List[str]) -> bool:
    return (
        _is_standard_shape(hand_list, tiles_combination, jiang_pair=False)
        or _seven_pairs_type(hand_list, tiles_combination) != "none"
    )


def _all_jiang_tiles(all_tiles: List[int]) -> bool:
    return bool(all_tiles) and all(_is_jiang(tile) for tile in all_tiles)


def _is_flush(all_tiles: List[int]) -> bool:
    suits = {_suit(tile) for tile in all_tiles}
    return len(suits) == 1


def _is_quanqiuren(hand_list: List[int], tiles_combination: List[str], way_to_hepai: List[str]) -> bool:
    zimo_tokens = {"自摸", "杠上开花", "杠上花", "天胡"}
    return len(hand_list) == 2 and len(tiles_combination) == 4 and not any(t in way_to_hepai for t in zimo_tokens)


def _append_context_fans(names: List[str], has_shape: bool, way_to_hepai: List[str]) -> None:
    if not has_shape:
        return
    token_to_name = (
        (("天胡", "天和"), "天胡"),
        (("地胡", "地和"), "地胡"),
        (("海底", "海底捞月", "海底漫游"), "海底"),
        (("杠上开花", "杠上花"), "杠上开花"),
        (("杠上炮",), "杠上炮"),
        (("抢杠胡", "抢杠和", "抢杠"), "抢杠胡"),
    )
    for tokens, fan_name in token_to_name:
        if fan_name not in names and any(token in way_to_hepai for token in tokens):
            names.append(fan_name)


def changsha_base_from_fans(fan_list: List[str], dealer_related: bool = False) -> int:
    """Return one payer's base payment before bird multipliers."""
    if not fan_list:
        return 0
    big_count = sum(1 for name in fan_list if name in BIG_HU_NAMES)
    if big_count > 0:
        return (7 if dealer_related else 6) * big_count
    if "小胡" in fan_list:
        return 2 if dealer_related else 1
    return 0


class Changsha_Hepai_Check:
    def __init__(self, debug: bool = False):
        self.debug = debug

    def hepai_check(
        self,
        hand_list: List[int],
        tiles_combination: List[str],
        way_to_hepai: List[str],
        get_tile: int,
    ) -> Tuple[int, List[str]]:
        concealed = list(hand_list)
        melds = list(tiles_combination)
        ways = list(way_to_hepai or [])
        all_tiles = _expand_all(concealed, melds)

        if any(tile not in VALID_TILES for tile in all_tiles):
            return 0, []

        small_hu = _is_standard_shape(concealed, melds, jiang_pair=True)
        has_shape = _has_winning_shape(concealed, melds)
        big_names: List[str] = []

        if has_shape and _is_all_triplets(concealed, melds):
            big_names.append("碰碰胡")
        if has_shape and _all_jiang_tiles(all_tiles):
            big_names.append("将将胡")
        if has_shape and _is_flush(all_tiles):
            big_names.append("清一色")
        if has_shape and _is_quanqiuren(concealed, melds, ways):
            big_names.append("全求人")

        seven_pairs = _seven_pairs_type(concealed, melds)
        if seven_pairs == "normal":
            big_names.append("七小对")
        elif seven_pairs == "luxury":
            big_names.append("豪华七小对")

        _append_context_fans(big_names, has_shape, ways)

        if big_names:
            return changsha_base_from_fans(big_names), big_names
        if small_hu:
            return changsha_base_from_fans(["小胡"]), ["小胡"]
        return 0, []
