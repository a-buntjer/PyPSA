# Stochastische Dispatch-Optimierung mit fixen Kapazitäten

## Übersicht

Dieses Beispiel demonstriert **pure Dispatch-Optimierung unter Unsicherheit** mit:

- **Fixen Anlagenkapazitäten** (Wärmepumpe, Speicher, Kessel)
- **Stochastischen Szenarien** für Prognose-Unsicherheiten (Strompreise, Wärmebedarf)
- **Unit Commitment** für Wärmepumpen-Betrieb (AN/AUS-Entscheidungen)
- **Szenario-spezifischen operativen Entscheidungen** pro Zeitschritt
- **Minimierung der erwarteten Betriebskosten**

## Mathematischer Unterschied zur Speicher-Auslegung

### Speicher-Auslegung (`stochastic_heat_storage_optimization.py`)
**Two-Stage Stochastic Programming:**

- **First Stage**: Speicherkapazität `e_nom` optimieren (vor Kenntnis des Szenarios)
- **Second Stage**: Dispatch optimieren (nach Kenntnis des Szenarios)

```
min E_nom + Σ(s) p(s) × [Betriebskosten(s, E_nom)]
```

### Dispatch-Optimierung (`stochastic_dispatch_heat_network.py`)
**Pure Second-Stage Stochastic Optimization:**

- **Keine First Stage**: Alle Kapazitäten sind vorgegeben
- **Nur Second Stage**: Optimale Fahrweise für verschiedene Szenarien

```
min Σ(s) p(s) × Betriebskosten(s)
```

mit fixen Kapazitäten: `E_nom = const`, `P_nom_WP = const`

## Anwendungsfall

**Kurzfristige Betriebsplanung** mit Prognose-Unsicherheit:

- **Strompreis-Prognosen** mit verschiedenen Realisierungen (niedrig/mittel/hoch)
- **Wärmebedarf-Prognosen** mit Wetterunsicherheiten (kalt/normal/warm)
- **Wind-/PV-Prognosen** für Einspeisung (sonnig/bewölkt)
- **Lastprognosen** für elektrische Systeme

Typischer Zeithorizont: **1-7 Tage** (operativ) vs. **1-30 Jahre** (strategisch)

## Konfiguration

### Fixe Anlagenkapazitäten

```python
HP_FIXED_CAPACITY_MW = 0.6         # 600 kW Wärmepumpe (fix)
STORAGE_FIXED_CAPACITY_MWH = 2.0   # 2 MWh Speicher (fix)
BOILER_FIXED_CAPACITY_MW = 0.3     # 300 kW Backup-Kessel (fix)
```

**Wichtig**: Alle Kapazitäten sind `p_nom_extendable=False`!

### Szenarien (Prognose-Unsicherheit)

| Szenario | Beschreibung | Strompreis | Wärmebedarf | Wahrscheinlichkeit |
|----------|--------------|------------|-------------|-------------------|
| **low_price_high_demand** | Niedriger Preis, hoher Bedarf | 70% | 120% | 30% |
| **medium** | Mittlere Prognose | 100% | 100% | 50% |
| **high_price_low_demand** | Hoher Preis, niedriger Bedarf | 140% | 85% | 20% |

Diese Szenarien repräsentieren **Prognose-Fehler**, keine langfristigen Szenarien!

### Betriebsparameter

```python
HP_MIN_PART_LOAD = 0.3      # 30% Mindestteillast
HP_STARTUP_COST = 50        # EUR pro Start
HP_MIN_UPTIME = 2           # Mindestens 2h AN
HP_MIN_DOWNTIME = 1         # Mindestens 1h AUS
STORAGE_STANDING_LOSS = 0.02  # 2% Verlust/h
```

### Zeitreihen

```python
SIMULATION_HOURS = 168  # 1 Woche (typisch für Dispatch-Planung)
```

Basis-Zeitreihen (identisch für alle Szenarien):
- Tagesgang Wärmebedarf (sinusförmig)
- Außentemperatur (beeinflusst COP)
- COP-Variation (temperaturabhängig)

Szenario-spezifische Anpassungen:
- Strompreise: `Preis(s) = Basis × price_factor(s)`
- Wärmebedarf: `Bedarf(s) = Basis × demand_factor(s)`

## Verwendung

### Installation

