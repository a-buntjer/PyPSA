# CHP-Constraints in district_heating_system.py angepasst

## ✅ Durchgeführte Änderungen

Die CHP-Constraints in `district_heating_system.py` wurden entsprechend den Änderungen in `committable_extendable_chp1.py` angepasst.

## 📐 Änderungen im Detail

### Vorher (flexible Constraints)

```python
# Nominal proportionality
model.add_constraints(
    gen_eff * CHP_QP_RATIO * gen_p_nom - boiler_eff * boiler_p_nom == 0,
    name=f"chp-capacity-proportionality-{gen_name}",
)

# Coupling constraints mit Bandbreite
RHO_LOW = CHP_QP_RATIO * (1.0 - CHP_COUPLING_BAND)
RHO_HIGH = CHP_QP_RATIO * (1.0 + CHP_COUPLING_BAND)

model.add_constraints(
    heat_output - RHO_LOW * electric_output >= 0,
    name=f"chp-lower-coupling-{gen_name}",
)

model.add_constraints(
    heat_output
    - RHO_HIGH * electric_output
    - CHP_THERMAL_BIAS * (electric_output_nom - electric_output)
    <= 0,
    name=f"chp-upper-coupling-{gen_name}",
)
```

### Nachher (feste Constraints)

```python
# CONSTRAINT 1: Nominale Kapazitäts-Proportionalität
# Die nominalen Kapazitäten müssen im Verhältnis Q_nom/P_nom = CHP_QP_RATIO stehen
model.add_constraints(
    boiler_eff * boiler_p_nom - CHP_QP_RATIO * gen_eff * gen_p_nom == 0,
    name=f"chp-nominal-capacity-ratio-{gen_name}",
)

# CONSTRAINT 2: Festes Q/P-Verhältnis zu jedem Zeitpunkt
# Erzwingt: Q(t) = RHO * P(t) für alle Zeitpunkte (Teillast und Volllast)
model.add_constraints(
    heat_output - CHP_QP_RATIO * electric_output == 0,
    name=f"chp-fixed-power-ratio-{gen_name}",
)
```

## 🔄 Betroffene CHP-Anlagen

Die Constraints werden für alle CHP-Anlagen im System angewendet:

### Standort A:
- `chp_natural_gas` (Erdgas-KWK)
- `chp_biomethane` (Biomethan-KWK)
- `chp_biogas` (Biogas-KWK)

### Standort B:
- `chp_natural_gas` (Erdgas-KWK)
- `chp_biomethane` (Biomethan-KWK)
- `chp_biogas` (Biogas-KWK)

## 📊 Erwartete Ergebnisse

Für alle CHP-Anlagen gilt nun:

```
Q(t) / P(t) = CHP_QP_RATIO = 1.2632 (konstant)
```

Mit den Parametern:
- `CHP_ELECTRIC_EFF = 0.38` (38%)
- `CHP_THERMAL_EFF = 0.48` (48%)
- `CHP_QP_RATIO = 1.2632`

Dies bedeutet:
- **Volllast**: Q/P = 1.2632 ✓
- **Teillast**: Q/P = 1.2632 ✓
- **Aus**: Q = 0, P = 0 ✓

## ✅ Vorteile

1. **Mathematische Konsistenz**: Nominales und zeitabhängiges Q/P-Verhältnis sind identisch
2. **Einfachere Constraints**: Nur 2 Gleichheits-Constraints statt mehrerer Ungleichheits-Constraints
3. **Realistisches CHP-Verhalten**: Moderne CHP-Anlagen haben tatsächlich nahezu feste P/Q-Verhältnisse
4. **Keine Parameter-Konflikte**: `CHP_COUPLING_BAND` und `CHP_THERMAL_BIAS` werden nicht mehr benötigt

## 🔧 Beibehaltene Features

- **Status-Synchronisation**: Generator und Boiler müssen gemeinsam ein-/ausgeschaltet werden (bleibt erhalten)
- **Biogas-Limits**: Wöchentliche Mengenbeschränkung für Biogas (unverändert)
- **Alle anderen Constraints**: Bleiben unverändert

## 📝 Geänderte Dateien

- ✅ `district_heating_system.py` - CHP-Constraints aktualisiert
- ✅ `DISTRICT_HEATING_CHP_CONSTRAINTS.md` - Diese Dokumentation

## 🧪 Nächste Schritte

Um das System zu testen:

```bash
conda activate pypsa_test
cd examples/heat_networks
python district_heating_system.py
```

Dies wird die Optimierung mit den neuen festen CHP-Constraints durchführen.

## 📚 Verwandte Dateien

Die gleichen Änderungen wurden bereits in folgenden Dateien implementiert:
- `examples/commitable-and-extendable/committable_extendable_chp1.py`
- Dokumentation in `examples/commitable-and-extendable/README_CONSTRAINTS.md`

---

**Datum**: 1. Oktober 2025  
**Status**: ✅ ERFOLGREICH ABGESCHLOSSEN
