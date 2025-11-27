"""Test statistics fix with neues_netz stochastic+multiperiod."""

import sys
sys.path.insert(0, 'C:/Users/A64620/Documents/pypsa_tryout/PyPSA')
sys.path.insert(0, '.')

import neues_netz_config_parameters as cfg
import neues_netz_network_creator as creator
from run_neues_netz_optimization import prepare_time_series_data, optimize_network
import traceback

print("=" * 70)
print("TEST: Statistics fix with stochastic + multi-period")
print("=" * 70)

print(f"\n[1/3] Creating network...")
print(f"  Mode: {'STOCHASTIC' if cfg.USE_STOCHASTIC else 'DETERMINISTIC'}")
print(f"  Scenarios: {list(cfg.SCENARIOS.keys())}")
print(f"  Periods: {cfg.INVESTMENT_PERIODS}")

# Create network
n = creator.create_neues_netz_network(use_unit_commitment=False)

# Generate time series
heat_demand_dict, elec_price_dict, gas_price_dict, cop_dict = prepare_time_series_data()

# Set time series
creator.set_time_series(
    network=n,
    heat_demand_dict=heat_demand_dict,
    electricity_price_dict=elec_price_dict,
    gas_price_dict=gas_price_dict,
    cop_dict=cop_dict,
)

print(f"\n[2/3] Optimizing...")
n = optimize_network(n)
print(f"  Objective: {n.objective:.2f} EUR")

print(f"\n[3/3] Testing statistics...")

tests = [
    ('capex', lambda: n.statistics.capex()),
    ('installed_capacity', lambda: n.statistics.installed_capacity()),
    ('energy_balance', lambda: n.statistics.energy_balance()),
    ('withdrawal', lambda: n.statistics.withdrawal()),
    ('supply', lambda: n.statistics.supply()),
]

results = {}
for name, func in tests:
    print(f"\n  Testing {name}...")
    try:
        result = func()
        print(f"    [OK] Shape: {result.shape}")
        if not result.empty:
            print(f"    First rows:\n{result.head(2)}")
        results[name] = 'PASS'
    except Exception as e:
        print(f"    [FAIL] {type(e).__name__}: {e}")
        if 'broadcast' in str(e).lower():
            print("    ^ This is the broadcasting error!")
            traceback.print_exc()
        results[name] = 'FAIL'

print("\n" + "=" * 70)
print("SUMMARY")
print("=" * 70)
passed = sum(1 for v in results.values() if v == 'PASS')
print(f"Tests: {passed}/{len(results)} passed")
for name, result in results.items():
    print(f"  {'[OK]' if result == 'PASS' else '[FAIL]'} {name}")
print("=" * 70)
