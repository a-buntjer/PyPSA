#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Neues Wärmenetz - Vollständiges Optimierungsbeispiel

Erstellt Netzwerk, generiert synthetische Zeitreihen und optimiert.
"""

import pypsa
import pandas as pd
import numpy as np
from pathlib import Path
import sys

# Import lokale Module
sys.path.insert(0, str(Path(__file__).parent))
import neues_netz_config_parameters as cfg
import neues_netz_network_creator as creator


def generate_synthetic_heat_demand(base_demand_mw=5.0, scenario_factor=1.0, year=2027):
    """
    Generiert synthetisches Wärmelastprofil für ein Jahr (8760 Stunden).
    
    Args:
        base_demand_mw: Basis-Spitzenlast in MW
        scenario_factor: Szenario-Skalierung (0.9 = niedrig, 1.0 = mittel, 1.1 = hoch)
        year: Jahr für Trendberechnung
    
    Returns:
        pd.Series mit stündlichen Werten [MW]
    """
    hours = 8760
    timestamps = pd.date_range(f"{year}-01-01", periods=hours, freq="h")
    
    # Jahresgang (Winter höher als Sommer)
    day_of_year = np.arange(hours) / 24
    seasonal = 1.0 + 0.4 * np.cos(2 * np.pi * (day_of_year - 15) / 365)  # Maximum im Januar
    
    # Tagesgang (Morgens und Abends Peaks)
    hour_of_day = np.arange(hours) % 24
    daily = 0.6 + 0.2 * np.cos(2 * np.pi * (hour_of_day - 7) / 24)  # Morgen-Peak um 7 Uhr
    daily += 0.2 * np.cos(2 * np.pi * (hour_of_day - 19) / 24)  # Abend-Peak um 19 Uhr
    
    # Zufälliges Rauschen
    np.random.seed(42 + year)
    noise = np.random.normal(1.0, 0.1, hours)
    
    # Kombiniere alle Komponenten
    demand = base_demand_mw * seasonal * daily * noise * scenario_factor
    
    # Nie negativ
    demand = np.maximum(demand, 0.1)
    
    return pd.Series(demand, index=timestamps, name="heat_demand")


def generate_synthetic_electricity_price(base_price=90.0, scenario_factor=1.0, 
                                         variation=20.0, year=2027):
    """
    Generiert synthetischen Strompreis für ein Jahr (8760 Stunden).
    
    Args:
        base_price: Basis-Strompreis in EUR/MWh
        scenario_factor: Szenario-Skalierung
        variation: Tägliche Preisvariation in EUR/MWh
        year: Jahr
    
    Returns:
        pd.Series mit stündlichen Preisen [EUR/MWh]
    """
    hours = 8760
    timestamps = pd.date_range(f"{year}-01-01", periods=hours, freq="h")
    
    # Tagesgang (teuer tagsüber, billig nachts)
    hour_of_day = np.arange(hours) % 24
    daily = base_price + variation * np.sin(2 * np.pi * (hour_of_day - 6) / 24)
    
    # Wochengang (Wochenende billiger)
    day_of_week = (np.arange(hours) // 24) % 7
    weekly = np.where(day_of_week >= 5, 0.85, 1.0)  # Sa/So: -15%
    
    # Zufälliges Rauschen
    np.random.seed(100 + year)
    noise = np.random.normal(1.0, 0.05, hours)
    
    # Kombiniere
    price = daily * weekly * noise * scenario_factor
    
    # Nie negativ, min 10 EUR/MWh
    price = np.maximum(price, 10.0)
    
    return pd.Series(price, index=timestamps, name="electricity_price")


def generate_synthetic_gas_price(base_price=40.0, year=2027):
    """
    Generiert synthetischen Gaspreis (konstant).
    
    Args:
        base_price: Gaspreis in EUR/MWh
        year: Jahr
    
    Returns:
        pd.Series mit stündlichen Preisen [EUR/MWh]
    """
    hours = 8760
    timestamps = pd.date_range(f"{year}-01-01", periods=hours, freq="h")
    
    # Gaspreis weitgehend konstant, leichte Schwankung im Winter
    day_of_year = np.arange(hours) / 24
    seasonal = 1.0 + 0.1 * np.cos(2 * np.pi * (day_of_year - 15) / 365)
    
    price = base_price * seasonal
    
    return pd.Series(price, index=timestamps, name="gas_price")


def generate_synthetic_cop(base_cop=3.0, year=2027):
    """
    Generiert synthetischen COP für Luft-Wärmepumpe.
    
    COP variiert mit Außentemperatur:
    - Winter (kalt): niedrigerer COP (2.0 - 2.5)
    - Sommer (warm): höherer COP (3.5 - 4.5)
    
    Args:
        base_cop: Durchschnittlicher COP
        year: Jahr
    
    Returns:
        pd.Series mit stündlichen COP-Werten [-]
    """
    hours = 8760
    timestamps = pd.date_range(f"{year}-01-01", periods=hours, freq="h")
    
    # Jahresgang der Außentemperatur (vereinfacht)
    day_of_year = np.arange(hours) / 24
    temp_celsius = 10.0 + 10.0 * np.cos(2 * np.pi * (day_of_year - 200) / 365)  # Min im Januar
    
    # Tagesgang
    hour_of_day = np.arange(hours) % 24
    temp_daily = 3.0 * np.sin(2 * np.pi * (hour_of_day - 6) / 24)  # Nachts kälter
    
    temp = temp_celsius + temp_daily
    
    # COP-Modell: COP = 0.4 * (T_out + 273) / (T_supply - T_out)
    # Vereinfacht: COP steigt mit Außentemperatur
    # Bei -10°C: COP ≈ 2.0, bei +20°C: COP ≈ 4.5
    cop = 2.0 + 0.1 * (temp + 10)
    
    # Begrenze COP auf realistischen Bereich
    cop = np.clip(cop, 2.0, 4.5)
    
    return pd.Series(cop, index=timestamps, name="cop")


def prepare_time_series_data():
    """
    Erstellt alle benötigten Zeitreihen für alle Szenarien und Perioden.
    
    Returns:
        Tuple von Dictionaries: (heat_demand, electricity_price, gas_price, cop)
    """
    print("\n" + "=" * 80)
    print("GENERIERE SYNTHETISCHE ZEITREIHEN")
    print("=" * 80)
    
    heat_demand_dict = {}
    electricity_price_dict = {}
    gas_price_dict = {}
    cop_dict = {}
    
    for scenario_name, scenario_params in cfg.SCENARIOS.items():
        print(f"\nSzenario: {scenario_name}")
        
        demand_factor = scenario_params["demand_factor"]
        elec_factor = scenario_params["electricity_price_factor"]
        growth_rate = scenario_params["demand_growth_rate"]
        
        for period_idx, period in enumerate(cfg.INVESTMENT_PERIODS):
            print(f"  Periode {period}...", end=" ")
            
            # Berechne Wachstum seit Basisjahr 2027
            years_passed = period - 2027
            growth_multiplier = (1 + growth_rate) ** years_passed
            
            # Strompreis-Trend
            base_elec_price = cfg.get_electricity_base_price(period)
            
            # Generiere Zeitreihen
            heat_demand = generate_synthetic_heat_demand(
                base_demand_mw=5.0,
                scenario_factor=demand_factor * growth_multiplier,
                year=period
            )
            
            elec_price = generate_synthetic_electricity_price(
                base_price=base_elec_price,
                scenario_factor=elec_factor,
                variation=20.0,
                year=period
            )
            
            gas_price = generate_synthetic_gas_price(
                base_price=cfg.get_gas_price(period),
                year=period
            )
            
            cop = generate_synthetic_cop(
                base_cop=3.0,
                year=period
            )
            
            # Speichere in Dictionaries
            heat_demand_dict[(scenario_name, period)] = heat_demand
            electricity_price_dict[(scenario_name, period)] = elec_price
            gas_price_dict[period] = gas_price  # Gas-Preis scenario-unabhängig
            cop_dict[(scenario_name, period)] = cop
            
            print(f"OK (Spitzenlast: {heat_demand.max():.1f} MW, "
                  f"Ø Strom: {elec_price.mean():.1f} EUR/MWh)")
    
    print("\n" + "=" * 80)
    print("ZEITREIHEN GENERIERT")
    print("=" * 80)
    
    return heat_demand_dict, electricity_price_dict, gas_price_dict, cop_dict


def optimize_network(network):
    """
    Optimiert das Netzwerk mit PyPSA.
    
    Args:
        network: PyPSA Network mit gesetzten Zeitreihen
    
    Returns:
        Optimiertes Network
    """
    print("\n" + "=" * 80)
    print("STARTE OPTIMIERUNG")
    print("=" * 80)
    
    solver_name = cfg.SOLVER_CONFIG["solver_name"]
    time_limit = cfg.SOLVER_CONFIG["time_limit"]
    threads = cfg.SOLVER_CONFIG["threads"]
    
    print(f"\nSolver: {solver_name}")
    print(f"Threads: {threads}")
    print(f"Time Limit: {time_limit}s")
    print(f"Multi-Investment: True")
    print(f"Stochastic: {cfg.USE_STOCHASTIC}")
    
    # Optimiere
    try:
        network.optimize(
            solver_name=solver_name,
            solver_options={
                "time_limit": time_limit,
                "threads": threads,
            },
            multi_investment_periods=True,
        )
        
        print("\n" + "=" * 80)
        print("OPTIMIERUNG ERFOLGREICH")
        print("=" * 80)
        print(f"\nZielfunktionswert: {network.objective:,.2f} EUR")
        
        return network
        
    except Exception as e:
        print("\n" + "=" * 80)
        print("OPTIMIERUNG FEHLGESCHLAGEN")
        print("=" * 80)
        print(f"\nFehler: {e}")
        raise


def print_results(network):
    """
    Gibt Optimierungsergebnisse aus.
    
    Args:
        network: Optimiertes PyPSA Network
    """
    print("\n" + "=" * 80)
    print("OPTIMIERUNGSERGEBNISSE")
    print("=" * 80)
    
    # Check if stochastic (MultiIndex components)
    is_stochastic = isinstance(network.links.index, pd.MultiIndex)
    
    if is_stochastic:
        scenarios = network.links.index.get_level_values(0).unique()
        print(f"\nStochastische Optimierung mit {len(scenarios)} Szenarien")
        
        for scenario in scenarios:
            print(f"\n{'='*80}")
            print(f"SZENARIO: {scenario.upper()}")
            print(f"{'='*80}")
            
            # Links (Erzeuger)
            print("\nInstallierte Leistungen [MW]:")
            for link_name in ["luft_wp", "gaskessel"]:
                link_idx = (scenario, link_name)
                if link_idx in network.links.index:
                    p_nom_opt = network.links.at[link_idx, "p_nom_opt"]
                    print(f"  {link_name:20s}: {p_nom_opt:8.2f} MW")
            
            # Stores (Speicher)
            print("\nInstallierte Speicherkapazität [MWh]:")
            store_idx = (scenario, "heat_storage")
            if store_idx in network.stores.index:
                e_nom_opt = network.stores.at[store_idx, "e_nom_opt"]
                print(f"  heat_storage:         {e_nom_opt:8.2f} MWh")
            
            # Jahresenergie
            print("\nJahresenergien [MWh]:")
            for period in cfg.INVESTMENT_PERIODS:
                period_mask = network.snapshots.get_level_values(0) == period
                period_snapshots = network.snapshots[period_mask]
                
                print(f"\n  Periode {period}:")
                
                # Wärmelast
                load_idx = (scenario, "heat_demand")
                if load_idx in network.loads_t.p_set.columns:
                    demand_total = network.loads_t.p_set.loc[period_snapshots, load_idx].sum()
                    print(f"    Wärmelast:           {demand_total/1000:8.2f} GWh")
                
                # Wärmepumpe
                link_idx = (scenario, "luft_wp")
                if link_idx in network.links_t.p1.columns:
                    wp_heat = network.links_t.p1.loc[period_snapshots, link_idx].sum()
                    print(f"    Wärmepumpe:          {wp_heat/1000:8.2f} GWh")
                
                # Gaskessel
                link_idx = (scenario, "gaskessel")
                if link_idx in network.links_t.p1.columns:
                    boiler_heat = network.links_t.p1.loc[period_snapshots, link_idx].sum()
                    print(f"    Gaskessel:           {boiler_heat/1000:8.2f} GWh")
    
    else:
        # Deterministisch
        print("\nDeterministische Optimierung")
        
        # Links (Erzeuger)
        print("\nInstallierte Leistungen [MW]:")
        for link_name in ["luft_wp", "gaskessel"]:
            if link_name in network.links.index:
                p_nom_opt = network.links.at[link_name, "p_nom_opt"]
                print(f"  {link_name:20s}: {p_nom_opt:8.2f} MW")
        
        # Stores (Speicher)
        print("\nInstallierte Speicherkapazität [MWh]:")
        if "heat_storage" in network.stores.index:
            e_nom_opt = network.stores.at["heat_storage", "e_nom_opt"]
            print(f"  heat_storage:         {e_nom_opt:8.2f} MWh")
        
        # Jahresenergie
        print("\nJahresenergien [MWh]:")
        for period in cfg.INVESTMENT_PERIODS:
            period_mask = network.snapshots.get_level_values(0) == period
            period_snapshots = network.snapshots[period_mask]
            
            print(f"\n  Periode {period}:")
            
            # Wärmelast
            if "heat_demand" in network.loads_t.p_set.columns:
                demand_total = network.loads_t.p_set.loc[period_snapshots, "heat_demand"].sum()
                print(f"    Wärmelast:           {demand_total/1000:8.2f} GWh")
            
            # Wärmepumpe
            if "luft_wp" in network.links_t.p1.columns:
                wp_heat = network.links_t.p1.loc[period_snapshots, "luft_wp"].sum()
                print(f"    Wärmepumpe:          {wp_heat/1000:8.2f} GWh")
            
            # Gaskessel
            if "gaskessel" in network.links_t.p1.columns:
                boiler_heat = network.links_t.p1.loc[period_snapshots, "gaskessel"].sum()
                print(f"    Gaskessel:           {boiler_heat/1000:8.2f} GWh")
    
    print("\n" + "=" * 80)


def main():
    """Hauptfunktion: Erstellt Netzwerk, setzt Zeitreihen, optimiert."""
    
    print("=" * 80)
    print("NEUES WÄRMENETZ - VOLLSTÄNDIGE OPTIMIERUNG")
    print("=" * 80)
    print(f"\nModus: {'STOCHASTISCH' if cfg.USE_STOCHASTIC else 'DETERMINISTISCH'}")
    print(f"Szenarien: {list(cfg.SCENARIOS.keys())}")
    print(f"Perioden: {cfg.INVESTMENT_PERIODS}")
    print()
    
    # 1. Erstelle Netzwerk
    network = creator.create_neues_netz_network(use_unit_commitment=False)
    
    # 2. Generiere Zeitreihen
    heat_demand_dict, elec_price_dict, gas_price_dict, cop_dict = prepare_time_series_data()
    
    # 3. Setze Zeitreihen
    creator.set_time_series(
        network=network,
        heat_demand_dict=heat_demand_dict,
        electricity_price_dict=elec_price_dict,
        gas_price_dict=gas_price_dict,
        cop_dict=cop_dict,
    )
    
    # 4. Optimiere
    network = optimize_network(network)
    
    # 5. Ergebnisse ausgeben
    print_results(network)
    
    print("\n" + "=" * 80)
    print("FERTIG")
    print("=" * 80)


if __name__ == "__main__":
    main()