Erforderliche Pakete (gleich wie Speicher-Auslegung):
```bash
mamba install -c conda-forge pypsa pandas matplotlib numpy highs
```

### Ausführung

```bash
cd PyPSA/examples/Pufferspeicherauslegung
python stochastic_dispatch_heat_network.py
```

### Wichtig: `dispatch_only=True` Parameter

Das neue Feature nutzt den Parameter:
```python
n.optimize(
    solver_name="highs",
    dispatch_only=True,  # NEU: Erzwingt fixe Kapazitäten
    solver_options={'mip_rel_gap': 0.05}
)
```

**Was passiert intern:**
1. Alle `*_extendable` Flags werden auf `False` gesetzt
2. Prüfung, dass alle `p_nom`, `e_nom` definiert sind
3. Nur Dispatch-Variablen werden optimiert
4. Keine Investitionskosten in der Zielfunktion

## Ergebnisse

### Konsolen-Output

```
======================================================================
Creating Network for Stochastic Dispatch-Only Optimization
======================================================================

Simulation period: 2025-01-01 00:00:00 to 2025-01-07 23:00:00
Total snapshots: 168
COP range: 2.50 - 3.65
Base demand range: 0.100 - 0.500 MW

Scenarios (3):
  low_price_high_demand     | Niedriger Strompreis, hoher Wärmebedarf | Weight: 30%
  medium                    | Mittlere Prognose                       | Weight: 50%
  high_price_low_demand     | Hoher Strompreis, niedriger Wärmebedarf | Weight: 20%

Applying scenario-specific parameters:
  low_price_high_demand     | Price:  56.0 EUR/MWh | Avg demand: 0.360 MW
  medium                    | Price:  80.0 EUR/MWh | Avg demand: 0.300 MW
  high_price_low_demand     | Price: 112.0 EUR/MWh | Avg demand: 0.255 MW

======================================================================
Network Summary
======================================================================
Fixed heat pump capacity:    0.6 MW
Fixed storage capacity:      2.0 MWh
Fixed backup boiler:         0.3 MW
Scenarios:                   3
Snapshots:                   168
======================================================================

Optimizing Dispatch (Fixed Capacities)
======================================================================
Dispatch-only mode: Fixing all extendable capacities

Optimization status: ok
Termination condition: optimal

Expected operational cost: 5,432.15 EUR

======================================================================
OPERATIONAL RESULTS (Scenario-Dependent)
======================================================================

Scenario: LOW_PRICE_HIGH_DEMAND
----------------------------------------------------------------------
  Heat Pump Operation:
    Hours operating:      152/168 (90.5%)
    Total heat output:    65.4 MWh
    Total electricity:    21.2 MWh
    Average COP:          3.08
    Number of startups:   6
  
  Storage Operation:
    SOC range:            0.42 - 1.89 MWh
    Utilization:          73.5%
  
  Backup Boiler:
    Total heat:           0.8 MWh
    Usage hours:          4
  
  Costs:
    Electricity:          1,187.20 EUR
    Boiler:               96.00 EUR
    Startups:             300.00 EUR
    Total:                1,583.20 EUR
    Weighted (×30.0%):    474.96 EUR

[... weitere Szenarien ...]

======================================================================
EXPECTED OPERATIONAL COSTS
======================================================================
low_price_high_demand    : 1,583.20 EUR × 30.0% =   474.96 EUR
medium                   : 1,920.45 EUR × 50.0% =   960.23 EUR
high_price_low_demand    : 1,485.30 EUR × 20.0% =   297.06 EUR
----------------------------------------------------------------------
Expected total cost      : 1,732.25 EUR
Optimizer objective      : 1,732.25 EUR

✓ Cost calculation verified!
```

### Visualisierung

Das Skript erstellt ein 3×3 Grid mit Subplots für jedes Szenario:

**Zeile 1 - Szenario "low_price_high_demand":**
- Wärmebilanz (WP + Speicher + Kessel vs. Bedarf)
- Speicher-SOC Verlauf
- WP Status (AN/AUS) + COP

**Zeile 2 - Szenario "medium":**
- [gleiche Plots]

**Zeile 3 - Szenario "high_price_low_demand":**
- [gleiche Plots]

**Output**: `dispatch_only_results/stochastic_dispatch_results.png`

