#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Neues Wärmenetz - PyPSA Network Creator

Vereinfachte Topologie für neues Wärmenetz:
- Erzeuger: Luft-Wasser-Wärmepumpe, Erdgaskessel, Fremdwärme (11 GWh/a)
- Speicher: Wärmespeicher (ausbaubar)
- 3 Szenarien mit gleicher Gewichtung (1/3 jeweils)
- 2 Investitionsperioden: 2027-2037 (BEW aktiv), 2037-2042 (keine BEW)

Basiert auf sylt_network_creator_v4.py, stark vereinfacht.
"""

import pypsa
import pandas as pd
import numpy as np
from pathlib import Path
import sys

# Import lokales Config-Modul
sys.path.insert(0, str(Path(__file__).parent.parent / "03_config"))
import neues_netz_config_parameters as cfg


def create_neues_netz_network(use_unit_commitment=None):
    """
    Erstellt PyPSA-Netzwerk für neues Wärmenetz.
    
    Struktur (7 Busse):
    - Märkte (3): electricity_market, gas_market, external_heat_market
    - Netzanschlüsse (2): site_electricity (für WP), site_gas (für Kessel)
    - Wärme (1): central_heat
    - Speicher (1): heat_storage (an central_heat)
    
    Args:
        use_unit_commitment: Wenn True, MILP mit committable constraints
                            Wenn False, LP (kontinuierlich, schneller)
                            Wenn None, aus Config
    
    Returns:
        pypsa.Network: Optimierungsfähiges Netzwerk
    """
    
    if use_unit_commitment is None:
        use_unit_commitment = cfg.SOLVER_CONFIG.get("use_unit_commitment", False)
    
    print("=" * 80)
    print("NEUES WÄRMENETZ - NETWORK CREATOR")
    print("=" * 80)
    print(f"Unit Commitment: {use_unit_commitment} ({'MILP' if use_unit_commitment else 'LP'})")
    print()
    
    # =============================================================================
    # 1. Initialize Network
    # =============================================================================
    print("Schritt 1: Initialisiere PyPSA Network...")
    
    network = pypsa.Network(name="Neues Wärmenetz")
    
    # Create multi-period snapshots via set_snapshots (aligns internal structures)
    snapshot_tuples = []
    for period in cfg.INVESTMENT_PERIODS:
        period_snapshots = pd.date_range(
            start=f"{period}-01-01 00:00",
            freq="h",
            periods=8760,
        )
        snapshot_tuples.extend((period, ts) for ts in period_snapshots)
    
    multi_index_snapshots = pd.MultiIndex.from_tuples(
        snapshot_tuples,
        names=["period", "timestep"],
    )
    network.set_snapshots(multi_index_snapshots)
    try:
        network.set_investment_periods(cfg.INVESTMENT_PERIODS)
    except AttributeError:
        # Fallback for older PyPSA versions without helper
        network.investment_periods = pd.Index(cfg.INVESTMENT_PERIODS, name="period")
    
    # Set investment period weightings (years)
    network.investment_period_weightings.loc[:, "years"] = cfg.INVESTMENT_PERIOD_WEIGHTINGS
    
    # Set objective weightings with discounting
    r_objective = cfg.ECONOMIC_PARAMS["discount_rate_objective"]
    T = 0
    objective_weights = []
    
    for period in network.investment_periods:
        nyears = int(network.investment_period_weightings.at[period, 'years'])
        discounts = [(1 / (1 + r_objective) ** t) for t in range(T, T + nyears)]
        weight = sum(discounts)
        objective_weights.append(weight)
        T += nyears
    
    network.investment_period_weightings.loc[:, "objective"] = objective_weights
    
    print(f"  OK Network initialisiert: {network.name}")
    print(f"  OK Snapshots: {len(network.snapshots):,} stündliche Zeitschritte")
    print(f"  OK Investitionsperioden: {cfg.INVESTMENT_PERIODS}")
    print(f"  OK Perioden-Gewichtung (Jahre): {dict(cfg.INVESTMENT_PERIOD_WEIGHTINGS)}")
    print(f"  OK Perioden-Gewichtung (diskontiert, r={r_objective:.1%}): "
          f"{dict(zip(network.investment_periods, objective_weights))}")
    print()
    
    # =============================================================================
    # 2. Register Carriers
    # =============================================================================
    print("Schritt 2: Registriere Energieträger...")
    
    carriers = [
        ("heat", "Fernwärme", "#d62728", 0.0),
        ("electricity", "Strom", "#ff7f0e", 0.0),
        ("gas", "Erdgas", "#8B4513", 0.201),
        ("heat_pump", "Wärmepumpe", "#1f77b4", 0.0),
        ("gas_boiler", "Gaskessel", "#8c564b", 0.201),
        ("external_heat", "Fremdwärme", "#2ca02c", 0.0),
    ]
    
    for name, nice_name, color, co2 in carriers:
        network.add(
            "Carrier",
            name,
            nice_name=nice_name,
            color=color,
            co2_emissions=co2,
        )
    
    print(f"  OK Registriert: {len(carriers)} Energieträger")
    print()
    
    # =============================================================================
    # 3. Add Buses
    # =============================================================================
    print("Schritt 3: Füge Busse hinzu...")
    
    # Markt-Busse
    network.add("Bus", "electricity_market", carrier="electricity", v_nom=1.0)
    network.add("Bus", "gas_market", carrier="gas", v_nom=1.0)
    network.add("Bus", "external_heat_market", carrier="external_heat", v_nom=1.0)
    
    # Netzanschluss-Busse (mit Netzentgelten)
    network.add("Bus", "site_electricity", carrier="electricity", v_nom=1.0)
    network.add("Bus", "site_gas", carrier="gas", v_nom=1.0)
    
    # Wärme-Bus
    network.add("Bus", "central_heat", carrier="heat", v_nom=1.0)
    
    print(f"  OK Erstellt: {len(network.buses)} Busse")
    print()
    
    # =============================================================================
    # 4. Add Market Price Generators
    # =============================================================================
    print("Schritt 4: Füge Marktpreis-Generatoren hinzu...")
    
    # Strom-Marktpreis (wird später mit Zeitreihe gefüllt)
    network.add(
        "Generator",
        "electricity_market_price",
        bus="electricity_market",
        carrier="electricity",
        p_nom=1e6,  # Unbegrenzt
        marginal_cost=0.0,  # Wird durch Zeitreihe überschrieben
    )
    
    # Gas-Marktpreis
    network.add(
        "Generator",
        "gas_market_price",
        bus="gas_market",
        carrier="gas",
        p_nom=1e6,
        marginal_cost=0.0,  # Wird durch Zeitreihe überschrieben
    )
    
    # Fremdwärme-Marktpreis
    network.add(
        "Generator",
        "external_heat_market_price",
        bus="external_heat_market",
        carrier="external_heat",
        p_nom=1e6,
        marginal_cost=cfg.ENERGY_PRICES["fremdwaerme"]["price"],
    )
    
    print(f"  OK Erstellt: 3 Marktpreis-Generatoren")
    print()
    
    # =============================================================================
    # 5. Add Network Tariff Links (Market -> Site)
    # =============================================================================
    print("Schritt 5: Füge Netzentgelt-Links hinzu...")
    
    # Strom: Markt -> Netzanschluss (mit Netzentgelten + Abgaben)
    electricity_tariff = (
        cfg.NETWORK_TARIFFS["electricity"]["arbeitspreis_mischpreis_eur_mwh"] +
        sum(cfg.LEVIES_AND_TAXES["electricity"].values())
    )
    
    network.add(
        "Link",
        "grid_electricity",
        bus0="electricity_market",
        bus1="site_electricity",
        efficiency=1.0,
        p_nom=1e6,
        p_max_pu=1.0,  # WICHTIG: Erlaubt Strom-Durchfluss
        marginal_cost=electricity_tariff,
    )
    
    # Gas: Markt -> Netzanschluss (mit Netzentgelten + Abgaben)
    gas_tariff = (
        cfg.NETWORK_TARIFFS["gas"]["arbeitspreis_mischpreis_eur_mwh"] +
        sum(cfg.LEVIES_AND_TAXES["gas"].values())
    )
    
    network.add(
        "Link",
        "grid_gas",
        bus0="gas_market",
        bus1="site_gas",
        efficiency=1.0,
        p_nom=1e6,
        p_max_pu=1.0,  # WICHTIG: Erlaubt Gas-Durchfluss
        marginal_cost=gas_tariff,
    )
    
    print(f"  OK Erstellt: 2 Netzentgelt-Links")
    print(f"    - Strom-Netzentgelt: {electricity_tariff:.2f} EUR/MWh")
    print(f"    - Gas-Netzentgelt: {gas_tariff:.2f} EUR/MWh")
    print()
    
    # =============================================================================
    # 6. Add Heat Generators
    # =============================================================================
    print("Schritt 6: Füge Wärmeerzeuger hinzu...")
    
    # --- 6a. Luft-Wasser-Wärmepumpe (ausbaubar) ---
    tech_wp = cfg.TECHNOLOGIES["luft_wp"]
    
    # CAPEX mit BEW-Förderung in Periode 1, ohne in Periode 2
    capex_wp_period1 = cfg.get_technology_capex("luft_wp", apply_bew_subsidy=True)
    capex_wp_period2 = cfg.get_technology_capex("luft_wp", apply_bew_subsidy=False)
    
    # Annuitäten berechnen
    annuity_wp_period1 = cfg.calculate_annuity(
        capex_wp_period1 * 1000,  # EUR/kW -> EUR/MW
        tech_wp["lifetime_years"]
    )
    annuity_wp_period2 = cfg.calculate_annuity(
        capex_wp_period2 * 1000,
        tech_wp["lifetime_years"]
    )
    
    # Link: Strom -> Wärme (Multi-Output nicht nötig, da nur Wärme)
    network.add(
        "Link",
        "luft_wp",
        bus0="site_electricity",
        bus1="central_heat",
        carrier="heat_pump",
        efficiency=tech_wp["cop"],  # Wird durch COP-Zeitreihe überschrieben
        p_nom=0.0,
        p_nom_extendable=True,
        p_nom_max=tech_wp["p_nom_max_mw"],
        capital_cost=annuity_wp_period1 + tech_wp["opex_fixed_eur_per_kw_year"] * 1000,  # Initial für Periode 1
        build_year=2027,  # WICHTIG: Für multi-period
        lifetime=tech_wp["lifetime_years"],
    )
    
    # WICHTIG: Zeit-variable capital_cost für WP setzen wir später in set_time_series()
    # da PyPSA das Dictionary-Format nicht akzeptiert
    
    # --- 6b. Erdgaskessel (ausbaubar) ---
    tech_kessel = cfg.TECHNOLOGIES["gaskessel"]
    
    annuity_kessel = cfg.calculate_annuity(
        tech_kessel["base_capex_eur_per_kw"] * 1000,
        tech_kessel["lifetime_years"]
    )
    
    network.add(
        "Link",
        "gaskessel",
        bus0="site_gas",
        bus1="central_heat",
        carrier="gas_boiler",
        efficiency=tech_kessel["efficiency"],
        p_nom=0.0,
        p_nom_extendable=True,
        p_nom_max=tech_kessel["p_nom_max_mw"],
        capital_cost=annuity_kessel + tech_kessel["opex_fixed_eur_per_kw_year"] * 1000,
        build_year=2027,  # WICHTIG: Für multi-period
        lifetime=tech_kessel["lifetime_years"],
    )
    
    # --- 6c. Fremdwärme (fixe 11 GWh/a Contracting-Vertrag) ---
    # DEAKTIVIERT FÜR TEST - Nur WP + Kessel + Speicher testen
    # tech_fremdwaerme = cfg.TECHNOLOGIES["fremdwaerme"]
    # 
    # # WICHTIG: Fremdwärme ist auf 11 GWh/a begrenzt (Contracting-Vertrag)
    # # Wir modellieren das als Generator (nicht Link!) mit carrier_attribute
    # # um die jährliche Energiebeschränkung zu erzwingen
    # 
    # fremdwaerme_annual_energy = tech_fremdwaerme["annual_energy_gwh"] * 1000  # MWh
    # fremdwaerme_p_nom = 10.0  # MW - hohe Nennleistung für Peaks
    # 
    # # Als Generator mit Energiebeschränkung über p_max_pu
    # # p_max_pu wird so gesetzt, dass max. 11 GWh/a möglich ist
    # # 11000 MWh / 8760h = 1.256 MW Durchschnitt
    # # Bei p_nom=10 MW: p_max_pu = 1.256/10 = 0.126 im Durchschnitt
    # # Aber für Flexibilität: Wir setzen p_max_pu=0.4 und achten darauf,
    # # dass der hohe Preis die Nutzung begrenzt
    # 
    # network.add(
    #     "Generator",
    #     "fremdwaerme_supply",
    #     bus="external_heat_market",
    #     carrier="external_heat",
    #     p_nom=fremdwaerme_p_nom,
    #     p_nom_extendable=False,
    #     marginal_cost=cfg.ENERGY_PRICES["fremdwaerme"]["price"],
    # )
    # 
    # # Füge Link hinzu, der die Fremdwärme ins Netz einspeist
    # network.add(
    #     "Link",
    #     "fremdwaerme",
    #     bus0="external_heat_market",
    #     bus1="central_heat",
    #     carrier="external_heat",
    #     efficiency=1.0,
    #     p_nom=fremdwaerme_p_nom,
    #     p_nom_extendable=False,
    #     p_max_pu=1.0,
    #     capital_cost=0.0,
    # )
    
    print(f"  OK Erstellt: 2 Wärmeerzeuger")
    print(f"    - Luft-WP: ausbaubar bis {tech_wp['p_nom_max_mw']} MW")
    print(f"      Capital Cost Periode 1 (mit BEW): {annuity_wp_period1/1000:.0f} EUR/kW/a")
    print(f"      Capital Cost Periode 2 (ohne BEW): {annuity_wp_period2/1000:.0f} EUR/kW/a")
    print(f"    - Gaskessel: ausbaubar bis {tech_kessel['p_nom_max_mw']} MW")
    print()
    
    # =============================================================================
    # 7. Add Heat Load
    # =============================================================================
    print("Schritt 7: Füge Wärmelast hinzu...")
    
    # Platzhalter - wird später mit Zeitreihe gefüllt
    network.add(
        "Load",
        "heat_demand",
        bus="central_heat",
        carrier="heat",
        p_set=0.0,  # Wird durch Zeitreihe überschrieben
    )
    
    print(f"  OK Erstellt: Wärmelast (Zeitreihe folgt)")
    print()
    
    # =============================================================================
    # 8. Add Heat Storage
    # =============================================================================
    print("Schritt 8: Füge Wärmespeicher hinzu...")
    
    storage_params = cfg.STORAGE
    
    annuity_storage = cfg.calculate_annuity(
        storage_params["capex_eur_per_mwh"],
        storage_params["lifetime_years"]
    )
    
    network.add(
        "Store",
        "heat_storage",
        bus="central_heat",
        carrier="heat",
        e_nom=storage_params["existing_capacity_mwh"],
        e_nom_extendable=True,
        e_nom_max=storage_params["extendable_max_mwh"],
        e_cyclic=False,
        capital_cost=annuity_storage,
        standing_loss=storage_params["standing_loss_per_hour"],
        e_initial=0.0,
    )
    
    print(f"  OK Erstellt: Wärmespeicher")
    print(f"    - Max. Ausbau: {storage_params['extendable_max_mwh']} MWh")
    print(f"    - Capital Cost: {annuity_storage:,.0f} EUR/MWh/a")
    print()

    # =============================================================================
    # 9. Optional: Szenarien vorbereiten (PyPSA verwaltet Index-Struktur)
    # =============================================================================
    if cfg.USE_STOCHASTIC:
        print("Schritt 9: Szenarien vorbereiten...")
        scenario_probabilities = {
            name: data["probability"]
            for name, data in cfg.SCENARIOS.items()
        }
        network.set_scenarios(scenario_probabilities)
        print(f"  OK Szenarien gesetzt: {list(scenario_probabilities.keys())}")
        print(f"    - Wahrscheinlichkeiten: {scenario_probabilities}")
        print()
    
    # =============================================================================
    # 10. Summary
    # =============================================================================
    print("=" * 80)
    print("NETWORK SUMMARY")
    print("=" * 80)
    print(f"Busse:         {len(network.buses)}")
    print(f"Links:         {len(network.links)}")
    print(f"Stores:        {len(network.stores)}")
    print(f"Loads:         {len(network.loads)}")
    print(f"Generators:    {len(network.generators)}")
    print(f"Snapshots:     {len(network.snapshots):,}")
    print(f"Perioden:      {network.investment_periods.tolist()}")
    print()
    print("!!  WICHTIG: Zeitreihen müssen noch gesetzt werden!")
    print("   - Wärmelast (3 Szenarien)")
    print("   - Strompreise (3 Szenarien)")
    print("   - Gaspreise")
    print("   - COP-Profile für Luft-WP")
    print("=" * 80)
    
    return network


def set_time_series(network, heat_demand_dict, electricity_price_dict,
                   gas_price_dict, cop_dict, p_nom_max_wp_dict=None):
    """
    Setzt Zeitreihen für Netzwerk - unterstützt DETERMINISTISCH und STOCHASTISCH.
    
    Modus wird über cfg.USE_STOCHASTIC gesteuert:
    - False: Deterministisch (nur 'mittel' Szenario, keine MultiIndex)
    - True:  Stochastisch (3 Szenarien mit MultiIndex via set_scenarios())
    
    Args:
        network: PyPSA Network
        heat_demand_dict: {(scenario, period): pd.Series} - Wärmelast [MW]
        electricity_price_dict: {(scenario, period): pd.Series} - Strompreis [EUR/MWh]
        gas_price_dict: {period: pd.Series} - Gaspreis [EUR/MWh]
        cop_dict: {(scenario, period): pd.Series} - COP für Luft-WP [-]
        p_nom_max_wp_dict: {(scenario, period): pd.Series} - Relative max. Leistung WP [-] (optional)
    """
    
    # Check mode from config
    use_stochastic = cfg.USE_STOCHASTIC
    
    if use_stochastic:
        _set_time_series_stochastic(network, heat_demand_dict, electricity_price_dict,
                                   gas_price_dict, cop_dict, p_nom_max_wp_dict)
    else:
        _set_time_series_deterministic(network, heat_demand_dict, electricity_price_dict,
                                       gas_price_dict, cop_dict, p_nom_max_wp_dict)


def _set_time_series_stochastic(network, heat_demand_dict, electricity_price_dict,
                                gas_price_dict, cop_dict, p_nom_max_wp_dict=None):
    """
    Setzt Zeitreihen STOCHASTISCH (3 Szenarien mit MultiIndex-Spalten).
    
    WICHTIG: Ruft network.set_scenarios() auf, um MultiIndex für Komponenten zu erstellen!
    """
    
    print("\nSetze Zeitreihen (STOCHASTISCH mit 3 Szenarien)...")
    
    # Get scenarios from config
    scenarios = list(cfg.SCENARIOS.keys())
    print(f"  Szenarien: {scenarios}")
    
    if not isinstance(network.generators.index, pd.MultiIndex):
        raise ValueError("Erwarte MultiIndex-Komponenten nach network.set_scenarios().")
    
    # Jetzt haben alle Komponenten MultiIndex: (scenario, original_name)
    # Beispiel: network.loads.index = [('niedrig', 'heat_demand'), ('mittel', 'heat_demand'), ...]
    
    # Initialize time series DataFrames mit MultiIndex columns
    print("\n  Initialisiere Zeitreihen-DataFrames...")
    
    # Generators: marginal_cost für electricity_supply und gas_supply
    gen_cols = network.generators.index
    network.generators_t.marginal_cost = pd.DataFrame(
        0.0, index=network.snapshots, columns=gen_cols
    )
    
    # Links: efficiency für luft_wp (temperaturabhängiger COP)
    link_cols = network.links.index
    network.links_t.efficiency = pd.DataFrame(
        index=network.snapshots, columns=link_cols
    )
    # Fill with static efficiency first
    for col in link_cols:
        network.links_t.efficiency[col] = network.links.loc[col, "efficiency"]
    
    # Loads: p_set für heat_demand
    load_cols = network.loads.index
    network.loads_t.p_set = pd.DataFrame(
        0.0, index=network.snapshots, columns=load_cols
    )
    
    print(f"    - Generators: {len(gen_cols)} columns (scenarios x components)")
    print(f"    - Links: {len(link_cols)} columns")
    print(f"    - Loads: {len(load_cols)} columns")
    
    # Set time series für jede Periode und jedes Szenario
    print("\n  Setze Zeitreihen für alle Perioden und Szenarien...")
    
    for period in cfg.INVESTMENT_PERIODS:
        # Get period snapshots - network.snapshots is MultiIndex (period, timestamp)
        idx = pd.IndexSlice[period, :]
        
        for scenario_name in scenarios:
            # --- ELECTRICITY MARKET GENERATOR (marginal_cost = strompreis) ---
            elec_price = electricity_price_dict[(scenario_name, period)]
            gen_col = (scenario_name, "electricity_market_price")  # Korrekter Generator-Name!
            network.generators_t.marginal_cost.loc[idx, gen_col] = elec_price.values
            
            # --- GAS MARKET GENERATOR (marginal_cost = gaspreis + CO2) ---
            gas_price = gas_price_dict[period]  # Gaspreis scenario-unabhängig
            
            # Add CO2 price (scenario-unabhängig)
            # Vereinfacht: Verwende festen CO2-Preis von 80 EUR/t
            co2_price = 80.0  # EUR/tCO2
            co2_emissions = 0.201  # tCO2/MWh (Standard für Erdgas)
            gas_price_total = gas_price + co2_price * co2_emissions
            
            gen_col = (scenario_name, "gas_market_price")  # Korrekter Generator-Name!
            network.generators_t.marginal_cost.loc[idx, gen_col] = gas_price_total.values
            
            # --- HEAT LOAD (p_set = wärmebedarf) ---
            demand = heat_demand_dict[(scenario_name, period)]
            load_col = (scenario_name, "heat_demand")
            network.loads_t.p_set.loc[idx, load_col] = demand.values
            
            # --- AIR HEAT PUMP COP (efficiency = dynamic COP) ---
            cop = cop_dict[(scenario_name, period)]
            link_col = (scenario_name, "luft_wp")
            network.links_t.efficiency.loc[idx, link_col] = cop.values
    
    print("  OK Zeitreihen gesetzt (stochastisch, MultiIndex-Spalten)")
    
    # Validation
    print("\nZeitreihen-Check:")
    print(f"  OK Loads: {list(network.loads_t.p_set.columns)}")
    print(f"  OK Generators (marginal_cost): {list(network.generators_t.marginal_cost.columns)}")
    print(f"  OK Links (efficiency): {list(network.links_t.efficiency.columns)}")
    
    # Print example values (first hour, first scenario)
    first_scenario = scenarios[0]
    first_period = cfg.INVESTMENT_PERIODS[0]
    first_snap = (first_period, network.snapshots.get_level_values(1)[0])
    
    print(f"\nBeispiel-Werte (erste Stunde {first_period}, Szenario '{first_scenario}'):")
    print(f"  Wärmelast:        {network.loads_t.p_set.loc[first_snap, (first_scenario, 'heat_demand')]:.2f} MW")
    print(f"  Strompreis:       {network.generators_t.marginal_cost.loc[first_snap, (first_scenario, 'electricity_market_price')]:.2f} EUR/MWh")
    print(f"  COP Luft-WP:      {network.links_t.efficiency.loc[first_snap, (first_scenario, 'luft_wp')]:.2f}")
    print()


def _set_time_series_deterministic(network, heat_demand_dict, electricity_price_dict,
                                   gas_price_dict, cop_dict, p_nom_max_wp_dict=None):
    """
    Setzt Zeitreihen DETERMINISTISCH (nur 'mittel' Szenario, keine MultiIndex).
    
    Verwendet nur das 'mittel' Szenario aus den Dictionaries und setzt einfache
    Series ohne MultiIndex-Struktur.
    """
    
    print("\nSetze Zeitreihen (DETERMINISTISCH, nur 'mittel' Szenario)...")
    
    # Use only 'mittel' scenario
    scenario = 'mittel'
    print(f"  Verwende Szenario: '{scenario}'")
    
    # Initialize time series DataFrames with simple column names
    print("\n  Initialisiere Zeitreihen-DataFrames...")
    
    # Generators: marginal_cost
    if "marginal_cost" not in network.generators_t or network.generators_t.marginal_cost.empty:
        network.generators_t.marginal_cost = pd.DataFrame(
            0.0, index=network.snapshots, columns=network.generators.index
        )
    
    # Links: efficiency
    if "efficiency" not in network.links_t or network.links_t.efficiency.empty:
        network.links_t.efficiency = pd.DataFrame(
            index=network.snapshots, columns=network.links.index
        )
        # Fill with static efficiency values
        for col in network.links.index:
            network.links_t.efficiency[col] = network.links.loc[col, "efficiency"]
    
    # Loads: p_set
    if "p_set" not in network.loads_t or network.loads_t.p_set.empty:
        network.loads_t.p_set = pd.DataFrame(
            0.0, index=network.snapshots, columns=network.loads.index
        )
    
    print(f"    - Generators: {len(network.generators)} columns")
    print(f"    - Links: {len(network.links)} columns")
    print(f"    - Loads: {len(network.loads)} columns")
    
    # Set time series für jede Periode
    print("\n  Setze Zeitreihen für alle Perioden...")
    
    for period in cfg.INVESTMENT_PERIODS:
        # Get period snapshots - network.snapshots is MultiIndex (period, timestamp)
        idx = pd.IndexSlice[period, :]
        
        # --- ELECTRICITY MARKET GENERATOR (marginal_cost = strompreis) ---
        elec_price = electricity_price_dict[(scenario, period)]
        network.generators_t.marginal_cost.loc[idx, "electricity_market_price"] = elec_price.values
        
        # --- GAS MARKET GENERATOR (marginal_cost = gaspreis + CO2) ---
        gas_price = gas_price_dict[period]
        
        # Add CO2 price
        co2_price = 80.0  # EUR/tCO2
        co2_emissions = 0.201  # tCO2/MWh (Standard für Erdgas)
        gas_price_total = gas_price + co2_price * co2_emissions
        
        network.generators_t.marginal_cost.loc[idx, "gas_market_price"] = gas_price_total.values
        
        # --- HEAT LOAD (p_set = wärmebedarf) ---
        demand = heat_demand_dict[(scenario, period)]
        network.loads_t.p_set.loc[idx, "heat_demand"] = demand.values
        
        # --- AIR HEAT PUMP COP (efficiency = dynamic COP) ---
        cop = cop_dict[(scenario, period)]
        network.links_t.efficiency.loc[idx, "luft_wp"] = cop.values
    
    print("  OK Zeitreihen gesetzt (deterministisch, einfache Series)")
    
    # Validation
    print("\nZeitreihen-Check:")
    print(f"  OK Loads: {list(network.loads_t.p_set.columns)}")
    print(f"  OK Generators (marginal_cost): {list(network.generators_t.marginal_cost.columns)}")
    print(f"  OK Links (efficiency): {list(network.links_t.efficiency.columns)}")
    
    # Print example values (first hour)
    first_period = cfg.INVESTMENT_PERIODS[0]
    first_snap = (first_period, network.snapshots.get_level_values(1)[0])
    
    print(f"\nBeispiel-Werte (erste Stunde {first_period}, Szenario '{scenario}'):")
    print(f"  Wärmelast:        {network.loads_t.p_set.loc[first_snap, 'heat_demand']:.2f} MW")
    print(f"  Strompreis:       {network.generators_t.marginal_cost.loc[first_snap, 'electricity_market_price']:.2f} EUR/MWh")
    print(f"  COP Luft-WP:      {network.links_t.efficiency.loc[first_snap, 'luft_wp']:.2f}")
    print()


def set_fremdwaerme_constraint(network):
    """
    Setzt p_max_pu Zeitreihe für Fremdwärme-Generator, um die jährliche
    Energiebeschränkung von 11 GWh/a zu erzwingen.
    
    WICHTIG: Muss NACH set_time_series() aufgerufen werden.
    
    Args:
        network: PyPSA Network mit gesetzten Szenarien und Zeitreihen
    """
    
    print("\nSetze Fremdwärme-Energiebeschränkung...")
    
    # Get fremdwaerme annual energy limit from config
    annual_energy_gwh = cfg.TECHNOLOGIES["fremdwaerme"]["annual_energy_gwh"]
    annual_energy_mwh = annual_energy_gwh * 1000
    
    # Calculate required average power to stay within limit
    # 11 GWh/a = 11000 MWh / 8760 h = 1.256 MW average
    max_average_mw = annual_energy_mwh / 8760
    
    # Get p_nom of fremdwaerme_supply generator
    is_stochastic = isinstance(network.generators.index, pd.MultiIndex)
    
    if is_stochastic:
        # Get p_nom from first scenario (same for all scenarios)
        scenarios = list(cfg.SCENARIOS.keys())
        first_scenario = scenarios[0]
        p_nom = network.generators.loc[(first_scenario, "fremdwaerme_supply"), "p_nom"]
    else:
        scenarios = []
        p_nom = network.generators.loc["fremdwaerme_supply", "p_nom"]
    
    # Calculate p_max_pu that limits annual energy
    # If we want max 11 GWh/a with p_nom=10 MW:
    # p_max_pu = 1.256 MW / 10 MW = 0.126 (very restrictive)
    # 
    # Better: Set p_max_pu = 0.3 to allow peaks, and rely on high price
    # to discourage usage beyond 11 GWh/a
    p_max_pu_value = min(1.0, max_average_mw / p_nom * 2.0)  # Factor 2 for flexibility
    
    print(f"  Max. {annual_energy_gwh} GWh/a = {max_average_mw:.2f} MW Durchschnitt")
    print(f"  Generator p_nom: {p_nom:.1f} MW")
    print(f"  Setze p_max_pu: {p_max_pu_value:.3f} (erlaubt Peaks, aber begrenzt Jahresenergie)")
    
    # Set p_max_pu time series for fremdwaerme_supply
    if is_stochastic:
        for scenario in scenarios:
            gen_col = (scenario, "fremdwaerme_supply")
            if "p_max_pu" not in network.generators_t or network.generators_t.p_max_pu.empty:
                network.generators_t.p_max_pu = pd.DataFrame(
                    1.0, index=network.snapshots, columns=network.generators.index
                )
            network.generators_t.p_max_pu[gen_col] = p_max_pu_value
    else:
        if "p_max_pu" not in network.generators_t or network.generators_t.p_max_pu.empty:
            network.generators_t.p_max_pu = pd.DataFrame(
                1.0, index=network.snapshots, columns=network.generators.index
            )
        network.generators_t.p_max_pu["fremdwaerme_supply"] = p_max_pu_value
    
    print("  OK Fremdwärme-Beschränkung gesetzt")
    print()


# =============================================================================
# MODULE TEST
# =============================================================================

if __name__ == "__main__":
    """Test: Network erstellen und Struktur ausgeben."""
    
    network = create_neues_netz_network(use_unit_commitment=False)
    
    print("\nNetwork erfolgreich erstellt!")
    print(f"\nKomponenten:")
    print(f"  Busse:      {network.buses.index.tolist()}")
    print(f"  Links:      {network.links.index.tolist()}")
    print(f"  Stores:     {network.stores.index.tolist()}")
    print(f"  Loads:      {network.loads.index.tolist()}")
    print(f"  Generators: {network.generators.index.tolist()}")
