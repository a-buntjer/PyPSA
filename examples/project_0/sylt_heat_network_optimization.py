"""
Fernwärme Westerland (Sylt) - Multi-Horizon Stochastic Optimization
====================================================================

Umfassendes PyPSA-Modell mit:
- Multi-Horizon-Optimierung (2027, 2030, 2035, 2040, 2045)
- Stochastische Programmierung (3 Szenarien: Preis & Wärmebedarf)
- Committable Erzeuger (unit commitment für alle)
- Extendable neue Technologien
- Bestandsanlagen mit Außerbetriebnahmen

MARKIERTE ANNAHMEN:
- [ANNAHME] = Fehlende Kosten/Effizienz ergänzt mit Literaturwerten
- [STANDARD] = Standardwerte aus Transformationsplan
"""

import pypsa
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path

# ============================================================================
# KONFIGURATION
# ============================================================================

# Investment-Perioden (Multi-Horizon)
INVESTMENT_PERIODS = [2027, 2030, 2035, 2040, 2045]
PERIOD_WEIGHTS = [3, 5, 5, 5, 5]  # Jahre pro Periode

# Zeitreihen-Auflösung (repräsentative Tage)
HOURS_PER_PERIOD = 8760  # 1 Jahr vollständig

# Szenarien (Preis & Wärmebedarf)
SCENARIOS = {
    "optimistic": {"probability": 0.25, "demand_factor": 0.9, "price_factor": 0.85},
    "base": {"probability": 0.50, "demand_factor": 1.0, "price_factor": 1.0},
    "pessimistic": {"probability": 0.25, "demand_factor": 1.1, "price_factor": 1.15},
}

# Wirtschaftliche Parameter [STANDARD aus Transformationsplan]
DISCOUNT_RATE = 0.06  # 6% Zinssatz
SUBSIDY_RATE = 0.40  # 40% Förderquote
ISLAND_SURCHARGE = 0.30  # 30% Inselaufschlag
PLANNING_COSTS = 0.20  # 20% Planungskosten
CONSTRUCTION_COSTS = 0.20  # 20% Anlagenbaukosten

# CO2-Preise [STANDARD gemäß nationaler Entwicklung]
CO2_PRICES = {
    2027: 55,   # EUR/tCO2
    2030: 80,
    2035: 120,
    2040: 160,
    2045: 200,
}

# ============================================================================
# ZEITREIHEN UND PROFILE
# ============================================================================

def create_heat_demand_profile(year, scenario_factor=1.0):
    """
    Erstelle Wärmebedarfsprofil für ein Jahr.
    [ANNAHME] Verwendung eines typischen Fernwärmelastprofils analog 2022.
    
    Entwicklung: Linear von 30 GWh (2025) auf 50 GWh (2045)
    """
    # Linearer Anstieg
    base_demand = 30 + (50 - 30) * (year - 2025) / (2045 - 2025)  # GWh
    annual_demand = base_demand * scenario_factor  # GWh
    
    # [ANNAHME] Typisches Fernwärmelastprofil
    # Tagesverlauf mit Morgen- und Abendspitze
    hours = np.arange(HOURS_PER_PERIOD)
    day_of_year = hours // 24
    hour_of_day = hours % 24
    
    # Jahresverlauf (Winter > Sommer)
    seasonal = 0.7 + 0.3 * np.cos(2 * np.pi * day_of_year / 365.25)
    
    # Tagesverlauf (Morgenspitze 7h, Abendspitze 19h)
    daily = (0.6 + 
             0.2 * np.exp(-((hour_of_day - 7) ** 2) / 8) +  # Morgenspitze
             0.2 * np.exp(-((hour_of_day - 19) ** 2) / 8))  # Abendspitze
    
    # Kombiniere und normiere auf Jahresenergie
    profile = seasonal * daily
    profile = profile / profile.sum() * annual_demand * 1000  # MW
    
    return profile


