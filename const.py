"""Constants for the GeliosPro integration."""

DOMAIN = "gelios_tracker"

CONF_USERNAME = "username"
CONF_PASSWORD = "password"
CONF_UNITS = "units"            # list of selected unit_id (strings)
CONF_ALL_UNITS = "all_units"    # {id: name} for display

DEFAULT_SCAN_INTERVAL = 300     # seconds between polls
API_BASE_URL = "https://admin.geliospro.com/sdk/"

# Persistent storage for last known good data
STORAGE_VERSION = 1
STORAGE_KEY = f"{DOMAIN}.last_data"