"""Final comprehensive test of stochastic NetCDF export/import fix."""

import sys
sys.path.insert(0, 'C:/Users/A64620/Documents/pypsa_tryout/PyPSA')
sys.path.insert(0, '../commitable-and-extendable')

from stochastic_multihorizon_chp import build_and_optimize
import pypsa

print("=" * 70)
print("FINAL TEST: Stochastic Network NetCDF Export/Import Fix")
print("=" * 70)

# Build fresh network
print("\n[1/5] Building stochastic network...")
n_original = build_and_optimize()

print(f"      Objective: {n_original.objective:.2f} EUR")
print(f"      Scenarios: {list(n_original.scenarios)}")
print(f"      Periods: {list(n_original.investment_periods)}")

# Export
print("\n[2/5] Exporting to NetCDF...")
n_original.export_to_netcdf('final_test_stochastic.nc')
print("      [OK] Export successful")

# Import
print("\n[3/5] Importing from NetCDF...")
n_imported = pypsa.Network('final_test_stochastic.nc')
print("      [OK] Import successful")

# Validate
print("\n[4/5] Validating data integrity...")

tests_passed = 0
tests_total = 0

# Test 1: Scenarios preserved
tests_total += 1
if n_imported.has_scenarios and set(n_original.scenarios) == set(n_imported.scenarios):
    print("      [PASS] Scenarios preserved")
    tests_passed += 1
else:
    print(f"      [FAIL] Scenarios: {list(n_original.scenarios)} != {list(n_imported.scenarios)}")

# Test 2: Periods preserved
tests_total += 1
if n_imported.has_periods and list(n_original.investment_periods) == list(n_imported.investment_periods):
    print("      [PASS] Investment periods preserved")
    tests_passed += 1
else:
    print("      [FAIL] Investment periods mismatch")

# Test 3: Objective match
tests_total += 1
obj_diff = abs(n_original.objective - n_imported.objective)
if obj_diff < 1e-2:
    print(f"      [PASS] Objective match (diff: {obj_diff:.6f} EUR)")
    tests_passed += 1
else:
    print(f"      [FAIL] Objective mismatch: {obj_diff:.2f} EUR")

# Test 4: Capacity data preserved
tests_total += 1
idx_test = ('low_cost', 'wind_turbine')
if idx_test in n_original.generators.index and idx_test in n_imported.generators.index:
    cap_orig = n_original.generators.at[idx_test, 'p_nom_opt']
    cap_import = n_imported.generators.at[idx_test, 'p_nom_opt']
    cap_diff = abs(cap_orig - cap_import)
    if cap_diff < 1e-6:
        print(f"      [PASS] Capacity data preserved (wind: {cap_orig:.2f} MW)")
        tests_passed += 1
    else:
        print(f"      [FAIL] Capacity mismatch: {cap_diff:.6f} MW")
else:
    print("      [FAIL] Generator index structure changed")

# Test 5: Time series converted (object -> float)
tests_total += 1
col_test = ('low_cost', 'gas_supply')
if col_test in n_imported.generators_t.marginal_cost.columns:
    dtype_imported = n_imported.generators_t.marginal_cost[col_test].dtype
    if dtype_imported in [float, 'float64', 'float32']:
        print(f"      [PASS] Object dtype converted to {dtype_imported}")
        tests_passed += 1
    else:
        print(f"      [FAIL] Still object dtype: {dtype_imported}")
else:
    print("      [FAIL] Time series column missing")

# Summary
print(f"\n[5/5] Test Results: {tests_passed}/{tests_total} passed")

if tests_passed == tests_total:
    print("\n" + "=" * 70)
    print("SUCCESS! Stochastic NetCDF export/import works perfectly!")
    print("=" * 70)
    print("\nFix applied:")
    print("  - Added fix_mixed_dtype_object_arrays() in _ExporterNetCDF.finish()")
    print("  - Converts object dtypes with mixed int/float to float64")
    print("  - Enables successful NetCDF export for stochastic networks")
    print("\nWhat was the problem?")
    print("  - Stochastic networks have MultiIndex time series")
    print("  - Different scenarios may have different numeric types (int vs float)")
    print("  - xarray/NetCDF cannot serialize object arrays with mixed types")
    print("\nSolution:")
    print("  - Detect object dtype variables before export")
    print("  - Convert numeric object arrays to float64")
    print("  - Preserves data precision while enabling NetCDF serialization")
    print("=" * 70)
else:
    print("\n" + "=" * 70)
    print(f"WARNING: {tests_total - tests_passed} test(s) failed")
    print("=" * 70)
