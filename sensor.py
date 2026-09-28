"""Sensor platform for GeliosPro integration."""
import logging

from homeassistant.components.sensor import SensorEntity
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, CONF_ALL_UNITS

_LOGGER = logging.getLogger(__name__)


# field -> (json paths, icon, unit, device_class, state_class, is_numeric)
SENSOR_DEFS = {
    "lat":     (["lmsg.lat", "position.lat", "lat", "latitude"],
                "mdi:latitude", None, None, None, True),
    "lon":     (["lmsg.lon", "position.lon", "lon", "lng", "longitude"],
                "mdi:longitude", None, None, None, True),
    "speed":   (["lmsg.speed", "position.speed", "speed", "telemetry.speed"],
                "mdi:speedometer", "km/h", None, "measurement", True),
    "course":  (["lmsg.course", "position.course", "course", "direction"],
                "mdi:compass", "deg", None, "measurement", True),
    "sats":    (["lmsg.sats", "position.sats", "sats", "satellites"],
                "mdi:satellite-variant", None, None, "measurement", True),
    "alt":     (["lmsg.height", "position.alt", "alt", "altitude", "height"],
                "mdi:elevation-rise", "m", None, "measurement", True),
    "voltage": (["lmsg.voltage", "voltage", "telemetry.voltage"],
                "mdi:car-battery", "V", "voltage", "measurement", True),
    "address": (["lmsg.address", "address", "position.address"],
                "mdi:map-marker", None, None, None, False),
    "fuel":    (["fuel", "telemetry.fuel", "fuel.level"],
                "mdi:fuel", None, None, "measurement", True),
}


def _extract(data, paths):
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


def _to_number(val):
    try:
        f = float(val)
        return int(f) if f.is_integer() else f
    except (TypeError, ValueError):
        return val


async def async_setup_entry(hass, config_entry, async_add_entities):
    coordinator = hass.data[DOMAIN][config_entry.entry_id]
    all_units = config_entry.data.get(CONF_ALL_UNITS, {})

    entities = []
    for uid in coordinator.unit_ids:
        name = all_units.get(str(uid), str(uid))
        for attr in SENSOR_DEFS:
            entities.append(GeliosSensor(coordinator, uid, name, attr))

    async_add_entities(entities, update_before_add=True)


class GeliosSensor(CoordinatorEntity, RestoreEntity, SensorEntity):
    """One field of one Gelios unit."""

    def __init__(self, coordinator, unit_id, unit_name, attr):
        super().__init__(coordinator)
        self._unit_id = str(unit_id)
        self._attr = attr
        paths, icon, unit, device_class, state_class, is_numeric = SENSOR_DEFS[attr]

        self._paths = paths
        self._is_numeric = is_numeric
        self._attr_name = f"{unit_name} {attr}"
        self._attr_unique_id = f"gelios_{self._unit_id}_{attr}"
        self._attr_icon = icon
        if unit:
            self._attr_native_unit_of_measurement = unit
        if device_class:
            self._attr_device_class = device_class
        if state_class:
            self._attr_state_class = state_class
        self._restored_value = None

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        last = await self.async_get_last_state()
        if last is not None and last.state not in (None, "unknown", "unavailable"):
            self._restored_value = last.state

    @property
    def native_value(self):
        data = (self.coordinator.data or {}).get(self._unit_id)
        if data:
            val = _extract(data, self._paths)
            if val is not None:
                return _to_number(val) if self._is_numeric else val
        return self._restored_value

    @property
    def available(self) -> bool:
        return (
            self.coordinator.last_update_success
            or self.coordinator.data is not None
            or self._restored_value is not None
        )

    @property
    def device_info(self):
        return {
            "identifiers": {("gelios_tracker", self._unit_id)},
            "name": self._attr_name.rsplit(" ", 1)[0],
            "manufacturer": "GeliosPro",
            "model": "GPS Tracker",
        }