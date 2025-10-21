# simulate_cfr_vs_heuristic.py
from Poker_core import TexasHoldemGame, cards_str, evaluate_best_7
from cfr_holdem import HoldemCFR
import random, csv, os, time
from collections import defaultdict

# ---------- Utility helpers ----------
def compact(cards):
    """Return a compact string of cards (e.g., 'AHKD'), no spaces/commas."""
    return cards_str(cards).replace(" ", "") if cards else ""

RANKS = "23456789TJQKA"
def rank_index(r): return RANKS.index(r)

def hand_bucket(c1, c2):
    """Return a simplified hand bucket such as 'AKs' or 'QJo' or '77'."""
    r1, r2 = c1.rank, c2.rank
    s1, s2 = c1.suit, c2.suit
    if rank_index(r1) < rank_index(r2):
        r1, r2, s1, s2 = r2, r1, s2, s1
    suited = "s" if s1 == s2 else ("o" if r1 != r2 else "")
    return f"{r1}{r2}{suited}" if r1 != r2 else f"{r1}{r2}"

# ---------- Bot definitions ----------
class HeuristicBot:
    """Adaptive heuristic that learns EV per bucket."""
    def __init__(self, name="h_bot", bb=20):
        self.name = name
        self.bb = bb
        self.stats = defaultdict(lambda: {"n": 0, "ev": 0.0})

    def _ev(self, bucket):
        return self.stats[bucket]["ev"]

    def update(self, bucket, delta):
        rec = self.stats[bucket]
        rec["n"] += 1
        bb_delta = delta / self.bb
        rec["ev"] += (bb_delta - rec["ev"]) / rec["n"]

    def preflop_action(self, to_call, stack, bucket):
        ev = self._ev(bucket)
        if ev < -0.2:
            return ("fold", 0)
        if ev < 0.4:
            return ("call", 0)
        return ("raise", min(40, stack))

class CFRBot:
    """CFR-driven bot that follows learned strategy and keeps training."""
    def __init__(self, name="cfr_bot", trainer=None, explore=0.15):
        self.name = name
        self.trainer = trainer
        self.explore = explore  # exploration rate

    def preflop_action(self, to_call, stack, bucket):
        s = self.trainer.strategy(bucket)
        # Exploration: occasionally take random action
        if random.random() < self.explore:
            return random.choice([("fold", 0), ("call", 0), ("raise", min(40, stack))])

        # Normalize when no call required
        if to_call == 0:
            # ignore fold prob
            s_no_fold = [0.0, s[1], s[2]]
            total = s_no_fold[1] + s_no_fold[2]
            s = [0.0, s_no_fold[1] / total, s_no_fold[2] / total] if total > 0 else [0.0, 0.5, 0.5]

        r = random.random()
        if r < s[0]:
            return ("fold", 0)
        elif r < s[0] + s[1]:
            return ("call", 0)
        else:
            return ("raise", min(40, stack))

    def update(self, bucket, delta):
        # amplify learning; use slight randomness to avoid saturation
        noise = random.uniform(0.8, 1.2)
        self.trainer.train_once(bucket, delta * 5.0 * noise)

# ---------- Core hand simulation ----------
def simulate_hand(game, h_bot, cfr_bot, hand_id):
    game.reset_for_new_hand()
    game.rotate_button()
    game.post_blinds()
    game.deal_hole()

    h, c = game.players
    h.name, c.name = "h_bot", "cfr_bot"

    h_bucket = hand_bucket(*h.hole)
    c_bucket = hand_bucket(*c.hole)
    actions = {}

    # --- Preflop betting round ---
    for p, bucket, bot in [(h, h_bucket, h_bot), (c, c_bucket, cfr_bot)]:
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

    active = [p for p in [h, c] if not getattr(p, "folded", False)]
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
        ranks = {p.name: evaluate_best_7(p.hole + game.board) for p in [h, c]}
        best2 = max(v[:2] for v in ranks.values())
        winners = [n for n, v in ranks.items() if v[:2] == best2]
        share = game.pot // len(winners)
        for w in winners:
            if w == "h_bot": h.stack += share
            else: c.stack += share
        win_type = "showdown" if len(winners) == 1 else "split"

    # Updates
    h_bot.update(h_bucket, h.stack - 1000)
    cfr_bot.update(c_bucket, c.stack - 1000)

    row = {
        "HandID": hand_id,
        "Board": board,
        "Winner": "|".join(winners),
        "WinType": win_type,
        "Pot": game.pot,
        "h_Hole": compact(h.hole),
        "cfr_Hole": compact(c.hole),
        "h_Bucket": h_bucket,
        "cfr_Bucket": c_bucket,
        "h_Action": actions.get("h_bot", ""),
        "cfr_Action": actions.get("cfr_bot", ""),
        "h_Delta": round(h.stack - 1000, 1),
        "cfr_Delta": round(c.stack - 1000, 1),
    }
    return row, winners

# ---------- Simulation driver ----------
def run_sim(hands=10000, outfile="Poker_game/results_cfr_vs_heuristic.csv", seed=None):
    if seed is None:
        seed = int(time.time())
    random.seed(seed)

    game = TexasHoldemGame(["h_bot", "cfr_bot"], blinds=(10, 20))
    trainer = HoldemCFR("cfr_state.pkl")
    h_bot = HeuristicBot("h_bot")
    cfr_bot = CFRBot("cfr_bot", trainer)

    headers = [
        "HandID","Board","Winner","WinType","Pot",
        "h_Hole","cfr_Hole","h_Bucket","cfr_Bucket",
        "h_Action","cfr_Action","h_Delta","cfr_Delta"
    ]

    wins = defaultdict(int)

    with open(outfile, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=headers)
        w.writeheader()
        for i in range(1, hands + 1):
            row, winners = simulate_hand(game, h_bot, cfr_bot, i)
            w.writerow(row)
            for nm in winners:
                wins[nm] += 1
            if i % 1000 == 0:
                print(f"[{i}/{hands}] -> h_bot: {wins['h_bot']}, cfr_bot: {wins['cfr_bot']}")

    trainer.save_state()
    print("\n✅ CFR vs Heuristic Summary:")
    print(f"  cfr_bot : {wins['cfr_bot']}")
    print(f"  h_bot   : {wins['h_bot']}")
    print(f"Results saved in: {outfile}")
    print("Expected: CFR wins should increase with more runs 🚀")

if __name__ == "__main__":
    run_sim()
