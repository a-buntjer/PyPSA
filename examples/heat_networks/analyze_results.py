"""Analyze the district heating network results."""

import pypsa
import pandas as pd
import numpy as np

# Load network
n = pypsa.Network("district_heating_system.nc")

print("=" * 80)
print("DETAILED ANALYSIS OF DISTRICT HEATING NETWORK")
print("=" * 80)

print(f"\nTotal System Cost: {n.objective:,.2f} EUR")
print(f"Simulation period: {len(n.snapshots)} hours")

# =============================================================================
# INSTALLED CAPACITIES
# =============================================================================

print("\n" + "=" * 80)
print("INSTALLED CAPACITIES [MW]")
print("=" * 80)

print("\n--- Heat Production Technologies ---")
heat_tech = [link for link in n.links.index if any(x in link for x in ["pump", "boiler", "chp", "gas_boiler"])]
for link in sorted(heat_tech):
    capacity = n.links.at[link, "p_nom_opt"]
    if capacity > 0.1:
        print(f"{link:45s}: {capacity:8.2f} MW")

print("\n--- Heat Network Links ---")
heat_network = [link for link in n.links.index if "heat_site" in link]
for link in sorted(heat_network):
    capacity = n.links.at[link, "p_nom_opt"]
    print(f"{link:45s}: {capacity:8.2f} MW")

print("\n--- Grid Connections ---")
grid_links = [link for link in n.links.index if "grid_" in link]
for link in sorted(grid_links):
    capacity = n.links.at[link, "p_nom_opt"]
    if capacity > 0.1:
        print(f"{link:45s}: {capacity:8.2f} MW")

print("\n--- Thermal Storage ---")
for store in n.stores.index:
    capacity = n.stores.at[store, "e_nom_opt"]
    if capacity > 0.1:
        print(f"{store:45s}: {capacity:8.2f} MWh")

# =============================================================================
# ENERGY PRODUCTION
# =============================================================================

print("\n" + "=" * 80)
print("ENERGY PRODUCTION [MWh]")
print("=" * 80)

# Heat production by technology
print("\n--- Heat Production by Technology ---")
for link in sorted(heat_tech):
    if link in n.links_t.p1.columns:
        production = n.links_t.p1[link].sum()
        if production > 0.1:
            capacity = n.links.at[link, "p_nom_opt"]
            utilization = (production / (capacity * len(n.snapshots))) * 100 if capacity > 0 else 0
            print(f"{link:45s}: {production:10.2f} MWh  ({utilization:5.1f}% utilization)")

# Electricity consumption
print("\n--- Electricity Consumption ---")
electric_consumers = [link for link in n.links.index if "pump" in link or "electric_boiler" in link]
for link in sorted(electric_consumers):
    if link in n.links_t.p0.columns:
        consumption = n.links_t.p0[link].sum()
        if consumption > 0.1:
            print(f"{link:45s}: {consumption:10.2f} MWh")

# CHP electricity production
print("\n--- CHP Electricity Production ---")
chp_gen = [link for link in n.links.index if "chp_" in link and "_gen_" in link]
for link in sorted(chp_gen):
    if link in n.links_t.p1.columns:
        production = n.links_t.p1[link].sum()
        if production > 0.1:
            print(f"{link:45s}: {production:10.2f} MWh")

# =============================================================================
# GRID USAGE
# =============================================================================

print("\n" + "=" * 80)
print("GRID USAGE")
print("=" * 80)

for link in sorted(grid_links):
    if link in n.links_t.p0.columns:
        total = n.links_t.p0[link].sum()
        peak = n.links_t.p0[link].max()
        capacity = n.links.at[link, "p_nom_opt"]
        if total > 0.1:
            print(f"\n{link}:")
            print(f"  Total:    {total:10.2f} MWh")
            print(f"  Peak:     {peak:10.2f} MW")
            print(f"  Capacity: {capacity:10.2f} MW")
            if capacity > 0:
                print(f"  Peak/Cap: {(peak/capacity)*100:10.1f}%")

# =============================================================================
# HEAT BALANCE BY CONSUMER
# =============================================================================

print("\n" + "=" * 80)
print("HEAT BALANCE BY CONSUMER")
print("=" * 80)

consumers = ["consumer_1", "consumer_2", "consumer_3"]
for consumer in consumers:
    load_name = f"load_heat_{consumer[:-2]}c{consumer[-1]}"
    if load_name in n.loads.index:
        demand = n.loads_t.p[load_name].sum()
        print(f"\n{consumer.upper()}:")
        print(f"  Demand: {demand:10.2f} MWh")
        
        # Find supply links
        bus_name = f"bus_heat_{consumer}"
        supply_links = [link for link in n.links.index if n.links.at[link, "bus1"] == bus_name]
        
        print("  Supply sources:")
        for link in supply_links:
            if link in n.links_t.p1.columns:
                supply = n.links_t.p1[link].sum()
                if supply > 0.1:
                    print(f"    {link:40s}: {supply:10.2f} MWh ({supply/demand*100:5.1f}%)")

