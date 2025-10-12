from dataclasses import dataclass, field
from typing import List, Tuple, Dict, Optional
import random
import itertools
from enum import IntEnum

# ---------- Card & Deck ----------

RANKS = "23456789TJQKA"
SUITS = "♠♥♦♣"  # purely cosmetic for printing


@dataclass(frozen=True, order=True)
class Card:
    rank: str  # one of RANKS
    suit: str  # one of SUITS

    def __post_init__(self):
        if self.rank not in RANKS or self.suit not in SUITS:
            raise ValueError(f"Invalid card: {self.rank}{self.suit}")

    @property
    def rank_value(self) -> int:
        return RANKS.index(self.rank)  # 0..12

    def __str__(self) -> str:
        return f"{self.rank}{self.suit}"


class Deck:
    def __init__(self, seed: Optional[int] = None):
        self.cards: List[Card] = [Card(r, s) for r in RANKS for s in SUITS]
        if seed is not None:
            random.seed(seed)
        random.shuffle(self.cards)

    def deal(self, n: int) -> List[Card]:
        if n > len(self.cards):
            raise ValueError("Not enough cards left to deal")
        out = self.cards[:n]
        self.cards = self.cards[n:]
        return out


# ---------- Hand Evaluation ----------

class HandRank(IntEnum):
    HIGH_CARD = 0
    ONE_PAIR = 1
    TWO_PAIR = 2
    THREE_OF_A_KIND = 3
    STRAIGHT = 4
    FLUSH = 5
    FULL_HOUSE = 6
    FOUR_OF_A_KIND = 7
    STRAIGHT_FLUSH = 8


RANK_NAME = {
    HandRank.HIGH_CARD: "High Card",
    HandRank.ONE_PAIR: "One Pair",
    HandRank.TWO_PAIR: "Two Pair",
    HandRank.THREE_OF_A_KIND: "Three of a Kind",
    HandRank.STRAIGHT: "Straight",
    HandRank.FLUSH: "Flush",
    HandRank.FULL_HOUSE: "Full House",
    HandRank.FOUR_OF_A_KIND: "Four of a Kind",
    HandRank.STRAIGHT_FLUSH: "Straight Flush",
}


def _is_consecutive(values: List[int]) -> bool:
    return all(values[i] - 1 == values[i + 1] for i in range(len(values) - 1))


def _straight_high(values: List[int]) -> Optional[int]:
    """Return highest rank of a straight from given distinct rank values (desc sorted), Ace-low handled."""
    vals = sorted(set(values), reverse=True)
    # Ace-low: treat Ace as 1 (value -13) in an extra pass
    if 12 in vals:  # Ace present
        vals.append(-1)  # Ace as 1 below 2 which is 0
    # scan windows of length 5
    for i in range(len(vals) - 4):
        window = vals[i:i+5]
        if _is_consecutive(window):
            return window[0] if window[0] != -1 else 3  # 5 high straight -> rank value of '5' (which is 3)
    return None


def _cards_by_suit(cards: List[Card]) -> Dict[str, List[Card]]:
    d: Dict[str, List[Card]] = {s: [] for s in SUITS}
    for c in cards:
        d[c.suit].append(c)
    return d


def evaluate_five(cards5: List[Card]) -> Tuple[HandRank, List[int]]:
    """Evaluate exactly 5 cards. Return (rank, tiebreaker list). Higher is better."""
    ranks = sorted([c.rank_value for c in cards5], reverse=True)
    # Ace-low straight handling for 5 cards
    is_flush = len({c.suit for c in cards5}) == 1
    # Straight check
    straight_hi = None
    rset = sorted(set(ranks), reverse=True)
    if len(rset) == 5:
        if _is_consecutive(rset):
            straight_hi = rset[0]
        elif rset == [12, 3, 2, 1, 0]:  # A,5,4,3,2
            straight_hi = 3  # 5-high
    # Multiples
    counts: Dict[int, int] = {}
    for r in ranks:
        counts[r] = counts.get(r, 0) + 1
    # Sort by (count, rank) for kickers
    groups = sorted(((cnt, r) for r, cnt in counts.items()), reverse=True)
    if straight_hi is not None and is_flush:
        return (HandRank.STRAIGHT_FLUSH, [straight_hi])
    if groups[0][0] == 4:
        four = groups[0][1]
        kicker = max(r for r in ranks if r != four)
        return (HandRank.FOUR_OF_A_KIND, [four, kicker])
    if groups[0][0] == 3 and groups[1][0] == 2:
        return (HandRank.FULL_HOUSE, [groups[0][1], groups[1][1]])
    if is_flush:
        return (HandRank.FLUSH, ranks)
    if straight_hi is not None:
        return (HandRank.STRAIGHT, [straight_hi])
    if groups[0][0] == 3:
        trips = groups[0][1]
        kickers = sorted([r for r in ranks if r != trips], reverse=True)
        return (HandRank.THREE_OF_A_KIND, [trips] + kickers[:2])
    if groups[0][0] == 2 and groups[1][0] == 2:
        pair_hi = max(groups[0][1], groups[1][1])
        pair_lo = min(groups[0][1], groups[1][1])
        kicker = max(r for r in ranks if r != pair_hi and r != pair_lo)
        return (HandRank.TWO_PAIR, [pair_hi, pair_lo, kicker])
    if groups[0][0] == 2:
        pair = groups[0][1]
        kickers = [r for r in ranks if r != pair]
        return (HandRank.ONE_PAIR, [pair] + kickers[:3])
    return (HandRank.HIGH_CARD, ranks[:5])


