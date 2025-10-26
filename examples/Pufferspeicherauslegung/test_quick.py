"""
Quick test of stochastic heat storage optimization
===================================================
Reduced version for fast validation (24 hours, 2 scenarios)
"""

# Modify main script for quick test
import sys
sys.path.insert(0, '.')

# Import and modify configuration
import stochastic_heat_storage_optimization as main_script

# Override configuration for quick test
main_script.HOURS_TO_SIMULATE = 24  # Just 24 hours
main_script.MIP_GAP = 0.10  # 10% gap for speed
main_script.TIME_LIMIT = 300  # 5 minutes max

# Use only 2 scenarios for testing
main_script.SCENARIOS = {
    'medium': {
        'sheet': 'Mittlere_Netzprognose_2024',
        'weight': 0.6,
        'description': 'Mittleres Wetterjahr (2024)'
    },
    'cold': {
        'sheet': 'Mittlere_Netzprognose_2021',
        'weight': 0.4,
        'description': 'Kaltes Wetterjahr (2021)'
    },
}

print("="*70)
print("QUICK VALIDATION TEST")
print("="*70)
print(f"Hours: {main_script.HOURS_TO_SIMULATE}")
print(f"Scenarios: {len(main_script.SCENARIOS)}")
print(f"MIP Gap: {main_script.MIP_GAP*100}%")
print("="*70 + "\n")

# Run optimization
if __name__ == "__main__":
    try:
        n, data = main_script.main()
        print("\n" + "="*70)
        print("✓ QUICK TEST PASSED!")
        print("="*70)
        print("\nYou can now run the full optimization:")
        print("  python stochastic_heat_storage_optimization.py")
        print("="*70)
    except Exception as e:
        print(f"\n✗ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
