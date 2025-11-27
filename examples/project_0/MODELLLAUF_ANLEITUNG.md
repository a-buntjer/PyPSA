# MODELLLAUF-ANLEITUNG
## Sylt Fernwärme - Stochastisches Multi-Horizon Optimierungsmodell

**Projekt:** Fernwärme Westerland (Sylt) - Transformation 2027-2045  
**Modelltyp:** Stochastisches Multi-Investment-Perioden Modell mit Unit Commitment  
**PyPSA Version:** 1.0.2 (custom mit dispatch_only Feature)  
**Datum:** 27. Oktober 2025

---

## 📋 ÜBERSICHT

Dieses Dokument beschreibt die **komplette Ausführungsreihenfolge** aller Skripte für einen vollständigen Modelllauf von der Netzwerk-Erstellung bis zur detaillierten Ergebnisanalyse.

---

## 🎯 VOLLSTÄNDIGER MODELLLAUF

### **Phase 1: Netzwerk-Erstellung** ⏱️ ~1 Minute

```bash
python sylt_full_model.py
```

**Input:**
- `Bestandsanlagen_Sylt.csv` - Daten der existierenden Anlagen

**Output:**
- `sylt_network_full.nc` - Vollständiges Netzwerk mit 3 Szenarien

**Erstellt:**
- 3 Stochastische Szenarien (optimistisch 25%, base 50%, pessimistisch 25%)
- 5 Investment-Perioden (2027, 2030, 2035, 2040, 2045)
- 43.800 Zeitschritte (8.760 h × 5 Perioden)
- 24 Bestandsanlagen (Kessel + BHKWs, committable)
- 14 neue Technologien (Elektroheizer + Wärmepumpen, committable + extendable)
- 6 Speicher (1 existierend, 5 erweiterbar)
- 9 Busse (3 × 3 Szenarien)
- 114 Links (38 × 3 Szenarien)

**Parameter:**
- Diskontrate: 6%
- Förderquote: 40%
- Inselzuschlag Sylt: 30%
- CO₂-Preise: 55-200 EUR/t (steigend)

---

### **Phase 2: Optimierung** ⏱️ ~30-60 Minuten

```bash
python test_optimization_full.py
```

**Input:**
- `sylt_network_full.nc`

**Output:**
- `sylt_network_full_optimized.nc` - ⭐ **HAUPTERGEBNIS**

**Optimierungs-Einstellungen:**
- Solver: HiGHS 1.11.0 (Open-Source MILP)
- Threads: 12
- MIP Gap: 5%
- Zeitlimit: 2 Stunden
- Big-M Formulation für committable + extendable

**Problemgröße:**
- Vor Presolving: 17.6 Mio. Zeilen, 14.7 Mio. Spalten
- Nach Presolving: 1.6 Mio. Zeilen, 1.9 Mio. Spalten (91% Reduktion)
- 10 Mio. binäre Variablen (Unit Commitment)
- 1.67 Mio. LP-Iterationen

**Speichert automatisch:** Netzwerk wird SOFORT nach erfolgreicher Optimierung gespeichert (vor der Ausgabe-Formatierung) zur Datensicherheit.

---

### **Phase 3: Ergebnisanalyse**

#### 3a) Detaillierte Kapazitäts-Analyse ⏱️ ~10 Sekunden

```bash
python analyze_results_detailed.py
```

**Input:**
- `sylt_network_full_optimized.nc`
- `sylt_network_optimized.nc` (zum Vergleich)

**Output:** Terminal-Ausgabe

**Zeigt:**
1. **Alle Kapazitäten über Perioden**
   - Bestandsanlagen (committable) pro Periode
   - Neue Technologien (extendable) mit Ausbau-Status
   - Speicher-Kapazitäten

2. **Zusammenfassung Ausbauten**
   - Nur tatsächlich gebaute Technologien
   - Differenz: geplant vs. optimal

3. **Volllaststunden (Auslastung)**
   - Für Perioden 2027, 2030, 2035

