# Änderungen an den CHP-Constraints

## Zusammenfassung

Die CHP-Constraints in `committable_extendable_chp1.py` wurden umgearbeitet, um ein **festes Verhältnis** zwischen elektrischer und thermischer Leistung zu erzwingen - sowohl in Teillast als auch in Volllast.

## Alte Implementation (flexible Constraints)

Die alte Version verwendete:
- **Flexible Bandbreite**: `RHO_LOW` bis `RHO_HIGH` (± BCHP_COUPLING_BAND)
- **Teillast-Bias**: Zusätzliche thermische Flexibilität in Teillast
- **Status-Synchronisation**: Kommentiert aus (war problematisch)

```python
# Alte Constraints:
RHO_LOW = BCHP_QP_RATIO * (1.0 - BCHP_COUPLING_BAND)
RHO_HIGH = BCHP_QP_RATIO * (1.0 + BCHP_COUPLING_BAND)

# Untere Bandgrenze: Q >= RHO_LOW * P
model.add_constraints(
    heat_output - RHO_LOW * electric_output >= 0,
    name="bhkw-lower-coupling",
)

# Obere Bandgrenze: Q <= RHO_HIGH * P + BIAS * (P_nom - P)
model.add_constraints(
    heat_output
    - RHO_HIGH * electric_output
    - BCHP_THERMAL_BIAS * (electric_output_nom - electric_output)
    <= 0,
    name="bhkw-upper-coupling",
)
```

## Neue Implementation (feste Constraints)

Die neue Version erzwingt:
- **Festes Q/P-Verhältnis**: Exakt `BCHP_QP_RATIO` zu jedem Zeitpunkt
- **Keine Flexibilität**: Q(t) = RHO * P(t) für alle t
- **Einfachere Constraints**: Nur 2 statt 3+ Constraints

```python
# CONSTRAINT 1: Nominale Kapazitäts-Proportionalität
# Q_nom / P_nom = RHO
model.add_constraints(
    boiler_eff * boiler_p_nom - BCHP_QP_RATIO * generator_eff * generator_p_nom == 0,
    name="chp-nominal-capacity-ratio",
)

# CONSTRAINT 2: Festes Q/P-Verhältnis zu jedem Zeitpunkt
# Q(t) = RHO * P(t)
model.add_constraints(
    heat_output - BCHP_QP_RATIO * electric_output == 0,
    name="chp-fixed-power-ratio",
)
```

## Mathematische Bedeutung

### CONSTRAINT 1: Nominale Kapazitätsverhältnisse

Definiert das Verhältnis der nominalen (maximalen) Kapazitäten:

$$\frac{Q_{nom}}{P_{nom}} = \frac{\eta_{boiler} \cdot p_{nom,boiler}}{\eta_{gen} \cdot p_{nom,gen}} = \rho$$

Mit den aktuellen Parametern:
- `BCHP_ELECTRIC_EFF = 0.38` (ηgen)
- `BCHP_THERMAL_EFF = 0.48` (ηboiler)
- `BCHP_QP_RATIO = 1.2632` (ρ)

### CONSTRAINT 2: Zeitabhängige Leistungskopplung

Erzwingt dasselbe Verhältnis zu jedem Zeitpunkt t:

$$\frac{Q(t)}{P(t)} = \frac{\eta_{boiler} \cdot p_{boiler}(t)}{\eta_{gen} \cdot p_{gen}(t)} = \rho$$

Dies gilt für:
- **Volllast**: P(t) = Pnom, Q(t) = Qnom
- **Teillast**: P(t) < Pnom, Q(t) < Qnom
- **Aus**: P(t) = 0, Q(t) = 0

## Vorteile der neuen Constraints

1. **Mathematische Konsistenz**: 
   - Nominales Verhältnis und zeitabhängiges Verhältnis sind identisch
   - Keine Widersprüche zwischen Constraints

2. **Einfachheit**:
   - Nur 2 Gleichheits-Constraints (statt mehrerer Ungleichheits-Constraints)
   - Einfacher zu verstehen und debuggen

3. **Realistisches BHKW-Verhalten**:
   - Moderner BHKW haben tatsächlich nahezu feste P/Q-Verhältnisse
   - Thermodynamisch konsistent

4. **Keine Parameter-Konflikte**:
   - Keine `BCHP_COUPLING_BAND` mehr nötig
   - Keine `BCHP_THERMAL_BIAS` mehr nötig
   - Weniger Tuning-Parameter

## Erwartete Ergebnisse

Nach der Optimierung sollte gelten:

```python
# Für alle Stunden t mit BHKW-Betrieb:
Q(t) / P(t) ≈ BCHP_QP_RATIO (= 1.2632)

# Mit numerischer Toleranz (z.B. ±0.0001)
```

## Test-Anweisungen

Um die neuen Constraints zu testen:

```bash
# Aktiviere die Umgebung
conda activate pypsa_test

# Führe das Hauptskript aus
cd examples/commitable-and-extendable
python committable_extendable_chp1.py

# Oder führe das Testskript aus
python test_fixed_ratio.py
```

Das Testskript `test_fixed_ratio.py` überprüft:
1. Ob das Q/P-Verhältnis konstant ist
2. Ob es dem erwarteten Wert entspricht
3. Ob die nominalen Kapazitäten korrekt sind

## Dateien geändert

- `committable_extendable_chp1.py`: CHP-Constraints umgearbeitet
- `test_fixed_ratio.py`: Neues Testskript (erstellt)
- `update_constraints.py`: Hilfsskript für die Änderung (erstellt)
- `update_constraints2.py`: Verbessertes Hilfsskript (erstellt)
