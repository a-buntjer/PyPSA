# Capital Cost Methodology - District Heating System

## Übersicht

Das Skript `district_heating_system.py` verwendet eine differenzierte Methodik zur Berechnung der Kapitalkosten, die zwischen verschiedenen Kostenarten unterscheidet.

## 1. Zeitskalierung mit variabler Frequenz

### Snapshot-Frequenz
Die Zeitskalierung berücksichtigt die tatsächliche zeitliche Auflösung der Simulation:

```python
snapshot_duration_hours = (SNAPSHOTS[1] - SNAPSHOTS[0]).total_seconds() / 3600
total_hours = n_snapshots × snapshot_duration_hours
time_scale = total_hours / 8760
```

### Beispiele für verschiedene Frequenzen:

| Frequenz | Duration (h) | Snapshots (7 Tage) | Total Hours | Time Scale |
|----------|--------------|-------------------|-------------|------------|
| Stündlich | 1.0 | 168 | 168 | 0.0192 |
| 15-Minuten | 0.25 | 672 | 168 | 0.0192 |
| 3-Stunden | 3.0 | 56 | 168 | 0.0192 |
| Viertelstündlich | 0.25 | 8760×4 | 8760 | 1.0000 |

**Wichtig:** Die Gesamtstunden bleiben gleich, unabhängig von der Frequenz!

## 2. Zwei Arten von Kapitalkosten

### A) Investitionskosten für Anlagen (mit Annuität)

**Funktion:** `capex_to_capital_cost(investment_cost_per_mw)`

Für Neuinvestitionen in Anlagen (Wärmepumpen, BHKW, Kessel, etc.):

1. **Schritt 1 - Annuitätenberechnung:**
   ```
   annual_cost = investment_cost × annuity_factor
   annuity_factor = (i × (1+i)^n) / ((1+i)^n - 1)
   ```
   
   Bei i=5%, n=20 Jahre:
   ```
   annuity_factor = 0.080243
   ```

2. **Schritt 2 - Zeitskalierung:**
   ```
   capital_cost = annual_cost × (total_hours / 8760)
   ```

**Beispiel - Wärmepumpe (800.000 EUR/MW):**
```
Investition:        800.000 EUR/MW
Annualisiert:        64.194 EUR/MW/Jahr  (= 800.000 × 0.080243)
Für 7 Tage (168h):    1.231 EUR/MW       (= 64.194 × 168/8760)
```

### B) Jährliche Netzentgelte (nur Zeitskalierung)

**Funktion:** `annual_to_capital_cost(annual_cost_per_mw)`

Für bereits jährliche Kosten (Netzentgelte):

1. **Keine Annuität** - Werte sind bereits EUR/MW/Jahr
2. **Nur Zeitskalierung:**
   ```
   capital_cost = annual_cost × (total_hours / 8760)
   ```

**Beispiel - Stromnetzentgelt (115,61 EUR/kW/Jahr):**
```
Jährlich:           115.610 EUR/MW/Jahr
Für 7 Tage (168h):    2.217 EUR/MW       (= 115.610 × 168/8760)
```

## 3. Anwendung im Netzmodell

### Investitionskosten (mit Annuität):
- **Wärmepumpen**: 800.000 EUR/MW → `capex_to_capital_cost(800000)`
- **Elektrokessel**: 200.000 EUR/MW → `capex_to_capital_cost(200000)`
- **BHKW Erdgas**: 600.000 EUR/MW_el → `capex_to_capital_cost(600000)`
- **BHKW Biomethan**: 700.000 EUR/MW_el → `capex_to_capital_cost(700000)`
- **BHKW Biogas**: 750.000 EUR/MW_el → `capex_to_capital_cost(750000)`
- **Gaskessel**: 250.000 EUR/MW → `capex_to_capital_cost(250000)`
- **Wärmeleitungen**: 100.000-150.000 EUR/MW → `capex_to_capital_cost(...)`
- **Wärmespeicher**: 40.000 EUR/MWh → `capex_to_capital_cost(40000)`

### Jährliche Netzentgelte (nur Zeit):
- **Stromnetzentgelt**: 115,61 EUR/kW/Jahr → `annual_to_capital_cost(GRID_CHARGE_ELECTRIC_CAPACITY)`
- **Gasnetzentgelt**: 24,79 EUR/kW/Jahr → `annual_to_capital_cost(GRID_CHARGE_GAS_CAPACITY)`

## 4. Kostenvergleich

### Beispiel: Wärmepumpe vs. Stromnetzanschluss

**7 Tage Simulation (168 Stunden):**

| Komponente | Ursprungswert | Art | Faktor | PyPSA capital_cost |
|------------|---------------|-----|--------|-------------------|
| Wärmepumpe | 800.000 EUR/MW | Investition | 0.001539 | 1.231 EUR/MW |
| Netzanschluss | 115,61 EUR/kW/Jahr | Jährlich | 0.019178 | 2.217 EUR/MW |

**Jahressimulation (8760 Stunden):**

| Komponente | Ursprungswert | Art | Faktor | PyPSA capital_cost |
|------------|---------------|-----|--------|-------------------|
| Wärmepumpe | 800.000 EUR/MW | Investition | 0.080243 | 64.194 EUR/MW |
| Netzanschluss | 115,61 EUR/kW/Jahr | Jährlich | 1.000000 | 115.610 EUR/MW |

## 5. Validierung

Die Methodik stellt sicher, dass:

1. ✅ **Frequenzunabhängigkeit:** Gleiche Gesamtkosten bei 1h, 0.25h oder 3h Auflösung
2. ✅ **Korrekte Annuität:** Investitionskosten werden mit 5% Zins über 20 Jahre abgeschrieben
3. ✅ **Trennung der Kostenarten:** Netzentgelte (bereits jährlich) vs. Investitionen
4. ✅ **Zeitskalierung:** Kosten proportional zum Simulationszeitraum

## 6. Formeln - Zusammenfassung

```python
# Annuitätenfaktor (für Investitionen)
annuity_factor = (i × (1+i)^n) / ((1+i)^n - 1)
                = 0.080243  (bei i=5%, n=20 Jahre)

# Zeitskalierungsfaktor
total_hours = n_snapshots × snapshot_duration_hours
time_scale = total_hours / 8760

# Investitionskosten (Anlagen)
capital_cost_equipment = investment_cost × annuity_factor × time_scale

# Jährliche Kosten (Netzentgelte)
capital_cost_grid = annual_cost × time_scale
```

## 7. Code-Referenz

```python
# In build_network():

# Für Anlagen-Investitionen
capital_cost = capex_to_capital_cost(800000)  # Wärmepumpe

# Für jährliche Netzentgelte
capital_cost = annual_to_capital_cost(GRID_CHARGE_ELECTRIC_CAPACITY)
```

---

**Stand:** 2. Oktober 2025  
**Zinssatz:** 5,0%  
**Lebensdauer:** 20 Jahre  
**Annuitätenfaktor:** 0,080243