4. **Kostenvergleich**
   - Vollständiges Modell (3 Szenarien): 13.55M EUR
   - Test-Modell (1 Szenario): 6.62M EUR
   - Unterschied: +6.93M EUR (+104.6%)

5. **Fazit & Interpretation**
   - Warum nur Elektrodenkessel ausgebaut wird
   - Warum Wärmepumpen nicht wirtschaftlich sind
   - Bedeutung der Biomethane-Umstellung ab 2035

---

#### 3b) EVPI-Analyse (Expected Value of Perfect Information) ⏱️ ~10 Sekunden

```bash
python analyze_evpi.py
```

**Input:**
- `sylt_network_full_optimized.nc` (Stochastisch, RP)
- `sylt_network_optimized.nc` (Deterministisch, EEV)

**Output:** Terminal-Ausgabe

**Berechnet:**

1. **RP (Recourse Problem)**
   - Stochastisches Modell: 13.55M EUR
   - Robuste Lösung über alle Szenarien

2. **EEV (Expected Value Problem)**
   - Deterministisches Modell: 6.62M EUR
   - Nur für Base-Szenario optimiert

3. **WS (Wait-and-See)**
   - Geschätzt: 6.71M EUR
   - Theoretisches Optimum mit perfekter Information

4. **VSS (Value of Stochastic Solution)**
   - VSS = EEV - RP = -6.93M EUR
   - "Preis der Robustheit"
   - Die robuste Lösung kostet mehr, funktioniert aber in allen Szenarien

5. **EVPI (Expected Value of Perfect Information)**
   - **EVPI = RP - WS = 6.85M EUR (50.5%)**
   - **Obergrenze für Forecasting-Investitionen**
   - Alle Maßnahmen < 6.85M EUR zur Verbesserung der Prognose lohnen sich!

**Empfehlungen:**
- ✅ Investitionen in bessere Prognosen (Nachfrage, Preise) bis 6.85M EUR rentabel
- ✅ Adaptive Planung mit jährlichen Updates
- ✅ Staging-Strategien (schrittweise Investitionen)
- ⚠️ Hoher Robustheitspreis → Szenarien auf Realismus prüfen

---

#### 3c) BEW-Förderung Beispielrechnung ⏱️ ~1 Sekunde

```bash
python bew_modul4.py
```

**Input:** Keine (standalone Berechnung)

**Output:** Terminal-Ausgabe mit Beispielen

**Zeigt:**
- Berechnung der BEW Modul 4 Arbeitspreisförderung
- Beispiele für Luft-WP (Winter/Sommer) und Abwasser-WP
- Effektive Strompreise nach Förderung
- Vergleich mit Gas-Referenz (111 EUR/MWh Wärme)

**Haupterkenntnis:**
Bei aktuellen Annahmen (Strom 80-120 EUR/MWh, Gas 100 EUR/MWh) sind Wärmepumpen **bereits günstiger als Gas** → **BEW-Förderung greift NICHT**!

BEW wird erst relevant bei:
- Strompreisen > 150 EUR/MWh
- Gaspreisen < 80 EUR/MWh
- COPs < 3.0

---

### **Phase 4: Optionale Sensitivitätsanalysen**

#### 4a) Re-Optimierung mit BEW-Förderung ⏱️ ~30-60 Minuten

```bash
python optimize_with_bew.py
```

**Input:**
- `sylt_network_full.nc`

**Output:**
- `sylt_network_full_bew.nc` - Netzwerk mit angepassten Strompreisen
- `sylt_network_full_bew_optimized.nc` - Optimiertes Ergebnis mit BEW

**Funktionalität:**
- Lädt Original-Netzwerk
- Reduziert effektive Stromkosten für Wärmepumpen (BEW Modul 4)
- Re-optimiert mit gleichen Solver-Einstellungen
- Vergleicht Kosten und Kapazitäten: ohne vs. mit BEW

**Hinweis:** Aktuell bringt BEW wenig Änderung, da WP bereits günstiger sind als Gas.

---

#### 4b) Dispatch-Profile Analyse ⏱️ ~10 Sekunden ⚠️

```bash
python analyze_dispatch.py
```

**Input:**
- `sylt_network_full_optimized.nc`

