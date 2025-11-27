"""
Schnelle Optimierung NUR zum Speichern (ohne Ausgabe)
"""

import pypsa
from pathlib import Path

# Lade Netzwerk
network_file = Path(__file__).parent / "sylt_network_full.nc"
print("Lade Netzwerk...")
n = pypsa.Network(network_file)

print("Starte Optimierung...")
print("(Dies dauert ~55 Minuten, aber das Ergebnis wird SOFORT gespeichert)")

try:
    result = n.optimize(
        solver_name="highs",
        solver_options={
            "presolve": "on",
            "parallel": "on",
            "threads": 4,
            "time_limit": 7200.0,
            "mip_rel_gap": 0.005,
        }
    )
    
    if result[0] == "ok":
        print()
        print("OPTIMIERUNG ERFOLGREICH!")
        print(f"Zielfunktion: {n.objective:,.2f} EUR")
        
        # SOFORT speichern
        output_file = Path(__file__).parent / "sylt_network_full_optimized.nc"
        print(f"Speichere: {output_file}")
        n.export_to_netcdf(output_file)
        print("✓ GESPEICHERT!")
        print()
        print("Für Ergebnisse: python show_full_results.py")
    else:
        print(f"Fehler: {result}")
        
except Exception as e:
    print(f"FEHLER: {e}")
    import traceback
    traceback.print_exc()
