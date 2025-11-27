"""Detailed test of n.statistics for stochastic networks - check for data issues."""

import sys
sys.path.insert(0, 'C:/Users/A64620/Documents/pypsa_tryout/PyPSA')
sys.path.insert(0, '../commitable-and-extendable')

from stochastic_multihorizon_chp import build_and_optimize
import pypsa
import pandas as pd

print("=" * 70)
print("DETAILED TEST: n.statistics() data integrity for stochastic networks")
print("=" * 70)

# Build stochastic network
print("\n[1/4] Building stochastic network...")
n = build_and_optimize()

# Test energy balance in detail
print("\n[2/4] Detailed energy_balance() check...")
try:
    energy_balance = n.statistics.energy_balance()
    print(f"      Shape: {energy_balance.shape}")
    print(f"\n      First few rows:")
    print(energy_balance.head(10))
    
    # Check for NaN or inf values
    has_nan = energy_balance.isna().any().any()
    has_inf = (energy_balance == float('inf')).any().any() or (energy_balance == float('-inf')).any().any()
    
    print(f"\n      Contains NaN: {has_nan}")
    print(f"      Contains Inf: {has_inf}")
    
    if has_nan:
        print("\n      NaN locations:")
        print(energy_balance[energy_balance.isna().any(axis=1)])
    
except Exception as e:
    print(f"      ERROR: {e}")
    import traceback
    traceback.print_exc()

# Test capacity statistics
print("\n[3/4] Detailed capacity statistics check...")
try:
    capacity = n.statistics.installed_capacity()
    print(f"      Shape: {capacity.shape}")
    print(f"\n      First few rows:")
    print(capacity.head(10))
    
    # Check for negative capacities
    has_negative = (capacity < 0).any().any()
    print(f"\n      Contains negative values: {has_negative}")
    
    if has_negative:
        print("\n      Negative capacity locations:")
        print(capacity[(capacity < 0).any(axis=1)])
        
except Exception as e:
    print(f"      ERROR: {e}")
    import traceback
    traceback.print_exc()

# Test withdrawal/supply
print("\n[4/4] Testing withdrawal and supply...")
try:
    withdrawal = n.statistics.withdrawal()
    supply = n.statistics.supply()
    
    print(f"      Withdrawal shape: {withdrawal.shape}")
    print(f"      Supply shape: {supply.shape}")
    
    print(f"\n      Withdrawal first rows:")
    print(withdrawal.head(5))
    
    print(f"\n      Supply first rows:")
    print(supply.head(5))
    
except Exception as e:
    print(f"      ERROR: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 70)
print("DETAILED TEST COMPLETE")
print("=" * 70)
