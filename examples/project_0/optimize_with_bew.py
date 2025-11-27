"""
Sylt Modell MIT BEW Modul 4 Arbeitspreisförderung
==================================================

Re-optimiert das Modell mit reduzierten Stromkosten für Wärmepumpen
"""

import pypsa
import pandas as pd
import numpy as np
from pathlib import Path
import sys

# Importiere BEW-Berechnung
sys.path.insert(0, str(Path(__file__).parent))
from bew_modul4 import calculate_bew_subsidized_electricity_price

print("=" * 80)
print("MODELL MIT BEW MODUL 4 ARBEITSPREISFÖRDERUNG")
print("=" * 80)
print()

# Lade Original-Netzwerk (VOR Optimierung, aber mit Szenarien)
input_file = Path(__file__).parent / "sylt_network_full.nc"
n = pypsa.Network(input_file)

print("Original-Netzwerk geladen")
print(f"Szenarien: {n.scenarios.tolist()}")
print()

# =============================================================================
# ANPASSUNG: Strompreise für Wärmepumpen mit BEW reduzieren
# =============================================================================
print("Wende BEW Modul 4 Arbeitspreisförderung an...")
print()

# Identifiziere Wärmepumpen
heat_pump_links = [name for name in n.links.index if isinstance(name, tuple) and 
                   ("heat_pump" in name[1])]

print(f"Gefunden: {len(heat_pump_links)} Wärmepumpen-Einträge (über alle Szenarien)")

# Für jedes Szenario: Reduziere effektive Stromkosten der WP
gas_reference_price = 100.0  # EUR/MWh Gaspreis als Referenz
bew_subsidy_rate = 0.50      # 50% BEW-Förderung

# Speichere Original-Marginalkosten
original_marginal_costs = {}

for scenario in n.scenarios:
    print(f"  Anpasse Szenario '{scenario}'...")
    
    # Hole Generator für Strom
    elec_gen_idx = (scenario, "electricity_supply")
    
    if elec_gen_idx in n.generators_t.marginal_cost.columns:
        # Original Strompreise
        original_elec_prices = n.generators_t.marginal_cost[elec_gen_idx].copy()
        
        # Für Wärmepumpen: Erstelle reduzierte "virtuelle" Stromkosten
        # Dies simulieren wir durch REDUZIERTE marginal_cost der WP-Links
        
        for link_idx in heat_pump_links:
            if link_idx[0] == scenario and link_idx in n.links.index:
                base_name = link_idx[1]
                
                # Hole COP-Profil
                if link_idx in n.links_t.efficiency.columns:
                    cop_profile = n.links_t.efficiency[link_idx].values
                else:
                    # Default COP wenn nicht vorhanden
                    cop_profile = np.full(len(n.snapshots), 3.5)
                
                # Berechne effektive Strompreise mit BEW
                effective_prices = np.zeros_like(original_elec_prices.values)
                
                for i in range(len(original_elec_prices)):
                    elec_price = original_elec_prices.iloc[i]
                    cop = cop_profile[i] if i < len(cop_profile) else 3.5
                    
                    effective_prices[i] = calculate_bew_subsidized_electricity_price(
                        elec_price,
                        gas_reference_price,
                        cop,
                        bew_subsidy_rate
                    )
                
                # Speichere ursprüngliche marginal_cost
                if link_idx in n.links.index:
                    original_mc = n.links.loc[link_idx, "marginal_cost"]
                    original_marginal_costs[link_idx] = original_mc
                    
                    # Berechne durchschnittliche Ersparnis
                    avg_reduction = (original_elec_prices.mean() - effective_prices.mean()) / cop_profile.mean()
                    
                    # Setze neue marginal_cost (reduziert um BEW-Förderung / COP)
                    new_mc = max(0, original_mc - avg_reduction)
                    n.links.loc[link_idx, "marginal_cost"] = new_mc
                    
                    print(f"    {base_name:35s}: {original_mc:.2f} → {new_mc:.2f} EUR/MWh (-{avg_reduction:.2f})")

print()
print("BEW-Förderung angewendet!")
print()

# Speichere angepasstes Netzwerk
output_network = Path(__file__).parent / "sylt_network_full_bew.nc"
n.export_to_netcdf(output_network)
print(f"Netzwerk mit BEW gespeichert: {output_network}")
print()

# =============================================================================
# OPTIMIERUNG MIT BEW
# =============================================================================
print("=" * 80)
print("STARTE OPTIMIERUNG MIT BEW-FÖRDERUNG")
print("=" * 80)
print()

try:
    result = n.optimize(
        solver_name="highs",
        solver_options={
            "presolve": "on",
            "parallel": "on",
            "threads": 12,
            "time_limit": 7200.0,
            "mip_rel_gap": 0.05,
        }
    )
    
    if result[0] == "ok":
        print()
        print("OPTIMIERUNG ERFOLGREICH!")
        print(f"Zielfunktion: {n.objective:,.2f} EUR")
        print()
        
        # Speichere
        output_opt = Path(__file__).parent / "sylt_network_full_bew_optimized.nc"
        n.export_to_netcdf(output_opt)
        print(f"Optimiertes Netzwerk gespeichert: {output_opt}")
        print()
        
        # Schnelle Auswertung
        print("=" * 80)
        print("VERGLEICH: OHNE vs. MIT BEW")
        print("=" * 80)
        print()
        
        # Lade Original-Optimierung
        n_original = pypsa.Network(Path(__file__).parent / "sylt_network_full_optimized.nc")
        
        print(f"  OHNE BEW: {n_original.objective:>15,.2f} EUR")
        print(f"  MIT BEW:  {n.objective:>15,.2f} EUR")
        
        diff = n_original.objective - n.objective
        diff_percent = (diff / n_original.objective) * 100
        
        print()
        print(f"  Ersparnis: {diff:>15,.2f} EUR ({diff_percent:+.1f}%)")
        print()
        
        # Kapazitäten vergleichen
        print("NEUE KAPAZITÄTEN (MIT BEW):")
        first_scenario = n.scenarios[0]
        
        for idx in n.links.index:
            if isinstance(idx, tuple) and idx[0] == first_scenario:
                base_name = idx[1]
                if n.links.loc[idx, "p_nom_extendable"]:
                    p_opt = n.links.loc[idx, "p_nom_opt"]
                    p_init = n.links.loc[idx, "p_nom"]
                    if p_opt > p_init + 0.01:
                        print(f"  {base_name:40s}: {p_opt:7.2f} MW (war: {p_init:.2f} MW)")
        
        print()
        
    else:
        print(f"Optimierung fehlgeschlagen: {result}")

except Exception as e:
    print(f"FEHLER: {e}")
    import traceback
    traceback.print_exc()

print()
print("=" * 80)
print("Für detaillierte Analyse: python compare_bew_results.py")
print("=" * 80)
