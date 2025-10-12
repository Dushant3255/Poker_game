"""
read_cfr_state.py
Utility to inspect saved CFR state from cfr_state.pkl.
"""

import pickle
from pprint import pprint

def read_cfr_state(filename="cfr_state.pkl", top_n=10):
    try:
        with open(filename, "rb") as f:
            data = pickle.load(f)
        print(f"✅ Loaded CFR state from {filename}\n")
    except Exception as e:
        print(f"⚠️ Could not load {filename}: {e}")
        return

    print("📂 Keys:", list(data.keys()))
    print(f"\n🧠 Showing top {top_n} most updated buckets:\n")

    regrets = data.get("regrets", {})
    strategy_sum = data.get("strategy_sum", {})
    usage = data.get("usage_count", {})

    top = sorted(usage.items(), key=lambda kv: kv[1], reverse=True)[:top_n]
    for bucket, count in top:
        r = regrets.get(bucket, [0,0,0])
        s = strategy_sum.get(bucket, [0,0,0])
        total = sum(s)
        strat = [round(x/total,2) if total>0 else 0 for x in s]
        print(f"{bucket:4s} | n={count:5d} | regrets={r} | avg_strategy={strat}")

if __name__ == "__main__":
    read_cfr_state()
