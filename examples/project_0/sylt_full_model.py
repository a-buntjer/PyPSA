"""
Fernwärme Westerland (Sylt) - VOLLSTÄNDIGES Multi-Horizon Stochastic Model
===========================================================================

Vollumfängliches Modell mit:
- Multi-Investment-Perioden (2027, 2030, 2035, 2040, 2045)
- 3 Stochastischen Szenarien (optimistisch, base, pessimistisch)
- Committable Erzeugern (unit commitment)
- Extendable neuen Technologien
"""

import pypsa
import pandas as pd
import numpy as np
from pathlib import Path

# Investment-Perioden
INVESTMENT_PERIODS = [2027, 2030, 2035, 2040, 2045]

# Szenarien mit Wahrscheinlichkeiten
SCENARIOS = {
    "optimistic": {"probability": 0.25, "demand_factor": 0.9, "price_factor": 0.85},
    "base": {"probability": 0.50, "demand_factor": 1.0, "price_factor": 1.0},
    "pessimistic": {"probability": 0.25, "demand_factor": 1.1, "price_factor": 1.15},
}

# Zeitreihen
HOURS_PER_PERIOD = 8760

# Wirtschaftliche Parameter
DISCOUNT_RATE = 0.06
SUBSIDY_RATE = 0.40
ISLAND_SURCHARGE = 0.30
PLANNING_COSTS = 0.20
CONSTRUCTION_COSTS = 0.20

CO2_PRICES = {
    2027: 55,
    2030: 80,
    2035: 120,
    2040: 160,
    2045: 200,
}


def create_heat_demand_profile(year, scenario_factor=1.0):
    """Erstelle Wärmebedarfsprofil."""
    base_demand = 30 + (50 - 30) * (year - 2025) / (2045 - 2025)  # GWh
    annual_demand = base_demand * scenario_factor
    
    hours = np.arange(HOURS_PER_PERIOD)
    day_of_year = hours // 24
    hour_of_day = hours % 24
    
    seasonal = 0.7 + 0.3 * np.cos(2 * np.pi * day_of_year / 365.25)
    daily = (0.6 + 
             0.2 * np.exp(-((hour_of_day - 7) ** 2) / 8) +
             0.2 * np.exp(-((hour_of_day - 19) ** 2) / 8))
    
    profile = seasonal * daily
    profile = profile / profile.sum() * annual_demand * 1000  # MW
    
    return profile


def create_electricity_price_profile(year, scenario_factor=1.0):
    """Strompreisverlauf."""
    base_price = 150 - (150 - 80) * (year - 2025) / (2045 - 2025)
    base_price *= scenario_factor
    
    hours = np.arange(HOURS_PER_PERIOD)
    hour_of_day = hours % 24
    daily_variation = 0.85 + 0.3 * np.sin(2 * np.pi * (hour_of_day - 6) / 24)
    
    profile = base_price * daily_variation
    return profile


def create_gas_price_profile(year, scenario_factor=1.0):
    """Gaspreisverlauf."""
    if year < 2035:
        base_price = 80 + (100 - 80) * (year - 2025) / (2035 - 2025)
    else:
        base_price = 100 + (120 - 100) * (year - 2035) / (2045 - 2035)
    
    base_price *= scenario_factor
    profile = np.full(HOURS_PER_PERIOD, base_price)
    return profile


def create_cop_profile_air():
    """COP-Profil für Luft-Wärmepumpen."""
    hours = np.arange(HOURS_PER_PERIOD)
    day_of_year = hours // 24
    cop = 2.5 + 1.0 * np.cos(2 * np.pi * (day_of_year - 180) / 365.25)
    return cop


def create_cop_profile_wastewater():
    """COP-Profil für Abwasser-Wärmepumpen."""
    return np.full(HOURS_PER_PERIOD, 3.8)


