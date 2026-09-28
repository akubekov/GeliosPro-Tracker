"""Config flow for GeliosPro integration."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_USERNAME, CONF_PASSWORD
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    SelectOptionDict,
)

from .const import DOMAIN, API_BASE_URL, CONF_UNITS, CONF_ALL_UNITS

_LOGGER = logging.getLogger(__name__)


class GeliosConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow for GeliosPro."""

    VERSION = 2

    def __init__(self) -> None:
        self._username: str | None = None
        self._password: str | None = None
        self._all_units: dict[str, str] = {}

    # Step 1: credentials
    async def async_step_user(self, user_input: dict[str, Any] | None = None):
        errors: dict[str, str] = {}

        if user_input is not None:
            self._username = user_input[CONF_USERNAME]
            self._password = user_input[CONF_PASSWORD]

            units = await self._fetch_units()
            if units is None:
                errors["base"] = "invalid_auth"
            elif not units:
                errors["base"] = "no_units"
            else:
                self._all_units = units
                return await self.async_step_select()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_USERNAME): str,
                    vol.Required(CONF_PASSWORD): str,
                }
            ),
            errors=errors,
        )

    # Step 2: unit selection
    async def async_step_select(self, user_input: dict[str, Any] | None = None):
        if user_input is not None:
            selected = user_input.get(CONF_UNITS) or []
            if isinstance(selected, str):
                selected = [selected]
            if not selected:
                return self.async_show_form(
                    step_id="select",
                    data_schema=self._select_schema(),
                    errors={"base": "no_selection"},
                )

            data = {
                CONF_USERNAME: self._username,
                CONF_PASSWORD: self._password,
                CONF_UNITS: selected,
                CONF_ALL_UNITS: self._all_units,
            }
            return self.async_create_entry(
                title=f"GeliosPro ({len(selected)} unit(s))", data=data
            )

        return self.async_show_form(
            step_id="select",
            data_schema=self._select_schema(),
        )

    def _select_schema(self) -> vol.Schema:
        """Multi-select schema using SelectSelector."""
        options: list[SelectOptionDict] = [
            SelectOptionDict(value=uid, label=f"{name} (id={uid})")
            for uid, name in self._all_units.items()
        ]
        return vol.Schema(
            {
                vol.Required(CONF_UNITS): SelectSelector(
                    SelectSelectorConfig(
                        options=options,
                        multiple=True,
                        mode=SelectSelectorMode.LIST,
                    )
                )
            }
        )

    async def _fetch_units(self) -> dict[str, str] | None:
        """Return {str(id): name} or None on error."""
        session = async_get_clientsession(self.hass)
        query = {
            "login": self._username,
            "pass": self._password,
            "svc": "get_units",
            "params": "{}",
        }
        try:
            async with session.get(API_BASE_URL, params=query, timeout=20) as resp:
                if resp.status != 200:
                    _LOGGER.warning("Gelios get_units: HTTP %s", resp.status)
                    return None
                data = await resp.json(content_type=None)
                if not isinstance(data, list):
                    _LOGGER.warning("Unexpected get_units response: %s", data)
                    return None
                return {
                    str(u["id"]): u.get("name", str(u["id"]))
                    for u in data
                    if isinstance(u, dict) and "id" in u
                }
        except Exception as err:  # noqa: BLE001
            _LOGGER.error("Error fetching Gelios units: %s", err)
            return None