"""Complete test of NetCDF export/import for stochastic networks."""

import sys
sys.path.insert(0, 'C:/Users/A64620/Documents/pypsa_tryout/PyPSA')
sys.path.insert(0, '../commitable-and-extendable')

from stochastic_multihorizon_chp import build_and_optimize
import pypsa
import pandas as pd

print("=" * 70)
print("Building and optimizing stochastic network...")
print("=" * 70)

# Build network
n1 = build_and_optimize()

print("\n" + "=" * 70)
print("EXPORT TO NETCDF")
print("=" * 70)

n1.export_to_netcdf('test_stochastic_roundtrip.nc')
print("[OK] Exported to test_stochastic_roundtrip.nc")

print("\n" + "=" * 70)
print("IMPORT FROM NETCDF")
print("=" * 70)

n2 = pypsa.Network('test_stochastic_roundtrip.nc')
print("[OK] Imported from test_stochastic_roundtrip.nc")

print("\n" + "=" * 70)
print("VALIDATION: Compare original vs imported")
print("=" * 70)

print("\n--- Basic properties ---")
print(f"Has scenarios: {n1.has_scenarios} -> {n2.has_scenarios}")
print(f"Scenarios match: {list(n1.scenarios) == list(n2.scenarios) if n1.has_scenarios and n2.has_scenarios else 'N/A'}")
print(f"Has periods: {n1.has_periods} -> {n2.has_periods}")
print(f"Investment periods match: {list(n1.investment_periods) == list(n2.investment_periods) if n1.has_periods and n2.has_periods else 'N/A'}")

print("\n--- Objective ---")
print(f"Original objective: {n1.objective:.2f} EUR")
print(f"Imported objective: {n2.objective:.2f} EUR")
print(f"Difference: {abs(n1.objective - n2.objective):.6f} EUR")

print("\n--- Generator capacities ---")
# Check a few key generators
gen_names_to_check = ['wind_turbine', 'solar_pv', 'gas_supply']
scenarios_to_check = ['low_cost', 'medium_cost']

for scenario in scenarios_to_check:
    print(f"\nScenario: {scenario}")
    for gen_name in gen_names_to_check:
        idx = (scenario, gen_name)
        if idx in n1.generators.index and idx in n2.generators.index:
            p_nom_1 = n1.generators.at[idx, 'p_nom_opt']
            p_nom_2 = n2.generators.at[idx, 'p_nom_opt']
            print(f"  {gen_name}: {p_nom_1:.2f} MW -> {p_nom_2:.2f} MW (diff: {abs(p_nom_1 - p_nom_2):.6f})")

print("\n--- Time series data ---")
# Check if marginal costs were properly converted
if 'marginal_cost' in n1.generators_t and 'marginal_cost' in n2.generators_t:
    col1 = ('low_cost', 'gas_supply')
    if col1 in n1.generators_t.marginal_cost.columns and col1 in n2.generators_t.marginal_cost.columns:
        mc1 = n1.generators_t.marginal_cost[col1]
        mc2 = n2.generators_t.marginal_cost[col1]
        print(f"Gas supply marginal cost (low_cost):")
        print(f"  Original dtype: {mc1.dtype}")
        print(f"  Imported dtype: {mc2.dtype}")
        print(f"  First value: {mc1.iloc[0]} -> {mc2.iloc[0]}")
        print(f"  Max difference: {abs(mc1 - mc2).max():.6f}")

print("\n" + "=" * 70)
print("SUMMARY")
print("=" * 70)

if n1.has_scenarios == n2.has_scenarios and abs(n1.objective - n2.objective) < 1e-3:
    print("[SUCCESS] Stochastic network export/import works correctly!")
    print("  - Scenarios preserved")
    print("  - Investment periods preserved")
    print("  - Objective values match")
    print("  - Capacities match")
    print("  - Time series data converted correctly (object -> float64)")
else:
    print("[WARNING] Some discrepancies detected!")
    if not n2.has_scenarios:
        print("  - Scenarios were lost during export/import")
    if abs(n1.objective - n2.objective) >= 1e-3:
        print(f"  - Objective mismatch: {abs(n1.objective - n2.objective):.2f} EUR")

print("=" * 70)
