"""Quick test for committable + stochastic bug."""

import sys
import pathlib

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import pandas as pd
import pypsa

n = pypsa.Network()

snapshots = pd.date_range("2025-01-01", periods=24, freq="h")
n.set_snapshots(snapshots)

n.add("Bus", "bus1")
n.add("Load", "load1", bus="bus1", p_set=100)
n.add(
    "Generator",
    "gen1",
    bus="bus1",
    p_nom=150,
    marginal_cost=50,
    committable=True,
    min_up_time=2,
    min_down_time=2,
    up_time_before=0,
    down_time_before=5,
)

n.set_scenarios(["scenario_A", "scenario_B"])

print("Network created. Attempting optimization...")
try:
    n.optimize(solver_name="highs")
    print("✅ SUCCESS!")
except Exception as e:
    print(f"❌ FAILED: {type(e).__name__}: {e}")
    import traceback
    traceback.print_exc()
