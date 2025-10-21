# simulate_random_vs_heuristic.py
from Poker_core import TexasHoldemGame, cards_str, evaluate_best_7
import random, csv, time
from collections import defaultdict

# ---------- Helper ----------
def compact(cards):
    """Return a compact string like 'AHKD'."""
    return cards_str(cards).replace(" ", "") if cards else ""

RANKS = "23456789TJQKA"
def rank_index(r): return RANKS.index(r)

def hand_bucket(c1, c2):
    """Return preflop bucket label (AKs, QJo, etc.)."""
    r1, r2 = c1.rank, c2.rank
    s1, s2 = c1.suit, c2.suit
    if rank_index(r1) < rank_index(r2):
        r1, r2, s1, s2 = r2, r1, s2, s1
    suited = "s" if s1 == s2 else ("o" if r1 != r2 else "")
    return f"{r1}{r2}{suited}" if r1 != r2 else f"{r1}{r2}"

# ---------- Bots ----------
class RandomBot:
    """Random-action bot."""
    def __init__(self, name="r_bot"):
        self.name = name
    def preflop_action(self, to_call, stack, bucket):
        roll = random.random()
        if to_call == 0:
            if roll < 0.05: return ("raise", min(40, stack))
            return ("call", 0)
        else:
            if roll < 0.25: return ("fold", 0)
            elif roll < 0.85: return ("call", 0)
            return ("raise", min(30, stack))
    def update(self, bucket, delta): pass

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
        # Slightly more aggressive bias so heuristic wins more often
        if ev < -0.1: return ("fold", 0)
        if ev < 0.3: return ("call", 0)
        return ("raise", min(50, stack))

# ---------- Simulation ----------
def simulate_hand(game, h_bot, r_bot, hand_id):
    game.reset_for_new_hand()
    game.rotate_button()
    game.post_blinds()
    game.deal_hole()

    h, r = game.players
    h.name, r.name = "h_bot", "r_bot"
    h_bucket = hand_bucket(*h.hole)
    r_bucket = hand_bucket(*r.hole)
    actions = {}

    # Preflop betting
    for p, bucket, bot in [(h, h_bucket, h_bot), (r, r_bucket, r_bot)]:
        to_call = max(0, game.big_blind - p.bet)
        act, amt = bot.preflop_action(to_call, p.stack, bucket)
        actions[p.name] = act
        if act == "fold":
            p.folded = True
        elif act == "call":
            call_amt = min(to_call, p.stack)
            p.stack -= call_amt
            p.bet += call_amt
            game.pot += call_amt
        elif act == "raise":
            pay = min(to_call + amt, p.stack)
            p.stack -= pay
            p.bet += pay
            game.pot += pay
            game.big_blind = p.bet

    board = ""
    winners = []
    win_type = ""

    active = [p for p in [h, r] if not getattr(p, "folded", False)]
    if len(active) == 1:
        w = active[0]
        w.stack += game.pot
        winners = [w.name]
        win_type = "fold"
    else:
        game.deal_flop()
        game.deal_turn()
        game.deal_river()
        board = compact(game.board)
        ranks = {p.name: evaluate_best_7(p.hole + game.board) for p in [h, r]}
        best2 = max(v[:2] for v in ranks.values())
        winners = [n for n, v in ranks.items() if v[:2] == best2]
        share = game.pot // len(winners)
        for w in winners:
            if w == "h_bot": h.stack += share
            else: r.stack += share
        win_type = "showdown" if len(winners) == 1 else "split"

    h_bot.update(h_bucket, h.stack - 1000)
    r_bot.update(r_bucket, r.stack - 1000)

    row = {
        "HandID": hand_id,
        "Board": board,
        "Winner": "|".join(winners),
        "WinType": win_type,
        "Pot": game.pot,
        "h_Hole": compact(h.hole),
        "r_Hole": compact(r.hole),
        "h_Bucket": h_bucket,
        "r_Bucket": r_bucket,
        "h_Action": actions.get("h_bot", ""),
        "r_Action": actions.get("r_bot", ""),
        "h_Delta": round(h.stack - 1000, 1),
        "r_Delta": round(r.stack - 1000, 1),
    }
    return row, winners

# ---------- Driver ----------
def run_sim(hands=10000, outfile="Poker_game/results_random_vs_heuristic.csv", seed=None):
    if seed is None:
        seed = int(time.time())
    random.seed(seed)
    game = TexasHoldemGame(["h_bot", "r_bot"], blinds=(10, 20))
    h_bot = HeuristicBot("h_bot")
    r_bot = RandomBot("r_bot")
    wins = defaultdict(int)

    headers = [
        "HandID","Board","Winner","WinType","Pot",
        "h_Hole","r_Hole","h_Bucket","r_Bucket",
        "h_Action","r_Action","h_Delta","r_Delta"
    ]

    with open(outfile, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=headers)
        w.writeheader()
        for i in range(1, hands + 1):
            row, winners = simulate_hand(game, h_bot, r_bot, i)
            w.writerow(row)
            for nm in winners:
                wins[nm] += 1
            if i % 1000 == 0:
                print(f"[{i}/{hands}] -> h_bot: {wins['h_bot']}, r_bot: {wins['r_bot']}")

    print("\n✅ Results for Random vs Heuristic:")
    print(f"  h_bot (Heuristic): {wins['h_bot']}")
    print(f"  r_bot (Random):    {wins['r_bot']}")
    print(f"CSV saved as: {outfile}")
    print("Expected: Heuristic > Random")

if __name__ == "__main__":
    run_sim()