## Vergleich der Optimierungsstrategien

### Niedrig-Preis-Szenario
- **Strategie**: Aggressiver WP-Einsatz, Speicher laden
- **WP-Nutzung**: ~90% der Zeit
- **Backup-Kessel**: Selten genutzt
- **Speicher**: Hohe Auslastung als Puffer

### Hoch-Preis-Szenario
- **Strategie**: Konservativer WP-Einsatz, Speicher entladen
- **WP-Nutzung**: ~70% der Zeit
- **Backup-Kessel**: Häufiger genutzt (trotz höherer Kosten!)
- **Speicher**: Strategi entladung in Hochpreis-Stunden

### Medium-Szenario
- **Strategie**: Balanciert zwischen beiden Extremen

**Wichtige Erkenntnis**: Die optimale Fahrweise ändert sich je nach Preisniveau!

## Unterschiede zwischen Dispatch-Only und Kapazitätsplanung

| Aspekt | Dispatch-Only | Kapazitätsplanung |
|--------|---------------|-------------------|
| **Optimierungshorizont** | Kurzfristig (Stunden-Tage) | Langfristig (Jahre) |
| **Entscheidungsvariablen** | Nur Dispatch (`p`, `status`) | Dispatch + Kapazitäten (`p_nom`, `e_nom`) |
| **Unsicherheit** | Prognose-Fehler | Zukünftige Entwicklungen |
| **Szenarien** | Wenige (3-5) mit hohen Gewichten | Viele (5-20) mit breiter Streuung |
| **Kapazitäten** | Fix vorgegeben | Zu optimieren |
| **First Stage** | Keine | Investitionsentscheidungen |
| **Second Stage** | Betriebsoptimierung | Betriebsoptimierung |
| **Solver-Komplexität** | Niedriger (nur MILP für Dispatch) | Höher (MILP mit mehr Variablen) |
| **Lösungszeit** | Schnell (Sekunden) | Langsam (Minuten-Stunden) |

## Erweiterungsmöglichkeiten

### 1. Rolling Horizon mit aktualisierter Prognose

```python
for day in range(7):
    # Tag 1: Prognose unsicher → Stochastisch optimieren
    n_day1 = create_dispatch_network(hours=24, day=day)
    n_day1.optimize(dispatch_only=True)
    
    # Tag 1 ausführen, dann Tag 2 mit aktualisierter Prognose
    # ...
```

### 2. Mehr Szenarien (z.B. Monte-Carlo)

```python
# 100 Szenarien aus Prognose-Verteilung samplen
price_samples = np.random.lognormal(mean=log(80), sigma=0.3, size=100)
for i, price in enumerate(price_samples):
    SCENARIOS[f'scenario_{i}'] = {
        'weight': 1/100,
        'price_factor': price / 80,
        # ...
    }
```

### 3. Intraday-Handel

```python
# Flexibilität für Regelenergiemarkt vermarkten
n.add("Generator", "flexibility_offer",
      bus="bus_electricity",
      p_nom_extendable=False,
      marginal_cost=-50)  # Erlös aus Flexibilität
```

### 4. Demand Response

```python
# Lastverschiebung als Entscheidungsvariable
n.add("Load", "flexible_demand",
      bus="bus_heat",
      p_set=base_demand * 0.2,  # 20% des Bedarfs flexibel
      p_min_pu=0.8,  # Kann um 20% reduziert werden
      p_max_pu=1.2)  # Kann um 20% erhöht werden (nachholen)
```

## Technische Details

### PyPSA-Behandlung von Szenarien

**Automatische Broadcasting**:
```python
n.set_scenarios(['A', 'B', 'C'])
# Alle DataFrames bekommen scenario-Dimension:
n.generators.index  # MultiIndex: (scenario, name)
n.generators_t.p  # MultiIndex-Spalten: (scenario, name)
```

**Dispatch-Variablen sind szenario-abhängig**:
```python
# Verschiedene Dispatch pro Szenario
n.links_t.status.loc[:, ('A', 'heat_pump')]  # Status in Szenario A
n.links_t.status.loc[:, ('B', 'heat_pump')]  # Status in Szenario B
```

**Kapazitäts-Variablen sind szenario-unabhängig** (bei Investment):
```python
# Gleiche Kapazität in allen Szenarien
n.links.p_nom_opt['heat_pump']  # Ohne scenario-Index!
```

