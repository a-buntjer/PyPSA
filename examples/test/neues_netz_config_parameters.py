#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Konfiguration für NEUES WÄRMENETZ

Vereinfachte Konfiguration ohne Excel-Datei für schnellen Start.
Anpassbar für spätere Excel-Integration.

NETZ-SPEZIFIKATION:
- Erzeuger: Luft-Wasser-Wärmepumpe, Erdgaskessel, Fremdwärme (11 GWh/a)
- Speicher: Wärmespeicher (ausbaubar)
- Szenarien: 3 gleichgewichtete Szenarien (Wärmelast + Strompreis variiert)
- Perioden: 2027-2037 (10 Jahre, BEW aktiv), 2037-2042 (5 Jahre, keine BEW)

MODI:
- USE_STOCHASTIC = False: Deterministisch (nur 'mittel' Szenario)
- USE_STOCHASTIC = True:  Stochastisch (3 Szenarien mit je 1/3 Wahrscheinlichkeit)
"""

import pandas as pd
import numpy as np

# =============================================================================
# BETRIEBSMODUS
# =============================================================================
# False = Deterministisch (nur 'mittel' Szenario), True = Stochastisch (3 Szenarien)
USE_STOCHASTIC = True  # Fix applied: Dimension alignment for stochastic Store constraints

# =============================================================================
# WIRTSCHAFTLICHE PARAMETER
# =============================================================================
ECONOMIC_PARAMS = {
    "discount_rate": 0.06,              # WACC für CAPEX-Annuitäten (6%)
    "discount_rate_objective": 0.03,    # Gesellschaftliche Zeitpräferenz für NPV (3%)
    "subsidy_rate": 0.40,               # BEW-Förderung (40%) - nur Periode 1
    "island_surcharge": 0.0,            # Kein Inselzuschlag für dieses Netz
    "planning_costs": 0.05,             # Planungskosten (5% von CAPEX)
    "construction_costs": 0.10,         # Baukosten (10% von CAPEX)
}

# =============================================================================
# TECHNOLOGIEN
# =============================================================================
TECHNOLOGIES = {
    "luft_wp": {
        "carrier": "heat_pump",
        "efficiency": 1.0,              # Wird durch COP-Zeitreihe überschrieben
        "cop": 3.0,                     # Durchschnittlicher COP (fallback)
        "cop_range": (2.0, 4.5),        # Min/Max COP bei verschiedenen Temperaturen
        "base_capex_eur_per_kw": 700,   # EUR/kW thermisch
        "opex_fixed_eur_per_kw_year": 15,
        "lifetime_years": 20,
        "p_nom_max_mw": 50,             # Max. Ausbau 50 MW
        "first_build_year": 2027,
    },
    "gaskessel": {
        "carrier": "gas_boiler",
        "efficiency": 0.95,
        "base_capex_eur_per_kw": 200,
        "opex_fixed_eur_per_kw_year": 8,
        "lifetime_years": 20,
        "p_nom_max_mw": 30,             # Max. Ausbau 30 MW
        "first_build_year": 2027,
    },
    "fremdwaerme": {
        "carrier": "heat",
        "efficiency": 1.0,
        "base_capex_eur_per_kw": 0,     # Keine Investitionskosten (Contracting)
        "opex_fixed_eur_per_kw_year": 0,
        "lifetime_years": 999,          # "Unendlich" (keine Abschreibung)
        "p_nom_max_mw": 3.0,            # Fixe 3 MW für 11 GWh/a
        "first_build_year": 2027,
        "annual_energy_gwh": 11.0,      # Fixe Einspeisung 11 GWh/a
    },
}

# =============================================================================
# ENERGIEPREISE (Statisch)
# =============================================================================
ENERGY_PRICES = {
    "electricity": {
        "base_price_2027": 90.0,        # EUR/MWh
        "base_price_2042": 100.0,       # EUR/MWh (leicht steigend)
        "daily_variation": 20.0,        # +/- 20 EUR/MWh Tagesvariation
    },
    "gas": {
        "erdgas_price": 40.0,           # EUR/MWh
        "biomethane_price": 70.0,       # EUR/MWh (nicht verwendet in diesem Zeitraum)
        "switch_year": 2050,            # Wechsel erst nach Simulationszeitraum
    },
    "fremdwaerme": {
        "price": 65.0,                  # EUR/MWh (Contracting-Preis)
    },
}

# =============================================================================
# NETZENTGELTE UND ABGABEN
# =============================================================================
NETWORK_TARIFFS = {
    "gas": {
        "leistungspreis_eur_mw_a": 0,       # Vereinfacht: nur Arbeitspreis
        "arbeitspreis_eur_mwh": 8.0,
        "arbeitspreis_mischpreis_eur_mwh": 8.0,
    },
    "electricity": {
        "leistungspreis_eur_mw_a": 0,       # Vereinfacht: nur Arbeitspreis
        "arbeitspreis_eur_mwh": 12.0,
        "arbeitspreis_mischpreis_eur_mwh": 12.0,
    },
}

LEVIES_AND_TAXES = {
    "electricity": {
        "kwkg_umlage": 0.357,           # EUR/MWh
        "stromnev_umlage": 0.417,
        "offshore_umlage": 0.591,
        "abschaltbare_lasten_umlage": 0.003,
        "konzessionsabgabe": 1.10,
        "stromsteuer": 2.05,
    },
    "gas": {
        "konzessionsabgabe": 0.27,      # EUR/MWh
        "erdgassteuer": 5.5,            # EUR/MWh (nur Kessel, nicht KWK)
        "co2_aufschlag": 8.0,           # EUR/MWh (ca. 40 EUR/t * 0.2 t/MWh)
    },
}

# =============================================================================
# BEW MODUL 4 PARAMETER
# =============================================================================
BEW_MODULE4 = {
    "foerderpreis_umweltwaerme_eur_mwh": 30.0,  # Förderung für Umweltwärme-Anteil
    "max_foerderquote": 0.40,                    # Max 40% Förderung
}

# =============================================================================
# CO2 PREISE (vereinfacht)
# =============================================================================
CO2_PRICES = {
    2027: 45,   # EUR/t CO2
    2030: 60,
    2035: 80,
    2037: 90,
    2042: 110,
}

# =============================================================================
# SZENARIEN (3 gleichgewichtet für stochastische Optimierung)
# =============================================================================
SCENARIOS = {
    "niedrig": {
        "probability": 1/3,
        "demand_factor": 0.90,              # -10% Wärmebedarf
        "demand_growth_rate": -0.005,       # -0.5% p.a.
        "electricity_price_factor": 0.85,   # -15% Strompreis
        "gas_price_factor": 1.0,
    },
    "mittel": {
        "probability": 1/3,
        "demand_factor": 1.0,               # Basis-Wärmebedarf (aus Excel 2023)
        "demand_growth_rate": 0.0,          # 0% p.a.
        "electricity_price_factor": 1.0,    # Basis-Strompreis
        "gas_price_factor": 1.0,
    },
    "hoch": {
        "probability": 1/3,
        "demand_factor": 1.10,              # +10% Wärmebedarf
        "demand_growth_rate": 0.01,         # +1% p.a.
        "electricity_price_factor": 1.20,   # +20% Strompreis
        "gas_price_factor": 1.0,
    },
}

# =============================================================================
# INVESTITIONSPERIODEN (2 Perioden)
# =============================================================================
INVESTMENT_PERIODS = [2027, 2037]

# Gewichtungen in Jahren (für Durchschnittsbildung)
INVESTMENT_PERIOD_WEIGHTINGS = {
    2027: 10,   # 2027-2036 (10 Jahre) - BEW aktiv
    2037: 5,    # 2037-2041 (5 Jahre) - keine BEW
}

# BEW-Aktivierung pro Periode
BEW_ACTIVE_PERIODS = {
    2027: True,     # Periode 1: BEW aktiv
    2037: False,    # Periode 2: BEW inaktiv
}

# =============================================================================
# SPEICHER
# =============================================================================
STORAGE = {
    "existing_capacity_mwh": 0.0,       # Kein Bestandsspeicher
    "extendable_max_mwh": 50.0,         # Max. Ausbau 50 MWh
    "capex_eur_per_mwh": 40000,         # 40.000 EUR/MWh
    "standing_loss_per_hour": 0.001,    # 0.1% pro Stunde
    "efficiency_charge": 0.95,
    "efficiency_discharge": 0.95,
    "lifetime_years": 25,
}

# =============================================================================
# SOLVER KONFIGURATION
# =============================================================================
SOLVER_CONFIG = {
    "solver_name": "highs",
    "time_limit": 3600,
    "threads": 12,
    "use_unit_commitment": False,       # LP - schneller für Stochastic
    "mip_gap": 0.01,                    # 1% MIP Gap für MILP
}

# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def calculate_annuity(capex, lifetime, discount_rate=None):
    """Berechnet Annuität aus Investitionskosten."""
    if discount_rate is None:
        discount_rate = ECONOMIC_PARAMS["discount_rate"]
    
    if discount_rate == 0:
        return capex / lifetime
    return capex * (discount_rate * (1 + discount_rate)**lifetime) / \
           ((1 + discount_rate)**lifetime - 1)


def apply_financial_factors(base_capex, apply_bew=True):
    """Wendet BEW-Förderung auf Investitionskosten an."""
    if apply_bew:
        return base_capex * (1 - ECONOMIC_PARAMS["subsidy_rate"])
    return base_capex


def get_co2_price(year):
    """Interpoliert CO2-Preis für beliebiges Jahr."""
    if year in CO2_PRICES:
        return CO2_PRICES[year]
    
    years = sorted(CO2_PRICES.keys())
    if year < years[0]:
        return CO2_PRICES[years[0]]
    if year > years[-1]:
        return CO2_PRICES[years[-1]]
    
    for i in range(len(years) - 1):
        if years[i] <= year <= years[i+1]:
            y0, y1 = CO2_PRICES[years[i]], CO2_PRICES[years[i+1]]
            x0, x1 = years[i], years[i+1]
            return y0 + (y1 - y0) * (year - x0) / (x1 - x0)


def get_electricity_base_price(year):
    """Interpoliert Basis-Strompreis."""
    p_2027 = ENERGY_PRICES["electricity"]["base_price_2027"]
    p_2042 = ENERGY_PRICES["electricity"]["base_price_2042"]
    
    if year <= 2027:
        return p_2027
    if year >= 2042:
        return p_2042
    
    return p_2027 + (p_2042 - p_2027) * (year - 2027) / (2042 - 2027)


def get_gas_price(year):
    """Gibt Gaspreis zurück."""
    switch_year = ENERGY_PRICES["gas"]["switch_year"]
    
    if year < switch_year:
        return ENERGY_PRICES["gas"]["erdgas_price"]
    else:
        return ENERGY_PRICES["gas"]["biomethane_price"]


def get_technology_capex(tech_name, apply_bew_subsidy=True):
    """Berechnet effektive Investitionskosten."""
    base_capex = TECHNOLOGIES[tech_name]["base_capex_eur_per_kw"]
    
    if apply_bew_subsidy and tech_name == "luft_wp":
        return apply_financial_factors(base_capex, apply_bew=True)
    return base_capex


def is_bew_active(period):
    """Prüft ob BEW in dieser Periode aktiv ist."""
    return BEW_ACTIVE_PERIODS.get(period, False)


# =============================================================================
# MODULE VALIDATION
# =============================================================================

if __name__ == "__main__":
    print("=" * 80)
    print("NEUES WÄRMENETZ - KONFIGURATION")
    print("=" * 80)
    print()
    
    print("1. Investitionsperioden:")
    for period in INVESTMENT_PERIODS:
        years = INVESTMENT_PERIOD_WEIGHTINGS[period]
        bew = "BEW aktiv" if is_bew_active(period) else "keine BEW"
        print(f"   {period}: {years} Jahre ({bew})")
    
    print("\n2. Szenarien:")
    for name, params in SCENARIOS.items():
        print(f"   {name}: {params['probability']*100:.0f}% - "
              f"Last {params['demand_factor']:.0%}, "
              f"Strom {params['electricity_price_factor']:.0%}")
    
    print("\n3. Technologien:")
    for tech_name in TECHNOLOGIES:
        tech = TECHNOLOGIES[tech_name]
        capex = get_technology_capex(tech_name, apply_bew_subsidy=True)
        print(f"   {tech_name}: {capex:.0f} EUR/kW, "
              f"η={tech.get('efficiency', tech.get('cop', 0)):.2f}")
    
    print("\n4. Energiepreise (2027):")
    print(f"   Strom: {get_electricity_base_price(2027):.1f} EUR/MWh")
    print(f"   Gas: {get_gas_price(2027):.1f} EUR/MWh")
    print(f"   Fremdwärme: {ENERGY_PRICES['fremdwaerme']['price']:.1f} EUR/MWh")
    
    print("\n5. Speicher:")
    print(f"   Max. Ausbau: {STORAGE['extendable_max_mwh']:.1f} MWh")
    print(f"   CAPEX: {STORAGE['capex_eur_per_mwh']:,.0f} EUR/MWh")
    
    print("\n" + "=" * 80)
    print("OK Konfiguration geladen")
    print("=" * 80)
