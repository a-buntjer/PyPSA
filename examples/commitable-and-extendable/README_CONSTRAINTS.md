# CHP Constraints - Änderungen Zusammenfassung

## ✅ Durchgeführte Änderungen

Die CHP-Constraints in `committable_extendable_chp1.py` wurden erfolgreich umgearbeitet.

### Hauptänderung

**ALT**: Flexible Bandbreite für Q/P-Verhältnis (±15% + Teillast-Bias)
**NEU**: Festes Q/P-Verhältnis für Teillast und Volllast

## 📐 Neue Constraints

### CONSTRAINT 1: Nominale Kapazitäts-Proportionalität
```python
model.add_constraints(
    boiler_eff * boiler_p_nom - BCHP_QP_RATIO * generator_eff * generator_p_nom == 0,
    name="chp-nominal-capacity-ratio",
)
```

**Bedeutung**: Die nominalen Kapazitäten müssen im Verhältnis Q_nom/P_nom = 1.2632 stehen

### CONSTRAINT 2: Zeitabhängiges Q/P-Verhältnis
```python
model.add_constraints(
    heat_output - BCHP_QP_RATIO * electric_output == 0,
    name="chp-fixed-power-ratio",
)
```

**Bedeutung**: Zu jedem Zeitpunkt t gilt: Q(t)/P(t) = 1.2632

## 🔢 Mathematische Verifikation

Mit den Parametern:
- `BCHP_ELECTRIC_EFF = 0.38` (38%)
- `BCHP_THERMAL_EFF = 0.48` (48%)
- `BCHP_QP_RATIO = 1.2632`

Ergibt sich:
- **Volllast**: Q/P = 1.2632 ✓
- **Teillast 75%**: Q/P = 1.2632 ✓
- **Teillast 50%**: Q/P = 1.2632 ✓
- **Teillast 40%** (Mindestlast): Q/P = 1.2632 ✓

Die Brennstoff-Input-Verhältnisse sind:
```
boiler_p_nom = 1.0000 * gen_p_nom
boiler_p(t) = 1.0000 * gen_p(t)
```

Dies bedeutet: Generator und Boiler benötigen **exakt gleich viel Brennstoff-Input** zu jedem Zeitpunkt.

## 📊 Vergleich Alt vs. Neu

| Aspekt | ALT | NEU |
|--------|-----|-----|
| Q/P in Volllast | 1.08 - 1.46 | 1.2632 (fest) |
| Q/P in Teillast | 1.08 - 1.76 | 1.2632 (fest) |
| Anzahl Constraints | 3+ | 2 |
| Parameter | BCHP_COUPLING_BAND, BCHP_THERMAL_BIAS | Keine zusätzlichen |
| Mathematische Konsistenz | Potenzielle Konflikte | Konsistent |

## 🧪 Tests

### Verifikationsskript (ohne PyPSA)
```bash
python verify_constraints.py
```
Prüft die mathematische Korrektheit der Constraints.

### Vollständiger Test (mit PyPSA & Optimierung)
```bash
python test_fixed_ratio.py
```
Führt die vollständige Optimierung durch und prüft:
- Ob Q/P-Verhältnis konstant ist
- Ob es dem erwarteten Wert entspricht
- Ob nominale Kapazitäten korrekt sind

### Hauptskript
```bash
python committable_extendable_chp1.py
```
Führt die vollständige Optimierung durch und erstellt:
- `committable_extendable_chp1.nc` (Ergebnisse)
- `committable_extendable_chp1_generator_dispatch.png` (Plot)
- `committable_extendable_chp1_heat_supply.png` (Plot)

## 📝 Geänderte Dateien

1. **committable_extendable_chp1.py** 
   - Funktion `add_chp_coupling_constraints()` umgeschrieben
   - Docstring aktualisiert
   
2. **Neue Dateien**:
   - `test_fixed_ratio.py` - Umfassender Test mit PyPSA
   - `verify_constraints.py` - Mathematische Verifikation
   - `AENDERUNGEN_CONSTRAINTS.md` - Detaillierte Dokumentation
   - `README_CONSTRAINTS.md` - Diese Zusammenfassung
   - `update_constraints.py` - Hilfsskript für Änderung
   - `update_constraints2.py` - Verbessertes Hilfsskript

## 🎯 Erwartete Ergebnisse

Nach der Optimierung sollte die Analyse zeigen:

```
Q/P-Verhältnis im Betrieb:
  Minimum:  1.263158
  Maximum:  1.263158
  Mittel:   1.263158
  Std.-Abw: 0.000000

✓✓✓ ERFOLG: Q/P-Verhältnis ist KONSTANT!
```

## ⚠️ Wichtige Hinweise

1. **Keine Flexibilität mehr**: Das BHKW hat kein flexibles Q/P-Verhältnis mehr
2. **Strikte Kopplung**: Elektrische und thermische Leistung sind fest gekoppelt
3. **Realistisch für moderne BHKW**: Entspricht dem Verhalten moderner Anlagen

## 🔄 Nächste Schritte

1. Führe `verify_constraints.py` aus → ✅ Erfolgreich
2. Führe `python committable_extendable_chp1.py` aus (erfordert funktionierende PyPSA-Umgebung)
3. Falls Probleme: Prüfe Solver-Installation (HiGHS, Gurobi, etc.)
4. Analysiere Ergebnisse mit den bestehenden Analyse-Skripten

## 📧 Fragen?

Die Änderungen sind dokumentiert in:
- `AENDERUNGEN_CONSTRAINTS.md` (detailliert)
- Diesem README (Zusammenfassung)
- Code-Kommentare in `committable_extendable_chp1.py`
