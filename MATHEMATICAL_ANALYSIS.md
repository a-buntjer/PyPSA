# Mathematische Analyse: Committable + Stochastic in PyPSA

## Fragestellung
Ist die Kombination von **committable** (Unit Commitment mit binären Variablen) und **stochastic** (szenariobasierte Optimierung) überhaupt im Rahmen einer gemischt-ganzzahlig linearen Optimierung (MILP) lösbar, oder wird das Problem nichtlinear/quadratisch?

## 1. Mathematische Formulierung

### 1.1 Standard Unit Commitment (ohne Stochastik)

**Variablen:**
- $p_{i,t}$ ∈ ℝ⁺: Leistung der Einheit i zur Zeit t (kontinuierlich)
- $u_{i,t}$ ∈ {0,1}: Status der Einheit i zur Zeit t (binär)
- $v_{i,t}$ ∈ {0,1}: Start-up der Einheit i zur Zeit t (binär)
- $w_{i,t}$ ∈ {0,1}: Shut-down der Einheit i zur Zeit t (binär)

**Typische Constraints (linear):**
```
p_{i,t} ≤ P_max * u_{i,t}                    (Big-M Constraint)
p_{i,t} ≥ P_min * u_{i,t}                    (Minimum Leistung)
v_{i,t} - w_{i,t} = u_{i,t} - u_{i,t-1}      (Status-Transition)
Σ_{τ=t-T_up}^{t} v_{i,τ} ≤ u_{i,t}          (Minimum Up-Time)
Σ_{τ=t-T_down}^{t} w_{i,τ} ≤ 1 - u_{i,t}    (Minimum Down-Time)
```

**Problemtyp:** MILP (Mixed Integer Linear Programming)
- Lineare Zielfunktion
- Lineare Constraints
- Binäre und kontinuierliche Variablen
- ✅ **Lösbar mit Standard-Solvern (CBC, Gurobi, CPLEX)**

### 1.2 Stochastische Optimierung (zwei-stufig, ohne Committable)

**Szenarien:** s ∈ {1, ..., S} mit Wahrscheinlichkeiten π_s

**Variablen:**
- **Erste Stufe (vor Szenariorealisierung):**
  - $x$ ∈ ℝ: Investitionsentscheidungen (deterministisch, szenariounabhängig)
  
- **Zweite Stufe (nach Szenariorealisierung):**
  - $p_{i,t,s}$ ∈ ℝ⁺: Leistung in Szenario s (kontinuierlich)
  - $y_{i,t,s}$ ∈ ℝ: Rezirkulation in Szenario s (kontinuierlich)

**Zielfunktion:**
```
min  c^T x + Σ_s π_s * (c_p^T p_s + c_y^T y_s)
```

**Problemtyp:** LP (Linear Programming) - falls keine binären Variablen
- ✅ **Lösbar - Standardproblem in stochastischer Optimierung**

### 1.3 Committable + Stochastic: Zwei-stufiges MILP

Jetzt kombinieren wir beide Ansätze:

#### Variante A: Binäre Variablen in 1. Stufe (deterministisch)
**Entscheidungsstruktur:**
- **Erste Stufe:** $u_{i,t}$ ∈ {0,1} - Status ist **szenariounabhängig**
- **Zweite Stufe:** $p_{i,t,s}$ ∈ ℝ⁺ - Leistung ist **szenarioabhängig**

**Mathematische Formulierung:**
```
min  Σ_{i,t} (c_startup * v_{i,t} + c_shutdown * w_{i,t}) 
     + Σ_s π_s * Σ_{i,t} c_{marginal} * p_{i,t,s}

s.t.
  # Erste Stufe (szenariounabhängig):
  v_{i,t} - w_{i,t} = u_{i,t} - u_{i,t-1}           ∀i,t
  u_{i,t}, v_{i,t}, w_{i,t} ∈ {0,1}                  ∀i,t
  
  # Zweite Stufe (für jedes Szenario s):
  p_{i,t,s} ≤ P_max * u_{i,t}                        ∀i,t,s  (Kopplung!)
  p_{i,t,s} ≥ P_min * u_{i,t}                        ∀i,t,s
  Σ_i p_{i,t,s} = Demand_{t,s}                       ∀t,s
```

**Analyse:**
- ✅ **Linear:** Alle Constraints sind linear
- ✅ **MILP:** Gemischt-ganzzahlig linear
- ✅ **Lösbar:** Dies ist ein Standard zwei-stufiges MILP
- 📊 **Komplexität:** NP-hart, aber mit modernen Solvern handhabbar

