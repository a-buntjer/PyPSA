"""
Konfigurationsdatei für Stochastische Pufferspeicher-Auslegung
==============================================================

Diese Datei kann importiert werden, um die Hauptparameter einfach anzupassen.

Verwendung:
    import config
    # Überschreibe Parameter im Hauptskript
"""

# ==================== Szenarien ====================

SCENARIOS_CONFIG = {
    # Standard: 3 Szenarien (Kalt, Mittel, Warm)
    'standard': {
        'cold': {
            'sheet': 'Mittlere_Netzprognose_2021',
            'weight': 0.25,
            'description': 'Kaltes Wetterjahr (2021)'
        },
        'medium': {
            'sheet': 'Mittlere_Netzprognose_2024',
            'weight': 0.50,
            'description': 'Mittleres Wetterjahr (2024)'
        },
        'warm': {
            'sheet': 'Mittlere_Netzprognose_2026',
            'weight': 0.25,
            'description': 'Warmes Wetterjahr (2026)'
        }
    },
    
    # Konservativ: Mehr Gewicht auf kaltes Jahr
    'conservative': {
        'cold': {
            'sheet': 'Mittlere_Netzprognose_2021',
            'weight': 0.50,  # Höhere Gewichtung
            'description': 'Kaltes Wetterjahr (2021)'
        },
        'medium': {
            'sheet': 'Mittlere_Netzprognose_2024',
            'weight': 0.35,
            'description': 'Mittleres Wetterjahr (2024)'
        },
        'warm': {
            'sheet': 'Mittlere_Netzprognose_2026',
            'weight': 0.15,
            'description': 'Warmes Wetterjahr (2026)'
        }
    },
    
    # Nur mittleres Jahr (deterministisch)
    'deterministic': {
        'medium': {
            'sheet': 'Mittlere_Netzprognose_2024',
            'weight': 1.0,
            'description': 'Mittleres Wetterjahr (2024)'
        }
    }
}

# Aktive Szenario-Konfiguration
ACTIVE_SCENARIO_SET = 'standard'  # Ändern zu 'conservative' oder 'deterministic'


# ==================== Wärmepumpe ====================

class HeatPumpConfig:
    """Wärmepumpen-Konfiguration"""
    
    # Installierte Leistung
    FIXED_CAPACITY_MW = 0.6  # [MW] - HAUPTPARAMETER
    
    # Wärmepumpen-Typ (muss in Excel-Datei existieren)
    TYPE = 'Fenagy H600'
    
    # Betriebsparameter
    MIN_PART_LOAD = 0.3  # 30% Mindestteillast wenn AN
    STARTUP_COST_EUR = 50  # [EUR] Kosten pro Start
    MIN_UPTIME_HOURS = 2  # [h] Mindest-Laufzeit
    MIN_DOWNTIME_HOURS = 1  # [h] Mindest-Stillstandszeit
    
    # COP Grenzen (für Plausibilität)
    COP_MIN = 1.5
    COP_MAX = 10.0
    
    @classmethod
    def get_config_dict(cls):
        """Gibt Konfiguration als Dictionary zurück"""
        return {
            'capacity_mw': cls.FIXED_CAPACITY_MW,
            'type': cls.TYPE,
            'min_part_load': cls.MIN_PART_LOAD,
            'startup_cost': cls.STARTUP_COST_EUR,
            'min_uptime': cls.MIN_UPTIME_HOURS,
            'min_downtime': cls.MIN_DOWNTIME_HOURS,
        }


# ==================== Thermischer Speicher ====================

class StorageConfig:
    """Thermischer Speicher-Konfiguration"""
    
    # Temperatur-Nennwerte
    TEMP_SUPPLY_NOMINAL_C = 70  # [°C] Vorlauf
    TEMP_RETURN_NOMINAL_C = 40  # [°C] Rücklauf
    
    # Verluste
    STANDING_LOSS_PER_HOUR = 0.02  # [%/h] 2% pro Stunde
    
    # Kosten
    CAPITAL_COST_PER_MWH = 50000  # [EUR/MWh]
    
    # Optimierungs-Grenzen
    E_NOM_MIN_MWH = 0.1  # [MWh] Minimum
    E_NOM_MAX_MWH = 20.0  # [MWh] Maximum
    
    # Betriebs-Constraints
    E_INITIAL_FRACTION = 0.5  # 50% Start-SOC
    E_CYCLIC = True  # Zyklische Randbedingung
    
    @classmethod
    def get_config_dict(cls):
        """Gibt Konfiguration als Dictionary zurück"""
        return {
            'temp_supply': cls.TEMP_SUPPLY_NOMINAL_C,
            'temp_return': cls.TEMP_RETURN_NOMINAL_C,
            'standing_loss': cls.STANDING_LOSS_PER_HOUR,
            'capital_cost': cls.CAPITAL_COST_PER_MWH,
            'e_nom_min': cls.E_NOM_MIN_MWH,
            'e_nom_max': cls.E_NOM_MAX_MWH,
        }


