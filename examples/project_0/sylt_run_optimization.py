"""
Fernwärme Westerland (Sylt) - Optimierung und Ergebnisanalyse
==============================================================

Führt die Multi-Horizon Stochastic Optimization durch und analysiert Ergebnisse.
"""

import pypsa
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path
import time

# ============================================================================
# OPTIMIERUNG
# ============================================================================

def run_optimization(network_file="sylt_network.nc"):
    """Führe Multi-Horizon Stochastic Optimization durch."""
    
    print("=" * 80)
    print("STARTE OPTIMIERUNG")
    print("=" * 80)
    print()
    
    # Lade Netzwerk
    n = pypsa.Network(network_file)
    
    print(f"✓ Netzwerk geladen: {network_file}")
    print(f"  Investment-Perioden: {n.investment_periods.tolist()}")
    print(f"  Szenarien: {n.scenarios.tolist()}")
    print(f"  Zeitschritte: {len(n.snapshots)}")
    print()
    
    # Optimierung
    print("Starte Optimierung (dies kann einige Minuten dauern)...")
    start_time = time.time()
    
    status, condition = n.optimize(
        solver_name="highs",
        multi_invest_periods=True,
        transmission_losses=0,
        extra_functionality=None,
    )
    
    elapsed = time.time() - start_time
    
    print()
    print("=" * 80)
    print("OPTIMIERUNGSERGEBNIS")
    print("=" * 80)
    print(f"Status: {status}")
    print(f"Bedingung: {condition}")
    print(f"Rechenzeit: {elapsed:.1f} Sekunden")
    print(f"Zielfunktion: {n.objective:,.0f} EUR")
    print()
    
    if status == "ok" and condition == "optimal":
        print("✓ Optimierung erfolgreich!")
    else:
        print("⚠ Optimierung nicht erfolgreich - prüfe Einstellungen")
        return None
    
    # Speichere optimiertes Netzwerk
    output_file = Path(network_file).parent / "sylt_network_optimized.nc"
    n.export_to_netcdf(output_file)
    print(f"✓ Optimiertes Netzwerk gespeichert: {output_file}")
    
    return n


# ============================================================================
# ERGEBNISANALYSE
# ============================================================================

def analyze_results(n):
    """Analysiere Optimierungsergebnisse."""
    
    print()
    print("=" * 80)
    print("ERGEBNISANALYSE")
    print("=" * 80)
    print()
    
    # 1. GESAMTKOSTEN PRO PERIODE
    print("1. GESAMTKOSTEN PRO INVESTITIONSPERIODE")
    print("-" * 80)
    
    for period in n.investment_periods:
        period_cost = calculate_period_cost(n, period)
        print(f"  {period}: {period_cost:,.0f} EUR")
    
    print()
    
    # 2. INSTALLIERTE KAPAZITÄTEN
    print("2. INSTALLIERTE KAPAZITÄTEN PRO PERIODE")
    print("-" * 80)
    
    analyze_capacities(n)
    
    print()
    
    # 3. ENERGIEMIX
    print("3. ENERGIEMIX PRO PERIODE")
    print("-" * 80)
    
    analyze_energy_mix(n)
    
    print()
    
    # 4. SPEICHERNUTZUNG
    print("4. SPEICHERNUTZUNG")
    print("-" * 80)
    
    analyze_storage(n)
    
    print()
    
    # 5. EVPI (Expected Value of Perfect Information)
    print("5. EVPI - WERT DER PERFEKTEN INFORMATION")
    print("-" * 80)
    
    calculate_evpi(n)
    
    print()


def calculate_period_cost(n, period):
    """Berechne Gesamtkosten für eine Periode."""
    
    # Kapitalkosten (Investment)
    capital_costs = 0
    
    # Links
    if hasattr(n.links, 'p_nom_opt'):
        links_period = n.links[n.links.build_year == period]
        if len(links_period) > 0:
            capital_costs += (links_period.p_nom_opt * links_period.capital_cost).sum()
    
    # Stores
    if hasattr(n.stores, 'e_nom_opt'):
        stores_period = n.stores[n.stores.build_year == period]
        if len(stores_period) > 0:
            capital_costs += (stores_period.e_nom_opt * stores_period.capital_cost).sum()
    
    # Betriebskosten (vereinfacht: aus Zielfunktion)
    operational_costs = n.objective / len(n.investment_periods)  # Näherung
    
    return capital_costs + operational_costs


