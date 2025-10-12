import pickle
import os
import random

class HoldemCFR:
    """
    Simplified but functional Counterfactual Regret Minimization (CFR) trainer
    for preflop decision buckets in Texas Hold’em.

    Tracks:
      - cumulative regrets for each action (fold, call, raise)
      - cumulative strategy sums (for averaging)
      - usage counts for statistics and visualization
    """

    ACTIONS = ["fold", "call", "raise"]

    def __init__(self, filename="cfr_state.pkl"):
        self.filename = filename
        self.regrets = {}
        self.strategy_sum = {}
        self.usage_count = {}

        if os.path.exists(filename):
            with open(filename, "rb") as f:
                data = pickle.load(f)
                self.regrets = data.get("regrets", {})
                self.strategy_sum = data.get("strategy_sum", {})
                self.usage_count = data.get("usage_count", {})
                print(f"📂 CFR state loaded from {filename} ({len(self.regrets)} buckets).")
        else:
            print("📁 Starting new CFR training state.")

    # ---------------- CORE METHODS ----------------

    def _get_strategy(self, bucket):
        """Compute current strategy from positive regrets."""
        regrets = self.regrets.get(bucket, [0.0, 0.0, 0.0])
        pos = [max(0.0, r) for r in regrets]
        total = sum(pos)
        if total > 0:
            strat = [x / total for x in pos]
        else:
            strat = [1 / 3] * 3  # equal probabilities if no regrets yet
        return strat

    def strategy(self, bucket):
        """Return *average* strategy (normalized strategy_sum)."""
        if bucket not in self.strategy_sum:
            return [1 / 3] * 3
        total = sum(self.strategy_sum[bucket])
        if total == 0:
            return [1 / 3] * 3
        return [x / total for x in self.strategy_sum[bucket]]

    def train_once(self, bucket, reward):
        """
        Perform one CFR update for a given bucket based on the observed reward.
        reward: numeric payoff from perspective of this bucket's action result.
        """
        if bucket not in self.regrets:
            self.regrets[bucket] = [0.0, 0.0, 0.0]
            self.strategy_sum[bucket] = [0.0, 0.0, 0.0]
            self.usage_count[bucket] = 0

        self.usage_count[bucket] += 1
        # Get current strategy (behavior policy)
        strategy = self._get_strategy(bucket)

        # Calculate counterfactual utilities (simulated expected outcomes)
        # For simplicity, we assign each action a small stochastic payoff difference
        # around the observed reward to create learning signal.
        util = [reward * (random.uniform(0.9, 1.1) if i == 2 else random.uniform(-0.5, 0.5))
                for i in range(3)]

        node_util = sum(strategy[a] * util[a] for a in range(3))

        # Regret update
        for a in range(3):
            regret = util[a] - node_util
            self.regrets[bucket][a] += regret

        # Strategy sum update (for averaging)
        for a in range(3):
            self.strategy_sum[bucket][a] += strategy[a]

    def average_strategy(self, bucket):
        """Return normalized average strategy for inspection."""
        strat = self.strategy(bucket)
        return {a: round(strat[i], 3) for i, a in enumerate(self.ACTIONS)}

    def save_state(self):
        """Persist training data to pickle."""
        data = {
            "regrets": self.regrets,
            "strategy_sum": self.strategy_sum,
            "usage_count": self.usage_count
        }
        with open(self.filename, "wb") as f:
            pickle.dump(data, f)
        print(f"💾 CFR state saved to {self.filename} ({len(self.regrets)} buckets).")

    # ---------------- UTILITIES ----------------

    def summarize(self, top_n=10):
        """Print summary of most-updated buckets."""
        if not self.regrets:
            print("⚠️ No CFR data yet.")
            return

        print("\n🧠 Top Updated Buckets:")
        top = sorted(self.usage_count.items(), key=lambda x: -x[1])[:top_n]
        for bucket, n in top:
            strat = self.average_strategy(bucket)
            print(f"{bucket:<4} | n={n:<5} | strategy={strat} | regrets={[round(x, 1) for x in self.regrets[bucket]]}")