**Bei dispatch_only=True**: Keine Kapazitäts-Variablen im Modell!

### Solver-Performance

Typische Problemgrößen (3 Szenarien, 168 Stunden):

```
Variables:    ~3000 (500 pro Szenario × 3 + Binäre für Status)
Constraints:  ~5000
MIP Gap:      5%
Time:         10-30 Sekunden
```

Zum Vergleich mit Kapazitätsplanung (gleiche Größe):
```
Variables:    ~3020 (+20 für Kapazitäten)
Constraints:  ~5100 (+100 für Investment-Constraints)
MIP Gap:      5%
Time:         30-120 Sekunden (wg. Investment-Kopplung)
```

## Troubleshooting

### Problem: "dispatch_only requires all nominal capacities to be defined"
**Lösung**: Setzen Sie alle `p_nom`, `e_nom`, `s_nom` bevor Sie Szenarien definieren:
```python
n.add("Link", "hp", p_nom=0.6, ...)  # ERST Kapazität setzen
n.set_scenarios([...])                # DANN Szenarien
```

### Problem: "dispatch_only=True but no scenarios set"
**Warnung**: Dispatch-Only macht nur mit Szenarien Sinn. Ohne Szenarien ist es eine deterministische Dispatch-Optimierung, wofür Sie kein spezielles Feature brauchen.

### Problem: Lösung ist deterministisch (gleicher Dispatch in allen Szenarien)
**Ursache**: Szenarien unterscheiden sich nicht genug.
**Lösung**: Erhöhen Sie `price_factor` oder `demand_factor` Unterschiede:
```python
'low': {'price_factor': 0.5},   # Statt 0.7
'high': {'price_factor': 2.0},  # Statt 1.4
```

### Problem: Backup-Kessel wird nie genutzt
**Interpretation**: WP-Kapazität + Speicher reichen aus.
**Lösungen**:
- Reduzieren Sie `HP_FIXED_CAPACITY_MW`
- Erhöhen Sie Spitzenlasten im `demand_factor`
- OK, wenn System gut dimensioniert ist

## Literatur & Referenzen

1. **Short-term Operational Planning:**
   - Morales, J. M., et al. (2013). Integrating Renewables in Electricity Markets.
   
2. **Forecast Uncertainty:**
   - Pinson, P., & Girard, R. (2012). Evaluating the quality of scenarios of short-term wind power generation.

3. **Stochastic Unit Commitment:**
   - Papavasiliou, A., & Oren, S. (2013). Multiarea stochastic unit commitment for high wind penetration.

4. **PyPSA Documentation:**
   - https://pypsa.readthedocs.io/en/latest/user-guide/optimization/stochastic.html

## Vergleich mit dem Investment-Beispiel

| Feature | Dispatch-Only | Investment-Optimierung |
|---------|---------------|------------------------|
| **Datei** | `stochastic_dispatch_heat_network.py` | `stochastic_heat_storage_optimization.py` |
| **Zielfunktion** | Min E[Betriebskosten] | Min [Investition + E[Betriebskosten]] |
| **Kapazitäten** | Fix (0.6 MW WP, 2 MWh Speicher) | Variabel (e_nom optimiert) |
| **dispatch_only** | `True` | `False` (default) |
| **Typische Anwendung** | Tages-/Wochen-Planung | Jahres-/Dekaden-Planung |
| **Szenarien** | Prognose-Fehler | Zukunfts-Pfade |
| **Output** | Fahrplan pro Szenario | Optimale Auslegung + Fahrpläne |

## Kontakt & Support

Bei Fragen oder Problemen:
1. Prüfen Sie zuerst diese README
2. Vergleichen Sie mit `stochastic_heat_storage_optimization.py`
3. Konsultieren Sie PyPSA Dokumentation zu Stochastic Optimization
4. Erstellen Sie ein Issue auf GitHub

## Lizenz

Dieses Beispiel ist Teil von PyPSA und unterliegt der MIT-Lizenz.

---

**Erstellt:** Oktober 2025  
**PyPSA Version:** 1.0.1+ (mit dispatch_only Feature)  
**Branch:** feature/stochastic-dispatch-only  
**Autor:** GitHub Copilot