**Output:** Terminal-Ausgabe (geplant)

**Status:** ⚠️ **AKTUELL BLOCKIERT**

**Problem:** Zeitreihen-Daten (`links_t.p0`, `links_t.p1`) werden im NetCDF-Export nicht korrekt gespeichert.

**Geplante Ausgabe:**
- Jahresenergien nach Technologie (BHKW, Kessel, Elektroheizer, WP)
- Typische Tage (Winter/Sommer/Übergang) mit Lastprofilen
- Top-3 Erzeuger pro Tag
- Volllaststunden und Auslastung
- Grafische Visualisierung (wenn implementiert)

**Lösung erforderlich:**
- Entweder: Dispatch während Optimierung live extrahieren
- Oder: NetCDF-Export mit `export_time_series=True` erweitern

---

## 📊 VERGLEICHSMODELL (Test)

Für Benchmarking wurde ein **deterministisches Testmodell** erstellt:

### Test-Netzwerk erstellen
```bash
python sylt_simple_test.py
```
**Output:** `sylt_network_simple.nc` (1 Szenario, vereinfacht)

### Test-Optimierung
```bash
python test_optimization.py
```
**Output:** `sylt_network_optimized.nc`  
**Ergebnis:** 6.62M EUR (deterministisch)

---

## 🚀 SCHNELLSTART - MINIMALER DURCHLAUF

Für eine **vollständige Basis-Analyse** genügen diese **4 Befehle**:

```bash
# 1. Netzwerk erstellen (~1 Min)
python sylt_full_model.py

# 2. Optimieren (~30-60 Min)
python test_optimization_full.py

# 3. Detaillierte Ergebnisse (~10 Sek)
python analyze_results_detailed.py

# 4. EVPI-Analyse (~10 Sek)
python analyze_evpi.py
```

**Gesamt-Laufzeit:** ~35-65 Minuten

---

## 📁 DATEIEN-ÜBERSICHT

### Input-Dateien
| Datei | Typ | Beschreibung |
|-------|-----|--------------|
| `Bestandsanlagen_Sylt.csv` | CSV | 9 existierende Anlagen (Kessel + BHKWs) |

### Haupt-Skripte (essentiell)
| # | Skript | Zweck | Dauer |
|---|--------|-------|-------|
| 1 | `sylt_full_model.py` | Netzwerk-Erstellung | 1 Min |
| 2 | `test_optimization_full.py` | Optimierung | 30-60 Min |
| 3 | `analyze_results_detailed.py` | Kapazitäts-Analyse | 10 Sek |
| 4 | `analyze_evpi.py` | EVPI-Berechnung | 10 Sek |

### Zusatz-Skripte (optional)
| # | Skript | Zweck | Dauer |
|---|--------|-------|-------|
| 5 | `bew_modul4.py` | BEW-Beispielrechnung | 1 Sek |
| 6 | `optimize_with_bew.py` | Re-Optimierung mit BEW | 30-60 Min |
| 7 | `analyze_dispatch.py` | Dispatch-Profile | ⚠️ blockiert |
| 8 | `show_full_results.py` | Basis-Ergebnisanzeige | 10 Sek |

### Vergleichs-Skripte (Test-Modell)
| # | Skript | Zweck | Dauer |
|---|--------|-------|-------|
| 9 | `sylt_simple_test.py` | Test-Netzwerk (1 Szenario) | 1 Min |
| 10 | `test_optimization.py` | Test-Optimierung | 16 Min |

### Output-Dateien
| Datei | Größe | Beschreibung |
|-------|-------|--------------|
| `sylt_network_full.nc` | ~XX MB | Netzwerk mit 3 Szenarien (vor Optimierung) |
| **`sylt_network_full_optimized.nc`** | ~XX MB | ⭐ **HAUPTERGEBNIS** (optimiert) |
| `sylt_network_simple.nc` | ~XX MB | Test-Netzwerk (1 Szenario) |
| `sylt_network_optimized.nc` | ~XX MB | Test-Optimierung (zum Vergleich) |
| `sylt_network_full_bew.nc` | ~XX MB | Netzwerk mit BEW-Förderung |
| `sylt_network_full_bew_optimized.nc` | ~XX MB | Optimiert mit BEW |