def create_electricity_price_profile(year, scenario_factor=1.0):
    """
    Erstelle Strompreisverlauf.
    [STANDARD] Interpoliert aus 2023-2045, sinkend aufgrund erneuerbarer Energien.
    """
    # [STANDARD] Basispreis sinkt von 150 EUR/MWh (2025) auf 80 EUR/MWh (2045)
    base_price = 150 - (150 - 80) * (year - 2025) / (2045 - 2025)
    base_price *= scenario_factor
    
    # [ANNAHME] Tageszeitliche Variation (niedrig nachts, hoch tagsüber)
    hours = np.arange(HOURS_PER_PERIOD)
    hour_of_day = hours % 24
    
    # Tagesprofil (niedriger Preis nachts 2-6h, höher tagsüber 10-20h)
    daily_variation = 0.85 + 0.3 * np.sin(2 * np.pi * (hour_of_day - 6) / 24)
    
    profile = base_price * daily_variation
    
    return profile


def create_gas_price_profile(year, scenario_factor=1.0):
    """
    Erstelle Erdgas-/Biomethanpreisverlauf.
    [STANDARD] Steigend aufgrund Biomethan-Umstellung.
    """
    # [STANDARD] Basispreis steigt von 80 EUR/MWh (2025) auf 120 EUR/MWh (2045)
    # ab 2035: Biomethan teurer
    if year < 2035:
        base_price = 80 + (100 - 80) * (year - 2025) / (2035 - 2025)
    else:
        base_price = 100 + (120 - 100) * (year - 2035) / (2045 - 2035)
    
    base_price *= scenario_factor
    
    # Konstant über das Jahr (keine saisonalen Variationen angenommen)
    profile = np.full(HOURS_PER_PERIOD, base_price)
    
    return profile


def create_cop_profile_air():
    """
    Erstelle COP-Profil für Luft-Wärmepumpen.
    [ANNAHME] Temperaturabhängig: COP = 2.0 (Winter) bis 4.0 (Sommer).
    """
    hours = np.arange(HOURS_PER_PERIOD)
    day_of_year = hours // 24
    
    # Jahreszeitlicher Verlauf (niedrig im Winter, hoch im Sommer)
    # Vorlauf 78°C, Außentemperatur -5°C (Winter) bis +20°C (Sommer)
    cop = 2.5 + 1.0 * np.cos(2 * np.pi * (day_of_year - 180) / 365.25)
    
    return cop


def create_cop_profile_wastewater():
    """
    Erstelle COP-Profil für Abwasser-Wärmepumpen.
    [ANNAHME] Konstanter COP ~3.5-4.0 (Abwasser hat stabile Temperatur).
    """
    cop = np.full(HOURS_PER_PERIOD, 3.8)
    
    return cop


# ============================================================================
# NETZWERK INITIALISIERUNG
# ============================================================================

def create_network():
    """Erstelle PyPSA-Netzwerk mit Multi-Horizon und Szenarien."""
    
    n = pypsa.Network()
    
    # Snapshots ZUERST setzen (vor investment_periods)
    n.set_snapshots(pd.date_range("2025-01-01", periods=HOURS_PER_PERIOD, freq="h"))
    
    # Investment-Perioden
    n.set_investment_periods(pd.Series(INVESTMENT_PERIODS, dtype=int))
    
    # Szenarien (Dictionary mit Namen: Wahrscheinlichkeit)
    scenario_weights = {name: SCENARIOS[name]["probability"] for name in SCENARIOS.keys()}
    n.set_scenarios(scenario_weights)
    
    print(f"✓ Netzwerk erstellt: {len(INVESTMENT_PERIODS)} Perioden, "
          f"{len(scenario_weights)} Szenarien, {HOURS_PER_PERIOD} Zeitschritte")
    
    return n


# ============================================================================
# BUSSE UND LASTEN
# ============================================================================

