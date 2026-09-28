"""DataUpdateCoordinator for the GeliosPro integration."""
import json
import logging
from datetime import timedelta

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.const import CONF_USERNAME, CONF_PASSWORD

from .const import (
    DOMAIN,
    API_BASE_URL,
    CONF_UNITS,
    DEFAULT_SCAN_INTERVAL,
    STORAGE_KEY,
    STORAGE_VERSION,
)

_LOGGER = logging.getLogger(__name__)


class GeliosDataUpdateCoordinator(DataUpdateCoordinator):
    """Polls API for all selected unit_id, persists last good data."""

    def __init__(self, hass: HomeAssistant, config_entry):
        self.username = config_entry.data[CONF_USERNAME]
        self.password = config_entry.data[CONF_PASSWORD]
        self.unit_ids = [str(u) for u in config_entry.data[CONF_UNITS]]
        self._store = Store(hass, STORAGE_VERSION, STORAGE_KEY)

        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_{config_entry.entry_id}",
            update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL),
        )

    # ---------- Persistence ----------
    async def async_load_stored(self) -> None:
        """Load last known data from disk before first refresh."""
        try:
            stored = await self._store.async_load()
        except Exception as err:  # noqa: BLE001
            _LOGGER.warning("Failed to load stored Gelios data: %s", err)
            return

        if not isinstance(stored, dict):
            return

        # Only keep data for currently selected units
        filtered = {
            uid: stored[uid] for uid in self.unit_ids if uid in stored
        }
        if filtered:
            self.data = filtered
            _LOGGER.info(
                "Restored last known Gelios data for %d unit(s)", len(filtered)
            )

    async def _async_save_stored(self, data: dict) -> None:
        try:
            await self._store.async_save(data)
        except Exception as err:  # noqa: BLE001
            _LOGGER.warning("Failed to save Gelios data: %s", err)

    # ---------- Update loop ----------
    async def _async_update_data(self):
        """Fetch fresh data; keep previous one if the API fails."""
        session = async_get_clientsession(self.hass)
        result = {}

        for uid in self.unit_ids:
            params = {"id_unit": int(uid)}
            query = {
                "login": self.username,
                "pass": self.password,
                "svc": "get_unit_info",
                "params": json.dumps(params, separators=(",", ":")),
            }
            try:
                async with session.get(
                    API_BASE_URL, params=query, timeout=20
                ) as resp:
                    if resp.status != 200:
                        _LOGGER.warning(
                            "Gelios get_unit_info %s: HTTP %s", uid, resp.status
                        )
                        continue
                    data = await resp.json(content_type=None)
                    if isinstance(data, list) and data:
                        data = data[0]
                    if isinstance(data, dict):
                        result[uid] = data
            except Exception as err:  # noqa: BLE001
                _LOGGER.error("Error fetching unit %s: %s", uid, err)

        # Merge with previously cached values so units that failed this
        # round keep their last known data.
        previous = self.data if isinstance(self.data, dict) else {}
        merged = {**previous, **result}

        if result:
            await self._async_save_stored(merged)
            return merged

        # Nothing fresh came back. If we have any cache, use it.
        if merged:
            _LOGGER.warning(
                "Gelios API returned no data; using cached values for %d unit(s)",
                len(merged),
            )
            return merged

        # First run + API down + no cache = fail (HA will show unavailable)
        raise UpdateFailed("No data received and no cached data available")