# ==================== Netzwerk & Kosten ====================

class NetworkConfig:
    """Netzwerk- und Kosten-Parameter"""
    
    # Stromkosten
    GRID_ELECTRICITY_PRICE_EUR_MWH = 80  # [EUR/MWh]
    
    # Backup-System
    PEAK_BOILER_COST_EUR_MWH = 120  # [EUR/MWh] - teuer!
    PEAK_BOILER_CAPACITY_MW = 5.0  # [MW]
    
    # Netzanschluss
    GRID_CONNECTION_CAPACITY_MW = 10.0  # [MW]
    
    @classmethod
    def get_config_dict(cls):
        """Gibt Konfiguration als Dictionary zurück"""
        return {
            'electricity_price': cls.GRID_ELECTRICITY_PRICE_EUR_MWH,
            'boiler_cost': cls.PEAK_BOILER_COST_EUR_MWH,
            'boiler_capacity': cls.PEAK_BOILER_CAPACITY_MW,
            'grid_capacity': cls.GRID_CONNECTION_CAPACITY_MW,
        }


# ==================== Simulation & Optimierung ====================

class SimulationConfig:
    """Simulations- und Optimierungs-Parameter"""
    
    # Zeitraum
    HOURS_TO_SIMULATE = 168  # [h] 1 Woche = 168 h
    # Alternativen:
    # - 24: 1 Tag (schnell)
    # - 168: 1 Woche (standard)
    # - 720: 1 Monat (~30 Tage)
    # - 8760: 1 Jahr (vollständig, langsam!)
    
    # Solver-Einstellungen
    SOLVER_NAME = 'highs'  # Empfohlen für MILP
    MIP_GAP_TOLERANCE = 0.05  # 5% Optimalitätslücke
    TIME_LIMIT_SECONDS = 1800  # 30 Minuten
    SOLVER_THREADS = 16  # Anzahl paralleler Threads
    
    # Output-Optionen
    SAVE_NETCDF = True  # Ergebnisse speichern
    CREATE_PLOTS = True  # Plots erstellen
    VERBOSE = True  # Detaillierte Ausgabe
    
    @classmethod
    def get_config_dict(cls):
        """Gibt Konfiguration als Dictionary zurück"""
        return {
            'hours': cls.HOURS_TO_SIMULATE,
            'solver': cls.SOLVER_NAME,
            'mip_gap': cls.MIP_GAP_TOLERANCE,
            'time_limit': cls.TIME_LIMIT_SECONDS,
            'threads': cls.SOLVER_THREADS,
        }


# ==================== Vordefinierte Konfigurationen ====================

class PresetConfigurations:
    """Vordefinierte Konfigurationen für typische Anwendungsfälle"""
    
    @staticmethod
    def quick_test():
        """Schneller Test (wenige Stunden, grobe Toleranz)"""
        return {
            'hours': 24,
            'scenarios': SCENARIOS_CONFIG['deterministic'],
            'mip_gap': 0.10,
            'time_limit': 300,
        }
    
    @staticmethod
    def standard():
        """Standard-Optimierung (1 Woche, 3 Szenarien)"""
        return {
            'hours': 168,
            'scenarios': SCENARIOS_CONFIG['standard'],
            'mip_gap': 0.05,
            'time_limit': 1800,
        }
    
    @staticmethod
    def detailed():
        """Detaillierte Optimierung (1 Monat, enge Toleranz)"""
        return {
            'hours': 720,
            'scenarios': SCENARIOS_CONFIG['standard'],
            'mip_gap': 0.01,
            'time_limit': 3600,
        }
    
    @staticmethod
    def annual():
        """Jahres-Optimierung (8760 h, konservative Szenarien)"""
        return {
            'hours': 8760,
            'scenarios': SCENARIOS_CONFIG['conservative'],
            'mip_gap': 0.02,
            'time_limit': 7200,  # 2 Stunden
        }