def add_buses_and_loads(n):
    """Füge Busse und Wärmelasten hinzu."""
    
    # Hauptbus: Fernwärmenetz
    n.add("Bus", "heat_network", carrier="heat")
    
    # Elektrizitätsbus (für Stromverbraucher)
    n.add("Bus", "electricity", carrier="AC")
    
    # Gasbus (für Erdgas/Biomethan)
    n.add("Bus", "gas", carrier="gas")
    
    # Eine Last hinzufügen (wird später für Szenarien angepasst)
    base_demand = create_heat_demand_profile(2027, 1.0)
    
    n.add(
        "Load",
        "heat_demand",
        bus="heat_network",
        p_set=base_demand,
        carrier="heat",
    )
    
    print(f"✓ Busse und Last hinzugefügt")


def update_loads_for_scenarios(n):
    """Aktualisiere Lasten nach set_scenarios für jede Periode/Szenario."""
    
    print("Aktualisiere Lasten für Szenarien und Perioden...")
    
    # Nach set_scenarios() hat loads_t.p_set MultiIndex-Spalten: (scenario, load_name)
    for scenario, params in SCENARIOS.items():
        for period in INVESTMENT_PERIODS:
            # Hole die Snapshots für diese Periode
            period_snapshots = n.snapshots[n.snapshots.get_level_values(0) == period]
            
            # Erstelle Lastprofil für diese Periode/Szenario
            demand_profile = create_heat_demand_profile(period, params["demand_factor"])
            
            # Setze die Last für dieses Szenario und diese Periode
            n.loads_t.p_set.loc[period_snapshots, (scenario, "heat_demand")] = demand_profile
    
    print(f"✓ Lasten aktualisiert für {len(SCENARIOS)} Szenarien × {len(INVESTMENT_PERIODS)} Perioden")


# ============================================================================
# TRÄGER (CARRIERS)
# ============================================================================

def add_carriers(n):
    """Füge Energieträger mit CO2-Emissionen hinzu."""
    
    # Elektrizität
    n.add("Carrier", "electricity", co2_emissions=0.086, color="#FFA500")  # [STANDARD] 86 gCO2/kWh
    
    # Erdgas (bis 2035)
    n.add("Carrier", "gas", co2_emissions=0.202, color="#8B4513")  # 202 gCO2/kWh (Hs-Wert)
    
    # Biomethan (ab 2035)
    n.add("Carrier", "biomethane", co2_emissions=0.0, color="#228B22")  # CO2-neutral
    
    # Wärme
    n.add("Carrier", "heat", co2_emissions=0.0, color="#DC143C")
    
    print("✓ Energieträger hinzugefügt")


# ============================================================================
# BESTANDSANLAGEN (COMMITTABLE)
# ============================================================================

def add_existing_plants(n):
    """
    Füge Bestandsanlagen aus CSV hinzu.
    Alle sind committable (unit commitment).
    Außerbetriebnahmen: Andreas-Dirks 2029, Friesische Str. 2035-2040.
    """
    
    # Lade Bestandsdaten
    csv_path = Path(__file__).parent / "Bestandsanlagen_Sylt.csv"
    df = pd.read_csv(csv_path)
    
    plant_count = 0
    
    for _, row in df.iterrows():
        plant_name = f"{row['Anlage']}_{row['Standort'].replace('.', '').replace(' ', '_')}"
        plant_type = row['Typ']
        
        # Standort-spezifische Außerbetriebnahme
        if "Andreas-Dirks" in row['Standort']:
            retirement_year = 2029
        elif "Friesische" in row['Standort']:
            retirement_year = 2040  # Weiterbetrieb mit Biomethan bis 2040
        else:
            retirement_year = 2035  # Dr.-Nicolas-Str.: konservative Annahme
        
        if plant_type == "Kessel":
            # Wärmekessel
            p_nom = row['Leistung_kWth'] / 1000  # MW
            efficiency = row['Wirkungsgrad_thermisch']
            
            # [ANNAHME] Betriebskosten für Bestandskessel
            marginal_cost = 5.0  # EUR/MWh
            
            # Committable Link (gas -> heat)
            for period in INVESTMENT_PERIODS:
                if period <= retirement_year:
                    # Gasträger wechselt ab 2035 zu Biomethan
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
                        committable=True,  # Unit commitment
                        build_year=period,
                        lifetime=40,
                        capital_cost=0,  # Bestandsanlage
                    )
                    plant_count += 1
        
        elif plant_type == "BHKW":
            # Blockheizkraftwerk (Gas -> Strom + Wärme)
            p_nom_el = row['Leistung_kWel'] / 1000  # MW elektrisch
            p_nom_th = row['Leistung_kWth'] / 1000  # MW thermisch
            eff_el = row['Wirkungsgrad_elektrisch']
            eff_th = row['Wirkungsgrad_thermisch']
            
            # [ANNAHME] Betriebskosten BHKW
            marginal_cost = 8.0  # EUR/MWh
            
            # Committable Link mit zwei Outputs
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
                        p_nom=p_nom_el / eff_el,  # Gas input
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


