# Simulation Energiesystem Fernwärme Westerland (Sylt)

## Zielsetzung
Die Simulation soll die Ergebnisse des Transformationsplans validieren und die zukünftige Entwicklung des Energiesystems modellieren. Ein Coding-Agent soll auf Basis dieser Informationen die Simulation programmieren.

## Technologien und Zeitpunkte
- Wärmepumpen:
  - WP1 Umgebungsluft: 2029/2030, 3,5 MW
  - WP2 Umgebungsluft: 2039/2040, 3,5 MW
  - Abwasser-WP: 2035/2040, 2,7–3,7 MW
- Elektrodenkessel: 2027, 5 MW
- Spitzenlastkessel/BHKW:
  - Friesische Straße: Weiterbetrieb bis 2035/2040 mit Biomethan
  - Andreas-Dirks-Straße: Außerbetriebnahme 2029

## Lastannahmen
- Wärmeabsatz 2024: ca. 30 GWh inkl. Verluste
- Entwicklung: Linearer Anstieg von 30 GWh (2025) auf 50 GWh (2045)
- Temperaturniveau: 78 °C / 50–55 °C

## Speicher
- Tagespufferspeicher: 12–14 Volllaststunden täglich für WP-Standorte
- Friesische Straße: Neudimensionierung für E-Kessel, derzeit 2×100 m³

## Netzentwicklung
- Phase 1 (2025–2028): Teil-Erschließung Nord und Nord-West
- Phase 2 (2029–2032): Erweiterung Nord und Nord-West, Teil-Erschließung Ost
- Phase 3 (2033–2036): Erweiterung Nord-Ost, Teil-Erschließung Süd
- Phase 4 (2037–2040): Erweiterung Süd, Teil-Erschließung Nord und Ost

## Wirtschaftliche Annahmen
- Zinssatz: 6 %
- Förderquote: 40 % der Investitionskosten
- Anlagenbaukosten: 20 % der Investitionskosten
- Planungskosten: 20 % der Investitionskosten
- Inselaufschlag: 30 % der Investitionskosten
- Abschreibungsdauer Leitungen: 40 Jahre
- Abschreibungsdauer restliche Investitionen: 20 Jahre

## Preisannahmen (Standardwerte)
- Strompreis (2045): sinkend, CO2-Preis steigend
- Primärenergiefaktor Strom: 0,24
- CO2-Emission Strom: 86 gCO2/kWh
- Hilfsenergie Netzpumpen: 1 % des Wärmebedarfs
- Hilfsstrom WP-Quellen: 2 % der Entzugswärme

## Fehlende Annahmen
- Strompreisverlauf: Standardwert interpoliert aus 2023–2045
- Erdgaspreisverlauf: Standardwert steigend
- Lastprofile: Jahresdauerlinie analog 2022 verwenden
- CO2-Preis: Standardwert gemäß nationaler Entwicklung

## Aufgaben für den Coding-Agenten
- Multi-Horizon-Optimierung für Zieljahre: 2027, 2030, 2035, 2040, 2045
- Stochastische Optimierung mit drei Szenarien (Preis & Wärmebedarf)
- Modellierung der Wärmeerzeuger mit Zeitpunkten und Leistungen
- Berücksichtigung der Netzentwicklung und Speicherbedarfe
- Integration der wirtschaftlichen Parameter und Preisannahmen
- Ergebnisdarstellung je Szenario und Zieljahr

## Bestandsanlagen
| Standort               | Anlage   | Typ    |   Baujahr | Leistung            | Eingespeiste Wärme (MWh)   | Erdgasverbrauch (MWh)   | Anteil Wärme   |   Wirkungsgrad thermisch | Wirkungsgrad elektrisch   |
|:-----------------------|:---------|:-------|----------:|:--------------------|:---------------------------|:------------------------|:---------------|-------------------------:|:--------------------------|
| Friesische Str. 53     | Kessel 1 | Kessel |      2020 | 5000 kWth           | 5250                       | 6363                    | 19,98 %        |                     0.92 |                           |
| Friesische Str. 53     | BHKW 1   | BHKW   |      2020 | 1269 kWth + 72 kWth | 4191                       | 8351                    | 15,95 %        |                     0.8  | 0.38                      |
| Friesische Str. 53     | BHKW 2   | BHKW   |      2020 | 1269 kWth + 72 kWth | 7264                       | 14472                   | 27,64 %        |                     0.8  | 0.38                      |
| Dr.-Nicolas-Str. 1     | Kessel 2 | Kessel |      1995 | 2400 kWth           |                            |                         | 0,02 %         |                     0.9  |                           |
| Dr.-Nicolas-Str. 1     | Kessel 3 | Kessel |      1995 | 2400 kWth           |                            |                         |                |                     0.9  |                           |
| Dr.-Nicolas-Str. 1     | Kessel 4 | Kessel |      1997 | 3200 kWth           |                            |                         |                |                     0.9  |                           |
| Andreas-Dirks-Str. 4-6 | Kessel 5 | Kessel |      1999 | 1350 kWth           | 2747                       | 3132                    | 11,2 %         |                     0.9  |                           |
| Andreas-Dirks-Str. 4-6 | Kessel 6 | Kessel |      1999 | 1900 kWth           |                            |                         |                |                     0.9  |                           |
| Andreas-Dirks-Str. 4-6 | BHKW 3   | BHKW   |      2009 | 741 kWth + 70 kWth  | 6817                       | 14671                   | 25,5 %         |                     0.8  | 0.38                      |