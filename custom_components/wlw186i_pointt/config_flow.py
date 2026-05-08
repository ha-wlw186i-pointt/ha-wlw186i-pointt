"""Config flow and options flow for the WLW186i Pointt integration.

Because the Bosch SingleKey-ID OAuth2 server only accepts the MyBuderus app's
custom-scheme redirect URI, we cannot use Home Assistant's built-in OAuth2
redirect mechanism.  Instead we implement a two-step "paste the URL" flow:

  1. We generate the authorization URL (with PKCE) and show it to the user.
  2. The user logs in, gets a "can't reach this site" page, copies the URL
     from the browser address bar, and pastes it into a text field.

This is the same approach used by the standalone test client.
"""

from __future__ import annotations

import base64
import hashlib
import logging
import secrets
from typing import Any
from urllib.parse import parse_qs, urlencode, urlparse

import aiohttp
import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import PointtApiClient, PointtAuthError, async_exchange_code
from .const import (
    CLIENT_ID,
    CONF_ACCESS_TOKEN,
    CONF_EXPIRES_AT,
    CONF_GATEWAY_ID,
    CONF_GATEWAY_TYPE,
    CONF_REFRESH_TOKEN,
    CONF_SCAN_INTERVAL,
    CONF_TOKEN_TYPE,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    MAX_SCAN_INTERVAL,
    MIN_SCAN_INTERVAL,
    OIDC_AUTHORIZE_URL,
    REDIRECT_URI,
    SCOPES,
    STYLE_ID,
)

_LOGGER = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# PKCE helpers
# ---------------------------------------------------------------------------

def _generate_pkce_pair() -> tuple[str, str]:
    """Generate a PKCE code_verifier and code_challenge (S256)."""
    code_verifier = secrets.token_urlsafe(64)[:128]
    digest = hashlib.sha256(code_verifier.encode("ascii")).digest()
    code_challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
    return code_verifier, code_challenge


def _build_auth_url(state: str, code_challenge: str) -> str:
    """Build the SingleKey-ID authorization URL."""
    params = {
        "response_type": "code",
        "client_id": CLIENT_ID,
        "redirect_uri": REDIRECT_URI,
        "scope": " ".join(SCOPES),
        "state": state,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
        "prompt": "login",
        "style_id": STYLE_ID,
    }
    return f"{OIDC_AUTHORIZE_URL}?{urlencode(params)}"


def _parse_callback_url(url_string: str) -> tuple[str | None, str | None]:
    """Extract authorization code and state from the callback URL.

    Returns ``(code, state)`` — either may be ``None``.
    """
    url_string = url_string.strip()
    parsed = urlparse(url_string)
    params = parse_qs(parsed.query)

    # Fallback: some browsers mangle the custom-scheme URL
    if "code" not in params and "code=" in url_string:
        idx = url_string.find("?")
        if idx != -1:
            params = parse_qs(url_string[idx + 1 :])

    code = params.get("code", [None])[0]
    state = params.get("state", [None])[0]
    return code, state


# ---------------------------------------------------------------------------
# Config flow
# ---------------------------------------------------------------------------