# ============================================================================
# NEUE TECHNOLOGIEN (COMMITTABLE + EXTENDABLE)
# ============================================================================

def add_new_technologies(n):
    """
    Füge neue Technologien hinzu (committable + extendable).
    - Wärmepumpen (Luft: 2029/2039, Abwasser: 2035/2040)
    - Elektrodenkessel: 2027
    """
    
    tech_count = 0
    
    # 1. ELEKTRODENKESSEL (2027, 5 MW)
    # [ANNAHME] Investitionskosten: 150 EUR/kW (mit Inselaufschlag + Planung)
    inv_cost_eheater = 150 * (1 + ISLAND_SURCHARGE + PLANNING_COSTS + CONSTRUCTION_COSTS)
    inv_cost_eheater *= (1 - SUBSIDY_RATE)  # Nach Förderung
    
    for period in INVESTMENT_PERIODS:
        if period >= 2027:
            n.add(
                "Link",
                f"electric_heater_{period}",
                bus0="electricity",
                bus1="heat_network",
                carrier="electricity",
                p_nom_extendable=True,
                p_nom=5.0 if period == 2027 else 0,  # Initial 5 MW in 2027
                efficiency=0.99,  # [ANNAHME] Elektrische Wärmepumpe nahezu 100%
                marginal_cost=2.0,  # [ANNAHME] Wartung
                capital_cost=inv_cost_eheater * 1000,  # EUR/MW
                committable=True,
                build_year=period,
                lifetime=25,
            )
            tech_count += 1
    
    # 2. LUFT-WÄRMEPUMPE 1 (2029, 3.5 MW)
    # [ANNAHME] Investitionskosten: 800 EUR/kW (Großwärmepumpe mit Peripherie)
    inv_cost_hp_air = 800 * (1 + ISLAND_SURCHARGE + PLANNING_COSTS + CONSTRUCTION_COSTS)
    inv_cost_hp_air *= (1 - SUBSIDY_RATE)
    
    cop_air = create_cop_profile_air()
    
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
                efficiency=cop_air,  # Zeitvariabler COP
                marginal_cost=3.0,  # [ANNAHME] Wartung
                capital_cost=inv_cost_hp_air * 1000,
                committable=True,
                build_year=period,
                lifetime=20,
            )
            tech_count += 1
    
    # 3. LUFT-WÄRMEPUMPE 2 (2039, 3.5 MW)
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
                efficiency=cop_air,
                marginal_cost=3.0,
                capital_cost=inv_cost_hp_air * 1000,
                committable=True,
                build_year=period,
                lifetime=20,
            )
            tech_count += 1
    
    # 4. ABWASSER-WÄRMEPUMPE (2035, 2.7-3.7 MW)
    # [ANNAHME] Investitionskosten: 1200 EUR/kW (höher wegen Abwasseranbindung)
    inv_cost_hp_ww = 1200 * (1 + ISLAND_SURCHARGE + PLANNING_COSTS + CONSTRUCTION_COSTS)
    inv_cost_hp_ww *= (1 - SUBSIDY_RATE)
    
    cop_ww = create_cop_profile_wastewater()
    
    for period in INVESTMENT_PERIODS:
        if period >= 2035:
            n.add(
                "Link",
                f"heat_pump_wastewater_{period}",
                bus0="electricity",
                bus1="heat_network",
                carrier="electricity",
                p_nom_extendable=True,
                p_nom=3.2 if period == 2035 else 0,  # Mittelwert 2.7-3.7 MW
                p_nom_max=3.7,  # Obere Grenze
                efficiency=cop_ww,
                marginal_cost=4.0,  # [ANNAHME] Höhere Wartung
                capital_cost=inv_cost_hp_ww * 1000,
                committable=True,
                build_year=period,
                lifetime=20,
            )
            tech_count += 1
    
    print(f"✓ {tech_count} neue Technologien hinzugefügt (committable + extendable)")
    print(f"  [ANNAHME] Investitionskosten: E-Kessel {inv_cost_eheater:.0f} EUR/kW, "
          f"Luft-WP {inv_cost_hp_air:.0f} EUR/kW, Abwasser-WP {inv_cost_hp_ww:.0f} EUR/kW")