def analyze_capacities(n):
    """Analysiere installierte Kapazitäten."""
    
    for period in n.investment_periods:
        print(f"  Periode {period}:")
        
        # Links (Erzeuger)
        links_period = n.links[n.links.build_year == period]
        
        if len(links_period) > 0:
            for idx, row in links_period.iterrows():
                if hasattr(n.links_t, 'p_nom_opt') and idx in n.links.index:
                    capacity = n.links.loc[idx, 'p_nom_opt']
                else:
                    capacity = row['p_nom']
                
                if capacity > 0.01:  # Nur relevante Kapazitäten
                    print(f"    {idx}: {capacity:.2f} MW")
        
        # Stores (Speicher)
        stores_period = n.stores[n.stores.build_year == period]
        
        if len(stores_period) > 0:
            for idx, row in stores_period.iterrows():
                if hasattr(n.stores_t, 'e_nom_opt') and idx in n.stores.index:
                    capacity = n.stores.loc[idx, 'e_nom_opt']
                else:
                    capacity = row['e_nom']
                
                if capacity > 0.01:
                    print(f"    {idx}: {capacity:.2f} MWh")
        
        print()


def analyze_energy_mix(n):
    """Analysiere Energiemix (Wärmeerzeugung nach Technologie)."""
    
    for period in n.investment_periods:
        print(f"  Periode {period}:")
        
        # Summiere Energieerzeugung pro Carrier
        energy_by_carrier = {}
        
        # Links
        if hasattr(n.links_t, 'p1'):
            for link in n.links.index:
                if str(period) in link:
                    carrier = n.links.loc[link, 'carrier']
                    
                    # Wärmeerzeugung (bus1 = heat_network)
                    if n.links.loc[link, 'bus1'] == 'heat_network':
                        energy = n.links_t.p1[link].sum() / 1000  # GWh
                        
                        if carrier not in energy_by_carrier:
                            energy_by_carrier[carrier] = 0
                        energy_by_carrier[carrier] += energy
        
        # Ausgabe
        total_energy = sum(energy_by_carrier.values())
        
        for carrier, energy in sorted(energy_by_carrier.items(), key=lambda x: -x[1]):
            percentage = (energy / total_energy * 100) if total_energy > 0 else 0
            print(f"    {carrier}: {energy:.1f} GWh ({percentage:.1f}%)")
        
        print(f"    GESAMT: {total_energy:.1f} GWh")
        print()


def analyze_storage(n):
    """Analysiere Speichernutzung."""
    
    for store in n.stores.index:
        if hasattr(n.stores_t, 'e'):
            avg_level = n.stores_t.e[store].mean()
            max_level = n.stores_t.e[store].max()
            capacity = n.stores.loc[store, 'e_nom']
            
            if capacity > 0.01:
                utilization = (avg_level / capacity * 100) if capacity > 0 else 0
                print(f"  {store}:")
                print(f"    Kapazität: {capacity:.2f} MWh")
                print(f"    Ø Füllstand: {avg_level:.2f} MWh ({utilization:.1f}%)")
                print(f"    Max Füllstand: {max_level:.2f} MWh")
                print()


def calculate_evpi(n):
    """
    Berechne EVPI (Expected Value of Perfect Information).
    EVPI = Kosten (Stochastisch) - Kosten (Deterministisch)
    """
    
    stochastic_cost = n.objective
    
    print(f"  Stochastische Kosten: {stochastic_cost:,.0f} EUR")
    print()
    print("  [INFO] Deterministische Kosten müssen durch separate Optimierung")
    print("  ohne Szenarien berechnet werden (nicht hier implementiert).")
    print()
    print("  EVPI = Kosten(Stochastisch) - Kosten(Deterministisch)")
    print("  EVPI zeigt den Wert der Information über Unsicherheiten.")


# ============================================================================
# VISUALISIERUNG
# ============================================================================

