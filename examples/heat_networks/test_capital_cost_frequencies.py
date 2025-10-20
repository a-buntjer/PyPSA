"""Test script to verify capital cost calculation with different snapshot frequencies.

This script demonstrates that the capital cost calculation correctly handles
different time resolutions (hourly, 15-minute, 3-hourly) and properly
distinguishes between equipment investments and annual grid charges.
"""

import pandas as pd


def calculate_annuity_factor(interest_rate: float, lifetime: int) -> float:
    """Calculate annuity factor."""
    if interest_rate == 0:
        return 1.0 / lifetime
    return (interest_rate * (1 + interest_rate) ** lifetime) / (
        (1 + interest_rate) ** lifetime - 1
    )


def scale_capital_cost(
    capital_cost_annual: float,
    snapshot_duration_hours: float,
    n_snapshots: int,
    hours_per_year: int = 8760,
) -> float:
    """Scale annual capital cost to simulation period."""
    total_hours = n_snapshots * snapshot_duration_hours
    return capital_cost_annual * (total_hours / hours_per_year)


def capex_to_capital_cost(
    investment_cost_per_mw: float,
    annuity_factor: float,
    snapshot_duration_hours: float,
    n_snapshots: int,
) -> float:
    """Convert equipment investment to capital cost (with annuity)."""
    annual_cost = investment_cost_per_mw * annuity_factor
    return scale_capital_cost(annual_cost, snapshot_duration_hours, n_snapshots)


def annual_to_capital_cost(
    annual_cost_per_mw: float, snapshot_duration_hours: float, n_snapshots: int
) -> float:
    """Convert annual cost to capital cost (time scaling only)."""
    return scale_capital_cost(annual_cost_per_mw, snapshot_duration_hours, n_snapshots)


# Configuration
INTEREST_RATE = 0.05
LIFETIME_YEARS = 20
DAYS = 7

# Example costs
HEAT_PUMP_INVESTMENT = 800000  # EUR/MW investment
GRID_CHARGE_ANNUAL = 115610  # EUR/MW/year (already annual!)

# Calculate annuity factor
annuity_factor = calculate_annuity_factor(INTEREST_RATE, LIFETIME_YEARS)

print("=" * 80)
print("CAPITAL COST CALCULATION TEST")
print("=" * 80)
print(f"\nEconomic parameters:")
print(f"  Interest rate: {INTEREST_RATE*100:.1f}%")
print(f"  Lifetime: {LIFETIME_YEARS} years")
print(f"  Annuity factor: {annuity_factor:.6f}")
print()

# Test different snapshot frequencies
test_cases = [
    ("Stündlich (hourly)", 1.0, DAYS * 24),
    ("Viertelstündlich (15-min)", 0.25, DAYS * 24 * 4),
    ("3-Stunden (3-hourly)", 3.0, DAYS * 8),
    ("Jahressimulation stündlich", 1.0, 8760),
]

print("=" * 80)
print("TEST: VERSCHIEDENE ZEITAUFLÖSUNGEN")
print("=" * 80)
print()

for case_name, duration_h, n_snaps in test_cases:
    total_hours = n_snaps * duration_h
    time_scale = total_hours / 8760

    # Calculate capital costs
    heat_pump_cc = capex_to_capital_cost(
        HEAT_PUMP_INVESTMENT, annuity_factor, duration_h, n_snaps
    )
    grid_charge_cc = annual_to_capital_cost(GRID_CHARGE_ANNUAL, duration_h, n_snaps)

    print(f"{case_name}:")
    print(f"  Snapshot duration: {duration_h:.2f} h ({duration_h*60:.0f} min)")
    print(f"  Number of snapshots: {n_snaps}")
    print(f"  Total hours: {total_hours:.1f} h ({total_hours/24:.1f} days)")
    print(f"  Time scale: {time_scale:.6f}")
    print()
    print(f"  Wärmepumpe (Investment {HEAT_PUMP_INVESTMENT/1000:.0f}k EUR/MW):")
    print(f"    → Annualisiert: {HEAT_PUMP_INVESTMENT * annuity_factor:.2f} EUR/MW/Jahr")
    print(f"    → PyPSA capital_cost: {heat_pump_cc:.2f} EUR/MW")
    print()
    print(f"  Netzentgelt (bereits {GRID_CHARGE_ANNUAL/1000:.2f}k EUR/MW/Jahr):")
    print(f"    → Keine Annuität!")
    print(f"    → PyPSA capital_cost: {grid_charge_cc:.2f} EUR/MW")
    print()
    print("-" * 80)
    print()

# Verify that different frequencies give same result for same time period
print("=" * 80)
print("VERIFIKATION: FREQUENZUNABHÄNGIGKEIT")
print("=" * 80)
print()

freq_cases = [
    ("Stündlich", 1.0, 168),
    ("Viertelstündlich", 0.25, 672),
    ("3-Stunden", 3.0, 56),
]

results = []
for name, dur, snaps in freq_cases:
    hp_cc = capex_to_capital_cost(HEAT_PUMP_INVESTMENT, annuity_factor, dur, snaps)
    grid_cc = annual_to_capital_cost(GRID_CHARGE_ANNUAL, dur, snaps)
    results.append((name, hp_cc, grid_cc))
    print(f"{name:20s}: WP={hp_cc:8.3f} EUR/MW, Grid={grid_cc:8.3f} EUR/MW")

# Check all equal
hp_values = [r[1] for r in results]
grid_values = [r[2] for r in results]

if all(abs(v - hp_values[0]) < 0.01 for v in hp_values):
    print("\n✅ Wärmepumpe: Alle Frequenzen ergeben gleiches Ergebnis!")
else:
    print("\n❌ FEHLER: Wärmepumpe-Werte unterscheiden sich!")

if all(abs(v - grid_values[0]) < 0.01 for v in grid_values):
    print("✅ Netzentgelt: Alle Frequenzen ergeben gleiches Ergebnis!")
else:
    print("❌ FEHLER: Netzentgelt-Werte unterscheiden sich!")

print()
print("=" * 80)
print("TEST ABGESCHLOSSEN")
print("=" * 80)