**Interpretation:**
- Unit Commitment-Entscheidungen (u_{i,t}) müssen **vor** Szenariorealisierung getroffen werden
- Kraftwerke werden deterministisch an/aus geschaltet
- Nur die Leistungsabgabe (p_{i,t,s}) passt sich an Szenarien an
- **Sinnvoll für:** Vortagesplanung mit Unsicherheit in Nachfrage/Wind/Solar

#### Variante B: Binäre Variablen in 2. Stufe (szenarioabhängig)
**Entscheidungsstruktur:**
- **Erste Stufe:** Nur Investitionen (falls multi-period)
- **Zweite Stufe:** $u_{i,t,s}$ ∈ {0,1} - Status ist **szenarioabhängig**

**Mathematische Formulierung:**
```
min  Σ_s π_s * Σ_{i,t} (c_startup * v_{i,t,s} + c_{marginal} * p_{i,t,s})

s.t.
  # Für jedes Szenario s:
  p_{i,t,s} ≤ P_max * u_{i,t,s}                      ∀i,t,s
  v_{i,t,s} - w_{i,t,s} = u_{i,t,s} - u_{i,t-1,s}    ∀i,t,s
  u_{i,t,s}, v_{i,t,s}, w_{i,t,s} ∈ {0,1}            ∀i,t,s
```

**Analyse:**
- ✅ **Linear:** Alle Constraints sind linear
- ✅ **MILP:** Gemischt-ganzzahlig linear
- ✅ **Lösbar:** Auch dies ist ein Standard MILP
- ⚠️ **Komplexität:** Wesentlich mehr binäre Variablen (Faktor S)
- ⚠️ **Realistisch?** Kraftwerke können nicht "nach" Szenariorealisierung an/aus geschaltet werden

**Interpretation:**
- Jedes Szenario hat eigene Unit Commitment-Entscheidungen
- **Unrealistisch für:** Realtime-Entscheidungen (man kennt das Szenario erst wenn es eintritt)
- **Evtl. sinnvoll für:** "Was wäre wenn"-Analysen oder Benchmark

## 2. PyPSA's Implementierung

### 2.1 Was PyPSA aktuell macht (ohne Stochastik)

```python
# Aus constraints.py, Zeile ~308ff
com_i: pd.Index = c.committables.difference(c.inactive_assets)
status = n.model[f"{c.name}-status"]        # u_{i,t} ∈ {0,1}
start_up = n.model[f"{c.name}-start_up"]    # v_{i,t} ∈ {0,1}
shut_down = n.model[f"{c.name}-shut_down"]  # w_{i,t} ∈ {0,1}

# Big-M Constraint: p_{i,t} ≤ P_max * u_{i,t}
lhs_upper = (1, p), (-nominal_capacity, status)
```

**Index-Struktur:** `(snapshot, name)` - 2D

### 2.2 Was mit Stochastik passiert

Nach `n.set_scenarios()`:
- **Alle Indizes werden MultiIndex:** `(scenario, snapshot, name)` - 3D
- **Status-Variable:** `status[scenario, snapshot, name]` ∈ {0,1}

```python
# Wenn man die Constraints aufbaut:
active.loc[sns[1:], min_up_time_i]  # ❌ FAILS - .loc[] erwartet 2D, bekommt 3D
```

### 2.3 Das technische Problem (nicht mathematisches!)

**Es ist NICHT ein Problem der mathematischen Lösbarkeit!**

Das Problem ist rein **implementierungstechnisch**:
- PyPSA's `constraints.py` nutzt pandas `.loc[]` Indexierung
- `.loc[]` wurde für 2D-Indizes (snapshot, name) geschrieben
- Bei MultiIndex (scenario, snapshot, name) versagt die Indexierung

**Lösung wäre:** Überall `.loc[]` → `.sel()` (xarray) oder `.loc[(slice(None), sns), names]` (pandas MultiIndex)

## 3. Welche Variante sollte PyPSA implementieren?

### Option A: Status in 1. Stufe (empfohlen ✅)

**Modellierung:**
```python
# Status ist NICHT szenarioabhängig:
status[snapshot, name] ∈ {0,1}

# Leistung IST szenarioabhängig:
p[scenario, snapshot, name] ∈ ℝ⁺

# Constraint:
p[s, t, i] ≤ P_max * status[t, i]  für alle s
```

**Vorteile:**
- ✅ Realistisch: Unit Commitment vor Szenariorealisierung
- ✅ Weniger binäre Variablen (Faktor 1/S Reduktion)
- ✅ Schneller lösbar
- ✅ Typisch in Strommarktplanung (day-ahead mit Unsicherheit)