# ============================================================================
# SPEICHER
# ============================================================================

def add_storage(n):
    """
    Füge Wärmespeicher hinzu.
    - Bestehend: 2×100 m³ Friesische Str.
    - Neu: Tagespufferspeicher mit 12-14 Volllaststunden für WP-Standorte
    """
    
    # [ANNAHME] Speicherkapazität: 60 kWh/m³ (Temperaturdifferenz 50K)
    energy_per_volume = 0.06  # MWh/m³
    
    # 1. BESTANDSSPEICHER (Friesische Str.: 2×100 m³ = 200 m³)
    existing_capacity = 200 * energy_per_volume  # 12 MWh
    
    n.add(
        "Store",
        "storage_existing",
        bus="heat_network",
        carrier="heat",
        e_nom=existing_capacity,
        e_cyclic=True,
        capital_cost=0,  # Bestandsanlage
        standing_loss=0.02,  # [ANNAHME] 2% Verlust pro Stunde
    )
    
    # 2. NEUE SPEICHER (extendable, ab 2027)
    # [ANNAHME] Investitionskosten: 400 EUR/kWh
    inv_cost_storage = 400 * (1 + ISLAND_SURCHARGE + PLANNING_COSTS + CONSTRUCTION_COSTS)
    inv_cost_storage *= (1 - SUBSIDY_RATE)
    
    # Dimensionierung: 12-14h Volllaststunden bei Spitzenlast
    # Spitzenlast ~15 MW (aus 50 GWh / 8760h * 3 Winterfaktor)
    target_hours = 13  # Mittelwert
    target_capacity = 15 * target_hours  # ~195 MWh
    
    for period in INVESTMENT_PERIODS:
        if period >= 2027:
            n.add(
                "Store",
                f"storage_new_{period}",
                bus="heat_network",
                carrier="heat",
                e_nom_extendable=True,
                e_nom=0,
                e_nom_max=target_capacity,
                e_cyclic=True,
                capital_cost=inv_cost_storage * 1000,  # EUR/MWh
                standing_loss=0.015,  # [ANNAHME] Bessere Dämmung
                build_year=period,
                lifetime=30,
            )
    
    print(f"✓ Speicher hinzugefügt: {existing_capacity:.1f} MWh bestehend, "
          f"bis {target_capacity:.0f} MWh erweiterbar")
    print(f"  [ANNAHME] Investitionskosten Speicher: {inv_cost_storage:.0f} EUR/kWh")


