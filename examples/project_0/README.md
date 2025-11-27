# Fernwärme Westerland (Sylt) - PyPSA Optimierungsmodell

## Übersicht

Umfassendes PyPSA-Modell für die Transformation des Fernwärmesystems Westerland auf Sylt mit:

- **Multi-Horizon-Optimierung**: 5 Investment-Perioden (2027, 2030, 2035, 2040, 2045)
- **Stochastische Programmierung**: 3 Szenarien (optimistisch/base/pessimistisch)
- **Committable Erzeuger**: Unit Commitment für alle Technologien
- **Extendable Technologien**: Neue Anlagen mit Kapazitätserweiterung

## Dateien

1. **sylt_heat_network_optimization.py** - Hauptskript zur Netzwerkerstellung
2. **sylt_run_optimization.py** - Optimierung und Ergebnisanalyse
3. **Bestandsanlagen_Sylt.csv** - Daten der bestehenden Anlagen
4. **Simulation_Energiesystem_Sylt.md** - Transformationsplan

## Schnellstart

```bash
# 1. Netzwerk erstellen
python sylt_heat_network_optimization.py

# 2. Optimierung durchführen und Ergebnisse analysieren
python sylt_run_optimization.py
```

## Modellkomponenten

### Bestandsanlagen (Committable)

Aus `Bestandsanlagen_Sylt.csv`:

| Standort | Anlage | Typ | Leistung | Außerbetriebnahme |
|----------|--------|-----|----------|-------------------|
| Friesische Str. 53 | Kessel 1 | Kessel | 5.0 MW | 2040 (Biomethan) |
| Friesische Str. 53 | BHKW 1 | BHKW | 1.3 MW | 2040 (Biomethan) |
| Friesische Str. 53 | BHKW 2 | BHKW | 1.3 MW | 2040 (Biomethan) |
| Andreas-Dirks-Str. 4-6 | Kessel 5 | Kessel | 1.4 MW | 2029 |
| Andreas-Dirks-Str. 4-6 | Kessel 6 | Kessel | 1.9 MW | 2029 |
| Andreas-Dirks-Str. 4-6 | BHKW 3 | BHKW | 0.8 MW | 2029 |
| Dr.-Nicolas-Str. 1 | Kessel 2-4 | Kessel | 2.4-3.2 MW | 2035 |

### Neue Technologien (Committable + Extendable)

| Technologie | Inbetriebnahme | Leistung | Status |
|-------------|----------------|----------|--------|
| Elektrodenkessel | 2027 | 5.0 MW | Extendable |
| Luft-Wärmepumpe 1 | 2029 | 3.5 MW | Extendable |
| Luft-Wärmepumpe 2 | 2039 | 3.5 MW | Extendable |
| Abwasser-Wärmepumpe | 2035 | 2.7-3.7 MW | Extendable |

### Speicher

- **Bestand**: 2×100 m³ (12 MWh) Friesische Str.
- **Neu**: Tagespufferspeicher, extendable bis ~195 MWh (12-14 Volllaststunden)

## Szenarien

| Szenario | Wahrscheinlichkeit | Wärmebedarf | Preisfaktor |
|----------|-------------------|-------------|-------------|
| Optimistisch | 25% | 90% | 85% |
| Base | 50% | 100% | 100% |
| Pessimistisch | 25% | 110% | 115% |

## Wirtschaftliche Parameter

- **Zinssatz**: 6%
- **Förderquote**: 40% der Investitionskosten
- **Inselaufschlag**: 30%
- **Planungskosten**: 20%
- **Abschreibung**: 20 Jahre (Anlagen), 40 Jahre (Leitungen)

## Annahmen und Datenquellen

### [STANDARD] - Aus Transformationsplan

- Wärmebedarfsentwicklung: 30 GWh (2025) → 50 GWh (2045)
- Strompreis: 150 EUR/MWh (2025) → 80 EUR/MWh (2045)
- Gaspreis: 80 EUR/MWh (2025) → 120 EUR/MWh (2045, Biomethan)
- CO2-Preise: 55 EUR/tCO2 (2027) → 200 EUR/tCO2 (2045)
- CO2-Emissionen Strom: 86 gCO2/kWh

### [ANNAHME] - Ergänzt mit Literaturwerten

