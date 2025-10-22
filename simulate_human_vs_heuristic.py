# simulate_human_vs_heuristic.py
from Poker_core import TexasHoldemGame, cards_str, evaluate_best_7
from Poker_game import betting_round
import csv, random, time
from collections import defaultdict, deque

# ---------- Helpers ----------
RANKS = "23456789TJQKA"
def compact(cards): return cards_str(cards).replace(" ", "") if cards else ""
def r_idx(r): return RANKS.index(r)
def board_str(game): return cards_str(game.board) if game.board else "[]"

def hand_bucket(c1, c2):
    """Preflop bucket label like AKs / QJo / 77."""
    r1, r2 = c1.rank, c2.rank
    s1, s2 = c1.suit, c2.suit
    if r_idx(r1) < r_idx(r2):
        r1, r2, s1, s2 = r2, r1, s2, s1
    suited = "s" if s1 == s2 else ("o" if r1 != r2 else "")
    return f"{r1}{r2}{suited}" if r1 != r2 else f"{r1}{r2}"

def bucket_strength(bucket: str) -> float:
    """Rough preflop strength in [0,1] for bluff detection & heuristics."""
    ranks_map = {r:i for i,r in enumerate(RANKS, start=2)}
    if len(bucket) == 2:  # pair
        return (ranks_map[bucket[0]] - 2) / 12
    hi, lo = ranks_map[bucket[0]], ranks_map[bucket[1]]
    suited = 0.08 if bucket.endswith("s") else 0.0
    connect = 0.05 if abs(hi - lo) == 1 else 0.0
    broad   = 0.08 if (hi >= 11 and lo >= 10) else 0.0
    base = (hi - 2) / 12 * 0.6 + (lo - 2) / 12 * 0.2
    return min(1.0, base + suited + connect + broad)

def is_weak_bucket(b): return bucket_strength(b) < 0.35

# ---------- Heuristic Bot ----------
class HeuristicBot:
    """Simple EV-based bot that improves its preflop evaluation."""
    def __init__(self, name="h_bot", bb=20):
        self.name = name
        self.bb = bb
        self.stats = defaultdict(lambda: {"n": 0, "ev": 0.0})
    def _ev(self, b): return self.stats[b]["ev"]
    def update(self, b, delta):
        rec = self.stats[b]; rec["n"] += 1
        bb_delta = delta / self.bb
        rec["ev"] += (bb_delta - rec["ev"]) / rec["n"]
    def preflop_action(self, to_call, stack, b):
        ev = self._ev(b)
        if ev < -0.1: return ("fold", 0)
        if ev < 0.35: return ("call", 0)
        return ("raise", min(40, stack))
    def postflop_action(self, to_call, stack):
        return ("check", 0) if to_call == 0 else ("call", 0)

# ---------- Hand summary (per-hand) & classification (last 5 hands) ----------
class HandSummary:
    def __init__(self):
        self.raised=False; self.called=False; self.checked=False; self.folded=False
    def label(self):
        if self.raised: return "raise"
        if self.called: return "call"
        if self.folded: return "fold"
        return "check"

class AggressionTracker:
    def __init__(self):
        self.last_human_action = ""
        self.history = deque(maxlen=5)  # last 5 hand labels
        self.category = ""              # Aggressive/Passive
    def record_action(self, act):
        self.last_human_action = act
    def record_hand(self, hand_label):
        self.history.append(hand_label)
        if len(self.history) == 5:
            raises = sum(1 for x in self.history if x == "raise")
            calls  = sum(1 for x in self.history if x == "call")
            folds  = sum(1 for x in self.history if x == "fold")
            checks = sum(1 for x in self.history if x == "check")
            total  = raises + calls + folds + checks
            # Weighted aggression score: raises count double
            ratio  = (raises*2 + calls) / max(1, total + raises)
            self.category = "Aggressive" if ratio > 0.6 else "Passive"
        else:
            self.category = ""
        return self.category

# ---------- Round state for dynamic min-raise ----------
class RoundState:
    def __init__(self, big_blind):
        self.big_blind = big_blind
        self.last_raise_size = big_blind  # per street: reset to BB
    def min_raise(self, to_call):
        # No-Limit rule: if facing a bet, min raise equals last raise size; if not, min bet = BB
        return self.last_raise_size if to_call > 0 else self.big_blind

