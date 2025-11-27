"""Test statistics with multi-period + stochastic network (neues_netz example)."""

import sys
sys.path.insert(0, 'C:/Users/A64620/Documents/pypsa_tryout/PyPSA')
import pypsa
import traceback

print("=" * 70)
print("TEST: Statistics with multi-period + stochastic (neues_netz)")
print("=" * 70)

# Import and run the neues_netz example
from neues_netz_network_creator import create_neues_netz_network, set_time_series
from neues_netz_config_parameters import (
    INVESTMENT_PERIODS, 
    SCENARIOS, 
    SCENARIO_WEIGHTS,
    USE_STOCHASTIC
)
from run_neues_netz_optimization import prepare_time_series_data, optimize_network

print(f"\n[1/3] Building network...")
print(f"  Use stochastic: {USE_STOCHASTIC}")
print(f"  Investment periods: {INVESTMENT_PERIODS}")
print(f"  Scenarios: {list(SCENARIOS.keys())}")

n = create_neues_netz_network(use_stochastic=USE_STOCHASTIC)

# Generate time series data
time_series_data = prepare_time_series_data(
    investment_periods=INVESTMENT_PERIODS,
    scenarios=SCENARIOS if USE_STOCHASTIC else None
)

# Set time series
set_time_series(n, time_series_data, use_stochastic=USE_STOCHASTIC)

# Optimize
print(f"\n[2/3] Optimizing...")
optimize_network(n)
print(f"  Objective: {n.objective:.2f} EUR")

# Test statistics
print(f"\n[3/3] Testing n.statistics methods...")

test_results = {}

# Test 1: capex
print("\n  Testing n.statistics.capex()...")
try:
    capex = n.statistics.capex()
    print(f"    [OK] Shape: {capex.shape}")
    print(f"    First rows:\n{capex.head(3)}")
    test_results['capex'] = 'PASS'
except Exception as e:
    print(f"    [FAIL] {type(e).__name__}: {e}")
    traceback.print_exc()
    test_results['capex'] = 'FAIL'

# Test 2: installed_capacity
print("\n  Testing n.statistics.installed_capacity()...")
try:
    capacity = n.statistics.installed_capacity()
    print(f"    [OK] Shape: {capacity.shape}")
    print(f"    First rows:\n{capacity.head(3)}")
    test_results['installed_capacity'] = 'PASS'
except Exception as e:
    print(f"    [FAIL] {type(e).__name__}: {e}")
    traceback.print_exc()
    test_results['installed_capacity'] = 'FAIL'

# Test 3: energy_balance
print("\n  Testing n.statistics.energy_balance()...")
try:
    energy_balance = n.statistics.energy_balance()
    print(f"    [OK] Shape: {energy_balance.shape}")
    print(f"    First rows:\n{energy_balance.head(3)}")
    test_results['energy_balance'] = 'PASS'
except Exception as e:
    print(f"    [FAIL] {type(e).__name__}: {e}")
    traceback.print_exc()
    test_results['energy_balance'] = 'FAIL'

# Test 4: withdrawal
print("\n  Testing n.statistics.withdrawal()...")
try:
    withdrawal = n.statistics.withdrawal()
    print(f"    [OK] Shape: {withdrawal.shape}")
    print(f"    First rows:\n{withdrawal.head(3)}")
    test_results['withdrawal'] = 'PASS'
except Exception as e:
    print(f"    [FAIL] {type(e).__name__}: {e}")
    traceback.print_exc()
    test_results['withdrawal'] = 'FAIL'

# Summary
print("\n" + "=" * 70)
print("TEST SUMMARY")
print("=" * 70)
passed = sum(1 for v in test_results.values() if v == 'PASS')
total = len(test_results)
print(f"Tests passed: {passed}/{total}")
for test, result in test_results.items():
    symbol = "[OK]" if result == 'PASS' else "[FAIL]"
    print(f"  {symbol} {test}")
print("=" * 70)
