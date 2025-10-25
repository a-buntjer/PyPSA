# Stochastische Pufferspeicher-Auslegung für Fernwärmenetze

## Übersicht

Dieses Beispiel demonstriert die **optimale Auslegung eines thermischen Pufferspeichers** für ein Fernwärmenetz mit:

- **Fixer Wärmepumpen-Leistung** (committable=True für AN/AUS-Betrieb)
- **Stochastischen Wetterszenarien** (Kalt, Mittel, Warm)
- **Temperaturabhängigem Wärmepumpen-COP** (polynomiale Wirkungsgradkurve)
- **Variablem Speicherenergieinhalt** basierend auf Vor-/Rücklauftemperaturen
- **Zeitreihen aus Excel-Dateien** (Wärmebedarf, Temperaturen)

## Mathematischer Rahmen

### Two-Stage Stochastic Optimization

Das Problem wird als **zweistufige stochastische Optimierung** formuliert:

#### First Stage (Here-and-Now Decisions)
Entscheidungen, die **vor** Kenntnis des Szenarios getroffen werden:
- **Speicherkapazität** `e_nom` [MWh] - **DAS OPTIMIERUNGSZIEL**

#### Second Stage (Wait-and-See Decisions)  
Entscheidungen, die **nach** Kenntnis des Szenarios getroffen werden:
- Wärmepumpen-Betrieb (AN/AUS Status)
- Speicher-Ladung/Entladung
- Spitzenlastkessel-Einsatz

### Zielfunktion

```
min: Σ(scenario) weight(scenario) × [
    Capital_cost(storage) +
    Σ(t) [
        Electricity_cost(t) +
        Boiler_cost(t) +
        Startup_cost(t)
    ]
]
```

**Subject to:**
- Wärmebalanz: Heat_demand(t) = HP_output(t) + Storage_discharge(t) + Boiler(t)
- Wärmepumpen-Constraints: Committable, min_uptime, min_downtime, part_load
- Speicher-Constraints: SOC bounds, standing losses, cyclic boundary
- Temperatur-abhängiger COP: COP(T_ambient, T_supply, T_return)

## Konfiguration

### Szenarien

Drei Wetterszenarien aus historischen Daten:

| Szenario | Jahr | Excel Sheet | Gewichtung | Beschreibung |
|----------|------|-------------|------------|--------------|
| **Cold** | 2021 | `Mittlere_Netzprognose_2021` | 25% | Kaltes Wetterjahr |
| **Medium** | 2024 | `Mittlere_Netzprognose_2024` | 50% | Mittleres Wetterjahr |
| **Warm** | 2026 | `Mittlere_Netzprognose_2026` | 25% | Warmes Wetterjahr |

### Wärmepumpe (Feste Kapazität)

```python
HP_FIXED_CAPACITY_MW = 0.6  # 600 kW installierte Leistung
HP_TYPE = 'Fenagy H600'     # Typ für Polynomial-Koeffizienten
HP_MIN_PART_LOAD = 0.3      # 30% Mindestteillast
HP_STARTUP_COST = 50        # EUR pro Start
HP_MIN_UPTIME = 2           # Mindestens 2 Stunden AN
HP_MIN_DOWNTIME = 1         # Mindestens 1 Stunde AUS
```

**COP-Modell** (Polynomiale Approximation):
```
COP = c₀ + c₁·T_amb + c₂·T_in + c₃·T_out + 
      c₄·T_amb² + c₅·T_amb·T_in + c₆·T_amb·T_out +
      c₇·T_in² + c₈·T_in·T_out + c₉·T_out²
```

Koeffizienten werden aus `Interpolationsformeln Parameter für Wärmepumpen.xlsx` geladen.

### Thermischer Speicher (Optimierungsziel)

```python
STORAGE_TEMP_SUPPLY_NOMINAL = 70    # °C Vorlauftemperatur
STORAGE_TEMP_RETURN_NOMINAL = 40    # °C Rücklauftemperatur
STORAGE_STANDING_LOSS = 0.02        # 2% Verlust pro Stunde
STORAGE_CAPITAL_COST_PER_MWH = 50000  # EUR/MWh

# Optimierung
e_nom_min = 0.1 MWh  # Minimum 100 kWh
e_nom_max = 20 MWh   # Maximum 20 MWh
```

