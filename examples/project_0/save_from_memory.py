"""
Lade das Netzwerk aus dem Terminal und speichere es manuell
"""

import pypsa
from pathlib import Path

# Das Netzwerk müsste noch im Speicher sein vom letzten Lauf
# Alternativ: Lade das nicht-optimierte und zeige was verfügbar ist

network_file = Path(__file__).parent / "sylt_network_full.nc"
print(f"Lade: {network_file}")

n = pypsa.Network(network_file)

print(f"Netzwerk geladen.")
print(f"Optimiert: {hasattr(n, 'objective') and n.objective is not None}")

if hasattr(n, 'objective') and n.objective is not None:
    print(f"Zielfunktion: {n.objective:,.2f} EUR")
    output_file = Path(__file__).parent / "sylt_network_full_optimized_manual.nc"
    n.export_to_netcdf(output_file)
    print(f"Gespeichert: {output_file}")
else:
    print("Netzwerk wurde noch nicht optimiert.")
    print("Starte Optimierung mit: python test_optimization_full.py")