# ============================================================================
# STROM- UND GASVERSORGUNG
# ============================================================================

def add_energy_supply(n):
    """Füge Strom- und Gasversorgung hinzu (Generators mit Zeitreihen)."""
    
    # Strom- und Gaspreise für alle Perioden und Szenarien
    for period in INVESTMENT_PERIODS:
        for scenario, params in SCENARIOS.items():
            # Strompreis
            elec_price = create_electricity_price_profile(
                period, 
                params["price_factor"]
            )
            
            n.add(
                "Generator",
                f"electricity_supply_{period}_{scenario}",
                bus="electricity",
                carrier="electricity",
                p_nom=1000,  # Unbegrenzt (Grid)
                marginal_cost=elec_price,
            )
            
            # Gaspreis
            gas_price = create_gas_price_profile(
                period,
                params["price_factor"]
            )
            
            # CO2-Kosten addieren
            co2_cost = CO2_PRICES[period] * 0.202  # EUR/MWh (202 kg CO2/MWh)
            
            n.add(
                "Generator",
                f"gas_supply_{period}_{scenario}",
                bus="gas",
                carrier="gas" if period < 2035 else "biomethane",
                p_nom=1000,
                marginal_cost=gas_price + co2_cost,
            )
    
    print(f"✓ Energieversorgung hinzugefügt: Strom + Gas für alle Perioden/Szenarien")
    print(f"  [STANDARD] CO2-Preise: {CO2_PRICES}")


# ============================================================================
# HAUPTFUNKTION
# ============================================================================

def main():
    """Hauptfunktion: Erstelle und optimiere Netzwerk."""
    
    print("=" * 80)
    print("FERNWÄRME WESTERLAND (SYLT) - MULTI-HORIZON STOCHASTIC OPTIMIZATION")
    print("=" * 80)
    print()
    
    # Erstelle Netzwerk
    n = create_network()
    
    # Füge Komponenten hinzu
    add_carriers(n)
    add_buses_and_loads(n)
    add_existing_plants(n)
    add_new_technologies(n)
    add_storage(n)
    add_energy_supply(n)
    
    print()
    print("=" * 80)
    print("NETZWERK ÜBERSICHT")
    print("=" * 80)
    print(f"Investment-Perioden: {INVESTMENT_PERIODS}")
    print(f"Szenarien: {list(SCENARIOS.keys())}")
    print(f"Zeitschritte pro Periode: {HOURS_PER_PERIOD}")
    print(f"Busse: {len(n.buses)}")
    print(f"Links (Erzeuger): {len(n.links)}")
    print(f"Speicher: {len(n.stores)}")
    print(f"Lasten: {len(n.loads)}")
    print()
    
    # Speichere Netzwerk
    output_file = Path(__file__).parent / "sylt_network.nc"
    n.export_to_netcdf(output_file)
    print(f"✓ Netzwerk gespeichert: {output_file}")
    
    print()
    print("=" * 80)
    print("NÄCHSTE SCHRITTE")
    print("=" * 80)
    print("1. Netzwerk wurde erstellt und gespeichert")
    print("2. Optimierung durchführen mit:")
    print("   n.optimize(solver_name='highs', multi_invest_periods=True)")
    print("3. Ergebnisse analysieren und visualisieren")
    print()
    print("[MARKIERTE ANNAHMEN]")
    print("- Lastprofile: Typisches Fernwärmelastprofil analog 2022")
    print("- COP-Profile: Temperaturabhängig (Luft 2.0-4.0, Abwasser 3.8)")
    print("- Investitionskosten: E-Kessel 150, Luft-WP 800, Abwasser-WP 1200 EUR/kW")
    print("- Speicherkosten: 400 EUR/kWh")
    print("- Betriebskosten: Kessel 5, BHKW 8, E-Kessel 2, WP 3-4 EUR/MWh")
    print("=" * 80)
    
    return n


if __name__ == "__main__":
    network = main()