def evaluate_best_7(cards: List[Card]) -> Tuple[HandRank, List[int], List[Card]]:
    """Return best (rank, tiebreakers, best5cards) among all 5-card combos from up to 7 cards."""
    best = None
    best_combo = None
    for combo in itertools.combinations(cards, 5):
        val = evaluate_five(list(combo))
        if (best is None) or (val > best):
            best = val
            best_combo = list(combo)
    assert best is not None and best_combo is not None
    return best[0], best[1], sorted(best_combo, key=lambda c: c.rank_value, reverse=True)


# ---------- Players & Game Flow ----------

@dataclass
class Player:
    name: str
    stack: int = 1000
    hole: List[Card] = field(default_factory=list)
    in_hand: bool = True
    bet: int = 0

    def reset_for_hand(self):
        self.hole.clear()
        self.in_hand = True
        self.bet = 0


class TexasHoldemGame:
    def __init__(self, player_names: List[str], blinds: Tuple[int, int] = (10, 20), seed: Optional[int] = None):
        if not 2 <= len(player_names) <= 9:
            raise ValueError("Texas Hold'em supports 2 to 9 players")
        self.players = [Player(n) for n in player_names]
        self.small_blind, self.big_blind = blinds
        self.button_index = 0
        self.deck = Deck(seed=seed)
        self.board: List[Card] = []
        self.pot: int = 0

    def rotate_button(self):
        self.button_index = (self.button_index + 1) % len(self.players)

    def post_blinds(self):
        sb_idx = (self.button_index + 1) % len(self.players)
        bb_idx = (self.button_index + 2) % len(self.players)
        self._post(self.players[sb_idx], self.small_blind)
        self._post(self.players[bb_idx], self.big_blind)

    def _post(self, player: Player, amount: int):
        post = min(player.stack, amount)
        player.stack -= post
        player.bet += post
        self.pot += post

    def deal_hole(self):
        for p in self.players:
            p.hole = self.deck.deal(2)

    def deal_flop(self):
        _ = self.deck.deal(1)  # burn
        self.board += self.deck.deal(3)

    def deal_turn(self):
        _ = self.deck.deal(1)
        self.board += self.deck.deal(1)

    def deal_river(self):
        _ = self.deck.deal(1)
        self.board += self.deck.deal(1)

    def reset_for_new_hand(self, reseed: Optional[int] = None):
        self.deck = Deck(seed=reseed)
        self.board = []
        self.pot = 0
        for p in self.players:
            p.reset_for_hand()

    def showdown(self) -> Tuple[List[int], Dict[int, Dict]]:
        """Return (winner_indices, detail_by_index). Ties split pot evenly (integer division, remainder ignored)."""
        active = [(i, p) for i, p in enumerate(self.players) if p.in_hand]
        evaluations = {}
        for i, player in active:
            rank, tiebreak, best5 = evaluate_best_7(player.hole + self.board)
            evaluations[i] = {
                "rank": rank,
                "tiebreak": tiebreak,
                "best5": best5,
            }

        def cmp_tuple(info):
            return (info["rank"], info["tiebreak"])

        best_tuple = None
        winners: List[int] = []
        for i, info in evaluations.items():
            t = cmp_tuple(info)
            if best_tuple is None or t > best_tuple:
                best_tuple = t
                winners = [i]
            elif t == best_tuple:
                winners.append(i)

        # split pot
        if winners:
            share = self.pot // len(winners)
            for i in winners:
                self.players[i].stack += share
        return winners, evaluations

    # --- Simplified single-hand run (no betting decisions; everyone checks/calls to showdown) ---
    def play_hand_all_in(self, reseed: Optional[int] = None) -> Dict:
        """Deal one hand where all players automatically go to showdown (core mechanics demo)."""
        self.reset_for_new_hand(reseed=reseed)
        self.post_blinds()
        self.deal_hole()
        self.deal_flop()
        self.deal_turn()
        self.deal_river()
        winners, detail = self.showdown()
        return {
            "board": self.board,
            "winners": winners,
            "detail": detail,
            "pot": self.pot,
        }


# ---------- Pretty Printing ----------

def cards_str(cards: List[Card]) -> str:
    return " ".join(str(c) for c in cards)


def describe_eval(info: Dict) -> str:
    rank = info["rank"]
    tiebreak = info["tiebreak"]
    best5 = info["best5"]
    return f"{RANK_NAME[rank]} ({cards_str(best5)}), tiebreak={tiebreak}"


# ---------- Tiny CLI Demo ----------

DEMO = """
Texas Hold'em Core Demo
-----------------------
This demo deals one hand to N players, runs straight to showdown (no betting),
and prints the winner(s). Use this file as a library to build full betting logic & UI.
"""

def demo_run():
    print(DEMO)
    names = ["Alice", "Bob", "Charlie"]
    game = TexasHoldemGame(names, blinds=(10, 20), seed=42)
    result = game.play_hand_all_in()
    print(f"Board: {cards_str(result['board'])}")
    for i, p in enumerate(game.players):
        print(f"{p.name:8} stack={p.stack:4}  hole={cards_str(p.hole)}  -> {describe_eval(result['detail'][i])}")
    ws = result["winners"]
    if len(ws) == 1:
        print(f"\nWinner: {game.players[ws[0]].name}  (+{result['pot']//len(ws)} chips)")
    else:
        winners = ", ".join(game.players[i].name for i in ws)
        print(f"\nSplit pot between: {winners}  (+{result['pot']//len(ws)} each)")


# ---------- Module entry ----------

if __name__ == "__main__":
    demo_run()