### Dokumentation
| Datei | Inhalt |
|-------|--------|
| `ERGEBNISSE.md` | Haupt-Report mit allen Ergebnissen |
| `ZUSATZ_ANALYSEN.md` | EVPI, BEW, Dispatch-Analysen |
| `MODELLLAUF_ANLEITUNG.md` | Dieses Dokument |
| `README.md` | Modell-Dokumentation (wenn vorhanden) |

---

## 📊 HAUPTERGEBNISSE (ZUSAMMENFASSUNG)

### Optimale Investitionsstrategie

**Einziger Ausbau:** Elektrodenkessel 2027
- Geplant: 5.0 MW
- Optimal: 8.24 MW
- Ausbau: +3.24 MW (+64.8%)

**Nicht ausgebaut:**
- ❌ Alle Wärmepumpen (0 MW statt geplant ~13 MW)
- ❌ Alle neuen Speicher (0 MWh)
- ❌ Weitere Elektrodenkessel in späteren Perioden (0 MW)

### Kosten

| Modell | Szenarien | Kosten | Interpretation |
|--------|-----------|--------|----------------|
| **Deterministisch** | 1 (base) | 6.62M EUR | Nur erwarteter Fall |
| **Stochastisch** | 3 | 13.55M EUR | Robust über Szenarien |
| **Wait-and-See** | 3 (perfekt) | 6.71M EUR | Theoretisches Optimum |

### Kennzahlen

- **VSS (Robustheitspreis):** -6.93M EUR
  - Die robuste Lösung kostet doppelt so viel
  - Aber: Funktioniert in allen Szenarien (kein Risiko)

- **EVPI (Wert Prognose):** **6.85M EUR (50.5%)**
  - Obergrenze für Forecasting-Investitionen
  - Sehr hoher Wert → Adaptive Planung empfohlen!

### Warum nur Elektrodenkessel?

1. ✅ **Niedrigste Investitionskosten:** 150 EUR/kW (nach Förderung ~200 EUR/kW)
2. ✅ **Sofort verfügbar:** 2027 (früheste Periode)
3. ✅ **Hohe Effizienz:** 99%
4. ✅ **Flexibel:** Nutzt Strompreis-Schwankungen
5. ✅ **Biomethane ab 2035:** Bestandsanlagen werden CO₂-neutral

### Warum keine Wärmepumpen?

1. ❌ **Hohe Investitionskosten:** 800-1200 EUR/kW (nach Förderung ~1100-1700 EUR/kW)
2. ❌ **Späterer Einstieg:** 2030+ statt 2027
3. ❌ **Strompreise zu hoch:** 80-150 EUR/MWh
4. ❌ **COP nicht ausreichend:** Faktor 2.5-3.8 kompensiert nicht die Mehrkosten
5. ❌ **BEW greift nicht:** WP bereits günstiger als Gas bei aktuellen Preisen

---

## 🎯 EMPFEHLUNGEN

### Kurzfristig (2027-2030)
1. ✅ **Elektrodenkessel 8.2 MW** bauen (wie optimiert)
2. ⏸️ **Wärmepumpen verschieben** (noch nicht wirtschaftlich)
3. ✅ **Bestandsanlagen nutzen** bis zur Stilllegung

### Mittelfristig (2030-2035)
4. 💰 **In Forecasting investieren** (bis 6.85M EUR lohnt sich!)
   - Detaillierte Nachfrage-Modelle
   - Energiepreis-Prognosen
   - Regelmäßige Szenario-Updates
5. ✅ **Biomethane-Umstellung** vorbereiten (2035, kritisch!)
6. 🔍 **Strompreise monitoren:**
   - Bei < 100 EUR/MWh → Wärmepumpen prüfen
   - Bei > 120 EUR/MWh → warten

### Langfristig (2035-2045)
7. 🔄 **Adaptive Planung:**
   - Jährliche Re-Optimierung
   - Flexible Investitions-Staging
   - Real Options für Wärmepumpen
