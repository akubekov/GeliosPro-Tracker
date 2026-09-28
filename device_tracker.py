"""Device tracker platform for GeliosPro integration."""
from __future__ import annotations

import logging

from homeassistant.components.device_tracker import (
    SourceType,
    TrackerEntity,
)
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, CONF_ALL_UNITS

_LOGGER = logging.getLogger(__name__)


def _extract(data: dict, paths: list[str]):
    for path in paths:
        cur = data
        ok = True
        for part in path.split("."):
            if isinstance(cur, dict) and part in cur:
                cur = cur[part]
            else:
                ok = False
                break
        if ok and cur is not None:
            return cur
    return None


def _to_float(val):
    try:
        return float(val) if val is not None else None
    except (TypeError, ValueError):
        return None


async def async_setup_entry(hass, config_entry, async_add_entities):
    coordinator = hass.data[DOMAIN][config_entry.entry_id]
    all_units = config_entry.data.get(CONF_ALL_UNITS, {})

    entities = []
    for uid in coordinator.unit_ids:
        name = all_units.get(str(uid), str(uid))
        entities.append(GeliosTracker(coordinator, uid, name))

    async_add_entities(entities, update_before_add=True)


class GeliosTracker(CoordinatorEntity, RestoreEntity, TrackerEntity):
    """GPS tracker entity for a single Gelios unit."""

    _attr_has_entity_name = False
    _attr_source_type = SourceType.GPS

    def __init__(self, coordinator, unit_id, unit_name):
        super().__init__(coordinator)
        self._unit_id = str(unit_id)
        self._unit_name = unit_name
        self._attr_name = unit_name
        self._attr_unique_id = f"gelios_tracker_{self._unit_id}"
        self._restored_lat = None
        self._restored_lon = None
        self._restored_attrs: dict = {}

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        last = await self.async_get_last_state()
        if last is None:
            return
        self._restored_lat = _to_float(last.attributes.get("latitude"))
        self._restored_lon = _to_float(last.attributes.get("longitude"))
        self._restored_attrs = {
            k: v for k, v in last.attributes.items()
            if k not in ("latitude", "longitude", "source_type", "friendly_name")
        }

    # ---------- Coordinates ----------
    @property
    def latitude(self) -> float | None:
        data = (self.coordinator.data or {}).get(self._unit_id)
        if data:
            val = _to_float(_extract(data, ["lmsg.lat", "position.lat", "lat", "latitude"]))
            if val is not None:
                return val
        return self._restored_lat

    @property
    def longitude(self) -> float | None:
        data = (self.coordinator.data or {}).get(self._unit_id)
        if data:
            val = _to_float(_extract(data, ["lmsg.lon", "position.lon", "lon", "lng", "longitude"]))
            if val is not None:
                return val
        return self._restored_lon

    # ---------- Extra attributes ----------
    @property
    def extra_state_attributes(self) -> dict:
        data = (self.coordinator.data or {}).get(self._unit_id)

        if not data:
            return dict(self._restored_attrs)

        def gv(paths):
            return _extract(data, paths)

        # address is at the top of lmsg; decode the escaped unicode is not
        # needed because HA handles it via json parser already.
        attrs = {
            "unit_id": self._unit_id,
            "address": gv(["lmsg.address", "address"]),
            "speed": gv(["lmsg.speed", "position.speed", "speed"]),
            "course": gv(["lmsg.course", "position.course", "course", "direction"]),
            "altitude": gv(["lmsg.height", "position.alt", "alt", "altitude", "height"]),
            "sats": gv(["lmsg.sats", "position.sats", "sats", "satellites"]),
            "last_update": gv(["lmsg.time", "lmsg.receive_time"]),
            "voltage": gv(["lmsg.voltage", "voltage", "telemetry.voltage"]),
        }
        return {k: v for k, v in attrs.items() if v is not None}

    @property
    def available(self) -> bool:
        return (
            self.coordinator.last_update_success
            or self.coordinator.data is not None
            or self._restored_lat is not None
        )

    @property
    def device_info(self):
        return {
            "identifiers": {("gelios_tracker", self._unit_id)},
            "name": self._unit_name,
            "manufacturer": "GeliosPro",
            "model": "GPS Tracker",
        }