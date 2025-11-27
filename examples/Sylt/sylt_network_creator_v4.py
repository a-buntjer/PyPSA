#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Sylt Fernwärme Simulator - PyPSA Network Creator V4 - REALISTISCHE TOPOLOGIE

VOLLSTÄNDIGE Implementierung mit Netzentgelten und Energiesteuer:
1. Markt-Busse (electricity_market, gas_market) mit Preisgeneratoren
2. Gas-Netzwerk mit Energiesteuer-Differenzierung (Kessel vs. BHKW)
3. Strom-Netzwerk mit BHKW1-Selbstverbrauch und WP-Netzanschlüssen (BEW-konform)
4. Auxiliary Loads (Hilfsstrombedarf) an allen Standorten
5. Standort-Busse mit Netzentgelten (Leistungs- und Arbeitspreis)

Änderungen V3 -> V4:
- V3: Vereinfachte Topologie (direkte Marktverbindungen, keine Netzentgelte)
- V4: Realistische Topologie mit 15 Bussen, Netzentgelten, Energiesteuer
- BHKW1: Selbstverbrauch für Friesische Straße + Überschusseinspeisung
- BHKW2+3: Direkte Markteinspeisung
- Gas-Energiesteuer: 5.5 EUR/MWh nur für Kessel (nicht für BHKWs gem. KWK-Regeln)
- Auxiliary Loads: ~5% der Wärmelast als Pumpenstrom
"""

import pypsa
import pandas as pd
import numpy as np
from pathlib import Path
import sys
import io

# # Set stdout to UTF-8 encoding
# if sys.stdout.encoding != 'utf-8':
#     sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# Import local modules
import sylt_config_v2_excel as cfg  # Excel-based configuration
import sylt_timeseries_v2 as ts


def create_baseline_network_v4(
    convert_chp: bool = False, use_unit_commitment: bool = None
):
    """
    Erstellt realistische Multi-Horizon-Netzwerk mit Netzentgelten und Energiesteuer.

    Struktur (15 Busse):
    - Märkte (2): electricity_market, gas_market
    - Gas-Netzwerk (8): 3 site_gas + 5 virtuelle Busse für Energiesteuer-Differenzierung
    - Strom-Netzwerk (4): 3 Auxiliary Loads + 2 WP-Netzanschlüsse + (1 E-Kessel)
    - Wärme (1): central_heat

    Gas-Energiesteuer:
    - Kessel: gas_kessel_friesische, gas_kessel_nicolas, gas_kessel_andreas (5.5 EUR/MWh)
    - BHKWs: gas_bhkw_friesische, gas_bhkw_andreas (KEINE Steuer gem. KWK-Regeln)

    BHKW-Differenzierung:
    - BHKW1: gas -> friesische_strom_load (Selbstverbrauch) + central_heat
             Überschuss: friesische_strom_load -> electricity_market
    - BHKW2: gas -> electricity_market (direkt) + central_heat
    - BHKW3: gas -> electricity_market (direkt) + central_heat

    Args:
        convert_chp: Nicht mehr verwendet (Multi-Output statt Dual-Link)
        use_unit_commitment: If True, use committable constraints (MILP)
                            If False, allow continuous operation (LP, faster)
                            If None, use value from config (default)

    Returns:
        pypsa.Network: Optimierungsfähiges Netzwerk
    """

    # Unit Commitment: Use parameter if provided, otherwise from Config
    if use_unit_commitment is None:
        use_unit_commitment = cfg.SOLVER_CONFIG.get(
            "use_unit_commitment", False
        )

    print("=" * 80)
    print("SYLT FERNWÄRME SIMULATOR - NETWORK CREATOR V4 (REALISTISCH)")
    print("=" * 80)
    print(
        f"Unit Commitment: {use_unit_commitment} ({'MILP' if use_unit_commitment else 'LP'})"
    )
    print()

    # Auxiliary electricity ratio (% of heat demand)
    AUXILIARY_ELECTRICITY_RATIO = 0.05  # 5% der Wärmelast als Pumpenstrom

    # =============================================================================
    # 1. Initialize Network
    # =============================================================================
    print("Step 1: Initializing PyPSA Network...")

    network = pypsa.Network(name="Sylt Fernwärme V3 (Standortbasiert)")

    # IMPORTANT: Multi-period snapshots need MANUAL creation!
    # Create snapshots for each investment period with correct year timestamps
    # CRITICAL FIX: Use from_tuples() + set_snapshots() method (like PyPSA example)!
    # TEST: Reduced to 168 hours (1 week) to match PyPSA example and test if stores work
    snapshot_data = []
    for period in cfg.INVESTMENT_PERIODS:
        period_start = pd.Timestamp(f"{period}-01-01")
        period_snapshots = pd.date_range(
            start=period_start,
            periods=168,  # TEMPORARILY REDUCED FROM 8760 TO TEST STORE BUG
            freq="h"
        )
        snapshot_data.extend([(period, snap) for snap in period_snapshots])
    
    # Convert to MultiIndex: (period, timestamp)
    # CRITICAL: Use set_snapshots() method, not direct assignment!
    # This initializes internal PyPSA data structures correctly for scenarios
    snapshots_multi_index = pd.MultiIndex.from_tuples(
        snapshot_data, names=["period", "timestep"]
    )
    network.set_snapshots(snapshots_multi_index)

    # Set investment periods (must match snapshot years)
    # network.investment_periods = cfg.INVESTMENT_PERIODS

    network.investment_period_weightings["years"] = (
        cfg.INVESTMENT_PERIOD_WEIGHTINGS
    )
    
    # Set investment period weightings with DISCOUNTING (PyPSA Multi-Horizon Standard)
    # WICHTIG: Diskontierung mit r_objective (gesellschaftliche Zeitpräferenz)
    # - r_objective = 3% (für Zielfunktions-Gewichtung, niedriger als WACC)
    # - r_capex = 6% (für CAPEX-Annuitäten, bleibt in calculate_annuity)
    # 
    # Formel: w_period = Sum_{t=T_start}^{T_end} [1 / (1 + r)^t]
    # 
    # Beispiel (r=3%):
    #   2027-2029 (3 Jahre): w = 1.000 + 0.971 + 0.943 = 2.913 (statt 3.0)
    #   2030-2034 (5 Jahre): w = 0.915 + ... + 0.813 = 4.317 (statt 5.0)
    #   2045-2049 (5 Jahre): w = 0.587 + ... + 0.522 = 2.771 (statt 5.0, -44%!)
    #
    # Effekt: Späte Perioden werden weniger gewichtet → verhindert unrealistische
    #         Verschiebung von Investitionen in die Zukunft
    
    r_objective = cfg.ECONOMIC_PARAMS["discount_rate_objective"]  # 3% aus Config
    T = 0  # Globaler Zeitzähler
    objective_weights = []
    
    for period in network.investment_periods:
        nyears = network.investment_period_weightings.at[period, 'years']
        
        # Berechne diskontierte Summe für alle Jahre in dieser Periode
        discounts = [(1 / (1 + r_objective) ** t) for t in range(T, T + nyears)]
        weight = sum(discounts)
        objective_weights.append(weight)
        
        T += nyears  # Inkrementiere globalen Zeitindex
    
    network.investment_period_weightings["objective"] = objective_weights

    print(f"  OK Network initialized: {network.name}")
    print(f"  OK Snapshots set: {len(network.snapshots)} hourly timesteps")
    print(f"  OK Investment periods: {cfg.INVESTMENT_PERIODS}")
    print(f"  OK Period weightings (years): {dict(cfg.INVESTMENT_PERIOD_WEIGHTINGS)}")
    print(f"  OK Period weightings (discounted, r={r_objective:.1%}): {dict(zip(network.investment_periods, objective_weights))}")
    print()

    # =============================================================================
    # 2. Register Carriers
    # =============================================================================
    print("Step 2: Registering energy carriers...")

    carriers = [
        ("heat", "Fernwärme", "#d62728", 0.0),
        ("electricity", "Strom", "#ff7f0e", 0.0),
        ("gas", "Erdgas", "#8B4513", 0.201),
        ("heat_pump", "Wärmepumpe", "#1f77b4", 0.0),
        ("electric_boiler", "Elektrodenkessel", "#9467bd", 0.0),
        ("gas_boiler", "Gaskessel", "#8c564b", 0.201),
        ("chp", "BHKW", "#e377c2", 0.201),
        ("heat_network", "Wärmenetz", "#ff9896", 0.0),  # For network feed links
    ]

    for name, nice_name, color, co2 in carriers:
        network.add(
            "Carrier",
            name,
            nice_name=nice_name,
            color=color,
            co2_emissions=co2,
        )

    print(f"  OK Registered {len(carriers)} carriers")
    print()

    # =============================================================================
    # 3. Add Buses
    # =============================================================================
    print(
        "Step 3: Adding Buses (15 total: Markets, Gas Network, Electricity Network, Heat)..."
    )

    # -------------------------------------------------------------------------
    # 3a. Market Buses (2)
    # -------------------------------------------------------------------------
    network.add(
        "Bus",
        "electricity_market",
        carrier="electricity",
        x=471400,
        y=6073500,
        v_nom=1.0,
    )
    network.add(
        "Bus", "gas_market", carrier="gas", x=471300, y=6073500, v_nom=1.0
    )

    # -------------------------------------------------------------------------
    # 3b. Site Gas Buses (3) - Mit Netzentgelten vom Markt
    # -------------------------------------------------------------------------
    network.add(
        "Bus", "friesische_gas", carrier="gas", x=471500, y=6073550, v_nom=1.0
    )
    network.add(
        "Bus", "nicolas_gas", carrier="gas", x=471600, y=6073550, v_nom=1.0
    )
    network.add(
        "Bus", "andreas_gas", carrier="gas", x=471400, y=6073550, v_nom=1.0
    )

    # -------------------------------------------------------------------------
    # 3c. Virtuelle Gas-Busse für Energiesteuer-Differenzierung (5)
    # -------------------------------------------------------------------------
    # Kessel: MIT Energiesteuer (5.5 EUR/MWh)
    network.add(
        "Bus",
        "gas_kessel_friesische",
        carrier="gas",
        x=471500,
        y=6073560,
        v_nom=1.0,
    )
    network.add(
        "Bus",
        "gas_kessel_nicolas",
        carrier="gas",
        x=471600,
        y=6073560,
        v_nom=1.0,
    )
    network.add(
        "Bus",
        "gas_kessel_andreas",
        carrier="gas",
        x=471400,
        y=6073560,
        v_nom=1.0,
    )

    # BHKWs: OHNE Energiesteuer (KWK-Privileg)
    network.add(
        "Bus",
        "gas_bhkw_friesische",
        carrier="gas",
        x=471500,
        y=6073570,
        v_nom=1.0,
    )
    network.add(
        "Bus",
        "gas_bhkw_andreas",
        carrier="gas",
        x=471400,
        y=6073570,
        v_nom=1.0,
    )

    # -------------------------------------------------------------------------
    # 3d. Site Electricity Buses (6) - Auxiliary Loads + WP-Netzanschlüsse
    # -------------------------------------------------------------------------
    # BHKW1 Selbstverbrauch + Auxiliary Load Friesische
    network.add(
        "Bus",
        "friesische_strom_load",
        carrier="electricity",
        x=471500,
        y=6073525,
        v_nom=1.0,
    )

    # Auxiliary Loads (nur Verbrauch, kein BHKW)
    network.add(
        "Bus",
        "nicolas_strom_load",
        carrier="electricity",
        x=471600,
        y=6073525,
        v_nom=1.0,
    )
    network.add(
        "Bus",
        "andreas_strom_load",
        carrier="electricity",
        x=471400,
        y=6073525,
        v_nom=1.0,
    )

    # E-Kessel Netzanschluss (vom Markt)
    network.add(
        "Bus",
        "friesische_electricity",
        carrier="electricity",
        x=471500,
        y=6073530,
        v_nom=1.0,
    )

    # WP-Netzanschlüsse (BEW-konform, dediziert)
    network.add(
        "Bus",
        "luft_wp_electricity",
        carrier="electricity",
        x=471700,
        y=6073525,
        v_nom=1.0,
    )
    network.add(
        "Bus",
        "abwasser_wp_electricity",
        carrier="electricity",
        x=471800,
        y=6073525,
        v_nom=1.0,
    )

    # -------------------------------------------------------------------------
    # 3e. Site Heat Buses (5) - Lokale Wärmeerzeugung vor Netzeinspeisung
    # -------------------------------------------------------------------------
    # Standort Friesische Straße (Kessel 1, BHKW 1+2, E-Kessel, Bestandsspeicher)
    network.add(
        "Bus", "friesische_heat", carrier="heat", x=471500, y=6073450, v_nom=1.0
    )
    
    # Standort Nicolas Straße (Kessel 2-4)
    network.add(
        "Bus", "nicolas_heat", carrier="heat", x=471600, y=6073450, v_nom=1.0
    )
    
    # Standort Andreas-Dirks-Straße (Kessel 5-6, BHKW 3)
    network.add(
        "Bus", "andreas_heat", carrier="heat", x=471400, y=6073450, v_nom=1.0
    )
    
    # WP-Standorte (jeder mit eigenem Speicher)
    network.add(
        "Bus", "luft_wp_heat", carrier="heat", x=471700, y=6073450, v_nom=1.0
    )
    network.add(
        "Bus", "abwasser_wp_heat", carrier="heat", x=471800, y=6073450, v_nom=1.0
    )

    # -------------------------------------------------------------------------
    # 3f. Central Heat Bus (1) - Fernwärmenetz-Sammelpunkt
    # -------------------------------------------------------------------------
    network.add(
        "Bus", "central_heat", carrier="heat", x=471500, y=6073400, v_nom=1.0
    )

    print(f"  OK Added 21 buses:")
    print(f"     2 market (electricity, gas)")
    print(f"     3 site gas (friesische, nicolas, andreas)")
    print(f"     5 virtual gas (kessel × 3, bhkw × 2) für Energiesteuer")
    print(f"     4 site electricity (3 aux loads, 1 E-Kessel)")
    print(f"     2 WP electricity (luft, abwasser) BEW-konform")
    print(f"     5 site heat (friesische, nicolas, andreas, luft_wp, abwasser_wp)")
    print(f"     1 central heat (Fernwärmenetz-Sammelpunkt)")
    print()

    # =============================================================================
    # 4. Add Market Generators (Price Sources)
    # =============================================================================
    print("Step 4: Adding Market Generators (Electricity & Gas)...")

    # Electricity supply (external grid with time-varying prices)
    network.add(
        "Generator",
        "electricity_supply",
        bus="electricity_market",
        carrier="electricity",
        p_nom=1000,  # Quasi unlimited
        p_nom_extendable=False,
        p_min_pu=-1,  # Allow feed-in (BHKW 2/3 sell electricity)
        # marginal_cost will be set via time series (electricity price)
    )

    # Gas supply (market with time-varying prices)
    network.add(
        "Generator",
        "gas_supply",
        bus="gas_market",
        carrier="gas",
        p_nom=1000,  # Quasi unlimited
        p_nom_extendable=False,
        p_min_pu=-1,  # Allow bidirectional flow (not needed for gas, but consistent)
        # marginal_cost will be set via time series (gas price + CO2)
    )

    print(f"  OK Added 2 market generators (1000 MW each)")
    print()

    # =============================================================================
    # 4b. Add Gas Grid Connection Links (Market -> Site Gas Bus)
    # =============================================================================
    print(
        "Step 4b: Adding Gas Grid Connection Links (with Network Tariffs)..."
    )

    # Gas grid connections with network tariffs (from Excel config)
    # IMPORTANT: Separate Leistungspreis (capital_cost) and Arbeitspreis (marginal_cost)
    gas_leistungspreis = cfg.NETWORK_TARIFFS["gas"]["leistungspreis_eur_mw_a"]
    gas_arbeitspreis = cfg.NETWORK_TARIFFS["gas"]["arbeitspreis_eur_mwh"]

    gas_connections = [
        (
            "gas_grid_friesische",
            "friesische_gas",
            10.0,
        ),  # 10 MW connection (main plant)
        ("gas_grid_nicolas", "nicolas_gas", 8.0),  # 8 MW connection
        ("gas_grid_andreas", "andreas_gas", 3.5),  # 3.5 MW connection
    ]

    for name, bus_out, p_nom in gas_connections:
        network.add(
            "Link",
            name,
            bus0="gas_market",
            bus1=bus_out,
            carrier="gas",
            p_nom=p_nom,
            p_nom_extendable=False,
            efficiency=1.0,  # No losses in grid connection
            capital_cost=gas_leistungspreis,
            marginal_cost=gas_arbeitspreis,
        )

    print(f"  OK Added {len(gas_connections)} gas grid connection links")
    print(f"     Arbeitspreis: {gas_arbeitspreis:.2f} EUR/MWh")
    print(f"     Leistungspreis: {gas_leistungspreis:,.0f} EUR/MW/a")
    print()

    # =============================================================================
    # 4c. Add Gas Energy Tax Links (Site Gas -> Virtual Gas Buses)
    # =============================================================================
    print("Step 4c: Adding Gas Energy Tax Links (Kessel vs BHKW)...")

    # Gas energy tax from config (only for boilers, not CHPs!)
    gas_energy_tax = cfg.NETWORK_TARIFFS["gas"].get(
        "energiesteuer_eur_mwh", 5.5
    )

    # Links for BOILERS (WITH energy tax)
    energy_tax_kessel_links = [
        (
            "gas_tax_kessel_friesische",
            "friesische_gas",
            "gas_kessel_friesische",
            10.0,
        ),
        ("gas_tax_kessel_nicolas", "nicolas_gas", "gas_kessel_nicolas", 8.0),
        ("gas_tax_kessel_andreas", "andreas_gas", "gas_kessel_andreas", 3.5),
    ]

    for name, bus_in, bus_out, p_nom in energy_tax_kessel_links:
        network.add(
            "Link",
            name,
            bus0=bus_in,
            bus1=bus_out,
            carrier="gas",
            p_nom=p_nom,
            p_nom_extendable=False,
            efficiency=1.0,
            capital_cost=0,
            marginal_cost=gas_energy_tax,  # 5.5 EUR/MWh
        )

    # Links for CHPs (NO energy tax - KWK privilege)
    energy_tax_bhkw_links = [
        (
            "gas_tax_bhkw_friesische",
            "friesische_gas",
            "gas_bhkw_friesische",
            5.0,
        ),
        ("gas_tax_bhkw_andreas", "andreas_gas", "gas_bhkw_andreas", 2.0),
    ]

    for name, bus_in, bus_out, p_nom in energy_tax_bhkw_links:
        network.add(
            "Link",
            name,
            bus0=bus_in,
            bus1=bus_out,
            carrier="gas",
            p_nom=p_nom,
            p_nom_extendable=False,
            efficiency=1.0,
            capital_cost=0,
            marginal_cost=0.0,  # NO energy tax for CHPs!
        )

    print(
        f"  OK Added {len(energy_tax_kessel_links)} kessel links (WITH tax: {gas_energy_tax} EUR/MWh)"
    )
    print(f"  OK Added {len(energy_tax_bhkw_links)} BHKW links (NO tax)")
    print()

    # =============================================================================
    # 4d. Add Electricity Grid Connection Links (Market -> Site Electricity Bus)
    # =============================================================================
    print(
        "Step 4d: Adding Electricity Grid Connections (with Network Tariffs)..."
    )

    # Electricity grid connections with network tariffs (from Excel config)
    # IMPORTANT: WPs get separate connections for BEW Modul 4 compliance (no fossil BHKW electricity)
    # IMPORTANT: Separate Leistungspreis (capital_cost) and Arbeitspreis (marginal_cost)
    elec_leistungspreis = cfg.NETWORK_TARIFFS["electricity"][
        "leistungspreis_eur_mw_a"
    ]
    elec_arbeitspreis = cfg.NETWORK_TARIFFS["electricity"][
        "arbeitspreis_eur_mwh"
    ]

    elec_connections = [
        (
            "elec_grid_friesische",
            "friesische_electricity",
            15.0,
        ),  # 15 MW (E-Kessel)
        (
            "elec_grid_friesische_load",
            "friesische_strom_load",
            5.0,
        ),  # 5 MW (BHKW1 self-cons + aux)
        (
            "elec_grid_nicolas_load",
            "nicolas_strom_load",
            0.5,
        ),  # 0.5 MW (aux only)
        (
            "elec_grid_andreas_load",
            "andreas_strom_load",
            0.5,
        ),  # 0.5 MW (aux only)
        (
            "elec_grid_luft_wp",
            "luft_wp_electricity",
            10.0,
        ),  # 10 MW (Luft-WP only, BEW compliant)
        (
            "elec_grid_abwasser_wp",
            "abwasser_wp_electricity",
            10.0,
        ),  # 10 MW (Abwasser-WP only, BEW compliant)
    ]

    for name, bus_out, p_nom in elec_connections:
        network.add(
            "Link",
            name,
            bus0="electricity_market",
            bus1=bus_out,
            carrier="electricity",
            p_nom=p_nom,
            p_nom_extendable=False,
            efficiency=1.0,
            capital_cost=elec_leistungspreis,
            marginal_cost=elec_arbeitspreis,
        )

    print(
        f"  OK Added {len(elec_connections)} electricity grid connection links"
    )
    print(f"     Arbeitspreis: {elec_arbeitspreis:.2f} EUR/MWh")
    print(f"     Leistungspreis: {elec_leistungspreis:,.0f} EUR/MW/a")
    print(
        f"     BEW Compliance: WPs have separate connections (no BHKW access)"
    )
    print()

    # =============================================================================
    # 5. Add Heat Demand and Auxiliary Electricity Loads
    # =============================================================================
    print("Step 5: Adding Heat Demand and Auxiliary Electricity Loads...")

    # Heat load at central bus (p_set will be set later via timeseries)
    network.add(
        "Load",
        "central_heat_load",
        bus="central_heat",
        carrier="heat",
    )

    # Auxiliary electricity loads (pump electricity, controls, etc.)
    # p_set will be calculated and set later via timeseries
    auxiliary_loads = [
        ("auxiliary_load_friesische", "friesische_strom_load"),
        ("auxiliary_load_nicolas", "nicolas_strom_load"),
        ("auxiliary_load_andreas", "andreas_strom_load"),
    ]

    for name, bus in auxiliary_loads:
        network.add(
            "Load",
            name,
            bus=bus,
            carrier="electricity",
        )

    print(f"  OK Added central heat load")
    print(f"  OK Added 3 auxiliary electricity loads")
    print(
        f"     Note: p_set will be calculated from heat demand ({AUXILIARY_ELECTRICITY_RATIO*100:.1f}%) via timeseries"
    )
    print()

    # =============================================================================
    # 6. Add Existing Gas Boilers as Links
    # =============================================================================
    print("Step 6: Adding Existing Gas Boilers as Links...")
    print("  NOTE: Connecting from gas_kessel_* buses (WITH energy tax)")

    # CSV is in 06_docs/Projektinitialisierung/
    csv_path = (
        Path(__file__).parent.parent
        / "06_docs"
        / "Projektinitialisierung"
        / "Bestandsanlagen_Sylt.csv"
    )
    df_plants = pd.read_csv(csv_path, sep=",")

    # Filter Gaskessel
    df_boilers = df_plants[df_plants["Typ"] == "Kessel"].copy()

    boiler_count = 0
    for idx, row in df_boilers.iterrows():
        name = row["Anlage"]
        standort = row["Standort"]
        p_nom = row["Leistung_kWth"] / 1000  # MW
        efficiency = row["Wirkungsgrad_thermisch"]
        build_year = int(row["Baujahr"])

        # Connect from gas_kessel_* buses (WITH energy tax)
        # Connect TO site heat buses (not central_heat directly!)
        if "Friesische" in standort:
            bus_gas = "gas_kessel_friesische"
            bus_heat = "friesische_heat"
        elif "Nicolas" in standort:
            bus_gas = "gas_kessel_nicolas"
            bus_heat = "nicolas_heat"
        elif "Andreas" in standort:
            bus_gas = "gas_kessel_andreas"
            bus_heat = "andreas_heat"
        else:
            raise ValueError(f"Unknown location: {standort}")

        # CRITICAL: PyPSA calculates retirement_year = build_year + lifetime
        # So lifetime must be (end_year - build_year), NOT remaining years!
        if "Friesische" in standort:
            # Kessel 1 (2020): Modern boiler, runs until 2040 (Biomethan)
            end_year = 2040
            lifetime = end_year - build_year  # 2040 - 2020 = 20
        elif "Nicolas" in standort:
            # Kessel 2-4 (1995-1997): Old boilers, run until 2035
            end_year = 2035
            lifetime = end_year - build_year  # 2035 - 1995 = 40, etc.
        elif "Andreas" in standort:
            # Kessel 5-6 (1999): Decommissioned 2029
            end_year = 2029
            lifetime = end_year - build_year  # 2029 - 1999 = 30
        else:
            end_year = 2045
            lifetime = end_year - build_year

        # CRITICAL FIX: p_min_pu should ONLY apply when committable=True
        # Otherwise, ALL boilers must run at ≥30% simultaneously -> infeasible!
        p_min_pu_value = 0.3 if use_unit_commitment else 0.0

        # CRITICAL: For PyPSA to respect build_year/lifetime, assets must be extendable!
        # Set p_nom_extendable=True with p_nom_max=p_nom to allow PyPSA to retire them
        network.add(
            "Link",
            name,
            bus0=bus_gas,  # From gas_kessel_* (WITH energy tax)
            bus1=bus_heat,
            carrier="gas_boiler",
            p_nom=0,  # Start at 0 for extendable
            p_nom_extendable=True,  # Required for lifetime enforcement!
            p_nom_max=p_nom,  # Limit to existing capacity
            efficiency=efficiency,
            build_year=build_year,
            lifetime=lifetime,
            capital_cost=0,  # Already built (no new investment cost)
            marginal_cost=5.0,  # Only O&M (energy tax already in gas_tax_kessel_* links)
            committable=use_unit_commitment,
            p_min_pu=p_min_pu_value,
        )
        boiler_count += 1
        print(
            f"    {name:15s} {p_nom:6.2f} MW  {bus_gas:25s} -> {bus_heat:20s}  (Baujahr {build_year}, lifetime {lifetime}a)"
        )

    print(f"  OK Added {boiler_count} gas boilers (DIRECT from gas_market)")

    # Add emergency backup boiler (extendable, expensive, ensures feasibility)
    print("\nStep 5b: Adding Emergency Backup Boiler (extendable)...")
    network.add(
        "Link",
        "Emergency_Backup_Boiler",
        bus0="gas_market",  # Direct from gas market
        bus1="central_heat",  # Direct to central heat
        carrier="gas_boiler",
        p_nom=0,  # Start with 0 MW
        p_nom_extendable=True,  # Can be expanded
        p_nom_min=0,
        p_nom_max=50,  # Max 50 MW (enough for any situation)
        efficiency=0.85,  # Lower efficiency (older technology)
        capital_cost=100000,  # Very expensive investment (100k EUR/MW/a)
        marginal_cost=200,  # Very expensive operation (200 EUR/MWh)
        build_year=2027,
        lifetime=20,
    )
    print(
        f"  OK Added emergency backup boiler (p_nom_extendable, marginal_cost=200 EUR/MWh)"
    )
    print(f"     This ensures model feasibility even if all other plants fail")
    print()

    # =============================================================================
    # 7. Add Existing CHPs as Multi-Output Links (with BHKW Differentiation)
    # =============================================================================
    # TEMPORARILY DISABLED TO TEST IF MULTI-OUTPUT LINKS CAUSE STORE BUG
    print(
        "Step 7: CHPs DEAKTIVIERT - Testing if multi-output links cause store bug..."
    )
    
    # # CSV is already loaded from Step 6
    # # Filter BHKWs
    # df_chps = df_plants[df_plants["Typ"] == "BHKW"].copy()

    # chp_count = 0
    # for idx, row in df_chps.iterrows():
    #     name = row["Anlage"]
    #     standort = row["Standort"]
    #     p_nom_el = row["Leistung_kWel"] / 1000  # MW electrical
    #     p_nom_th = row["Leistung_kWth"] / 1000  # MW thermal
    #     eta_el = row["Wirkungsgrad_elektrisch"]
    #     eta_th = row["Wirkungsgrad_thermisch"]
    #     build_year = int(row["Baujahr"])

    #     # Connect from gas_bhkw_* buses (NO energy tax - KWK privilege)
    #     # Connect TO site heat buses (not central_heat directly!)
        
    #     # BHKW differentiation:
    #     # BHKW 1: Self-consumption model (friesische_strom_load)
    #     # BHKW 2: Market model (electricity_market)
    #     # BHKW 3: Market model (electricity_market)
    #     if name == "BHKW 1":
    #         bus_gas = "gas_bhkw_friesische"
    #         bus_elec = "friesische_strom_load"  # Self-consumption!
    #         bus_heat = "friesische_heat"  # Friesische Standort
    #     elif name == "BHKW 2":
    #         bus_gas = "gas_bhkw_friesische"
    #         bus_elec = "electricity_market"  # Direct to market
    #         bus_heat = "friesische_heat"  # Friesische Standort
    #     elif name == "BHKW 3":
    #         bus_gas = "gas_bhkw_andreas"
    #         bus_elec = "electricity_market"  # Direct to market
    #         bus_heat = "andreas_heat"  # Andreas Standort
    #     else:
    #         raise ValueError(f"Unknown BHKW: {name}")

    #     # CRITICAL: PyPSA calculates retirement_year = build_year + lifetime
    #     # So lifetime must be (end_year - build_year), NOT remaining years!
    #     if "Friesische" in standort:
    #         # BHKW 1-2 (2020): Run until 2040 (Biomethan)
    #         end_year = 2040
    #         lifetime = end_year - build_year  # 2040 - 2020 = 20
    #     elif "Andreas" in standort:
    #         # BHKW 3 (2009): Decommissioned 2029
    #         end_year = 2029
    #         lifetime = end_year - build_year  # 2029 - 2009 = 20
    #     else:
    #         end_year = 2045
    #         lifetime = end_year - build_year

    #     # CRITICAL FIX: p_min_pu should ONLY apply when committable=True
    #     p_min_pu_value = 0.35 if use_unit_commitment else 0.0

    #     # CRITICAL FIX: p_nom_max must be GAS INPUT, not electrical output!
    #     # For a CHP: Gas Input = P_el / η_el
    #     # Example: P_el = 0.999 MW, η_el = 0.38 => Gas = 2.629 MW
    #     p_nom_max_gas = p_nom_el / eta_el  # Gas input capacity

    #     # Multi-Output Link (PyPSA allows bus1, bus2 for multiple outputs)
    #     # bus0: Gas input (from gas_bhkw_*)
    #     # bus1: Electricity output (to market OR to friesische_strom_load)
    #     # bus2: Heat output (coupled via efficiency2)
    #     # CRITICAL: For PyPSA to respect build_year/lifetime, assets must be extendable!
    #     network.add(
    #         "Link",
    #         name,
    #         bus0=bus_gas,
    #         bus1=bus_elec,
    #         bus2=bus_heat,
    #         carrier="chp",
    #         p_nom=0,  # Start at 0 for extendable
    #         p_nom_extendable=True,  # Required for lifetime enforcement!
    #         p_nom_max=p_nom_max_gas,  # FIXED: Gas input limit, not electrical!
    #         efficiency=eta_el,  # Electrical efficiency
    #         efficiency2=eta_th,  # Thermal efficiency
    #         build_year=build_year,
    #         lifetime=lifetime,
    #         capital_cost=0,  # Already built (no new investment cost)
    #         marginal_cost=5.0,  # Only O&M (no energy tax, already in gas_tax_bhkw_* with 0 cost)
    #         committable=use_unit_commitment,
    #         p_min_pu=p_min_pu_value,
    #     )
    #     chp_count += 1
    #     print(
    #         f"    {name:15s} P_el={p_nom_el:.3f} MW, Q_th={p_nom_th:.3f} MW  "
    #         f"GasMax={p_nom_max_gas:.3f} MW  "
    #         f"{bus_gas:25s} => {bus_heat} + {bus_elec}"
    #     )

    # print(f"  OK Added {chp_count} CHPs as multi-output links")
    print(f"  OK CHPs deaktiviert - Kessel + Emergency Backup sichern Versorgung")
    print()

    # =============================================================================
    # 7b. Add BHKW1 Excess Feed Link (Self-consumption -> Market)
    # =============================================================================
    # ALSO DISABLED (no BHKW1 to feed from)
    # print("Step 7b: Adding BHKW1 Excess Feed Link...")

    # # Link to sell excess BHKW1 electricity to market
    # # (when BHKW1 produces more than aux load needs)
    # network.add(
    #     "Link",
    #     "bhkw1_excess_feed",
    #     bus0="friesische_strom_load",
    #     bus1="electricity_market",
    #     carrier="electricity",
    #     p_nom=5.0,  # Max 5 MW (BHKW1 capacity)
    #     p_nom_extendable=False,
    #     efficiency=1.0,  # No losses
    #     capital_cost=0,
    #     marginal_cost=0,  # Negative cost = revenue! Use electricity price from market
    # )
    # print(
    #     f"  OK Added BHKW1 excess feed link (friesische_strom_load -> electricity_market)"
    # )
    # print(
    #     f"     Allows BHKW1 to sell surplus electricity when aux load is low"
    # )
    print(f"Step 7b: BHKW1 Excess Feed Link deaktiviert (kein BHKW1)")
    print()

    # =============================================================================
    # 8. Add New Technology Links
    # =============================================================================
    print("Step 8: Adding New Technology Links...")
    print("  NOTE: Connecting from dedicated grid connections (BEW-compliant)")

    # Get CAPEX values with BEW subsidy
    elec_capex = (
        cfg.get_technology_capex("Elektrodenkessel", apply_bew_subsidy=True)
        * 1000
    )  # EUR/MW
    luft_capex = (
        cfg.get_technology_capex("Luft-Wärmepumpe", apply_bew_subsidy=True)
        * 1000
    )
    abw_capex = (
        cfg.get_technology_capex("Abwasser-Wärmepumpe", apply_bew_subsidy=True)
        * 1000
    )

    # Get discount factor for annualization
    discount_factor = cfg.get_discount_factor(
        cfg.INVESTMENT_PERIODS[0], base_year=2027
    )

    # 1. Elektrodenkessel (available from config)
    network.add(
        "Link",
        "Elektrodenkessel",
        bus0="friesische_electricity",  # From dedicated E-Kessel grid connection
        bus1="friesische_heat",  # NEW: Site-specific heat bus!
        carrier="electric_boiler",
        p_nom=0,
        p_nom_extendable=True,
        p_nom_min=0,
        p_nom_max=15.0,  # Max 15 MW
        efficiency=cfg.TECHNOLOGIES["Elektrodenkessel"]["efficiency"],
        capital_cost=elec_capex * discount_factor,
        build_year=cfg.TECHNOLOGIES["Elektrodenkessel"]["first_build_year"],
        lifetime=cfg.TECHNOLOGIES["Elektrodenkessel"]["lifetime_years"],
    )
    print(
        f"    Elektrodenkessel:  0 -> 15 MW  (Available {cfg.TECHNOLOGIES['Elektrodenkessel']['first_build_year']}, eff={cfg.TECHNOLOGIES['Elektrodenkessel']['efficiency']:.2f})"
    )

    # 2. Luft-Wärmepumpe (available from config, COP dynamic via time series)
    network.add(
        "Link",
        "Luft-WP",
        bus0="luft_wp_electricity",  # BEW-compliant dedicated grid connection
        bus1="luft_wp_heat",  # NEW: Site-specific heat bus for Luft-WP!
        carrier="heat_pump",
        p_nom=0,
        p_nom_extendable=True,
        p_nom_min=0,
        p_nom_max=10.0,  # Max 10 MW
        efficiency=3.0,  # Placeholder, will be overwritten by time series COP
        capital_cost=luft_capex * discount_factor,
        build_year=cfg.TECHNOLOGIES["Luft-Wärmepumpe"]["first_build_year"],
        lifetime=cfg.TECHNOLOGIES["Luft-Wärmepumpe"]["lifetime_years"],
    )
    print(
        f"    Luft-WP:           0 -> 10 MW  (Available {cfg.TECHNOLOGIES['Luft-Wärmepumpe']['first_build_year']}, COP dynamic)"
    )

    # 3. Abwasser-Wärmepumpe (available from config, constant COP)
    network.add(
        "Link",
        "Abwasser-WP",
        bus0="abwasser_wp_electricity",  # BEW-compliant dedicated grid connection
        bus1="abwasser_wp_heat",  # NEW: Site-specific heat bus for Abwasser-WP!
        carrier="heat_pump",
        p_nom=0,
        p_nom_extendable=True,
        p_nom_min=0,
        p_nom_max=5.0,  # Max 5 MW
        efficiency=cfg.TECHNOLOGIES["Abwasser-Wärmepumpe"]["cop"],
        capital_cost=abw_capex * discount_factor,
        build_year=cfg.TECHNOLOGIES["Abwasser-Wärmepumpe"]["first_build_year"],
        lifetime=cfg.TECHNOLOGIES["Abwasser-Wärmepumpe"]["lifetime_years"],
    )
    print(
        f"    Abwasser-WP:       0 -> 5 MW   (Available {cfg.TECHNOLOGIES['Abwasser-Wärmepumpe']['first_build_year']}, COP={cfg.TECHNOLOGIES['Abwasser-Wärmepumpe']['cop']:.1f})"
    )

    print(f"  OK Added 3 new technology links")
    print()

    # =============================================================================
    # 8b. Add Network Feed Links (Site → Central Heat Distribution)
    # =============================================================================
    print("Step 8b: Adding Network Feed Links...")
    print("  NOTE: Each site heat bus feeds central distribution with ~5% losses")

    # Network efficiency (95% = 5% distribution losses)
    network_efficiency = 0.95
    # High capacity (no bottleneck, 1 GW = 1000 MW)
    network_capacity = 1000.0

    # Define site heat buses that need to feed central_heat
    site_buses = [
        "friesische_heat",
        "nicolas_heat",
        "andreas_heat",
        "luft_wp_heat",
        "abwasser_wp_heat",
    ]

    for site_bus in site_buses:
        link_name = f"feed_{site_bus}_to_central"
        network.add(
            "Link",
            link_name,
            bus0=site_bus,  # From site-specific heat bus
            bus1="central_heat",  # To central distribution
            carrier="heat_network",
            p_nom=network_capacity,  # High capacity (no bottleneck)
            p_nom_extendable=False,  # Fixed capacity
            efficiency=network_efficiency,  # 95% efficiency (5% losses)
            capital_cost=0,  # No additional cost (network exists)
            marginal_cost=0,  # No transport cost
        )
        print(f"    {site_bus:25s} -> central_heat  (eff={network_efficiency:.2%}, p_nom={network_capacity:.0f} MW)")

    print(f"  OK Added {len(site_buses)} network feed links")
    print()

    # =============================================================================
    # 9. Add Site-Specific Storage
    # =============================================================================
    print("Step 9: Adding Site-Specific Storage...")
    print("  NOTE: Using from_tuples() snapshot format + simple store parameters")

    # Get CAPEX from Excel config STORAGE section (EUR/MWh)
    capex_storage = cfg.STORAGE["capex_eur_per_mwh"]
    capex_adj = cfg.apply_financial_factors(capex_storage)
    capex_ann = capex_adj * discount_factor

    # =========================================================================
    # STORES RE-ENABLED - TESTING WITHOUT CHPs (multi-output links)
    # =========================================================================
    # Hypothese: Multi-Output Links (bus2/efficiency2) verursachen Broadcasting-Bug
    # Test: Stores aktivieren OHNE CHPs -> sollte funktionieren
    # =========================================================================
    
    # 1. Existing storage at Friesische Str. (2×100 m³ = 12 MWh, fixed)
    network.add(
        "Store",
        "Bestandsspeicher_Friesische",
        bus="friesische_heat",
        carrier="heat",
        e_nom_extendable=False,
        e_nom=cfg.STORAGE["existing_capacity_mwh"],  # Fixed 12 MWh
        e_initial=cfg.STORAGE["existing_capacity_mwh"] / 2,  # Start at 50% SOC
        standing_loss=cfg.STORAGE["standing_loss_per_hour"],
        capital_cost=0,  # Already built
        lifetime=30,
        build_year=2027,
    )

    # 2. Storage for Luft-WP site (extendable)
    network.add(
        "Store",
        "Speicher_Luft_WP",
        bus="luft_wp_heat",
        carrier="heat",
        e_nom_extendable=True,
        e_nom=0,
        e_nom_max=195,  # Max 195 MWh
        e_initial=0,  # Start empty
        standing_loss=0.003 / 24,
        capital_cost=capex_ann,
        lifetime=30,
        build_year=2027,
    )

    # 3. Storage for Abwasser-WP site (extendable)
    network.add(
        "Store",
        "Speicher_Abwasser_WP",
        bus="abwasser_wp_heat",
        carrier="heat",
        e_nom_extendable=True,
        e_nom=0,
        e_nom_max=195,  # Max 195 MWh
        e_initial=0,  # Start empty
        standing_loss=0.003 / 24,
        capital_cost=capex_ann,
        lifetime=30,
        build_year=2027,
    )

    print(f"  OK Added 3 stores - Testing WITHOUT CHPs to isolate bug cause")
    print()

    # =============================================================================
    # 9. Add Network Feed Links (Sites -> Central)
    # =============================================================================
    # =============================================================================
    # 10. SAVE ORIGINAL NAMES (before scenarios create MultiIndex)
    # =============================================================================
    original_generator_names = list(network.generators.index)
    original_link_names = list(network.links.index)
    original_load_names = list(network.loads.index)

    print(f"Step 10: Saved original component names:")
    print(f"  Generators: {len(original_generator_names)}")
    print(f"  Links: {len(original_link_names)}")
    print(f"  Loads: {len(original_load_names)}")
    print()

    # =============================================================================
    # 11. CLEANUP: Ensure all links have bus2/efficiency2 defined (PyPSA consistency)
    # =============================================================================
    # Problem: PyPSA creates bus2/efficiency2 columns when first multi-output link is added,
    # but doesn't backfill existing links. We need to explicitly set bus2="" and efficiency2=1.0
    # for single-output links that were added before the first CHP.
    print("Step 11b: Cleanup bus2/efficiency2 for consistency...")
    if "bus2" in network.links.columns:
        # Find links with NaN or missing bus2 (single-output links added before CHPs)
        missing_bus2 = network.links["bus2"].isna() | (
            network.links["bus2"] == ""
        )
        if missing_bus2.any():
            print(
                f"  Found {missing_bus2.sum()} links without bus2 - setting to empty string"
            )
            network.links.loc[missing_bus2, "bus2"] = ""

            # Also set efficiency2=1.0 for these (no second output)
            if "efficiency2" in network.links.columns:
                missing_eff2 = (
                    missing_bus2 & network.links["efficiency2"].isna()
                )
                if missing_eff2.any():
                    print(
                        f"  Setting efficiency2=1.0 for {missing_eff2.sum()} single-output links"
                    )
                    network.links.loc[missing_eff2, "efficiency2"] = 1.0
        else:
            print(f"  All links have bus2 defined")
    print()

    # =============================================================================
    # 12. SET SCENARIOS (BEFORE time series!)
    # =============================================================================
    print("Step 12: Setting scenarios for stochastic optimization...")

    # DEBUG: Check bus2 BEFORE set_scenarios
    print(f"\n[DEBUG] Links status:")
    print(f"  Total links: {len(network.links)}")
    if "bus2" in network.links.columns:
        has_bus2_before = network.links["bus2"].notna()
        print(
            f"  Links with bus2: {has_bus2_before.sum()} (should be 3 CHPs only!)"
        )
    else:
        print(f"  No bus2 column (no multi-output links)")
    chp_links = network.links[network.links["carrier"] == "chp"]
    print(f"  CHPs: {len(chp_links)}")

    # PyPSA set_scenarios expects Dict[str, float] with probabilities only
    scenario_probs = {name: params["probability"] for name, params in cfg.SCENARIOS.items()}
    network.set_scenarios(scenario_probs)

    print(f"  OK Scenarios set: {len(cfg.SCENARIOS)} scenarios")
    for name, prob in scenario_probs.items():
        print(f"     {name}: {prob*100:.0f}%")
    print()

    # =============================================================================
    # 13. SET TIME SERIES (with MultiIndex after set_scenarios)
    # =============================================================================
    print("Step 13: Setting time series (heat demand, prices, COP, ...)...")
    print("  NOTE: Time series use (scenario, component_name) MultiIndex")

    # Import SIMPLIFIED time series setter (skip complex BEW/Grid features)
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from src.modules.sylt_timeseries_setter import set_all_timeseries

    set_all_timeseries(
        network=network,
        scenarios=cfg.SCENARIOS,
        investment_periods=cfg.INVESTMENT_PERIODS,
        original_generator_names=original_generator_names,
        original_link_names=original_link_names,
        original_load_names=original_load_names,
    )

    print()

    # =============================================================================
    # 15. FINAL VALIDATION
    # =============================================================================
    print("=" * 80)
    print("NETWORK CREATION COMPLETE - VALIDATION")
    print("=" * 80)

    print(f"\nBuses: {len(network.buses)}")
    print(
        f"  Market:      {len([b for b in network.buses.index if 'market' in b])}"
    )
    print(
        f"  Site Gas:    {len([b for b in network.buses.index if '_gas' in b and 'market' not in b])}"
    )
    print(
        f"  Site Elec:   {len([b for b in network.buses.index if '_electricity' in b and 'market' not in b])}"
    )
    print(
        f"  Site Heat:   {len([b for b in network.buses.index if '_heat' in b and 'central' not in b])}"
    )
    print(
        f"  Central:     {len([b for b in network.buses.index if 'central' in b])}"
    )

    print(f"\nGenerators: {len(network.generators)}")
    print(
        f"  Market Generators: {len([g for g in network.generators.index if isinstance(g, str)])}"
    )
    print(
        f"  After scenarios:   {len([g for g in network.generators.index if isinstance(g, tuple)])}"
    )

    print(f"\nLinks: {len(network.links)}")
    print(f"  Original (before scenarios): {len(original_link_names)}")
    print(
        f"  Gas grid connections:  {len([l for l in original_link_names if 'gas_grid' in l])}"
    )
    print(
        f"  Elec grid connections: {len([l for l in original_link_names if 'elec_grid' in l])}"
    )
    print(
        f"  After scenarios:       {len([l for l in network.links.index if isinstance(l, tuple)])}"
    )

    print(f"\nStores: {len(network.stores)}")

    print(f"\nLoads: {len(network.loads)}")

    print(f"\nSnapshots: {len(network.snapshots):,}")
    print(f"Investment Periods: {len(network.investment_periods)}")
    print(f"Scenarios: {len(cfg.SCENARIOS)}")
    print(f"  Stochastic Optimization: ENABLED")
    for name, params in cfg.SCENARIOS.items():
        print(f"    {name}: {params['probability']*100:.0f}% probability")


    print("\n" + "=" * 80)
    print("NETWORK TOPOLOGY SUMMARY V4")
    print("=" * 80)
    print("\nELECTRICITY STRUCTURE:")
    print("  electricity_market (commodity)")
    print("    +- BHKW 2 -> full feed-in")
    print("    +- BHKW 3 -> full feed-in")
    print("    +- BHKW 1 (excess) -> feed-in via friesische_strom_load")
    print("    +- Grid Connections (70k EUR/MW/a + 18 EUR/MWh):")
    print("         +- friesische_electricity -> Elektrodenkessel")
    print(
        "         +- friesische_strom_load -> BHKW 1 self-consumption + aux load"
    )
    print("         +- nicolas_strom_load -> auxiliary load")
    print("         +- andreas_strom_load -> auxiliary load")
    print("         +- luft_wp_electricity -> Luft-WP (BEW Modul 4: no BHKW!)")
    print(
        "         +- abwasser_wp_electricity -> Abwasser-WP (BEW Modul 4: no BHKW!)"
    )
    print("\nGAS STRUCTURE:")
    print("  gas_market (commodity)")
    print("    +- Grid Connections (100k EUR/MW/a + 14 EUR/MWh):")
    print("         +- friesische_gas")
    print(
        "         |    +- gas_kessel_friesische (+5.5 EUR/MWh tax) -> Kessel 1"
    )
    print("         |    +- gas_bhkw_friesische (NO tax) -> BHKW 1+2")
    print("         +- nicolas_gas")
    print(
        "         |    +- gas_kessel_nicolas (+5.5 EUR/MWh tax) -> Kessel 2-4"
    )
    print("         +- andreas_gas")
    print(
        "              +- gas_kessel_andreas (+5.5 EUR/MWh tax) -> Kessel 5-6"
    )
    print("              +- gas_bhkw_andreas (NO tax) -> BHKW 3")
    print("\nAUXILIARY LOADS:")
    print(
        f"  3 sites × {AUXILIARY_ELECTRICITY_RATIO*100:.1f}% of heat demand = pump electricity"
    )

    print("\n" + "=" * 80)
    print("READY FOR OPTIMIZATION")
    print("=" * 80 + "\n")

    return network


if __name__ == "__main__":
    print("Creating Sylt Fernwärme Network V4 (Realistisch)...\n")

    network = create_baseline_network_v4()

    print("\nNetwork creation successful!")
    print(
        f"Components: {len(network.buses)} buses, {len(network.generators)} generators, "
        f"{len(network.links)} links, {len(network.stores)} stores, {len(network.loads)} loads"
    )