# ==================== Anwendungsbeispiele ====================

"""
# Beispiel 1: Standard-Konfiguration verwenden
from config import HeatPumpConfig, StorageConfig, SimulationConfig

HP_FIXED_CAPACITY_MW = HeatPumpConfig.FIXED_CAPACITY_MW
HOURS_TO_SIMULATE = SimulationConfig.HOURS_TO_SIMULATE

# Beispiel 2: Parameter überschreiben
HeatPumpConfig.FIXED_CAPACITY_MW = 1.2  # 1.2 MW statt 0.6 MW
StorageConfig.E_NOM_MAX_MWH = 50.0  # Größerer Speicher erlaubt

# Beispiel 3: Preset verwenden
preset = PresetConfigurations.quick_test()
HOURS_TO_SIMULATE = preset['hours']
SCENARIOS = preset['scenarios']
MIP_GAP = preset['mip_gap']

# Beispiel 4: Kosten-Sensitivitätsanalyse
for electricity_price in [60, 80, 100, 120]:
    NetworkConfig.GRID_ELECTRICITY_PRICE_EUR_MWH = electricity_price
    # Run optimization...
    # Analyze how optimal storage size changes with price

# Beispiel 5: WP-Kapazitäts-Variation
for hp_capacity in [0.4, 0.6, 0.8, 1.0, 1.2]:
    HeatPumpConfig.FIXED_CAPACITY_MW = hp_capacity
    # Run optimization...
    # Find optimal storage size for each HP capacity
"""


# ==================== Validierung ====================

def validate_configuration():
    """Prüft die Konfiguration auf Plausibilität"""
    
    errors = []
    warnings = []
    
    # WP-Kapazität
    if HeatPumpConfig.FIXED_CAPACITY_MW <= 0:
        errors.append("WP-Kapazität muss positiv sein")
    if HeatPumpConfig.FIXED_CAPACITY_MW > 10:
        warnings.append(f"Große WP-Kapazität: {HeatPumpConfig.FIXED_CAPACITY_MW} MW")
    
    # Speicher-Grenzen
    if StorageConfig.E_NOM_MIN_MWH >= StorageConfig.E_NOM_MAX_MWH:
        errors.append("Speicher E_MIN muss kleiner als E_MAX sein")
    
    # Teillast
    if not 0 < HeatPumpConfig.MIN_PART_LOAD <= 1:
        errors.append("Teillast muss zwischen 0 und 1 liegen")
    
    # Szenarien-Gewichte
    total_weight = sum(s['weight'] for s in SCENARIOS_CONFIG[ACTIVE_SCENARIO_SET].values())
    if abs(total_weight - 1.0) > 0.01:
        errors.append(f"Szenarien-Gewichte müssen 1.0 ergeben (aktuell: {total_weight})")
    
    # Output
    if errors:
        print("❌ Konfigurationsfehler:")
        for e in errors:
            print(f"  - {e}")
        return False
    
    if warnings:
        print("⚠️  Warnungen:")
        for w in warnings:
            print(f"  - {w}")
    
    print("✅ Konfiguration ist valide")
    return True


if __name__ == "__main__":
    print("="*70)
    print("KONFIGURATIONSÜBERSICHT")
    print("="*70)
    
    print("\n🔧 Wärmepumpe:")
    for k, v in HeatPumpConfig.get_config_dict().items():
        print(f"  {k}: {v}")
    
    print("\n🔋 Speicher:")
    for k, v in StorageConfig.get_config_dict().items():
        print(f"  {k}: {v}")
    
    print("\n🔌 Netzwerk:")
    for k, v in NetworkConfig.get_config_dict().items():
        print(f"  {k}: {v}")
    
    print("\n⚙️  Simulation:")
    for k, v in SimulationConfig.get_config_dict().items():
        print(f"  {k}: {v}")
    
    print(f"\n🌍 Szenarien ({ACTIVE_SCENARIO_SET}):")
    for name, cfg in SCENARIOS_CONFIG[ACTIVE_SCENARIO_SET].items():
        print(f"  {name}: {cfg['weight']:.0%} - {cfg['description']}")
    
    print("\n" + "="*70)
    validate_configuration()
    print("="*70)