class WLW186iPointtConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for WLW186i Pointt."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialise flow-scoped state."""
        self._state: str | None = None
        self._code_verifier: str | None = None
        self._code_challenge: str | None = None
        self._reauth_entry: ConfigEntry | None = None

    # Step 1 — show the auth URL to the user
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Generate auth URL and present it to the user."""
        self._state = secrets.token_urlsafe(32)
        self._code_verifier, self._code_challenge = _generate_pkce_pair()
        auth_url = _build_auth_url(self._state, self._code_challenge)

        # Store the URL so the template can render it
        self.context["auth_url"] = auth_url

        return self.async_show_form(
            step_id="callback",
            data_schema=vol.Schema(
                {vol.Required("callback_url"): str}
            ),
            description_placeholders={"auth_url": auth_url},
        )

    # Step 2 — user pastes the callback URL
    async def async_step_callback(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Parse the pasted callback URL and exchange the code for tokens."""
        errors: dict[str, str] = {}

        if user_input is not None:
            code, cb_state = _parse_callback_url(user_input["callback_url"])

            if not code:
                errors["callback_url"] = "invalid_url"
            else:
                if cb_state and cb_state != self._state:
                    _LOGGER.warning("OAuth state mismatch (expected %s, got %s)", self._state, cb_state)

                session = async_get_clientsession(self.hass)
                try:
                    tokens = await async_exchange_code(
                        session, code, REDIRECT_URI, self._code_verifier
                    )
                except PointtAuthError as err:
                    _LOGGER.error("Token exchange failed: %s", err)
                    errors["callback_url"] = "token_exchange_failed"
                else:
                    # Discover gateways
                    return await self._async_discover_gateway(session, tokens)

        # Re-show the form (with or without errors)
        auth_url = _build_auth_url(self._state, self._code_challenge)
        return self.async_show_form(
            step_id="callback",
            data_schema=vol.Schema(
                {vol.Required("callback_url"): str}
            ),
            description_placeholders={"auth_url": auth_url},
            errors=errors,
        )

    async def _async_discover_gateway(
        self,
        session: aiohttp.ClientSession,
        tokens: dict[str, Any],
    ) -> ConfigFlowResult:
        """Use the new tokens to find and select the best gateway."""
        client = PointtApiClient(
            session=session,
            access_token=tokens["access_token"],
            refresh_token=tokens.get("refresh_token", ""),
            expires_at=tokens.get("expires_at", 0),
        )

        try:
            gateway_id, gateway_type = await client.async_select_gateway()
        except Exception as err:
            _LOGGER.error("Gateway discovery failed: %s", err)
            return self.async_abort(reason="no_gateway")

        new_data = {
            CONF_ACCESS_TOKEN: tokens["access_token"],
            CONF_REFRESH_TOKEN: tokens.get("refresh_token", ""),
            CONF_EXPIRES_AT: tokens.get("expires_at", 0),
            CONF_TOKEN_TYPE: tokens.get("token_type", "Bearer"),
            CONF_GATEWAY_ID: gateway_id,
            CONF_GATEWAY_TYPE: gateway_type,
        }

        # Reauth flow: update the existing entry with fresh tokens and reload
        if self._reauth_entry is not None:
            return self.async_update_reload_and_abort(
                self._reauth_entry,
                data=new_data,
            )

        # Normal first-time setup: prevent duplicate entries
        await self.async_set_unique_id(gateway_id)
        self._abort_if_unique_id_configured()

        return self.async_create_entry(
            title=f"WLW186i ({gateway_id})",
            data=new_data,
            options={CONF_SCAN_INTERVAL: DEFAULT_SCAN_INTERVAL},
        )

    # -- Re-authentication --------------------------------------------------

    async def async_step_reauth(
        self, entry_data: dict[str, Any]
    ) -> ConfigFlowResult:
        """Handle re-authentication when the refresh token has expired."""
        self._reauth_entry = self.hass.config_entries.async_get_entry(
            self.context["entry_id"]
        )
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask the user to re-authenticate."""
        if user_input is not None:
            return await self.async_step_user()
        return self.async_show_form(step_id="reauth_confirm")

    # -- Options flow -------------------------------------------------------

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """Return the options flow handler."""
        return WLW186iPointtOptionsFlow()


class WLW186iPointtOptionsFlow(OptionsFlow):
    """Handle options for WLW186i Pointt."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(data=user_input)

        current_interval = self.config_entry.options.get(
            CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
        )

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_SCAN_INTERVAL,
                        default=current_interval,
                    ): vol.All(
                        vol.Coerce(int),
                        vol.Range(min=MIN_SCAN_INTERVAL, max=MAX_SCAN_INTERVAL),
                    ),
                }
            ),
        )
