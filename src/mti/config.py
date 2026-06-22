"""Project constants — datasets, thresholds, and schema names."""

from datetime import date

# Analysis window (align STM + weather; drop incomplete current month in analysis)
ANALYSIS_START = date(2019, 1, 1)

STM_CSV_URL = "https://donneesouvertes.stm.info/fichiers/Incidents%20m%C3%A9tro.csv"
STM_CSV_FILENAME = "stm_incidents_metro.csv"
STM_ENCODING = "cp1252"
STM_DELIMITER = ";"

# Montreal Intl A (YUL) — StationID 51157, Climate ID 7025251
WEATHER_STN_ID = 51157
WEATHER_CLIMATE_ID = "7025251"
WEATHER_API_BASE = "https://api.weather.gc.ca/collections/climate-daily/items"
WEATHER_CSV_FILENAME = "weather_yul_daily.csv"

# French CSV headers are mapped by column position for Delta-safe bronze tables.
STM_RAW_COLUMNS = [
    "incident_id",
    "incident_type",
    "cause_primary",
    "cause_secondary",
    "symptom",
    "line",
    "tour_number",
    "time_start",
    "time_end",
    "duration_text",
    "vehicle",
    "car_door",
    "material_type",
    "location_code",
    "material_damage",
    "kfs",
    "door",
    "metro_emergency",
    "cat",
    "evacuation",
    "calendar_year",
    "calendar_year_month",
    "calendar_month",
    "day_of_month",
    "day_of_week",
    "calendar_date",
]

# Logical field names used in silver/gold (Delta-safe English names)
STM_COLS = {
    "incident_id": "incident_id",
    "incident_type": "incident_type",
    "cause_primary": "cause_primary",
    "symptom": "symptom",
    "line": "line",
    "time_start": "time_start",
    "time_end": "time_end",
    "duration_text": "duration_text",
    "calendar_date": "calendar_date",
}

# French headers in the raw CSV (pandas local reads only)
STM_CSV_HEADERS = {
    "incident_id": "Numero d'incident",
    "incident_type": "Type d'incident",
    "cause_primary": "Cause primaire",
    "symptom": "Symptome",
    "line": "Ligne",
    "time_start": "Heure de l'incident",
    "time_end": "Heure de reprise",
    "duration_text": "Incident en minutes",
    "calendar_date": "Jour calendaire",
}

LINE_MAP = {
    "Ligne verte": (1, "Green"),
    "Ligne orange": (2, "Orange"),
    "Ligne jaune": (4, "Yellow"),
    "Ligne bleue": (5, "Blue"),
}

# Weather derived-flag thresholds (document in FINDINGS.md)
SNOW_DAY_CM = 5.0
HEAVY_RAIN_MM = 15.0
COLD_SNAP_MAX_C = -15.0

# Unity Catalog volume (Databricks Free Edition — /FileStore is disabled)
# Free Edition often uses catalog "workspace", not "main"
UC_CATALOGS = ("workspace", "main")
UC_SCHEMA = "default"
UC_VOLUME = "mti"

DELTA_TABLES = {
    "raw_stm": ("bronze", "raw_stm_incidents"),
    "raw_weather": ("bronze", "raw_weather_daily"),
    "clean_stm": ("silver", "clean_stm_incidents"),
    "clean_weather": ("silver", "clean_weather_daily"),
    "fact_daily": ("gold", "fact_incidents_daily"),
    "fact_by_line": ("gold", "fact_incidents_by_line_daily"),
    "fact_weather": ("gold", "fact_weather_daily"),
    "fact_joined": ("gold", "fact_incidents_weather_daily"),
}
