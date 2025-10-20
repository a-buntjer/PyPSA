# Fix-Vorschlag: Committable + Stochastic Kompatibilität

## Problem

Status-Variablen für committable Units bekommen fälschlicherweise eine `scenario`-Dimension, 
obwohl sie (wie Investitionsvariablen) szenariounabhängige **erste-Stufe-Entscheidungen** sein sollten.

## Ursache

**In `pypsa/optimization/variables.py`:**

### Investitionsvariablen (FUNKTIONIERT ✅)

```python
def define_nominal_variables(n: Network, c_name: str, attr: str) -> None:
    """Initialize variables for nominal capacities."""
    c = n.components[c_name]
    ext_i = c.extendables.difference(c.inactive_assets)
    if ext_i.empty:
        return
    
    # ✅ Entfernt explizit scenario-Dimension!
    if isinstance(ext_i, pd.MultiIndex):
        ext_i = ext_i.unique(level="name")
    
    n.model.add_variables(coords=[ext_i], name=f"{c.name}-{attr}")
```

**Resultat:** `Generator-p_nom (name)` - **OHNE** scenario-Dimension ✅

---

### Status-Variablen (BUG ❌)

```python
def define_status_variables(n: Network, sns: Sequence, c_name: str, ...) -> None:
    """Initialize variables for unit commitment status."""
    c = n.components[c_name]
    com_i = c.committables.difference(c.inactive_assets)
    
    active = c.da.active.sel(name=com_i, snapshot=sns)
    
    # ❌ Übernimmt ALLE Dimensionen von active inkl. scenario!
    coords = active.coords
    
    n.model.add_variables(
        coords=coords,
        name=f"{c.name}-status",
        binary=True
    )
```

**Resultat:** `Generator-status (scenario, snapshot, name)` - **MIT** scenario-Dimension ❌

## Lösung

### Option A: Minimaler Fix (Quick & Dirty)

**In `define_status_variables()` nach Zeile 70:**

```python
def define_status_variables(n: Network, sns: Sequence, c_name: str, ...) -> None:
    c = n.components[c_name]
    com_i = c.committables.difference(c.inactive_assets)
    
    if com_i.empty:
        return
    
    # ✅ NEU: Entferne scenario-Dimension (analog zu Investitionen)
    if isinstance(com_i, pd.MultiIndex):
        com_i = com_i.unique(level="name")
    
    # ✅ NEU: Baue coords explizit ohne scenario
    coords = [sns, com_i]
    
    active = c.da.active.sel(name=com_i, snapshot=sns)
    is_binary = not is_linearized
    kwargs = {"upper": 1, "lower": 0} if not is_binary else {}
    
    n.model.add_variables(
        coords=coords,  # ← Statt active.coords
        name=f"{c.name}-status",
        mask=active,
        binary=is_binary,
        **kwargs
    )
```

**Änderungen:**
1. Füge `if isinstance(com_i, pd.MultiIndex)` Check hinzu (wie bei Investitionen)
2. Baue `coords = [sns, com_i]` explizit (ohne scenario)
3. `mask=active` bleibt (Linopy macht Broadcasting automatisch)

---

### Option B: Sauberer Fix mit Broadcasting-Logik

**Falls `mask=active` Probleme macht (active hat scenario, coords nicht):**

```python
def define_status_variables(n: Network, sns: Sequence, c_name: str, ...) -> None:
    c = n.components[c_name]
    com_i = c.committables.difference(c.inactive_assets)
    
    if com_i.empty:
        return
    
    # Entferne scenario-Dimension
    if isinstance(com_i, pd.MultiIndex):
        com_i = com_i.unique(level="name")
    
    # Baue coords ohne scenario
    coords = [sns, com_i]
    
    # Berechne mask ohne scenario (aggregiere über alle Szenarien)
    active = c.da.active.sel(name=com_i, snapshot=sns)
    if "scenario" in active.dims:
        # Unit ist aktiv wenn in IRGENDEINEM Szenario aktiv
        mask = active.any(dim="scenario")
    else:
        mask = active
    
    is_binary = not is_linearized
    kwargs = {"upper": 1, "lower": 0} if not is_binary else {}
    
    n.model.add_variables(
        coords=coords,
        name=f"{c.name}-status",
        mask=mask,  # Jetzt ohne scenario-Dimension
        binary=is_binary,
        **kwargs
    )
```