**Nachteile:**
- Konservativere Lösung (muss für alle Szenarien funktionieren)

### Option B: Status in 2. Stufe (möglich, aber zweifelhaft)

**Modellierung:**
```python
# Alles ist szenarioabhängig:
status[scenario, snapshot, name] ∈ {0,1}
p[scenario, snapshot, name] ∈ ℝ⁺
```

**Vorteile:**
- Flexibler (perfekte Information)
- Niedrigere Zielfunktionswerte

**Nachteile:**
- ❌ Unrealistisch für operative Planung
- ❌ Viel mehr binäre Variablen
- ❌ Wesentlich längere Lösungszeiten

## 4. Ist das Problem lösbar?

### ✅ JA - Es ist ein MILP!

**Mathematisch:**
- Alle Constraints sind **linear**
- Zielfunktion ist **linear** (oder quadratisch bei quadratischen Kosten, dann MIQP)
- Variablen sind **binär** oder **kontinuierlich**
- **Keine bilinearen Terme** wie $u_{i,t} \cdot u_{i,t,s}$ oder $p_{i,t} \cdot u_{i,t,s}$

**Die Big-M Formulierung bleibt linear:**
```
p_{i,t,s} ≤ P_max * u_{i,t}
```
Dies ist eine **lineare Ungleichung** in den Variablen p_{i,t,s} und u_{i,t}.

### Warum ist das linear?

Ein typischer **nichtlinearer** Term wäre:
```
# ❌ Nichtlinear (bilinear):
p_{i,t,s} = efficiency_{i,t} * u_{i,t,s} * fuel_{i,t,s}

# ❌ Nichtlinear (quadratisch):
cost = p_{i,t}^2

# ✅ Linear (Big-M):
p_{i,t,s} ≤ M * u_{i,t}
```

Die Big-M Formulierung vermeidet Nichtlinearität, indem sie die Multiplikation 
$p \cdot u$ durch eine **Ungleichung** ersetzt.

## 5. Fazit

### Mathematisch ✅
**Das Problem ist lösbar als MILP** - unabhängig davon, ob Status in Stufe 1 oder 2 ist.

### Implementierung ❌
**PyPSA's aktuelle Implementierung ist nicht kompatibel** mit MultiIndex-Strukturen in den Committable-Constraints.

### Empfehlung für Fix:

**Variante A umsetzen (Status in 1. Stufe):**

```python
def define_operational_constraints_for_committables(n, sns, c):
    # Status-Variablen OHNE Szenario-Dimension erstellen
    if hasattr(n, 'scenarios') and n.scenarios is not None:
        # Nur über snapshots und names, NICHT über scenarios
        status_coords = [sns, com_i]
    else:
        # Original-Verhalten
        status_coords = [sns, com_i]
    
    status = n.model.add_variables(
        coords=status_coords,
        name=f"{c.name}-status",
        binary=True
    )
    
    # Leistung MIT Szenario-Dimension
    p = n.model[f"{c.name}-p"]  # Hat Dimension [scenario, snapshot, name]
    
    # Constraint mit Broadcasting:
    # p[s,t,i] ≤ P_max * status[t,i] für alle s
    if hasattr(n, 'scenarios'):
        # status wird über scenarios gebroadcastet
        status_broadcast = status.expand_dims(scenario=n.scenarios.index)
    else:
        status_broadcast = status
    
    lhs_upper = (1, p), (-nominal_capacity, status_broadcast)
    n.model.add_constraints(lhs_upper, "<=", 0, ...)
```

### Implementierungsaufwand:

**Kleine Änderung (1-2 Tage):**
- Status-Variablen ohne Szenario-Dimension erstellen
- Broadcasting in Constraints hinzufügen
- Tests schreiben

**Aufwand lohnt sich:**
- Mathematisch korrekt
- Performant
- Realistisches Modell

## 6. Literatur & Validierung

Diese Formulierung ist **Standardliteratur** in stochastischer Unit Commitment:

- Takriti et al. (1996): "A stochastic model for the unit commitment problem"
- Papavasiliou & Oren (2013): "Multiarea stochastic unit commitment"
- Dvorkin et al. (2018): "A Hybrid Stochastic/Interval Approach to Transmission-Constrained Unit Commitment"

Alle nutzen **Status in 1. Stufe, Leistung in 2. Stufe** - und alle sind MILP.

## 7. PyPSA's Aktuelle Implementierung

### 7.1 Was PyPSA TATSÄCHLICH macht

Nach Analyse der Dokumentation und des Codes (`docs/user-guide/optimization/stochastic.md`, Zeile 252):