def main():
    """Erstelle vollumfängliches Netzwerk mit Szenarien."""
    
    print("=" * 80)
    print("FERNWÄRME WESTERLAND (SYLT) - VOLLSTÄNDIGES STOCHASTISCHES MODELL")
    print("=" * 80)
    print()
    
    n = pypsa.Network()
    
    # Snapshots und Investment-Perioden
    n.set_snapshots(pd.date_range("2025-01-01", periods=HOURS_PER_PERIOD, freq="h"))
    n.set_investment_periods(pd.Series(INVESTMENT_PERIODS, dtype=int))
    
    print(f"✓ Netzwerk erstellt: {len(INVESTMENT_PERIODS)} Perioden, {HOURS_PER_PERIOD} Zeitschritte")
    print(f"  Snapshots vor Szenarien: {len(n.snapshots)}")
    
    # Carrier
    n.add("Carrier", "electricity", co2_emissions=0.086, color="#FFA500")
    n.add("Carrier", "gas", co2_emissions=0.202, color="#8B4513")
    n.add("Carrier", "biomethane", co2_emissions=0.0, color="#228B22")
    n.add("Carrier", "heat", co2_emissions=0.0, color="#DC143C")
    
    # Busse
    n.add("Bus", "heat_network", carrier="heat")
    n.add("Bus", "electricity", carrier="electricity")
    n.add("Bus", "gas", carrier="gas")
    
    # Last - ohne p_set, setzen wir später für jedes Szenario
    n.add("Load", "heat_demand", bus="heat_network", carrier="heat")
    
    print("✓ Busse und Last hinzugefügt")
    
    # Lade Bestandsanlagen
    csv_path = Path(__file__).parent / "Bestandsanlagen_Sylt.csv"
    df = pd.read_csv(csv_path)
    
    plant_count = 0
    
    for idx, row in df.iterrows():
        plant_name = f"{row['Anlage']}_{row['Standort'].replace('.', '').replace(' ', '_')}"
        plant_type = str(row['Typ'])
        
        if "Andreas-Dirks" in row['Standort']:
            retirement_year = 2029
        elif "Friesische" in row['Standort']:
            retirement_year = 2040
        else:
            retirement_year = 2035
        
        if plant_type == "Kessel":
            p_nom = float(row['Leistung_kWth']) / 1000
            efficiency = float(row['Wirkungsgrad_thermisch'])
            marginal_cost = 5.0
            
            for period in INVESTMENT_PERIODS:
                if period <= retirement_year:
                    carrier = "biomethane" if period >= 2035 else "gas"
                    
                    n.add(
                        "Link",
                        f"{plant_name}_{period}",
                        bus0="gas",
                        bus1="heat_network",
                        carrier=carrier,
                        p_nom=p_nom,
                        efficiency=efficiency,
                        marginal_cost=marginal_cost,
                        committable=True,
                        build_year=period,
                        lifetime=40,
                        capital_cost=0,
                    )
                    plant_count += 1
        
        elif plant_type == "BHKW":
            p_nom_el = float(row['Leistung_kWel']) / 1000
            p_nom_th = float(row['Leistung_kWth']) / 1000
            eff_el = float(row['Wirkungsgrad_elektrisch'])
            eff_th = float(row['Wirkungsgrad_thermisch'])
            marginal_cost = 8.0
            
            for period in INVESTMENT_PERIODS:
                if period <= retirement_year:
                    carrier = "biomethane" if period >= 2035 else "gas"
                    
                    n.add(
                        "Link",
                        f"{plant_name}_el_{period}",
                        bus0="gas",
                        bus1="electricity",
                        bus2="heat_network",
                        carrier=carrier,
                        p_nom=p_nom_el / eff_el,
                        efficiency=eff_el,
                        efficiency2=eff_th,
                        marginal_cost=marginal_cost,
                        committable=True,
                        build_year=period,
                        lifetime=30,
                        capital_cost=0,
                    )
                    plant_count += 1
    
    print(f"✓ {plant_count} Bestandsanlagen hinzugefügt (committable)")
    
    # Neue Technologien
    inv_cost_eheater = 150 * (1 + ISLAND_SURCHARGE + PLANNING_COSTS + CONSTRUCTION_COSTS) * (1 - SUBSIDY_RATE)
    inv_cost_hp_air = 800 * (1 + ISLAND_SURCHARGE + PLANNING_COSTS + CONSTRUCTION_COSTS) * (1 - SUBSIDY_RATE)
    inv_cost_hp_ww = 1200 * (1 + ISLAND_SURCHARGE + PLANNING_COSTS + CONSTRUCTION_COSTS) * (1 - SUBSIDY_RATE)
    
    # COP-Profile für alle Perioden erstellen (OHNE Szenarien, da noch nicht aktiviert)
    cop_air_full = pd.Series(index=n.snapshots, dtype=float)
    cop_ww_full = pd.Series(index=n.snapshots, dtype=float)
    
    for period in INVESTMENT_PERIODS:
        period_snapshots = n.snapshots[n.snapshots.get_level_values(0) == period]
        cop_air_full.loc[period_snapshots] = create_cop_profile_air()
        cop_ww_full.loc[period_snapshots] = create_cop_profile_wastewater()
    
    tech_count = 0
    
    # Elektrodenkessel
    for period in INVESTMENT_PERIODS:
        if period >= 2027:
            n.add(
                "Link",
                f"electric_heater_{period}",
                bus0="electricity",
                bus1="heat_network",
                carrier="electricity",
                p_nom_extendable=True,
                p_nom=5.0 if period == 2027 else 0,
                efficiency=0.99,
                marginal_cost=2.0,
                capital_cost=inv_cost_eheater * 1000,
                committable=True,
                build_year=period,
                lifetime=25,
            )
            tech_count += 1
    
    # Luft-WP 1 - Effizienz wird nach set_scenarios() gesetzt
    for period in INVESTMENT_PERIODS:
        if period >= 2029:
            n.add(
                "Link",
                f"heat_pump_air_1_{period}",
                bus0="electricity",
                bus1="heat_network",
                carrier="electricity",
                p_nom_extendable=True,
                p_nom=3.5 if period == 2029 else 0,
                marginal_cost=3.0,
                capital_cost=inv_cost_hp_air * 1000,
                committable=True,
                build_year=period,
                lifetime=20,
            )
            tech_count += 1
    
    # Luft-WP 2 - Effizienz wird nach set_scenarios() gesetzt
    for period in INVESTMENT_PERIODS:
        if period >= 2039:
            n.add(
                "Link",
                f"heat_pump_air_2_{period}",
                bus0="electricity",
                bus1="heat_network",
                carrier="electricity",
                p_nom_extendable=True,
                p_nom=3.5 if period == 2039 else 0,
                marginal_cost=3.0,
                capital_cost=inv_cost_hp_air * 1000,
                committable=True,
                build_year=period,
                lifetime=20,
            )
            tech_count += 1
    
    # Abwasser-WP - Effizienz wird nach set_scenarios() gesetzt
    for period in INVESTMENT_PERIODS:
        if period >= 2035:
            n.add(
                "Link",
                f"heat_pump_wastewater_{period}",
                bus0="electricity",
                bus1="heat_network",
                carrier="electricity",
                p_nom_extendable=True,
                p_nom=3.2 if period == 2035 else 0,
                p_nom_max=3.7,
                marginal_cost=4.0,
                capital_cost=inv_cost_hp_ww * 1000,
                committable=True,
                build_year=period,
                lifetime=20,
            )
            tech_count += 1
    
    print(f"✓ {tech_count} neue Technologien hinzugefügt (committable + extendable)")
    
    # Speicher
    n.add(
        "Store",
        "storage_existing",
        bus="heat_network",
        carrier="heat",
        e_nom=12.0,
        e_cyclic=True,
        capital_cost=0,
        standing_loss=0.02,
    )
    
    inv_cost_storage = 400 * (1 + ISLAND_SURCHARGE + PLANNING_COSTS + CONSTRUCTION_COSTS) * (1 - SUBSIDY_RATE)
    
    for period in INVESTMENT_PERIODS:
        if period >= 2027:
            n.add(
                "Store",
                f"storage_new_{period}",
                bus="heat_network",
                carrier="heat",
                e_nom_extendable=True,
                e_nom=0,
                e_nom_max=195,
                e_cyclic=True,
                capital_cost=inv_cost_storage * 1000,
                standing_loss=0.015,
                build_year=period,
                lifetime=30,
            )
    
    print("✓ Speicher hinzugefügt")
    
    # Generators (müssen ohne marginal_cost erstellt werden)
    n.add(
        "Generator",
        "electricity_supply",
        bus="electricity",
        carrier="electricity",
        p_nom=1000,
    )
    
    n.add(
        "Generator",
        "gas_supply",
        bus="gas",
        carrier="gas",
        p_nom=1000,
    )
    
    print("✓ Energieversorgung hinzugefügt")
    
    # JETZT aktivieren wir Szenarien - dies macht die Zeitreihen zu MultiIndex
    print()
    print("Aktiviere stochastische Szenarien...")
    scenario_weights = {name: SCENARIOS[name]["probability"] for name in SCENARIOS.keys()}
    n.set_scenarios(scenario_weights)
    print(f"✓ {len(SCENARIOS)} Szenarien aktiviert")
    print(f"  Snapshots nach Szenarien: {len(n.snapshots)} (MultiIndex)")
    
    # Jetzt setzen wir alle szenario-abhängigen Zeitreihen
    print()
    print("Setze szenario-spezifische Zeitreihen...")
    
    for scenario, params in SCENARIOS.items():
        print(f"  Szenario '{scenario}' (p={params['probability']:.2f})...")
        
        for period in INVESTMENT_PERIODS:
            period_snapshots = n.snapshots[n.snapshots.get_level_values(0) == period]
            
            # Last
            demand_profile = create_heat_demand_profile(period, params["demand_factor"])
            n.loads_t.p_set.loc[period_snapshots, (scenario, "heat_demand")] = demand_profile
            
            # Strompreis
            elec_price = create_electricity_price_profile(period, params["price_factor"])
            n.generators_t.marginal_cost.loc[period_snapshots, (scenario, "electricity_supply")] = elec_price
            
            # Gaspreis + CO2
            gas_price = create_gas_price_profile(period, params["price_factor"])
            co2_cost = CO2_PRICES[period] * 0.202
            n.generators_t.marginal_cost.loc[period_snapshots, (scenario, "gas_supply")] = gas_price + co2_cost
        
        # COP-Profile für Wärmepumpen (alle Links mit "heat_pump" im Namen)
        for link_name in n.links.index:
            if "heat_pump_air" in link_name:
                n.links_t.efficiency.loc[:, (scenario, link_name)] = cop_air_full
            elif "heat_pump_wastewater" in link_name:
                n.links_t.efficiency.loc[:, (scenario, link_name)] = cop_ww_full
    
    print("✓ Alle Zeitreihen gesetzt")
    
    print()
    print("=" * 80)
    print("NETZWERK ÜBERSICHT")
    print("=" * 80)
    print(f"Investment-Perioden: {INVESTMENT_PERIODS}")
    print(f"Szenarien: {list(SCENARIOS.keys())}")
    print(f"Zeitschritte pro Periode: {HOURS_PER_PERIOD}")
    print(f"Zeitschritte gesamt: {len(n.snapshots)}")
    print(f"Busse: {len(n.buses)}")
    print(f"Links (Erzeuger): {len(n.links)}")
    print(f"Speicher: {len(n.stores)}")
    print(f"Lasten: {len(n.loads)}")
    print()
    
    # Speichere
    output_file = Path(__file__).parent / "sylt_network_full.nc"
    n.export_to_netcdf(output_file)
    print(f"✓ Netzwerk gespeichert: {output_file}")
    
    return n


if __name__ == "__main__":
    network = main()