**Vorteile:**
- Explizite Behandlung der scenario-Dimension
- Konservativ: Unit ist aktiv wenn in EINEM Szenario aktiv
- Keine Broadcasting-Probleme

---

### Option C: Vollständiger Fix (mit start_up/shut_down)

**Gleiche Logik auch für `define_start_up_variables()` und `define_shut_down_variables()`:**

```python
def define_start_up_variables(n: Network, sns: Sequence, c_name: str, ...) -> None:
    c = n.components[c_name]
    com_i = c.committables.difference(c.inactive_assets)
    
    if com_i.empty:
        return
    
    # ✅ Entferne scenario-Dimension
    if isinstance(com_i, pd.MultiIndex):
        com_i = com_i.unique(level="name")
    
    # ✅ Baue coords explizit
    coords = [sns, com_i]
    
    active = c.da.active.sel(name=com_i, snapshot=sns)
    if "scenario" in active.dims:
        mask = active.any(dim="scenario")
    else:
        mask = active
    
    # Rest bleibt gleich...
```

## Auswirkungen auf Constraints

**In `constraints.py`:** Die meisten Constraints müssen **nicht** geändert werden!

**Warum?** Linopy macht automatisch Broadcasting:

```python
# Constraint (vorher):
# status[scenario, snapshot, name] ≥ 0

# Constraint (nachher mit Broadcasting):
# status[snapshot, name] ≥ 0  (gilt für alle Szenarien)

# Bei Kopplung mit Leistung:
# p[scenario, snapshot, name] ≤ P_max * status[snapshot, name]
# Broadcasting: status wird über scenarios ausgebreitet
```

**Was MUSS geändert werden:**

### 1. Status-Transition Constraints (Zeile 467-488)

**Problem:** `initially_up` muss szenariounabhängig sein.

```python
# VORHER (mit multi-dimensional handling):
if initially_up.ndim > 1:
    initially_up_mask = initially_up.any(dim=initially_up.dims[0])
    initially_up_indices = com_i[initially_up_mask.values]
else:
    initially_up_indices = com_i[initially_up.values]

# NACHHER (einfacher, da status keine scenario-Dimension hat):
initially_up_indices = com_i[initially_up.values]
```

### 2. Min Up/Down Time Constraints (Zeile 495-560)

**Problem:** Ähnlich - MultiIndex-Handling nicht mehr nötig.

```python
# VORHER:
if min_up_time_set.ndim > 1:
    min_up_time_mask = min_up_time_set.astype(bool).any(dim=min_up_time_set.dims[0])
    min_up_time_i = com_i[min_up_time_mask.values]
else:
    min_up_time_i = com_i[min_up_time_set.astype(bool)]

# NACHHER (einfacher):
min_up_time_i = com_i[min_up_time_set.astype(bool)]
```

### 3. Constraint-Anwendung mit Broadcasting

**Die meisten Constraints funktionieren automatisch:**

```python
# Big-M Constraint:
lhs_upper = (1, p), (-nominal_capacity, status)
# p hat Dimension (scenario, snapshot, name)
# status hat Dimension (snapshot, name)
# Linopy broadcasted automatisch über scenario! ✅

n.model.add_constraints(lhs_upper, "<=", 0, ...)
```

## Testing

### Test 1: Variablen-Dimensionen prüfen

```python
n = pypsa.Network()
n.set_snapshots(range(24))
n.add("Bus", "bus")
n.add("Generator", "gen", bus="bus", p_nom_extendable=True, committable=True)

# Mit Szenarien
n.set_scenarios({"low": 0.5, "high": 0.5})

# Optimierungsmodell erstellen
n.optimize.create_model()

# TESTEN:
status = n.model["Generator-status"]
p_nom = n.model["Generator-p_nom"]
p = n.model["Generator-p"]

print(f"p_nom dimensions: {p_nom.dims}")      # Sollte: ('name',)
print(f"status dimensions: {status.dims}")    # Sollte: ('snapshot', 'name')
print(f"p dimensions: {p.dims}")              # Sollte: ('scenario', 'snapshot', 'name')

# ✅ ERFOLG wenn status KEINE scenario-Dimension hat!
assert "scenario" not in status.dims
assert "scenario" not in p_nom.dims
assert "scenario" in p.dims
```

