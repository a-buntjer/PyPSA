# Zusammenfassung: Capital Cost Berechnung mit variabler Frequenz

## Implementierte Änderungen

### 1. Erweiterte `scale_capital_cost()` Funktion

**Neu:** Berücksichtigt die Snapshot-Frequenz (Duration in Stunden)

```python
def scale_capital_cost(
    capital_cost_annual: float, 
    snapshot_duration_hours: float,  # NEU!
    n_snapshots: int, 
    hours_per_year: int = 8760
) -> float:
    total_hours = n_snapshots * snapshot_duration_hours
    return capital_cost_annual * (total_hours / hours_per_year)
```

**Unterstützte Frequenzen:**
- ✅ Stündlich (1.0 h)
- ✅ Viertelstündlich (0.25 h / 15 min)
- ✅ 3-Stunden (3.0 h)
- ✅ Beliebige andere Frequenzen

### 2. Zwei separate Hilfsfunktionen

#### A) `capex_to_capital_cost()` - Für Investitionen

**Anwendung:** Anlagen, Geräte, Infrastruktur

```python
def capex_to_capital_cost(investment_cost_per_mw: float) -> float:
    """MIT Annuitätsberechnung + Zeitskalierung"""
    annual_cost = investment_cost_per_mw * annuity_factor  # Schritt 1
    return scale_capital_cost(annual_cost, snapshot_duration_hours, n_snapshots)  # Schritt 2
```

**Verwendet für:**
- Wärmepumpen (800.000 EUR/MW)
- Elektrokessel (200.000 EUR/MW)
- BHKW (600.000-750.000 EUR/MW)
- Gaskessel (250.000 EUR/MW)
- Wärmeleitungen (100.000-150.000 EUR/MW)
- Wärmespeicher (40.000 EUR/MWh)

#### B) `annual_to_capital_cost()` - Für jährliche Kosten

**Anwendung:** Netzentgelte (bereits jährlich)

```python
def annual_to_capital_cost(annual_cost_per_mw: float) -> float:
    """NUR Zeitskalierung (KEINE Annuität!)"""
    return scale_capital_cost(annual_cost_per_mw, snapshot_duration_hours, n_snapshots)
```

**Verwendet für:**
- Stromnetzentgelt (115,61 EUR/kW/Jahr = 115.610 EUR/MW/Jahr)
- Gasnetzentgelt (24,79 EUR/kW/Jahr = 24.790 EUR/MW/Jahr)

### 3. Automatische Frequenzerkennung

Im `build_network()`:

```python
# Bestimme Snapshot-Frequenz automatisch
if n_snapshots > 1:
    snapshot_freq = pd.Timedelta(SNAPSHOTS[1] - SNAPSHOTS[0])
    snapshot_duration_hours = snapshot_freq.total_seconds() / 3600.0
else:
    snapshot_duration_hours = 1.0  # Default
```

### 4. Verbesserte Ausgabe

```
Time resolution:
  Snapshot frequency: 1.00 hours (60 minutes)
  Number of snapshots: 168
  Total simulation time: 168.0 hours (7.0 days)

Economic parameters:
  Interest rate: 5.0%
  Lifetime: 20 years
  Annuity factor: 0.080243
  Time scale factor: 0.019178 (168.0/8760 hours)
  Equipment investment factor (annuity × time): 0.001539
  Grid charges factor (time only): 0.019178
```

## Validierung

### Test mit verschiedenen Frequenzen (7 Tage):

| Frequenz | Duration | Snapshots | Total Hours | WP capital_cost | Grid capital_cost |
|----------|----------|-----------|-------------|-----------------|-------------------|
| 1h | 1.0 h | 168 | 168 | 1231.12 EUR/MW | 2217.18 EUR/MW |
| 15min | 0.25 h | 672 | 168 | 1231.12 EUR/MW | 2217.18 EUR/MW |
| 3h | 3.0 h | 56 | 168 | 1231.12 EUR/MW | 2217.18 EUR/MW |

**✅ Ergebnis:** Identische Werte bei allen Frequenzen!

### Jahressimulation:

| Parameter | Wert |
|-----------|------|
| Wärmepumpe investment | 800.000 EUR/MW |
| Annualisiert | 64.194 EUR/MW/Jahr |
| Grid charge | 115.610 EUR/MW/Jahr |
| **→ Bei Jahressimulation** | |
| WP capital_cost | 64.194 EUR/MW |
| Grid capital_cost | 115.610 EUR/MW |

## Code-Änderungen im Detail

### Grid Connections (Zeilen ~678-714)

**Vorher:**
```python
capital_cost=capex_to_capital_cost(GRID_CHARGE_ELECTRIC_CAPACITY)
```

**Nachher:**
```python
capital_cost=annual_to_capital_cost(GRID_CHARGE_ELECTRIC_CAPACITY)
```

### Alle anderen Komponenten

Verwenden weiterhin `capex_to_capital_cost()`:
```python
capital_cost=capex_to_capital_cost(800000)  # Wärmepumpe
capital_cost=capex_to_capital_cost(600000)  # BHKW
# etc.
```

## Vorteile

1. ✅ **Korrekte Behandlung verschiedener Kostenarten**
   - Investitionen: Mit Annuität
   - Jährliche Kosten: Nur Zeitskalierung

2. ✅ **Frequenzunabhängigkeit**
   - Gleiche Ergebnisse bei 1h, 15min, 3h Auflösung
   - Automatische Erkennung der Frequenz

3. ✅ **Klarheit und Transparenz**
   - Zwei separate Funktionen mit klaren Namen
   - Ausführliche Dokumentation
   - Testskript zur Verifikation

4. ✅ **Flexibilität**
   - Unterstützt beliebige Snapshot-Frequenzen
   - Einfache Anpassung der Parameter (Zinssatz, Lebensdauer)

## Dateien

1. **district_heating_system.py** - Hauptskript (modifiziert)
2. **CAPITAL_COST_METHODOLOGY.md** - Ausführliche Dokumentation
3. **test_capital_cost_frequencies.py** - Testskript
4. **CHANGES_SUMMARY.md** - Diese Datei

---

**Datum:** 2. Oktober 2025  
**Status:** Implementiert und getestet ✅