#### Investitionskosten (inkl. Inselaufschlag, Planung, nach Förderung)
- **Elektrodenkessel**: 150 EUR/kW → 234 EUR/kW (nach Zuschlägen, vor Förderung)
- **Luft-Wärmepumpe**: 800 EUR/kW → 1,248 EUR/kW
- **Abwasser-Wärmepumpe**: 1,200 EUR/kW → 1,872 EUR/kW
- **Wärmespeicher**: 400 EUR/kWh → 624 EUR/kWh

#### Betriebskosten
- Kessel: 5 EUR/MWh
- BHKW: 8 EUR/MWh
- Elektrodenkessel: 2 EUR/MWh
- Wärmepumpen: 3-4 EUR/MWh

#### Wirkungsgrade und COP
- **Kessel**: η = 0.90-0.92 (aus CSV)
- **BHKW**: η_th = 0.80, η_el = 0.38 (aus CSV)
- **Elektrodenkessel**: η = 0.99
- **Luft-Wärmepumpe**: COP = 2.0-4.0 (temperaturabhängig, Jahresmittel ~3.0)
- **Abwasser-Wärmepumpe**: COP = 3.8 (konstant)

#### Lastprofile
- Typisches Fernwärmelastprofil analog 2022
- Saisonale Variation: Winter/Sommer-Faktor 0.7-1.0
- Tagesverlauf: Morgenspitze (7h), Abendspitze (19h)

#### Strompreisprofil
- Niedrig nachts (2-6h), hoch tagsüber (10-20h)
- Variation ±15% um Mittelwert

#### Speicherverluste
- Bestehend: 2% pro Stunde
- Neu: 1.5% pro Stunde (bessere Dämmung)

## Ergebnisse

Nach der Optimierung werden folgende Ergebnisse ausgegeben:

1. **Gesamtkosten**: Pro Investitionsperiode
2. **Installierte Kapazitäten**: Entwicklung über Zeit
3. **Energiemix**: Wärmeerzeugung nach Technologie
4. **Speichernutzung**: Kapazität und Auslastung
5. **EVPI**: Expected Value of Perfect Information

### Visualisierungen

- `sylt_capacity_evolution.png` - Kapazitätsentwicklung
- `sylt_energy_mix.png` - Energiemix pro Periode
- `sylt_storage_profile.png` - Speicherverlauf (2 Wochen)
- `sylt_dispatch.png` - Lastdeckung (1 Woche)

## Technische Details

### PyPSA-Features

- **Multi-Investment-Perioden**: Optimierung über 5 Zeitpunkte mit Kapazitätserweiterungen
- **Stochastische Szenarien**: Berücksichtigung von Preis- und Bedarfsunsicherheiten
- **Unit Commitment**: Binäre Entscheidungen für An/Aus-Schaltung aller Erzeuger
- **Extendable Components**: Kapazitätserweiterung neuer Technologien
- **Time Series**: 8760 Stunden pro Periode

### Solver

- **HiGHS**: Open-source MILP-Solver
- Erwartete Rechenzeit: 5-30 Minuten (abhängig von Hardware)

## Validierung

Das Modell wurde erstellt zur Validierung des Transformationsplans mit folgenden Aspekten:

1. ✅ Bestandsanlagen mit korrekten Wirkungsgraden
2. ✅ Zeitliche Außerbetriebnahmen gemäß Plan
3. ✅ Neue Technologien mit Inbetriebnahmezeitpunkten
4. ✅ Wirtschaftliche Parameter inkl. Inselzuschlag
5. ✅ Wärmebedarfsentwicklung 30→50 GWh
6. ✅ Umstellung Erdgas→Biomethan ab 2035
7. ✅ Speicherdimensionierung 12-14 Volllaststunden

## Kontakt und Weiterentwicklung

Mögliche Erweiterungen:

- [ ] Netzentwicklung (4 Phasen) mit geografischen Zonen
- [ ] Detaillierte Lastprofile aus Messdaten 2022
- [ ] Strompreis-Zeitreihen aus Marktdaten
- [ ] Sensitivitätsanalyse CO2-Preis/Förderung
- [ ] Vergleich mit deterministischer Optimierung (EVPI-Berechnung)
- [ ] Integration Sektorkopplung (Power-to-Heat)

## Lizenz

Basierend auf PyPSA (Open Source)