# =============================================================================
# COST BREAKDOWN
# =============================================================================

print("\n" + "=" * 80)
print("COST BREAKDOWN")
print("=" * 80)

# Calculate costs by component
print("\nCapital costs (annualized):")
capital_costs = {}

# Links
for link in n.links.index:
    p_nom_opt = n.links.at[link, "p_nom_opt"]
    capital_cost = n.links.at[link, "capital_cost"]
    if p_nom_opt > 0 and capital_cost > 0:
        cost = p_nom_opt * capital_cost
        capital_costs[link] = cost
        if cost > 10:
            print(f"  {link:43s}: {cost:10.2f} EUR/year")

# Stores
for store in n.stores.index:
    e_nom_opt = n.stores.at[store, "e_nom_opt"]
    capital_cost = n.stores.at[store, "capital_cost"]
    if e_nom_opt > 0 and capital_cost > 0:
        cost = e_nom_opt * capital_cost
        capital_costs[store] = cost
        print(f"  {store:43s}: {cost:10.2f} EUR/year")

total_capital = sum(capital_costs.values())
print(f"\n  Total capital costs: {total_capital:10.2f} EUR/year")

print("\nOperational costs:")
# This would require detailed calculation from marginal costs and production
# Simplified: Total cost - capital costs ≈ operational costs
operational = n.objective - total_capital
print(f"  Estimated operational costs: {operational:10.2f} EUR")

# =============================================================================
# TIME SERIES ANALYSIS
# =============================================================================

print("\n" + "=" * 80)
print("TIME SERIES STATISTICS")
print("=" * 80)

# Heat pump performance
print("\n--- Heat Pump Statistics ---")
hp_links = [link for link in n.links.index if "heat_pump" in link]
for hp in hp_links:
    if hp in n.links_t.efficiency.columns:
        cop_series = n.links_t.efficiency[hp]
        print(f"\n{hp}:")
        print(f"  Average COP: {cop_series.mean():.2f}")
        print(f"  Min COP:     {cop_series.min():.2f}")
        print(f"  Max COP:     {cop_series.max():.2f}")
        
        if hp in n.links_t.p1.columns:
            heat_prod = n.links_t.p1[hp]
            elec_cons = n.links_t.p0[hp]
            actual_cop = (heat_prod / elec_cons).replace([np.inf, -np.inf], 0).fillna(0)
            actual_cop = actual_cop[actual_cop > 0]
            if len(actual_cop) > 0:
                print(f"  Actual COP (when running): {actual_cop.mean():.2f}")

# Storage usage
print("\n--- Thermal Storage Statistics ---")
for store in n.stores.index:
    if store in n.stores_t.e.columns:
        energy = n.stores_t.e[store]
        capacity = n.stores.at[store, "e_nom_opt"]
        if capacity > 0.1:
            print(f"\n{store}:")
            print(f"  Capacity:     {capacity:.2f} MWh")
            print(f"  Average fill: {energy.mean():.2f} MWh ({energy.mean()/capacity*100:.1f}%)")
            print(f"  Max fill:     {energy.max():.2f} MWh ({energy.max()/capacity*100:.1f}%)")
            print(f"  Cycles:       {(n.stores_t.p[store].clip(lower=0).sum() / capacity):.2f}")

# =============================================================================
# BIOGAS CONSTRAINT CHECK
# =============================================================================

print("\n" + "=" * 80)
print("BIOGAS USAGE CHECK")
print("=" * 80)

biogas_links = [link for link in n.links.index if "biogas" in link]
if biogas_links:
    print("\nBiogas consumption by link:")
    total_biogas = 0
    for link in biogas_links:
        if link in n.links_t.p0.columns:
            usage = n.links_t.p0[link].sum()
            if usage > 0.01:
                print(f"  {link:43s}: {usage:10.2f} MWh")
                total_biogas += usage
    
    print(f"\n  Total biogas used:      {total_biogas:10.2f} MWh")
    print(f"  Weekly limit:           {500.0:10.2f} MWh")
    print(f"  Limit utilization:      {(total_biogas/500.0)*100:10.1f}%")
else:
    print("\nNo biogas usage detected.")

print("\n" + "=" * 80)
print("END OF ANALYSIS")
print("=" * 80)
