"""
Test ohne BHKW - nur um zu prüfen, ob das Basissystem feasible ist.
"""

import pypsa
import pandas as pd
import numpy as np
from pathlib import Path

SNAPSHOTS = pd.date_range("2024-01-01 00:00", "2024-01-01 23:00", freq="h")
DAYS = 1

def build_profiles(index):
    """Einfache Profile für Test."""
    base_electric_load = np.array([3, 3, 3, 3, 3, 4, 5, 6, 7, 7, 7, 6, 5, 5, 5, 6, 7, 8, 7, 6, 5, 4, 3, 3])
    base_heat_load = np.array([2, 2, 2, 2, 3, 4, 5, 6, 6, 5, 4, 4, 4, 4, 4, 5, 6, 7, 6, 5, 4, 3, 2, 2])
    base_wind_profile = np.array([0.3] * 24)
    base_market_price = np.array([50.0] * 24)
    
    electric_load = np.tile(base_electric_load, DAYS)
    heat_load = np.tile(base_heat_load, DAYS)
    wind_profile = np.tile(base_wind_profile, DAYS)
    market_price = np.tile(base_market_price, DAYS)
    
    return (
        pd.Series(electric_load, index=index),
        pd.Series(heat_load, index=index),
        pd.Series(wind_profile, index=index),
        pd.Series(market_price, index=index),
    )

def build_network() -> pypsa.Network:
    """Minimales Netzwerk OHNE BHKW."""
    
    n = pypsa.Network()
    n.set_snapshots(list(SNAPSHOTS))
    
    electric_load, heat_load, wind_profile, market_price = build_profiles(SNAPSHOTS)
    
    # Carriers and buses
    n.add("Carrier", "electric")
    n.add("Carrier", "gas", co2_emissions=0.20)
    n.add("Carrier", "heat")
    n.add("Carrier", "wind")
    n.add("Carrier", "market")
    
    n.add("Bus", "bus_electric", carrier="electric")
    n.add("Bus", "bus_gas", carrier="gas")
    n.add("Bus", "bus_heat", carrier="heat")
    
    # Demand
    n.add("Load", "electric_demand", bus="bus_electric", p_set=electric_load)
    n.add("Load", "heat_demand", bus="bus_heat", p_set=heat_load)
    
    # Wind
    n.add(
        "Generator",
        "wind_turbine",
        bus="bus_electric",
        carrier="wind",
        p_nom_extendable=True,
        capital_cost=900,
        marginal_cost=0.0,
        p_max_pu=wind_profile,
        p_nom_max=10,
    )
    
    # Grid trade
    n.add(
        "Generator",
        "grid_trade",
        bus="bus_electric",
        carrier="market",
        p_nom_extendable=True,
        p_nom_min=0.0,
        p_nom_max=10.0,
        p_min_pu=-1.0,
        p_max_pu=1.0,
        capital_cost=500.0,
        marginal_cost=market_price,
    )
    
    # Gas supply (wichtig!)
    n.add(
        "Generator",
        "gas_supply",
        bus="bus_gas",
        carrier="gas",
        p_nom_extendable=True,
        capital_cost=0,
        marginal_cost=25.0,  # Gaspreis
        p_nom_max=1000,
    )
    
    # Storage
    n.add(
        "Store",
        "gas_storage",
        bus="bus_gas",
        e_nom_extendable=True,
        e_initial=0,  # Start empty
        e_min_pu=0.0,
        standing_loss=0.0,
        capital_cost=30,
    )
    n.add(
        "Store",
        "thermal_buffer",
        bus="bus_heat",
        carrier="heat",
        e_nom_extendable=True,
        e_initial=0,  # Start empty
        e_min_pu=0.0,
        capital_cost=20,
        standing_loss=0.01,
    )
    
    # Auxiliary boiler (simple heat source)
    n.add(
        "Link",
        "aux_heat_boiler",
        bus0="bus_gas",
        bus1="bus_heat",
        carrier="heat",
        efficiency=0.92,
        capital_cost=350,
        p_nom_extendable=True,
        p_nom_max=60,
        marginal_cost=200,
    )
    
    return n

print("Building minimal network WITHOUT BHKW...")
n = build_network()

print("Optimizing...")
n.optimize(solver_name="highs", solver_options={"mip_rel_gap": 0.8, "threads": 16})

print("\nOptimization status:", n.optimization_results.status)
print("Objective:", n.objective)

print("\nGenerator capacities:")
print(n.generators.p_nom_opt)

print("\nLink capacities:")
print(n.links.p_nom_opt)

print("\nStore capacities:")
print(n.stores.e_nom_opt)

print("\n==> Das Basissystem ist", "FEASIBLE" if n.optimization_results.status == "ok" else "INFEASIBLE")