### Test 2: Constraint-Broadcasting prüfen

```python
# Nach Optimierung:
n.optimize()

# Status sollte für alle Szenarien gleich sein
status_var = n.model["Generator-status"]
print(f"Status shape: {status_var.solution.shape}")
# Sollte: (snapshots, generators) - OHNE scenario

# Aber p ist szenarioabhängig
p_var = n.model["Generator-p"]
print(f"p shape: {p_var.solution.shape}")
# Sollte: (scenarios, snapshots, generators)
```

### Test 3: Mit quick_test.py

```python
# Unser bestehender Test sollte funktionieren:
python quick_test.py

# Erwartung: KEIN KeyError mehr!
# Status: ok
# Objective: <some value>
```

## Geschätzter Aufwand

| Task | Zeit | Schwierigkeit |
|------|------|---------------|
| Fix in `define_status_variables()` | 10 min | Leicht |
| Fix in `define_start_up_variables()` | 5 min | Leicht |
| Fix in `define_shut_down_variables()` | 5 min | Leicht |
| Entfernen von MultiIndex-Handling in `constraints.py` | 20 min | Mittel |
| Testing mit `quick_test.py` | 10 min | Leicht |
| Testing mit `test_committable_stochastic.py` | 15 min | Mittel |
| Testing mit `stochastic_multihorizon_chp.py` (committable=True) | 30 min | Schwer |
| **Gesamt** | **~1.5 Stunden** | **Mittel** |

## Vorteile des Fixes

1. ✅ **Mathematisch korrekt:** Status in Stufe 1 (wie Investitionen)
2. ✅ **Konsistent:** Gleiche Behandlung wie `p_nom`, `e_nom`, `s_nom`
3. ✅ **Performant:** Weniger binäre Variablen (Faktor 1/S)
4. ✅ **Dokumentiert:** Passt zur offiziellen PyPSA-Dokumentation
5. ✅ **Einfach:** Minimaler Code-Change, kein Refactoring
6. ✅ **Rückwärtskompatibel:** Ändert nichts an nicht-stochastischen Netzen

## Risiken

| Risiko | Wahrscheinlichkeit | Mitigation |
|--------|-------------------|------------|
| Broadcasting-Fehler in Constraints | Niedrig | Linopy handhabt das automatisch |
| Bestehende Tests brechen | Niedrig | Keine Tests für committable+stochastic existieren |
| Unerwartete Edge-Cases | Mittel | Umfangreiches Testing mit verschiedenen Kombinationen |
| mask-Dimensionen passen nicht | Mittel | Option B verwenden (explizites any()) |

## Empfehlung

**Start mit Option A (Minimaler Fix):**
1. Implementiere in `define_status_variables()`
2. Teste mit `quick_test.py`
3. Falls `mask`-Fehler → Option B
4. Erweitere auf `start_up` und `shut_down`
5. Vereinfache `constraints.py` (MultiIndex-Handling entfernen)
6. Vollständiges Testing

**Falls Option A funktioniert:** Aufwand ca. 1-2 Stunden total.
**Falls komplexere Anpassungen nötig:** Aufwand ca. 4-6 Stunden.

## Next Steps

1. [ ] Implementiere Fix in `variables.py` (Option A)
2. [ ] Teste mit `quick_test.py`
3. [ ] Falls erfolgreich: Erweitere auf `start_up`/`shut_down`
4. [ ] Teste mit `test_committable_stochastic.py` (alle 4 Tests)
5. [ ] Optional: Vereinfache `constraints.py`
6. [ ] Aktiviere `committable=True` in `stochastic_multihorizon_chp.py`
7. [ ] Dokumentation aktualisieren
8. [ ] Pull Request zu PyPSA upstream?