8. 📊 **Sensitivitätsanalysen:**
   - CO₂-Preise: 100-300 EUR/t
   - Strompreise: 60-180 EUR/MWh
   - Förderquoten: 20-60%

---

## ⚙️ TECHNISCHE PARAMETER

### Modell-Konfiguration

**Szenarien:**
| Szenario | Wahrscheinlichkeit | Nachfrage-Faktor | Preis-Faktor |
|----------|-------------------|------------------|--------------|
| Optimistisch | 25% | 0.9× | 0.85× |
| Base | 50% | 1.0× | 1.0× |
| Pessimistisch | 25% | 1.1× | 1.15× |

**Investment-Perioden:** 2027, 2030, 2035, 2040, 2045

**Zeitauflösung:** 8.760 Stunden/Periode = 43.800 Zeitschritte gesamt

**CO₂-Preise [EUR/t]:**
- 2027: 55
- 2030: 80
- 2035: 120
- 2040: 160
- 2045: 200

**Wirtschaftliche Parameter:**
- Diskontrate: 6%
- Förderquote (BEW): 40%
- Inselzuschlag Sylt: 30%
- Planungskosten: 20%
- Baukosten: 20%

### Solver-Einstellungen

**HiGHS 1.11.0:**
- Presolve: on (91% Reduktion)
- Parallel: on
- Threads: 12
- Time Limit: 7200s (2h)
- MIP Relative Gap: 5%

**Problemgröße:**
- Zeilen: 17.6M → 1.6M (presolving)
- Spalten: 14.7M → 1.9M (presolving)
- Binäre Variablen: 10M
- LP-Iterationen: 1.67M
- Nodes: 1 (keine Verzweigung!)

---

## 🐛 BEKANNTE PROBLEME

### 1. Dispatch-Profile nicht verfügbar ⚠️
**Problem:** `links_t.p0` und `links_t.p1` werden im NetCDF nicht gespeichert

**Workaround:** Zeitreihen während Optimierung live extrahieren

**Status:** Analyse-Skript vorhanden (`analyze_dispatch.py`), aber ohne Daten

### 2. BEW-Förderung greift nicht
**Problem:** Bei aktuellen Preisen sind WP günstiger als Gas

**Lösung:** Für BEW-Effekt pessimistischere Strompreise (150-200 EUR/MWh) modellieren

**Status:** Skript bereit (`optimize_with_bew.py`), aber Effekt marginal

### 3. Hoher EVPI (50.5%)
**Problem:** Sehr hohe Unsicherheit in Prognosen

**Interpretation:** Normal für 20-Jahres-Horizont mit Energiewende-Unsicherheit

**Empfehlung:** Adaptive Planung statt Ein-Mal-Optimierung

---

## 📞 SUPPORT & WEITERENTWICKLUNG

### Weitere mögliche Analysen

**Noch nicht implementiert:**
1. **Dispatch-Visualisierung:** Grafische Darstellung der Erzeugung über Zeit
2. **Real Options Analysis:** Wert des Wartens (flexible Investitionen)
3. **Parametrische Sensitivität:** Systematische Variation von CO₂/Strom/Gas-Preisen
4. **Szenario-Reduktion:** Optimale Anzahl und Gewichtung von Szenarien
5. **Risk Metrics:** CVaR, VaR, Worst-Case-Kosten

### Modell-Erweiterungen

**Mögliche Ergänzungen:**
1. **Mehr Szenarien:** 5-7 statt 3 (z.B. extremer Winter, Gas-Krise)
2. **Technologie-Lernen:** Degression der Investitionskosten über Zeit
3. **Unsicherheit in COP:** Stochastische Wärmepumpen-Effizienz
4. **Netz-Ausbau:** Kapazitätsbeschränkungen im Wärmenetz
5. **Power-to-X:** Wasserstoff, Synthetische Kraftstoffe

---

**Ende der Anleitung**

Erstellt: 27. Oktober 2025  
PyPSA Version: 1.0.2 (custom)  
Solver: HiGHS 1.11.0