> **Investment variables (i.e. `p_nom`, `s_nom`, `e_nom`) are scenario-independent first-stage decisions**, 
> they do not have a scenario dimension (i.e. are common across all scenarios). This is also called 
> **non-anticipativity constraint**. Operational variables, on the other hand, are fully scenario-indexed.

**Variablen-Struktur aus der Dokumentation:**
```
Variables:
----------
 * Generator-p_nom (name)                    # ✅ OHNE scenario
 * Link-p_nom (name)                         # ✅ OHNE scenario
 * Store-e_nom (name)                        # ✅ OHNE scenario
 * StorageUnit-p_nom (name)                  # ✅ OHNE scenario
 * Generator-p (scenario, name, snapshot)    # ✅ MIT scenario
 * Link-p (scenario, name, snapshot)         # ✅ MIT scenario
 * Store-e (scenario, name, snapshot)        # ✅ MIT scenario
```

**Code-Beweis aus `variables.py` (Zeile 153-176):**
```python
def define_nominal_variables(n: Network, c_name: str, attr: str) -> None:
    """Initialize variables for nominal capacities."""
    c = n.components[c_name]
    ext_i = c.extendables.difference(c.inactive_assets)
    if ext_i.empty:
        return
    if isinstance(ext_i, pd.MultiIndex):
        ext_i = ext_i.unique(level="name")  # ← Entfernt scenario-Dimension!

    n.model.add_variables(coords=[ext_i], name=f"{c.name}-{attr}")
```

**➡️ PyPSA implementiert bereits GENAU die Variante A (Status in 1. Stufe)!**

### 7.2 Warum funktioniert es dann nicht für Committable?

**Das Problem:** Committable-Status-Variablen werden ANDERS behandelt als Investitionsvariablen.

**Aus `variables.py` (Zeile 67-77):**
```python
def define_status_variables(n: Network, sns: Sequence, c_name: str, ...) -> None:
    """Initialize variables for unit commitment status."""
    c = n.components[c_name]
    com_i = c.committables.difference(c.inactive_assets)
    
    active = c.da.active.sel(name=com_i, snapshot=sns)
    coords = active.coords  # ← Nimmt ALLE Koordinaten von active!
    
    n.model.add_variables(
        coords=coords,  # ← Enthält scenario-Dimension wenn Szenarien aktiv!
        name=f"{c.name}-status",
        binary=True
    )
```

**Das Problem:**
- `c.da.active` hat nach `set_scenarios()` die Dimensionen `(scenario, snapshot, name)`
- `coords = active.coords` übernimmt **alle** Dimensionen
- Status-Variablen bekommen **fälschlicherweise** eine scenario-Dimension!

**Was passieren sollte:**
```python
# Für Investitionsvariablen (RICHTIG):
coords = [ext_i]  # Nur name-Dimension

# Für Status-Variablen (AKTUELL FALSCH):
coords = active.coords  # (scenario, snapshot, name)

# Für Status-Variablen (SOLLTE SEIN):
coords = [sns, com_i]  # Nur (snapshot, name) - OHNE scenario!
```

### 7.3 Vergleich der Implementierungen

| Feature | Investitionsvariablen | Status-Variablen (committable) |
|---------|----------------------|--------------------------------|
| **Code-Zeile** | `variables.py:176` | `variables.py:77` |
| **Index-Handling** | ✅ `ext_i.unique(level="name")` | ❌ `coords = active.coords` |
| **MultiIndex-aware** | ✅ Ja, entfernt scenario | ❌ Nein, behält alles |
| **Dimensionen** | `(name)` | `(scenario, snapshot, name)` |
| **Funktioniert mit Szenarien** | ✅ Ja | ❌ Nein |
| **Design-Intention** | Stufe 1 (deterministisch) | Stufe 1 (deterministisch) |
| **Tatsächliche Implementierung** | Stufe 1 ✅ | Stufe 2 ❌ (unbeabsichtigt) |

### 7.4 Andere Alternativen

#### Alternative 1: Status in Stufe 2 (szenarioabhängig) 🔴 **NICHT EMPFOHLEN**

**Würde bedeuten:**
```python
# Status-Variablen mit scenario-Dimension BEHALTEN
status[scenario, snapshot, name] ∈ {0,1}
```

**Warum PyPSA dies NICHT tut:**
- ❌ Unrealistisch für operative Planung
- ❌ Widerspricht dem Non-Anticipativity-Prinzip
- ❌ Viel mehr binäre Variablen (Faktor S)
- ❌ Inkonsistent mit Investitionsvariablen
- ❌ Nicht dokumentiert in der offiziellen Semantik