**Temperaturabhängiger Energieinhalt**:
```
E_actual(t) = E_nom × [T_supply(t) - T_return(t)] / [T_supply_nom - T_return_nom]
```

### Backup-Systeme

- **Netzstrom**: 80 EUR/MWh (für Wärmepumpe)
- **Spitzenlastkessel**: 120 EUR/MWh (teurer Backup)

## Dateistruktur

### Input-Dateien (Excel)

1. **`Mittlere_Netzprognose_2021_2024_2026_WP_Auslegung.xlsx`**
   - Sheets: `Mittlere_Netzprognose_2021`, `_2024`, `_2026`
   - Spalten:
     - `Datum`: Zeitstempel
     - `Thermische Leistung` / `Leistung`: Wärmebedarf [kW]
     - `VLT`: Vorlauftemperatur [°C]
     - `RLT`: Rücklauftemperatur [°C]
     - `AT`: Außentemperatur [°C]

2. **`Interpolationsformeln Parameter für Wärmepumpen.xlsx`**
   - Polynomial-Koeffizienten für verschiedene WP-Typen
   - Spalten: `Wärmpumpentyp`, `Fenagy H600`, `Fenagy H300`, etc.
   - Rows: `Intercept`, `T_amb`, `T_in`, `T_out`, `T_amb²`, etc.

3. **`2025 02 26 Speicher - Maße Kosten Verluste 1.xlsx`**
   - Speicher-Spezifikationen (optional für erweiterte Analyse)

4. **`Netz und Wärmepumpenparameter für Simulation.xlsx`**
   - Netzwerk-Parameter (optional)

### Output-Dateien

1. **`stochastic_heat_storage_results.nc`**
   - PyPSA Network im NetCDF-Format
   - Enthält alle Optimierungsergebnisse

2. **`stochastic_heat_storage_optimization.png`**
   - 3×n_scenarios Subplots:
     - Wärmebilanz (WP-Output, Speicher, Bedarf)
     - Speicher-SOC Verlauf
     - Wärmepumpen-COP und Status

## Verwendung

### Installation

Erforderliche Pakete:
```bash
mamba install -c conda-forge pypsa pandas openpyxl matplotlib numpy highs
```

### Ausführung

```bash
cd PyPSA/examples/Pufferspeicherauslegung
python stochastic_heat_storage_optimization.py
```

### Anpassung

**Wärmepumpen-Leistung ändern:**
```python
HP_FIXED_CAPACITY_MW = 1.2  # 1.2 MW statt 0.6 MW
```

**Szenarien-Gewichtung ändern:**
```python
SCENARIOS = {
    'cold': {'sheet': '...', 'weight': 0.4},   # 40% statt 25%
    'medium': {'sheet': '...', 'weight': 0.3}, # 30% statt 50%
    'warm': {'sheet': '...', 'weight': 0.3},   # 30% statt 25%
}
```

**Simulationszeitraum ändern:**
```python
HOURS_TO_SIMULATE = 8760  # Ganzes Jahr statt 1 Woche
```

**Optimierungs-Toleranz:**
```python
MIP_GAP = 0.01  # 1% statt 5%
TIME_LIMIT = 3600  # 1 Stunde statt 30 Minuten
```

## Ergebnisse

### Konsolen-Output

Das Skript gibt detaillierte Informationen aus:

1. **Netzwerk-Konfiguration**
   - Szenarien und Gewichtungen
   - WP-Parameter und COP-Range
   - Wärmebedarfs-Statistiken

2. **Optimierung**
   - Solver-Fortschritt (HiGHS)
   - Konvergenz-Informationen

3. **Ergebnisse**
   - **Optimale Speicherkapazität** (konsistent über alle Szenarien)
   - **WP-Betriebsstatistiken** (szenario-spezifisch)
     - Betriebsstunden und Prozentsatz
     - Durchschnittlicher COP
     - Anzahl Starts und Start-Kosten
   - **Speicher-Auslastung** (szenario-spezifisch)
     - SOC-Range
     - Vollzyklen
   - **Backup-Kessel-Nutzung**
   - **Ökonomische Zusammenfassung**
     - Strom-, Kessel-, Start-Kosten
     - Speicher-Investition
     - Gewichtete Gesamtkosten

