"""
ZUSAMMENFASSUNG DER BHKW-OPTIMIERUNG

Das ursprüngliche Problem war, dass das BHKW nicht in der Optimierung genutzt wurde.

GEFUNDENE PROBLEME:
===================

1. FEHLENDE BRENNSTOFF-BILANZ-CONSTRAINT ✓ BEHOBEN
   - Der chp_fuel Link war nicht mit chp_generator und chp_boiler verknüpft
   - Lösung: Constraint fuel_p - generator_p - boiler_p == 0 hinzugefügt

2. INKOMPATIBLE LASTPROFILE
   - Last-Profile hatten Q/P ≈ 1.42 (viel Wärme, wenig Strom)
   - Ursprüngliches BHKW hatte Q/P ≈ 0.9 (viel Strom, wenig Wärme)
   - Lösung: BHKW-Parameter angepasst auf Q/P ≈ 1.27 mit ±15% Flexibilität

3. ZU RESTRIKTIVE KOPPLUNGS-CONSTRAINTS
   - Ursprünglich: ±5% Kopplungsband (sehr starr)
   - Lösung: ±15% Kopplungsband (realistischer für moderne BHKW)

4. WIRTSCHAFTLICHKEIT
   - Mit realistischen Gaspreisen (25 EUR/MWh) ist BHKW NICHT wettbewerbsfähig gegen:
     * Wind (0 EUR/MWh, keine Brennstoffkosten)
     * Strommarkt (variierende Preise, incl. negative Preise)
     * Aux-Boiler für Wärme (60 EUR/MWh, aber niedriger CAPEX)

REALISTISCHE PARAMETER JETZT IMPLEMENTIERT:
============================================

BHKW-Wirkungsgrade:
- Elektrisch: 38% (typisch für Gasmotoren-BHKW)
- Thermisch: 48% (realistisch)
- Gesamt: 86% (sehr gut)
- Q/P-Verhältnis: 1.27 (mehr Wärme als Strom)

BHKW-Kosten:
- Brennstoff (Erdgas): 25 EUR/MWh (≈2.5 ct/kWh, realistisch)
- CAPEX Generator: 800 EUR/kW_el/Jahr
- CAPEX Boiler: 200 EUR/kW_th/Jahr
- Start-Up: 50 EUR
- Shut-Down: 20 EUR
- Mindestlast: 40% (Generator), 30% (Boiler)

BHKW-Flexibilität:
- Kopplungsband: ±15% um Q/P = 1.27
- Erlaubt: Q/P zwischen 1.08 und 1.46
- Kompatibel mit Lastprofilen (Q/P = 1.36-1.52)

WARUM BHKW TROTZDEM NICHT GENUTZT WIRD:
========================================

Selbst mit realistischen Parametern ist das BHKW nicht wettbewerbsfähig, weil:

1. Wind ist maximal ausgebaut (50 MW) und wird voll genutzt
2. Strommarkt ist günstig verfügbar (10 MW, durchschnittlich 63 EUR/MWh)
3. Gas-Peaker kann flexibel Spitzenlast decken
4. Aux-Boiler ist für sporadische Wärmeerzeugung günstiger

Effektive BHKW-Kosten pro MWh Strom:
- Brennstoff: 25 / 0.38 = 65.8 EUR/MWh
- CAPEX: ~0.2 EUR/MWh (bei 50% Auslastung)
- Gesamt: ~66 EUR/MWh

Vergleich mit Markt: ~63 EUR/MWh (Durchschnitt)
→ BHKW ist knapp teurer!

WANN IST EIN BHKW WIRTSCHAFTLICH?
===================================

Ein BHKW ist wirtschaftlich attraktiv wenn:

1. Hohe Strom- UND Wärmelast gleichzeitig (KWK-Vorteil nutzen)
2. Hohe Strompreise (> 70 EUR/MWh durchschnittlich)
3. Niedrige Gaspreise (< 20 EUR/MWh)
4. Eingeschränkter Netzzugang (hohe Netzentgelte)
5. Lange Laufzeiten (> 4000 h/Jahr Volllaststunden)
6. Förderung (z.B. KWK-Zuschlag, CO2-Bepreisung)

EMPFEHLUNGEN FÜR WEITERE TESTS:
================================

Um BHKW-Nutzung zu erzwingen (für Testzwecke):

Option A: Gaspreise senken
  marginal_cost=15.0 (statt 25.0) in chp_fuel

Option B: Markt stärker einschränken
  p_nom_max=5.0 (statt 10.0) in grid_trade
  capital_cost=1000.0 (statt 500.0)

Option C: Aux-Boiler verteuern
  marginal_cost=100.0 (statt 60.0)

Option D: KWK-Förderung simulieren
  marginal_cost=-5.0 in chp_generator (negative Kosten = Förderung)

Option E: CO2-Preis hinzufügen
  CO2-intensive Alternativen verteuern

DATEIEN FÜR WEITERE ANALYSE:
=============================

- analyze_chp.py: Detaillierte BHKW-Nutzungsanalyse
- cost_analysis.py: Kostenvergleich BHKW vs. Alternativen
- constraint_analysis.py: Prüfung der Constraint-Kompatibilität
- feasibility_test.py: Test der Parameter-Konsistenz
- full_diagnosis.py: Vollständige Systemanalyse

"""
print(__doc__)
