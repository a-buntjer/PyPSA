"""
Dispatch-Profile Analyse
========================

Zeigt welche Anlagen wann und wie viel produzieren
"""

import pypsa
import pandas as pd
import numpy as np
from pathlib import Path
import matplotlib.pyplot as plt

# Lade optimiertes Netzwerk
network_file = Path(__file__).parent / "sylt_network_full_optimized.nc"
n = pypsa.Network(network_file)

print("=" * 80)
print("DISPATCH-PROFILE ANALYSE")
print("=" * 80)
print()

# Hilfsfunktion
def get_base_name(idx):
    return idx[1] if isinstance(idx, tuple) else idx

# Wähle ein Szenario für Analyse (base)
scenario = "base"

print(f"Analysiere Szenario: {scenario}")
print()

# =============================================================================
# 1. JAHRESENERGIEN PRO TECHNOLOGIE
# =============================================================================
print("=" * 80)
print("1. JAHRESENERGIEN NACH TECHNOLOGIE")
print("=" * 80)
print()

# Extrahiere Dispatch-Daten
for period in n.investment_periods:
    print(f"--- PERIODE {period} ---")
    print()
    
    # Filter Snapshots für diese Periode
    period_mask = n.snapshots.get_level_values(0) == period
    period_snapshots = n.snapshots[period_mask]
    
    # Links (Erzeuger)
    energy_by_tech = {}
    
    for idx in n.links.index:
        if isinstance(idx, tuple) and idx[0] == scenario:
            base_name = get_base_name(idx)
            build_year = n.links.loc[idx, "build_year"]
            
            if build_year == period:
                # Hole Dispatch
                if idx in n.links_t.p1.columns:
                    dispatch = n.links_t.p1[idx].loc[period_snapshots]
                    energy_mwh = dispatch.sum()
                    
                    if energy_mwh > 0.01:  # Nur wenn tatsächlich produziert
                        # Kategorisiere nach Typ
                        if "BHKW" in base_name:
                            tech_type = "BHKW (Bestand)"
                        elif "Kessel" in base_name:
                            tech_type = "Kessel (Bestand)"
                        elif "electric_heater" in base_name:
                            tech_type = "Elektrodenkessel"
                        elif "heat_pump_air" in base_name:
                            tech_type = "Luft-Wärmepumpe"
                        elif "heat_pump_wastewater" in base_name:
                            tech_type = "Abwasser-Wärmepumpe"
                        else:
                            tech_type = "Sonstige"
                        
                        if tech_type not in energy_by_tech:
                            energy_by_tech[tech_type] = 0
                        energy_by_tech[tech_type] += energy_mwh
    
    # Sortiert ausgeben
    total_energy = sum(energy_by_tech.values())
    
    print("Wärmeerzeugung nach Technologie:")
    for tech_type in sorted(energy_by_tech.keys()):
        energy = energy_by_tech[tech_type]
        share = (energy / total_energy) * 100 if total_energy > 0 else 0
        print(f"  {tech_type:30s}: {energy:>10,.0f} MWh ({share:5.1f}%)")
    
    print(f"  {'GESAMT':30s}: {total_energy:>10,.0f} MWh")
    print()

# =============================================================================
# 2. TYPISCHE TAGE (Winter, Sommer, Übergang)
# =============================================================================
print("=" * 80)
print("2. TYPISCHE TAGE - DISPATCH-PROFILE")
print("=" * 80)
print()

# Wähle repräsentative Tage
representative_days = {
    "Winter": 15,      # 15. Januar
    "Übergang": 105,   # 15. April
    "Sommer": 196,     # 15. Juli
}

for season, day_of_year in representative_days.items():
    print(f"--- {season.upper()} (Tag {day_of_year}) ---")
    
    # Nur erste Periode (2027) für Übersichtlichkeit
    period = 2027
    period_mask = n.snapshots.get_level_values(0) == period
    period_snapshots = n.snapshots[period_mask]
    
    # Extrahiere 24h für diesen Tag
    start_hour = (day_of_year - 1) * 24
    end_hour = start_hour + 24
    day_snapshots = period_snapshots[start_hour:end_hour]
    
    if len(day_snapshots) > 0:
        # Wärmelast
        heat_demand_idx = (scenario, "heat_demand")
        if heat_demand_idx in n.loads_t.p_set.columns:
            demand = n.loads_t.p_set[heat_demand_idx].loc[day_snapshots]
            print(f"  Wärmelast: {demand.mean():.2f} MW (Ø), {demand.max():.2f} MW (Peak)")
        
        # Top-3 Erzeuger
        top_producers = []
        for idx in n.links.index:
            if isinstance(idx, tuple) and idx[0] == scenario:
                base_name = get_base_name(idx)
                build_year = n.links.loc[idx, "build_year"]
                
                if build_year == period and idx in n.links_t.p1.columns:
                    dispatch = n.links_t.p1[idx].loc[day_snapshots]
                    energy_day = dispatch.sum()
                    if energy_day > 0.01:
                        top_producers.append((base_name, energy_day, dispatch.max()))
        
        # Sortiere nach Energie
        top_producers.sort(key=lambda x: x[1], reverse=True)
        
        print("  Top-3 Erzeuger:")
        for i, (name, energy, peak) in enumerate(top_producers[:3], 1):
            print(f"    {i}. {name:35s}: {energy:6.2f} MWh, Peak: {peak:5.2f} MW")
    
    print()

# =============================================================================
# 3. AUSLASTUNG (Volllaststunden)
# =============================================================================
print("=" * 80)
print("3. VOLLLASTSTUNDEN (AUSLASTUNG)")
print("=" * 80)
print()

for period in [2027, 2030, 2035]:  # Erste 3 Perioden
    print(f"--- PERIODE {period} ---")
    
    period_mask = n.snapshots.get_level_values(0) == period
    period_snapshots = n.snapshots[period_mask]
    
    for idx in n.links.index:
        if isinstance(idx, tuple) and idx[0] == scenario:
            base_name = get_base_name(idx)
            build_year = n.links.loc[idx, "build_year"]
            
            if build_year == period and idx in n.links_t.p1.columns:
                dispatch = n.links_t.p1[idx].loc[period_snapshots]
                energy_mwh = dispatch.sum()
                
                if energy_mwh > 0.01:
                    p_nom = n.links.loc[idx, "p_nom_opt"]
                    if p_nom > 0:
                        full_load_hours = energy_mwh / p_nom
                        utilization = (full_load_hours / 8760) * 100
                        
                        # Nur signifikante Anlagen anzeigen
                        if energy_mwh > 100:  # > 100 MWh/Jahr
                            print(f"  {base_name:40s}: {full_load_hours:>6,.0f} h ({utilization:5.1f}%)")
    print()

print("=" * 80)
print("Hinweis: Für detaillierte Grafiken siehe dispatch_plots.py")
print("=" * 80)