### Beispiel-Output

```
======================================================================
OPTIMAL THERMAL STORAGE CAPACITY
======================================================================

Scenario: COLD
  Optimal capacity: 2.45 MWh (2450 kWh)
  Investment cost: 122,500 EUR

Scenario: MEDIUM
  Optimal capacity: 2.45 MWh (2450 kWh)
  Investment cost: 122,500 EUR

Scenario: WARM
  Optimal capacity: 2.45 MWh (2450 kWh)
  Investment cost: 122,500 EUR

✓ Storage capacity is consistent across scenarios (first-stage decision)
  Optimal size: 2.45 MWh

----------------------------------------------------------------------
HEAT PUMP OPERATION (Scenario-Dependent)
----------------------------------------------------------------------

Scenario: COLD
  Operating hours: 145/168 (86.3%)
  Total heat output: 78.2 MWh
  Total electricity: 24.1 MWh
  Average COP (operating): 3.24
  Number of startups: 8
  Startup costs: 400 EUR

[...]

======================================================================
ECONOMIC SUMMARY
======================================================================

Scenario: COLD (weight: 25.00%)
  Electricity cost: 1,928 EUR
  Boiler cost: 0 EUR
  Startup cost: 400 EUR
  Storage investment: 122,500 EUR
  Scenario total: 124,828 EUR
  Weighted cost: 31,207 EUR

[...]

Expected total cost: 126,345 EUR
Optimizer objective: 126,345 EUR
======================================================================
```

## Physikalische Modellierung

### Wärmepumpe

**Elektrische zu thermische Leistung:**
```
P_thermal(t) = COP(T_amb(t), T_in(t), T_out(t)) × P_electric(t)
```

**Committable Constraints:**
- `status(t) ∈ {0, 1}` - Binäre Betriebsvariable
- `P_thermal(t) ≥ status(t) × p_nom × p_min_pu` - Mindestteillast
- `P_thermal(t) ≤ status(t) × p_nom` - Maximalleistung
- `Σ(t..t+min_uptime) status ≥ min_uptime × status(t)` - Mindestlaufzeit
- `Σ(t..t+min_downtime) (1-status) ≥ min_downtime × (1-status(t))` - Mindeststillstand

### Thermischer Speicher

**Energie-Bilanz:**
```
E(t+1) = E(t) × (1 - η_loss) + P_charge(t) - P_discharge(t)
```

**Temperaturabhängige Kapazität:**
```
E_max(t) = E_nom × ΔT(t) / ΔT_nom
```

wo `ΔT(t) = T_supply(t) - T_return(t)`

**Constraints:**
- `0 ≤ E(t) ≤ E_max(t)` - SOC-Grenzen
- `E(0) = E(T)` - Zyklische Randbedingung
- `E_nom_min ≤ E_nom ≤ E_nom_max` - Kapazitätsgrenzen

### Wärmebilanz

Für jeden Zeitschritt `t` und jedes Szenario `s`:
```
Heat_demand(s,t) = HP_output(s,t) + Storage_discharge(s,t) + Boiler(s,t)
```

## Erweiterungsmöglichkeiten

### 1. Mehrere Wärmepumpen
```python
for i in range(3):
    n.add("Link", f"{scenario}_heat_pump_{i}", ...)
```

### 2. Elektrische Lastflexibilität
```python
# Zeitabhängige Strompreise
electricity_price = pd.Series(spot_prices, index=n.snapshots)
n.generators_t.marginal_cost[f"{scenario}_grid"] = electricity_price
```

### 3. PV-Eigenversorgung
```python
n.add("Generator", f"{scenario}_pv",
      bus=f"{scenario}_bus_electricity",
      p_max_pu=pv_profile,  # Normalisiertes PV-Profil
      p_nom_extendable=True,
      capital_cost=800000)  # EUR/MW
```