# ---------- Action adapters (print state, validate raises, track behavior) ----------
def make_human_action_fn(game, tracker: AggressionTracker, round_state: RoundState, hand_summary: HandSummary):
    def fn(player, current_bet):
        to_call = max(0, current_bet - player.bet)
        print(f"🃏 Pot={game.pot} | Board={board_str(game)} | to_call={to_call} | {player.name} stack={player.stack}")
        mv = input("Your move? (fold/call/check/raise): ").strip().lower()
        if mv not in ("fold","call","check","raise"):
            mv = "call"
        tracker.record_action(mv)
        if mv == "raise":
            min_amt = round_state.min_raise(to_call)
            max_amt = max(0, player.stack - to_call)
            while True:
                try:
                    amt = int(input(f"Enter raise amount (min {min_amt}, max {max_amt}): "))
                except ValueError:
                    print("❌ Invalid number. Try again."); continue
                if amt < min_amt:
                    print(f"❌ Invalid raise — minimum is {min_amt}."); continue
                if amt > max_amt:
                    print(f"❌ Invalid raise — maximum is {max_amt}."); continue
                break
            round_state.last_raise_size = amt
            hand_summary.raised = True
            return mv, amt
        # non-raise bookkeeping
        if mv == "call": hand_summary.called = True
        elif mv == "check": hand_summary.checked = True
        elif mv == "fold": hand_summary.folded = True
        return mv, 0
    return fn

def make_heuristic_action_fn(game, bot: HeuristicBot, preflop: bool, b_bucket: str, round_state: RoundState):
    def fn(player, current_bet):
        to_call = max(0, current_bet - player.bet)
        print(f"🃏 Pot={game.pot} | Board={board_str(game)} | to_call={to_call} | {player.name} stack={player.stack}")
        act, amt = (bot.preflop_action(to_call, player.stack, b_bucket) if preflop
                    else bot.postflop_action(to_call, player.stack))
        if act == "raise":
            min_amt = round_state.min_raise(to_call)
            max_amt = max(0, player.stack - to_call)
            amt = max(min_amt, min(amt, max_amt))
            round_state.last_raise_size = amt
        print(f"→ {player.name} chooses {act}{'' if act!='raise' else f' {amt}'}")
        return act, amt
    return fn

# ---------- CSV writer ----------
def write_row(writer, hand_id, board, winner, win_type, game, human, opp, h_bucket, b_bucket, tracker, hand_summary):
    bluff = "Yes" if (tracker.last_human_action == "raise" and is_weak_bucket(h_bucket)) else "No"
    row = {
        "HandID": hand_id,
        "Board": board,
        "Winner": winner,
        "WinType": win_type,
        "Pot": game.pot,
        "human_Hole": compact(human.hole),
        "bot_Hole": compact(opp.hole),
        "human_Bucket": h_bucket,
        "bot_Bucket": b_bucket,
        "human_Action": tracker.last_human_action,
        "bot_Action": "",
        "human_Delta": round(human.stack - 1000, 1),
        "bot_Delta": round(opp.stack - 1000, 1),
        "PlayerCategory": tracker.category or "",
        "BluffDetected": bluff
    }
    writer.writerow(row)
    if bluff == "Yes":
        print(f"⚠️ Possible bluff detected: human raised with weak bucket ({h_bucket})")

