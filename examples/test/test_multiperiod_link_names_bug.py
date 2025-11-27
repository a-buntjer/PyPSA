#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test-Skript zur Reproduktion des Dual-Assignment Bugs

BUG: Bei Multi-Period + Multi-Szenario Optimierung mit Link-Namen die
     Jahres-Suffixe enthalten (z.B. 'grid_2027', 'grid_2030') tritt nach
     der Optimierung ein ValueError auf:
     
     ValueError: cannot reindex on an axis with duplicate labels
     
     Ort: pypsa/optimization/common.py, Zeile ~59, _set_dynamic_data()

Dieser Bug tritt auf weil:
1. Links mit Namen wie 'elec_grid_2027' und 'elec_grid_2030' werden erstellt
2. Nach Szenario-Expansion: (scenario, 'elec_grid_2027'), (scenario, 'elec_grid_2030')
3. Bei Dual-Zuweisung versucht PyPSA, c.names zu reindexen
4. Die Namen sind aber nicht mehr eindeutig weil sie in mehreren Szenarien vorkommen
"""

import pypsa
import pandas as pd
import numpy as np


def create_test_network_with_period_suffixes():
    """
    Erstellt ein Testnetzwerk mit Link-Namen die Jahres-Suffixe haben.
    Dies reproduziert den Bug aus dem Sylt-Netzwerk.
    """
    print("=" * 80)
    print("TEST: Multi-Period Link Names Bug Reproduktion")
    print("=" * 80)
    
    # Konfiguration
    periods = [2027, 2030]
    # Szenario-Wahrscheinlichkeiten (Format für set_scenarios)
    scenarios = {
        "low": 0.3,
        "base": 0.4,
        "high": 0.3,
    }
    # Zusätzliche Szenario-Parameter
    scenario_params = {
        "low": {"price_factor": 0.9},
        "base": {"price_factor": 1.0},
        "high": {"price_factor": 1.1},
    }
    
    # Erstelle Snapshots
    hourly_2027 = pd.date_range("2027-01-01", periods=8760, freq="h")
    hourly_2030 = pd.date_range("2030-01-01", periods=8760, freq="h")
    
    snapshots = pd.MultiIndex.from_tuples(
        [(p, t) for p in periods for t in (hourly_2027 if p == 2027 else hourly_2030)],
        names=["period", "snapshot"]
    )
    
    # Network erstellen
    network = pypsa.Network()
    network.snapshots = snapshots
    network.set_investment_periods(periods)
    network.investment_period_weightings.loc[2027, "years"] = 3
    network.investment_period_weightings.loc[2030, "years"] = 5
    
    # Busse
    network.add("Bus", "electricity_market", carrier="electricity")
    network.add("Bus", "site_electricity", carrier="electricity")
    network.add("Bus", "heat", carrier="heat")
    
    # Generator (Markt)
    network.add(
        "Generator",
        "electricity_price",
        bus="electricity_market",
        p_nom=1000,
        marginal_cost=80,  # wird später überschrieben
    )
    
    # =========================================================================
    # KRITISCH: Links MIT Jahres-Suffix (wie im Sylt-Netzwerk)
    # =========================================================================
    # Diese Link-Namen verursachen den Bug!
    for period in periods:
        network.add(
            "Link",
            f"elec_grid_{period}",  # <-- Jahres-Suffix!
            bus0="electricity_market",
            bus1="site_electricity",
            p_nom=100,
            efficiency=1.0,
            marginal_cost=15.0,  # Netzentgelt
        )
    
    # Wärmeerzeuger (ohne Jahres-Suffix - diese sind OK)
    network.add(
        "Link",
        "heat_pump",
        bus0="site_electricity",
        bus1="heat",
        p_nom_extendable=True,
        p_nom_max=10,
        efficiency=3.0,  # COP
        capital_cost=50000,
    )
    
    network.add(
        "Link",
        "gas_boiler",
        bus0="electricity_market",  # Vereinfacht
        bus1="heat",
        p_nom_extendable=True,
        p_nom_max=10,
        efficiency=0.9,
        capital_cost=20000,
    )
    
    # Wärmelast
    network.add(
        "Load",
        "heat_demand",
        bus="heat",
    )
    
    # Speicher
    network.add(
        "Store",
        "heat_storage",
        bus="heat",
        e_nom_extendable=True,
        e_nom_max=50,
        e_cyclic=True,
        capital_cost=1000,
    )
    
    print(f"\nKomponenten VOR Szenario-Expansion:")
    print(f"  Links: {list(network.links.index)}")
    print(f"  Stores: {list(network.stores.index)}")
    print(f"  Generators: {list(network.generators.index)}")
    
    # =========================================================================
    # Szenario-Expansion
    # =========================================================================
    print(f"\nSetze Szenarien: {list(scenarios.keys())}")
    network.set_scenarios(scenarios)
    
    print(f"\nKomponenten NACH Szenario-Expansion:")
    print(f"  Links: {len(network.links)} total")
    if isinstance(network.links.index, pd.MultiIndex):
        unique_names = network.links.index.get_level_values(1).unique()
        print(f"    Unique Namen: {list(unique_names)}")
    
    # =========================================================================
    # Zeitreihen setzen
    # =========================================================================
    print("\nSetze Zeitreihen...")
    
    # Wärmelast
    np.random.seed(42)
    heat_demand_base = 2.0 + 1.5 * np.sin(2 * np.pi * np.arange(8760) / 8760)
    noise = np.random.normal(1.0, 0.1, 8760)
    heat_demand_base = heat_demand_base * noise
    
    load_p_set = pd.DataFrame(index=snapshots)
    for scenario in scenarios.keys():
        col = (scenario, "heat_demand")
        demand_factor = scenario_params[scenario]["price_factor"]
        for period in periods:
            period_mask = snapshots.get_level_values(0) == period
            load_p_set.loc[period_mask, col] = heat_demand_base * demand_factor
    
    network.loads_t.p_set = load_p_set
    
    # Strompreise (marginal_cost)
    gen_mc = pd.DataFrame(index=snapshots)
    for scenario in scenarios.keys():
        col = (scenario, "electricity_price")
        price = 80 * scenario_params[scenario]["price_factor"]
        gen_mc[col] = price
    
    network.generators_t.marginal_cost = gen_mc
    
    print("  OK Zeitreihen gesetzt")
    
    return network, scenarios, scenario_params


def test_optimization():
    """Führt die Optimierung durch und zeigt den Bug."""
    
    network, scenarios, scenario_params = create_test_network_with_period_suffixes()
    
    print("\n" + "=" * 80)
    print("STARTE OPTIMIERUNG")
    print("=" * 80)
    print("\nDieser Test sollte den Bug reproduzieren:")
    print("  ValueError: cannot reindex on an axis with duplicate labels")
    print()
    
    try:
        network.optimize(
            solver_name="highs",
            solver_options={"threads": 4, "time_limit": 120},
        )
        
        print("\n" + "=" * 80)
        print("OPTIMIERUNG ERFOLGREICH (kein Bug!)")
        print("=" * 80)
        print(f"\nObjective: {network.objective:,.2f} EUR")
        
    except ValueError as e:
        if "cannot reindex" in str(e) or "duplicate labels" in str(e):
            print("\n" + "=" * 80)
            print("BUG REPRODUZIERT!")
            print("=" * 80)
            print(f"\nFehler: {e}")
            print("\nDieser Bug tritt auf in:")
            print("  pypsa/optimization/common.py, _set_dynamic_data()")
            print("  Zeile: .reindex(c.names, level='name', axis=1)")
            raise
        else:
            raise


def test_without_period_suffixes():
    """Vergleichstest OHNE Jahres-Suffixe - sollte funktionieren."""
    
    print("\n" + "=" * 80)
    print("VERGLEICHSTEST: Ohne Jahres-Suffixe")
    print("=" * 80)
    
    periods = [2027, 2030]
    scenarios = {
        "low": 0.3,
        "base": 0.4,
        "high": 0.3,
    }
    scenario_params = {
        "low": {"price_factor": 0.9},
        "base": {"price_factor": 1.0},
        "high": {"price_factor": 1.1},
    }
    
    hourly_2027 = pd.date_range("2027-01-01", periods=8760, freq="h")
    hourly_2030 = pd.date_range("2030-01-01", periods=8760, freq="h")
    
    snapshots = pd.MultiIndex.from_tuples(
        [(p, t) for p in periods for t in (hourly_2027 if p == 2027 else hourly_2030)],
        names=["period", "snapshot"]
    )
    
    network = pypsa.Network()
    network.snapshots = snapshots
    network.set_investment_periods(periods)
    network.investment_period_weightings.loc[2027, "years"] = 3
    network.investment_period_weightings.loc[2030, "years"] = 5
    
    network.add("Bus", "electricity_market", carrier="electricity")
    network.add("Bus", "site_electricity", carrier="electricity")
    network.add("Bus", "heat", carrier="heat")
    
    network.add(
        "Generator",
        "electricity_price",
        bus="electricity_market",
        p_nom=1000,
        marginal_cost=80,
    )
    
    # OHNE Jahres-Suffix - nur ein Link
    network.add(
        "Link",
        "elec_grid",  # <-- Kein Suffix!
        bus0="electricity_market",
        bus1="site_electricity",
        p_nom=100,
        efficiency=1.0,
        marginal_cost=15.0,
    )
    
    network.add(
        "Link",
        "heat_pump",
        bus0="site_electricity",
        bus1="heat",
        p_nom_extendable=True,
        p_nom_max=10,
        efficiency=3.0,
        capital_cost=50000,
    )
    
    network.add(
        "Load",
        "heat_demand",
        bus="heat",
    )
    
    network.add(
        "Store",
        "heat_storage",
        bus="heat",
        e_nom_extendable=True,
        e_nom_max=50,
        e_cyclic=True,
        capital_cost=1000,
    )
    
    print(f"\nKomponenten: {list(network.links.index)}")
    
    network.set_scenarios(scenarios)
    
    # Zeitreihen
    np.random.seed(42)
    heat_demand_base = 2.0 + 1.5 * np.sin(2 * np.pi * np.arange(8760) / 8760)
    noise = np.random.normal(1.0, 0.1, 8760)
    heat_demand_base = heat_demand_base * noise
    
    load_p_set = pd.DataFrame(index=snapshots)
    for scenario in scenarios.keys():
        col = (scenario, "heat_demand")
        for period in periods:
            period_mask = snapshots.get_level_values(0) == period
            load_p_set.loc[period_mask, col] = heat_demand_base * scenario_params[scenario]["price_factor"]
    
    network.loads_t.p_set = load_p_set
    
    gen_mc = pd.DataFrame(index=snapshots)
    for scenario in scenarios.keys():
        col = (scenario, "electricity_price")
        gen_mc[col] = 80 * scenario_params[scenario]["price_factor"]
    
    network.generators_t.marginal_cost = gen_mc
    
    print("Optimiere...")
    
    try:
        network.optimize(
            solver_name="highs",
            solver_options={"threads": 4, "time_limit": 120},
        )
        print(f"\nOK - Kein Bug! Objective: {network.objective:,.2f} EUR")
        
    except Exception as e:
        print(f"\nUnerwarteter Fehler: {e}")
        raise


if __name__ == "__main__":
    # Test 1: MIT Jahres-Suffixen (sollte Bug zeigen)
    try:
        test_optimization()
    except ValueError:
        print("\n>>> Bug wie erwartet aufgetreten <<<")
    
    # Test 2: OHNE Jahres-Suffixe - übersprungen für jetzt
    # test_without_period_suffixes()
    
    print("\n" + "=" * 80)
    print("TESTS ABGESCHLOSSEN")
    print("=" * 80)