### 4. Mehrere Speicher
```python
# Kurzzeit-Speicher (Puffer)
n.add("Store", f"{scenario}_short_term_storage",
      e_nom_extendable=True,
      standing_loss=0.05)  # Höhere Verluste

# Langzeit-Speicher (Saisonal)
n.add("Store", f"{scenario}_seasonal_storage",
      e_nom_extendable=True,
      standing_loss=0.001)  # Niedrigere Verluste
```

### 5. CO2-Budget
```python
n.add("GlobalConstraint", "co2_limit",
      carrier_attribute="co2_emissions",
      sense="<=",
      constant=1000)  # Tonnen CO2
```

## Technische Details

### Solver-Optionen (HiGHS)

```python
solver_options = {
    'mip_rel_gap': 0.05,      # 5% Optimalitätslücke
    'time_limit': 1800,       # 30 Minuten
    'threads': 16,            # Parallele Threads
    'parallel': 'on',         # Parallelisierung aktiviert
}
```

### Scenario-Dependent vs Independent Variables

**First-Stage (scenario-independent):**
- `e_nom` - Speicherkapazität
- `p_nom` - Generator-/Link-Kapazitäten (wenn extendable)

**Second-Stage (scenario-dependent):**
- `status` - Committable ON/OFF Status
- `p` - Dispatch (Leistung)
- `e` - Speicher-SOC
- `start_up` - Start-Ereignisse
- `shut_down` - Stopp-Ereignisse

PyPSA behandelt dies automatisch über den MultiIndex `(scenario, name)`.

## Troubleshooting

### Problem: "Heat pump type not found"
**Lösung:** Überprüfen Sie, ob `HP_TYPE` exakt mit einem Spaltennamen in der Excel-Datei übereinstimmt.

### Problem: "NaN values in data"
**Lösung:** Das Skript interpoliert automatisch. Prüfen Sie die Excel-Dateien auf leere Zeilen.

### Problem: Solver konvergiert nicht
**Lösungen:**
- Erhöhen Sie `MIP_GAP` (z.B. auf 0.1 = 10%)
- Erhöhen Sie `TIME_LIMIT`
- Reduzieren Sie `HOURS_TO_SIMULATE` für Tests
- Lockern Sie Constraints (z.B. `HP_MIN_UPTIME`)

### Problem: "Backup boiler used"
**Interpretation:** Die WP-Kapazität oder Speichergröße reicht nicht aus.
**Lösungen:**
- Erhöhen Sie `HP_FIXED_CAPACITY_MW`
- Erhöhen Sie `e_nom_max` (größerer Speicher erlaubt)
- Akzeptieren Sie geringe Backup-Nutzung als OK

### Problem: Optimierung zu langsam
**Lösungen:**
- Reduzieren Sie `HOURS_TO_SIMULATE` (z.B. 168 statt 8760)
- Verwenden Sie weniger Szenarien (z.B. nur 'medium')
- Erhöhen Sie `MIP_GAP`
- Setzen Sie `committable=False` für Tests

## Literatur & Referenzen

1. **Two-Stage Stochastic Programming:**
   - Birge, J. R., & Louveaux, F. (2011). Introduction to Stochastic Programming.
   
2. **Heat Pump COP Modeling:**
   - IEA Heat Pump Centre (2023). Heat Pump Performance Data.
   
3. **Thermal Energy Storage:**
   - Dincer, I., & Rosen, M. A. (2021). Thermal Energy Storage Systems and Applications.

4. **PyPSA Documentation:**
   - https://pypsa.readthedocs.io/
   - Siehe insbesondere: Optimization with Uncertainty, Multi-Investment

## Kontakt & Support

Bei Fragen oder Problemen:
1. Prüfen Sie zuerst diese README
2. Konsultieren Sie PyPSA Dokumentation
3. Erstellen Sie ein Issue auf GitHub

## Lizenz

Dieses Beispiel ist Teil von PyPSA und unterliegt der MIT-Lizenz.

---

**Erstellt:** Oktober 2025  
**PyPSA Version:** 1.0.1+  
**Autor:** GitHub Copilot & PyPSA Community
