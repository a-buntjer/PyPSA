"""Detailed test of NetCDF export for stochastic networks."""

import sys
sys.path.insert(0, 'C:/Users/A64620/Documents/pypsa_tryout/PyPSA')
sys.path.insert(0, '../commitable-and-extendable')

from stochastic_multihorizon_chp import build_and_optimize
import pypsa

print("=" * 70)
print("Building and optimizing stochastic network...")
print("=" * 70)

# Baue ein kleines stochastisches Netzwerk
n = build_and_optimize()

print("\n" + "=" * 70)
print("BEFORE EXPORT - Network structure")
print("=" * 70)

print(f"Has scenarios: {n.has_scenarios}")
print(f"Scenarios: {n.scenarios if hasattr(n, 'scenarios') else 'None'}")
print(f"Has periods: {n.has_periods}")
print(f"Investment periods: {n.investment_periods if hasattr(n, 'investment_periods') else 'None'}")

print("\n--- Generator static data ---")
print(f"Generator index type: {type(n.generators.index)}")
print(f"Generator index: {n.generators.index[:5]}")
print(f"Generator columns: {list(n.generators.columns)[:10]}")

print("\n--- Generator time series ---")
if 'marginal_cost' in n.generators_t:
    print(f"marginal_cost columns type: {type(n.generators_t.marginal_cost.columns)}")
    print(f"marginal_cost columns: {n.generators_t.marginal_cost.columns[:5]}")
    print(f"marginal_cost dtypes: {n.generators_t.marginal_cost.dtypes}")

print("\n" + "=" * 70)
print("ATTEMPTING EXPORT...")
print("=" * 70)

try:
    n.export_to_netcdf('test_stochastic_full.nc')
    print("[OK] Export successful!")
except Exception as e:
    print(f"[FAIL] Export failed: {type(e).__name__}")
    print(f"  Message: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 70)
print("ATTEMPTING IMPORT...")
print("=" * 70)

try:
    n2 = pypsa.Network('test_stochastic_full.nc')
    print("[OK] Import successful!")
    print(f"Has scenarios: {n2.has_scenarios}")
    print(f"Has periods: {n2.has_periods}")
    print(f"Objective: {n2.objective:.2f}")
except Exception as e:
    print(f"[FAIL] Import failed: {type(e).__name__}")
    print(f"  Message: {e}")
    import traceback
    traceback.print_exc()