**PyPSA's klare Design-Entscheidung (aus Dokumentation):**
> Investment variables are scenario-independent **first-stage decisions**

#### Alternative 2: Hybrid-Ansatz (teilweise szenarioabhängig) 🟡 **THEORETISCH MÖGLICH**

**Konzept:**
```python
# Investitionsentscheidungen: Stufe 1
p_nom[name] ∈ ℝ⁺

# Unit Commitment: Stufe 2 (für MANCHE Einheiten)
status[scenario, snapshot, name] ∈ {0,1}

# Leistung: Stufe 2
p[scenario, snapshot, name] ∈ ℝ⁺
```

**Anwendungsfall:**
- Langfristige Investition (deterministisch): Kraftwerk bauen ja/nein
- Kurzfristige Operation (szenarioabhängig): Kraftwerk an/aus in Abhängigkeit vom Wetter

**Problem:**
- 🔴 Inkonsistent mit PyPSA's Philosophie
- 🔴 Verwirrt Nutzer (wann was?)
- 🟢 Mathematisch korrekt
- 🟢 Evtl. sinnvoll für spezielle Use-Cases

#### Alternative 3: Status in Stufe 1 (wie Investitionen) ✅ **EMPFOHLEN**

**Dies ist PyPSA's EIGENTLICHE Intention!**

**Implementierung:**
```python
def define_status_variables(n: Network, sns: Sequence, c_name: str, ...) -> None:
    c = n.components[c_name]
    com_i = c.committables.difference(c.inactive_assets)
    
    # WENN MultiIndex (Szenarien), extrahiere nur 'name'-Level
    if isinstance(com_i, pd.MultiIndex):
        com_i = com_i.unique(level="name")  # ← WIE BEI INVESTITIONEN!
    
    # Status OHNE scenario-Dimension
    coords = [sns, com_i]  # ← Nur (snapshot, name)
    
    n.model.add_variables(
        coords=coords,
        name=f"{c.name}-status",
        binary=True
    )
```

**Vorteile:**
- ✅ Konsistent mit Investitionsvariablen
- ✅ Konsistent mit Dokumentation
- ✅ Realistisch für Vortagesplanung
- ✅ Deutlich weniger binäre Variablen
- ✅ Mathematisch korrekt (MILP)

## 8. Zusammenfassung

| Aspekt | Bewertung |
|--------|-----------|
| **Mathematisch lösbar?** | ✅ JA - es ist ein MILP |
| **Linear oder nichtlinear?** | ✅ LINEAR (mit Big-M) |
| **Quadratisch?** | Nur wenn quadratische Kosten gewünscht (dann MIQP, auch lösbar) |
| **PyPSA's Design** | ✅ Status in Stufe 1 (wie Investitionen) |
| **PyPSA's Implementierung** | ❌ Status bekommt fälschlich Stufe 2 |
| **PyPSA-Bug behebbar?** | ✅ JA - 1-Zeilen-Fix in `variables.py` |
| **Aufwand** | Gering (wenige Zeilen, ähnlich wie Investment-Variablen) |
| **Alternative Ansätze** | Theoretisch möglich, aber inkonsistent |
| **Empfehlung** | Fix in `define_status_variables()` analog zu `define_nominal_variables()` |

---

## 9. Antwort auf die Fragen

### **Frage 1: Ist committable + stochastic als MILP lösbar?**
✅ **JA** - Das Problem ist ein Standard zwei-stufiges MILP und mathematisch vollkommen korrekt formulierbar.

### **Frage 2: Passt das zu PyPSA's Implementierung?**
✅ **JA** - PyPSA implementiert bereits für Investitionsvariablen genau diesen Ansatz (Stufe 1 = deterministisch). 
Status-Variablen sollten genauso behandelt werden.

### **Frage 3: Gibt es andere Alternativen?**
🟡 **THEORETISCH JA** - Man könnte Status-Variablen szenarioabhängig machen (Stufe 2), aber:
- ❌ Widerspricht PyPSA's Non-Anticipativity-Prinzip
- ❌ Inkonsistent mit Investitionsvariablen
- ❌ Unrealistisch für operative Planung
- ❌ Deutlich höhere Rechenzeit

### **Fazit:**
Der Bug ist ein **Implementierungsfehler**: Status-Variablen verwenden `active.coords` (mit scenario), 
während Investitionsvariablen korrekt `ext_i.unique(level="name")` verwenden (ohne scenario). 
Die Lösung ist ein **1-Zeilen-Fix** analog zur Investitionsvariablen-Implementierung.