# ---------- One full hand ----------
def play_hand(game, bot: HeuristicBot, tracker: AggressionTracker, hand_id: int, writer):
    game.reset_for_new_hand()
    game.rotate_button()
    game.post_blinds()
    game.deal_hole()

    human, opp = game.players
    human.name, opp.name = "human", "h_bot"
    h_bucket = hand_bucket(*human.hole)
    b_bucket = hand_bucket(*opp.hole)

    print("\n=== New Hand ===")
    print("Your hole cards:", compact(human.hole), f"(bucket {h_bucket})")

    hand_summary = HandSummary()

    # --- Preflop ---
    print("\n--- Preflop ---")
    pre_state = RoundState(game.big_blind)
    action_fn = lambda p, cb: (make_human_action_fn(game, tracker, pre_state, hand_summary)(p, cb)
                               if p.name=="human"
                               else make_heuristic_action_fn(game, bot, True, b_bucket, pre_state)(p, cb))
    betting_round(game, game.big_blind, action_fn)
    active = [p for p in game.players if getattr(p, "in_hand", True)]
    if len(active) == 1:
        w = active[0]; w.stack += game.pot
        print(f"Winner: {w.name} (by fold) | Pot={game.pot}")
        tracker.record_hand(hand_summary.label())
        return write_row(writer, hand_id, "", w.name, "fold", game, human, opp, h_bucket, b_bucket, tracker, hand_summary)

    # --- Flop ---
    game.deal_flop(); print("Flop :", cards_str(game.board))
    flop_state = RoundState(game.big_blind)
    action_fn = lambda p, cb: (make_human_action_fn(game, tracker, flop_state, hand_summary)(p, cb)
                               if p.name=="human"
                               else make_heuristic_action_fn(game, bot, False, b_bucket, flop_state)(p, cb))
    betting_round(game, 0, action_fn)
    active = [p for p in game.players if getattr(p, "in_hand", True)]
    if len(active) == 1:
        w = active[0]; w.stack += game.pot
        print(f"Winner: {w.name} (by fold) | Pot={game.pot}")
        tracker.record_hand(hand_summary.label())
        return write_row(writer, hand_id, compact(game.board), w.name, "fold", game, human, opp, h_bucket, b_bucket, tracker, hand_summary)

    # --- Turn ---
    game.deal_turn(); print("Turn :", cards_str(game.board))
    turn_state = RoundState(game.big_blind)
    action_fn = lambda p, cb: (make_human_action_fn(game, tracker, turn_state, hand_summary)(p, cb)
                               if p.name=="human"
                               else make_heuristic_action_fn(game, bot, False, b_bucket, turn_state)(p, cb))
    betting_round(game, 0, action_fn)
    active = [p for p in game.players if getattr(p, "in_hand", True)]
    if len(active) == 1:
        w = active[0]; w.stack += game.pot
        print(f"Winner: {w.name} (by fold) | Pot={game.pot}")
        tracker.record_hand(hand_summary.label())
        return write_row(writer, hand_id, compact(game.board), w.name, "fold", game, human, opp, h_bucket, b_bucket, tracker, hand_summary)

    # --- River ---
    game.deal_river(); print("River:", cards_str(game.board))
    river_state = RoundState(game.big_blind)
    action_fn = lambda p, cb: (make_human_action_fn(game, tracker, river_state, hand_summary)(p, cb)
                               if p.name=="human"
                               else make_heuristic_action_fn(game, bot, False, b_bucket, river_state)(p, cb))
    betting_round(game, 0, action_fn)
    active = [p for p in game.players if getattr(p, "in_hand", True)]
    if len(active) == 1:
        w = active[0]; w.stack += game.pot
        print(f"Winner: {w.name} (by fold) | Pot={game.pot}")
        tracker.record_hand(hand_summary.label())
        return write_row(writer, hand_id, compact(game.board), w.name, "fold", game, human, opp, h_bucket, b_bucket, tracker, hand_summary)

    # --- Showdown ---
    ranks = {p.name: evaluate_best_7(p.hole + game.board) for p in [human, opp]}
    best2 = max(v[:2] for v in ranks.values())
    winners = [n for n, v in ranks.items() if v[:2] == best2]
    share = game.pot // len(winners)
    for wn in winners:
        if wn == "human": human.stack += share
        else: opp.stack += share
    names = ", ".join(winners)
    win_type = "showdown" if len(winners) == 1 else "split"
    print(f"Winner: {names} ({win_type}) | Pot={game.pot} | Board={cards_str(game.board)}")
    tracker.record_hand(hand_summary.label())
    write_row(writer, hand_id, compact(game.board), "|".join(winners), win_type, game, human, opp, h_bucket, b_bucket, tracker, hand_summary)

# ---------- Driver ----------
def run(hands=20, outfile="human_vs_heuristic.csv", seed=None):
    if seed is None: seed = int(time.time())
    random.seed(seed)
    game = TexasHoldemGame(["human","h_bot"], blinds=(10,20))
    bot = HeuristicBot()
    tracker = AggressionTracker()

    headers = ["HandID","Board","Winner","WinType","Pot",
               "human_Hole","bot_Hole","human_Bucket","bot_Bucket",
               "human_Action","bot_Action","human_Delta","bot_Delta",
               "PlayerCategory","BluffDetected"]
    with open(outfile, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=headers)
        w.writeheader()
        for i in range(1, hands+1):
            play_hand(game, bot, tracker, i, w)
    print(f"\n✅ Saved: {outfile}")

if __name__ == "__main__":
    run()
