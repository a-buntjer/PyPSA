# Bug Fix Progress: Committable + Stochastic in PyPSA

**Updated**: ✅ **VOLLSTÄNDIG BEHOBEN** (October 20, 2025)

---

## ✅ FINAL UPDATE: BUG ERFOLGREICH BEHOBEN!

### Lösung Implementiert

Der Fehler wurde durch Behandlung von Status-Variablen als **erste-Stufe-Entscheidungen** (szenariounabhängig) behoben, 
konsistent mit Investitionsvariablen (`p_nom`, `e_nom`, `s_nom`).

### Test-Ergebnisse

| Feature Combination | Status vor Fix | Status nach Fix |
|---------------------|----------------|-----------------|
| Committable + Multi-investment | ✅ WORKS | ✅ WORKS |
| Stochastic + Multi-investment | ✅ WORKS | ✅ WORKS |
| **Committable + Stochastic** | ❌ FAILS | ✅ **WORKS** |
| Committable + Stochastic + Multi-investment | ❌ FAILS | ✅ **WORKS** |

**Alle Kombinationen funktionieren jetzt!** 🎉

### Implementierte Änderungen

**1. `pypsa/optimization/variables.py`:**
- Entfernt scenario-Dimension aus `com_i` Index in allen drei Funktionen
- Status-Variablen haben jetzt Koordinaten `(snapshot, name)` statt `(scenario, snapshot, name)`
- Aggregiert `active` mask über Szenarien (konservativ: aktiv wenn in EINEM Szenario aktiv)

**2. `pypsa/optimization/constraints.py`:**
- Aggregiert `active` mask zu Beginn
- Aggregiert Parameter (min_up_time, min_down_time, up_time_before, down_time_before) mit `max()`
- Vereinfacht Code durch Entfernen von MultiIndex-Spezialbehandlung

### Mathematische Korrektheit

Siehe `MATHEMATICAL_ANALYSIS.md` für vollständige Analyse:
- Problem bleibt **gemischt-ganzzahlig linear (MILP)**
- Folgt Standard zwei-stufiger stochastischer Programmierung (Takriti et al. 1996)
- Unit Commitment vor Szenario-Realisierung (realistisch für day-ahead)

### Commit

```
commit f1242a0f
Fix committable + stochastic compatibility

BREAKING CHANGE: Status variables for committable units are now first-stage decisions
```

---

## Original Problem Description

**Note**: PyPSA v1.0.1 fixed the GlobalConstraints warning issue but the committable+stochastic bug remained until this fix.

## Root Cause

When `network.set_scenarios()` is called, all component indices become `MultiIndex` with structure `(scenario, name)`. However, the committable constraint generation code in `pypsa/optimization/constraints.py` was written assuming regular `Index` objects.

### Specific Issues Found

1. **IndexError (FIXED ✅)**:
   ```python
   # Line 469: initially_up.values is 2D (scenarios × generators)
   initially_up_indices = com_i[initially_up.values]  
   ```
   - Problem: Tries to use 2D array as 1D boolean mask
   - Fix: Check `ndim` and aggregate across scenarios with `.any()`

2. **ValueError in .item() (FIXED ✅)**:
   ```python
   # Lines 511, 541: With scenarios, these return arrays not scalars
   up_time_value = min_up_time_set.sel(name=g).item()
   down_time_value = min_down_time_set.sel(name=g).item()
   ```
   - Problem: `.item()` fails when result has multiple values (one per scenario)
   - Fix: Take `.max()` across scenarios before `.item()`

3. **KeyError in .loc[] indexing (NOT YET FIXED ❌)**:
   ```python
   # Line 526: active.loc[sns[1:], min_up_time_i]
   ```
   - Problem: `min_up_time_i` contains tuples like `('scenario_A', 'gen1')` but `active` expects different indexing
   - Cause: The entire constraint creation uses `.loc[]` which doesn't work well with MultiIndex
   - Solution needed: Refactor to use `.sel()` when scenarios are present

## Changes Made (Branch: `fix-committable-stochastic-bug`)

### File: `pypsa/optimization/constraints.py`

1. **Lines 467-477**: Handle multi-dimensional `initially_up`
   ```python
   if initially_up.ndim > 1:
       initially_up_mask = initially_up.any(dim=initially_up.dims[0])
       initially_up_indices = com_i[initially_up_mask.values]
   else:
       initially_up_indices = com_i[initially_up.values]
   ```

2. **Lines 495-502**: Handle multi-dimensional `min_up_time_set`
   ```python
   if min_up_time_set.ndim > 1:
       min_up_time_mask = min_up_time_set.astype(bool).any(dim=min_up_time_set.dims[0])
       min_up_time_i = com_i[min_up_time_mask.values]
   else:
       min_up_time_i = com_i[min_up_time_set.astype(bool)]
   ```

3. **Lines 506-514**: Handle multi-dimensional time values in min_up_time
   ```python
   up_time_data = min_up_time_set.sel(name=g)
   if up_time_data.ndim > 0:
       up_time_value = int(up_time_data.max().item())
   else:
       up_time_value = up_time_data.item()
   ```

4. **Lines 529-548**: Similar fixes for `min_down_time`

## Current Status

### ✅ Fixed
- `IndexError: too many indices for array` - RESOLVED
- `ValueError: can only convert an array of size 1 to a Python scalar` - RESOLVED

### ❌ Remaining Issues
- `KeyError: "not all values found in index 'scenario'"` in line 526
- Many other `.loc[]` operations likely have similar issues
- Needs comprehensive refactoring of all constraint creation to support MultiIndex

## Next Steps

### Short-term Fix (Recommended)
Add proper validation and a clear error message:
```python
def define_operational_constraints_for_committables(n, sns, c):
    if hasattr(n, 'scenarios') and len(n.scenarios) > 0:
        raise NotImplementedError(
            "Committable components with stochastic scenarios are not yet "
            "supported in PyPSA. Please use either committable=True OR "
            "stochastic scenarios, but not both simultaneously."
        )
    # ... rest of function
```

### Long-term Fix (Proper Solution)
Refactor the entire `define_operational_constraints_for_committables()` function to:
1. Detect if scenarios are present
2. Use `.sel()` instead of `.loc[]` for MultiIndex-aware selection
3. Properly aggregate constraints across scenarios
4. Test thoroughly with all combinations

## Testing

Test file: `examples/commitable-and-extendable/test_committable_stochastic.py`

Run: `mamba run -n energy_opt python test_committable_stochastic.py`

Quick test: `examples/commitable-and-extendable/quick_test.py`

## Conclusion

The bug is **deeper than initially expected**. It's not just a few index operations - the entire committable constraint generation architecture assumes single-scenario networks. A complete fix would require significant refactoring.

**Recommendation**: For now, document this as a known limitation and add a clear error message. The workaround (setting `committable=False` when using scenarios) is acceptable until a proper refactoring can be done.

## Related Files

- Main bug location: `pypsa/optimization/constraints.py` (function `define_operational_constraints_for_committables`)
- Test cases: `examples/commitable-and-extendable/test_committable_stochastic.py`
- Working example without committable: `examples/commitable-and-extendable/stochastic_multihorizon_chp.py`
