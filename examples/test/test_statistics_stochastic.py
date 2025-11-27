"""Test n.statistics for stochastic networks."""

import sys
sys.path.insert(0, 'C:/Users/A64620/Documents/pypsa_tryout/PyPSA')
sys.path.insert(0, '../commitable-and-extendable')

from stochastic_multihorizon_chp import build_and_optimize
import pypsa
import traceback

print("=" * 70)
print("TEST: n.statistics() for stochastic networks")
print("=" * 70)

# Build stochastic network
print("\n[1/5] Building stochastic network...")
n = build_and_optimize()
print(f"      Objective: {n.objective:.2f} EUR")
print(f"      Scenarios: {list(n.scenarios)}")

# Test 1: Basic statistics call
print("\n[2/5] Testing n.statistics()...")
try:
    stats = n.statistics()
    print(f"      [OK] Statistics generated")
    print(f"      Shape: {stats.shape}")
    print(f"      Columns: {list(stats.columns)[:5]}...")
except Exception as e:
    print(f"      [FAIL] Error: {type(e).__name__}: {e}")
    traceback.print_exc()

# Test 2: Energy balance
print("\n[3/5] Testing n.statistics.energy_balance()...")
try:
    energy_balance = n.statistics.energy_balance()
    print(f"      [OK] Energy balance generated")
    print(f"      Shape: {energy_balance.shape}")
    if not energy_balance.empty:
        print(f"      Index: {energy_balance.index[:3]}")
except Exception as e:
    print(f"      [FAIL] Error: {type(e).__name__}: {e}")
    traceback.print_exc()

# Test 3: Installed capacity
print("\n[4/5] Testing n.statistics.installed_capacity()...")
try:
    capacity = n.statistics.installed_capacity()
    print(f"      [OK] Installed capacity generated")
    print(f"      Shape: {capacity.shape}")
    if not capacity.empty:
        print(f"      Carriers: {list(capacity.index)[:5]}")
except Exception as e:
    print(f"      [FAIL] Error: {type(e).__name__}: {e}")
    traceback.print_exc()

# Test 4: Capital costs
print("\n[5/5] Testing n.statistics.capex()...")
try:
    capex = n.statistics.capex()
    print(f"      [OK] CAPEX generated")
    print(f"      Shape: {capex.shape}")
    if not capex.empty:
        print(f"      Components: {list(capex.index)[:5]}")
except Exception as e:
    print(f"      [FAIL] Error: {type(e).__name__}: {e}")
    traceback.print_exc()

print("\n" + "=" * 70)
print("TEST COMPLETE")
print("=" * 70)