def create_plots(n):
    """Erstelle Visualisierungen der Ergebnisse."""
    
    print()
    print("=" * 80)
    print("ERSTELLE VISUALISIERUNGEN")
    print("=" * 80)
    print()
    
    output_dir = Path(__file__).parent
    
    # 1. KAPAZITÄTSENTWICKLUNG
    plot_capacity_evolution(n, output_dir)
    
    # 2. ENERGIEMIX
    plot_energy_mix(n, output_dir)
    
    # 3. SPEICHERVERLAUF (erste Periode, base scenario)
    plot_storage_profile(n, output_dir)
    
    # 4. LASTDECKUNG (erste Periode)
    plot_dispatch(n, output_dir)
    
    print("✓ Alle Plots erstellt")


def plot_capacity_evolution(n, output_dir):
    """Plotte Kapazitätsentwicklung über Perioden."""
    
    fig, ax = plt.subplots(figsize=(12, 6))
    
    # Sammle Kapazitäten pro Technologie und Periode
    tech_capacities = {}
    
    for period in n.investment_periods:
        for link in n.links.index:
            if str(period) in link:
                carrier = n.links.loc[link, 'carrier']
                capacity = n.links.loc[link, 'p_nom_opt'] if hasattr(n.links, 'p_nom_opt') else n.links.loc[link, 'p_nom']
                
                if capacity > 0.01:
                    if carrier not in tech_capacities:
                        tech_capacities[carrier] = {p: 0 for p in n.investment_periods}
                    tech_capacities[carrier][period] += capacity
    
    # Plotte
    for carrier, capacities in tech_capacities.items():
        periods = list(capacities.keys())
        values = list(capacities.values())
        ax.plot(periods, values, marker='o', label=carrier, linewidth=2)
    
    ax.set_xlabel("Investitionsperiode", fontsize=12)
    ax.set_ylabel("Installierte Leistung [MW]", fontsize=12)
    ax.set_title("Kapazitätsentwicklung Fernwärme Westerland", fontsize=14, fontweight='bold')
    ax.legend(loc='best')
    ax.grid(True, alpha=0.3)
    
    plt.tight_layout()
    output_file = output_dir / "sylt_capacity_evolution.png"
    plt.savefig(output_file, dpi=300)
    print(f"  ✓ {output_file.name}")
    plt.close()


def plot_energy_mix(n, output_dir):
    """Plotte Energiemix pro Periode."""
    
    fig, ax = plt.subplots(figsize=(12, 6))
    
    # Sammle Energien
    energy_data = {carrier: [] for carrier in ['gas', 'biomethane', 'electricity']}
    periods = n.investment_periods.tolist()
    
    for period in periods:
        period_energy = {carrier: 0 for carrier in energy_data.keys()}
        
        if hasattr(n.links_t, 'p1'):
            for link in n.links.index:
                if str(period) in link:
                    carrier = n.links.loc[link, 'carrier']
                    
                    if n.links.loc[link, 'bus1'] == 'heat_network':
                        energy = n.links_t.p1[link].sum() / 1000  # GWh
                        
                        if carrier in period_energy:
                            period_energy[carrier] += energy
        
        for carrier in energy_data.keys():
            energy_data[carrier].append(period_energy[carrier])
    
    # Gestapeltes Balkendiagramm
    bottom = np.zeros(len(periods))
    
    colors = {'gas': '#8B4513', 'biomethane': '#228B22', 'electricity': '#FFA500'}
    
    for carrier, energies in energy_data.items():
        ax.bar(periods, energies, bottom=bottom, label=carrier, color=colors.get(carrier, 'gray'))
        bottom += energies
    
    ax.set_xlabel("Investitionsperiode", fontsize=12)
    ax.set_ylabel("Wärmeerzeugung [GWh]", fontsize=12)
    ax.set_title("Energiemix Wärmeerzeugung", fontsize=14, fontweight='bold')
    ax.legend(loc='best')
    ax.grid(True, alpha=0.3, axis='y')
    
    plt.tight_layout()
    output_file = output_dir / "sylt_energy_mix.png"
    plt.savefig(output_file, dpi=300)
    print(f"  ✓ {output_file.name}")
    plt.close()


