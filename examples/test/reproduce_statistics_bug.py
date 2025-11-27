"""Reproduce the statistics bug with stochastic networks."""

import sys
sys.path.insert(0, 'C:/Users/A64620/Documents/pypsa_tryout/PyPSA')
sys.path.insert(0, '../commitable-and-extendable')

from stochastic_multihorizon_chp import build_and_optimize
import traceback

print("=" * 70)
print("REPRODUCE BUG: n.statistics.capex() with stochastic network")
print("=" * 70)

# Build stochastic network
print("\n[1/2] Building stochastic network...")
n = build_and_optimize()

print(f"\nNetwork structure:")
print(f"  Has scenarios: {n.has_scenarios}")
print(f"  Scenarios: {list(n.scenarios)}")
print(f"  Generator index type: {type(n.generators.index)}")
print(f"  Generator index: {n.generators.index[:3]}")

# Try to call capex - this should trigger the bug
print("\n[2/2] Calling n.statistics.capex()...")
try:
    capex = n.statistics.capex()
    print(f"[OK] CAPEX calculated successfully")
    print(f"Shape: {capex.shape}")
    print(capex.head())
except ValueError as e:
    print(f"[FAIL] ValueError: {e}")
    print("\nFull traceback:")
    traceback.print_exc()
except Exception as e:
    print(f"[FAIL] {type(e).__name__}: {e}")
    print("\nFull traceback:")
    traceback.print_exc()

print("\n" + "=" * 70)