def plot_storage_profile(n, output_dir):
    """Plotte Speicherverlauf (erste 2 Wochen)."""
    
    if not hasattr(n.stores_t, 'e'):
        print("  [INFO] Keine Speicherdaten verfügbar")
        return
    
    fig, ax = plt.subplots(figsize=(14, 6))
    
    # Erste 336 Stunden (2 Wochen)
    hours = 336
    
    for store in n.stores.index:
        if n.stores.loc[store, 'e_nom'] > 0.01:
            profile = n.stores_t.e[store].iloc[:hours]
            ax.plot(profile.index[:hours], profile, label=store, linewidth=1.5)
    
    ax.set_xlabel("Zeit", fontsize=12)
    ax.set_ylabel("Speicherfüllstand [MWh]", fontsize=12)
    ax.set_title("Speicherverlauf (erste 2 Wochen)", fontsize=14, fontweight='bold')
    ax.legend(loc='best')
    ax.grid(True, alpha=0.3)
    
    plt.tight_layout()
    output_file = output_dir / "sylt_storage_profile.png"
    plt.savefig(output_file, dpi=300)
    print(f"  ✓ {output_file.name}")
    plt.close()


def plot_dispatch(n, output_dir):
    """Plotte Lastdeckung (erste Woche)."""
    
    if not hasattr(n.links_t, 'p1'):
        print("  [INFO] Keine Dispatch-Daten verfügbar")
        return
    
    fig, ax = plt.subplots(figsize=(14, 6))
    
    # Erste 168 Stunden (1 Woche)
    hours = 168
    
    # Sammle Erzeugung pro Technologie
    dispatch_data = {}
    
    for link in n.links.index:
        if n.links.loc[link, 'bus1'] == 'heat_network':
            carrier = n.links.loc[link, 'carrier']
            profile = n.links_t.p1[link].iloc[:hours]
            
            if carrier not in dispatch_data:
                dispatch_data[carrier] = np.zeros(hours)
            dispatch_data[carrier] += profile.values
    
    # Gestapelte Flächen
    time_index = n.snapshots[:hours]
    bottom = np.zeros(hours)
    
    colors = {'gas': '#8B4513', 'biomethane': '#228B22', 'electricity': '#FFA500'}
    
    for carrier, values in dispatch_data.items():
        ax.fill_between(time_index, bottom, bottom + values, 
                        label=carrier, alpha=0.7, color=colors.get(carrier, 'gray'))
        bottom += values
    
    # Last
    load = n.loads_t.p_set.iloc[:hours, 0]
    ax.plot(time_index, load, 'k--', label='Wärmebedarf', linewidth=2)
    
    ax.set_xlabel("Zeit", fontsize=12)
    ax.set_ylabel("Leistung [MW]", fontsize=12)
    ax.set_title("Lastdeckung Fernwärme (erste Woche)", fontsize=14, fontweight='bold')
    ax.legend(loc='best')
    ax.grid(True, alpha=0.3)
    
    plt.tight_layout()
    output_file = output_dir / "sylt_dispatch.png"
    plt.savefig(output_file, dpi=300)
    print(f"  ✓ {output_file.name}")
    plt.close()


# ============================================================================
# HAUPTFUNKTION
# ============================================================================

def main():
    """Hauptfunktion: Optimierung und Analyse."""
    
    # Pfad zum Netzwerk
    network_file = Path(__file__).parent / "sylt_network.nc"
    
    if not network_file.exists():
        print(f"❌ Netzwerk-Datei nicht gefunden: {network_file}")
        print("Bitte zuerst 'sylt_heat_network_optimization.py' ausführen.")
        return
    
    # Optimierung
    n = run_optimization(network_file)
    
    if n is None:
        print("❌ Optimierung fehlgeschlagen")
        return
    
    # Analyse
    analyze_results(n)
    
    # Visualisierung
    create_plots(n)
    
    print()
    print("=" * 80)
    print("FERTIG!")
    print("=" * 80)
    print("Alle Ergebnisse wurden analysiert und gespeichert.")
    print()


if __name__ == "__main__":
    main()
