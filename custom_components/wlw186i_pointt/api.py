"""Async API client for the Bosch/Buderus Pointt API.

Communicates with heat pump gateways (K40RF, etc.) via the Bosch cloud.
Uses aiohttp for non-blocking HTTP and implements the bulk API with
small-batch fetching and retry logic required by wireless gateways.
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Callable
from typing import Any
from urllib.parse import urlencode

import aiohttp

from .const import (
    BULK_BATCH_SIZE,
    BULK_INTER_BATCH_DELAY,
    BULK_RETRY_DELAY,
    CLIENT_ID,
    OIDC_TOKEN_URL,
    POINTT_BASE_URL,
    PREFERRED_GATEWAY_TYPES,
)

_LOGGER = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class PointtApiError(Exception):
    """Generic Pointt API error."""


class PointtAuthError(PointtApiError):
    """Authentication/authorization failure (token expired, revoked, etc.)."""


class PointtTokenExpiredError(PointtAuthError):
    """Refresh token is permanently expired or revoked — user must re-auth."""


class PointtGatewayTimeoutError(PointtApiError):
    """All paths in a batch returned 504."""


# ---------------------------------------------------------------------------
# Token refresh tuning
# ---------------------------------------------------------------------------
_TOKEN_REFRESH_MAX_ATTEMPTS: int = 3
_TOKEN_REFRESH_RETRY_DELAYS: tuple[int, ...] = (5, 15)


# ---------------------------------------------------------------------------
# Token helpers
# ---------------------------------------------------------------------------

async def async_refresh_token(
    session: aiohttp.ClientSession,
    refresh_token: str,
) -> dict[str, Any]:
    """Exchange a refresh token for a new access + refresh token pair.

    Returns the raw token response dict with an added ``expires_at`` field
    (epoch float).

    Raises ``PointtAuthError`` on failure.
    """
    data = {
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
        "client_id": CLIENT_ID,
    }
    headers = {"Content-Type": "application/x-www-form-urlencoded"}

    async with session.post(
        OIDC_TOKEN_URL, data=urlencode(data), headers=headers
    ) as resp:
        body = await resp.json(content_type=None)
        if resp.status != 200:
            error_code = body.get("error", "")
            description = body.get("error_description", error_code)
            _LOGGER.error("Token refresh failed (%s): %s", resp.status, body)
            # "invalid_grant" means the refresh token is expired or revoked
            # — no amount of retrying will help.
            if error_code == "invalid_grant":
                raise PointtTokenExpiredError(
                    f"Refresh token expired or revoked: {description}"
                )
            raise PointtAuthError(
                f"Token refresh failed ({resp.status}): {description}"
            )
        body["expires_at"] = time.time() + body.get("expires_in", 3600)
        return body


async def async_exchange_code(
    session: aiohttp.ClientSession,
    code: str,
    redirect_uri: str,
    code_verifier: str,
) -> dict[str, Any]:
    """Exchange an authorization code for tokens (PKCE flow).

    Returns the raw token response dict with an added ``expires_at`` field.

    Raises ``PointtAuthError`` on failure.
    """
    data = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": redirect_uri,
        "client_id": CLIENT_ID,
        "code_verifier": code_verifier,
    }
    headers = {"Content-Type": "application/x-www-form-urlencoded"}

    async with session.post(
        OIDC_TOKEN_URL, data=urlencode(data), headers=headers
    ) as resp:
        body = await resp.json(content_type=None)
        if resp.status != 200:
            _LOGGER.error("Token exchange failed (%s): %s", resp.status, body)
            raise PointtAuthError(
                f"Token exchange failed ({resp.status}): "
                f"{body.get('error_description', body.get('error', ''))}"
            )
        body["expires_at"] = time.time() + body.get("expires_in", 3600)
        return body


# ---------------------------------------------------------------------------
# API client
# ---------------------------------------------------------------------------

class PointtApiClient:
    """Async client for the Bosch/Buderus Pointt REST API."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        access_token: str,
        refresh_token: str,
        expires_at: float,
    ) -> None:
        self._session = session
        self._access_token = access_token
        self._refresh_token = refresh_token
        self._expires_at = expires_at
        self._token_lock = asyncio.Lock()
        # Callback set by the coordinator to persist refreshed tokens
        self.on_token_refresh: Callable[[dict[str, Any]], Any] | None = None

    # -- Token management ---------------------------------------------------

    @property
    def access_token(self) -> str:
        return self._access_token

    @property
    def refresh_token(self) -> str:
        return self._refresh_token

    @property
    def expires_at(self) -> float:
        return self._expires_at

    async def async_ensure_token_valid(self) -> None:
        """Refresh the access token if it is expired or about to expire."""
        if time.time() < self._expires_at - 60:
            return  # still valid

        async with self._token_lock:
            # Re-check after acquiring the lock — another coroutine may have
            # already refreshed while we were waiting.
            if time.time() < self._expires_at - 60:
                return
            await self._do_token_refresh()

    async def async_force_token_refresh(self) -> None:
        """Force a token refresh regardless of current expiry time.

        Used after receiving a 401 from the API, which indicates the access
        token was invalidated server-side before its normal expiry.
        """
        async with self._token_lock:
            await self._do_token_refresh()

    async def _do_token_refresh(self) -> None:
        """Perform the actual token refresh with retries.

        Retries on transient errors (server errors, network issues) but
        propagates ``PointtTokenExpiredError`` immediately since retrying
        an expired/revoked refresh token is pointless.
        """
        last_err: PointtAuthError | None = None

        for attempt in range(_TOKEN_REFRESH_MAX_ATTEMPTS):
            try:
                tokens = await async_refresh_token(
                    self._session, self._refresh_token
                )
            except PointtTokenExpiredError:
                raise  # permanent — retrying won't help
            except PointtAuthError as err:
                last_err = err
                if attempt < _TOKEN_REFRESH_MAX_ATTEMPTS - 1:
                    delay = _TOKEN_REFRESH_RETRY_DELAYS[attempt]
                    _LOGGER.warning(
                        "Token refresh attempt %d/%d failed, retrying in %ds: %s",
                        attempt + 1,
                        _TOKEN_REFRESH_MAX_ATTEMPTS,
                        delay,
                        err,
                    )
                    await asyncio.sleep(delay)
                    continue
                _LOGGER.error(
                    "Token refresh failed after %d attempts: %s",
                    _TOKEN_REFRESH_MAX_ATTEMPTS,
                    err,
                )
                raise
            else:
                # Success — update in-memory tokens
                old_rt = self._refresh_token
                self._access_token = tokens["access_token"]
                # Guard: ignore null / empty refresh tokens from the server
                self._refresh_token = (
                    tokens.get("refresh_token") or self._refresh_token
                )
                self._expires_at = tokens["expires_at"]

                if self._refresh_token != old_rt:
                    _LOGGER.debug("Refresh token was rotated by the server")

                if self.on_token_refresh:
                    await self.on_token_refresh(tokens)
                return

        # Should not be reached, but just in case
        if last_err:
            raise last_err

    def _auth_headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._access_token}",
            "Content-Type": "application/json",
        }

    # -- Gateway listing ----------------------------------------------------

    async def async_get_gateways(self) -> list[dict[str, Any]]:
        """Return the list of gateways registered on this account.

        Raises ``PointtAuthError`` on 401 and ``PointtApiError`` on other
        HTTP errors.
        """
        await self.async_ensure_token_valid()
        url = f"{POINTT_BASE_URL}gateways/"
        async with self._session.get(url, headers=self._auth_headers()) as resp:
            if resp.status == 401:
                raise PointtAuthError("Unauthorized (401) listing gateways")
            if resp.status != 200:
                text = await resp.text()
                raise PointtApiError(
                    f"GET /gateways/ returned {resp.status}: {text}"
                )
            return await resp.json(content_type=None)

    async def async_select_gateway(self) -> tuple[str, str]:
        """Discover gateways and pick the best one (prefers K40/ConnectKey).

        Returns ``(gateway_id, device_type)``.

        Raises ``PointtApiError`` if no gateways are found.
        """
        gateways = await self.async_get_gateways()
        if not gateways:
            raise PointtApiError("No gateways found on this account")

        for gw in gateways:
            dt = gw.get("deviceType", "").lower()
            if any(pref in dt for pref in PREFERRED_GATEWAY_TYPES):
                return gw["deviceId"], gw.get("deviceType", "unknown")

        # Fallback to the first gateway
        gw = gateways[0]
        return gw["deviceId"], gw.get("deviceType", "unknown")

    # -- Bulk API -----------------------------------------------------------

    async def async_bulk_get(
        self,
        gateway_id: str,
        resource_paths: list[str],
        *,
        skip_retries: bool = False,
    ) -> dict[str, Any]:
        """Fetch multiple resource paths via ``POST /bulk``.

        Uses small batches (default 5 paths) with inter-batch delays to avoid
        overloading the K40RF wireless gateway.  Paths that return 504 are
        retried once after a longer delay unless *skip_retries* is set.

        Returns a dict mapping each resource path to its payload dict, or
        ``None`` if the path returned 404, or an error-dict on failure.
        """
        await self.async_ensure_token_valid()

        results: dict[str, Any] = {}
        retry_paths: list[str] = []

        batches = [
            resource_paths[i : i + BULK_BATCH_SIZE]
            for i in range(0, len(resource_paths), BULK_BATCH_SIZE)
        ]

        for batch_idx, batch in enumerate(batches):
            if batch_idx > 0:
                await asyncio.sleep(BULK_INTER_BATCH_DELAY)

            _LOGGER.debug(
                "Bulk batch %d/%d (%d paths)", batch_idx + 1, len(batches), len(batch)
            )
            try:
                batch_results, batch_retries = await self._fetch_bulk_batch(
                    gateway_id, batch
                )
            except PointtAuthError:
                # 401 from the API — the access token may have been
                # invalidated server-side.  Force-refresh and retry once.
                _LOGGER.info(
                    "Bulk batch %d returned 401, refreshing token and retrying",
                    batch_idx + 1,
                )
                await self.async_force_token_refresh()
                batch_results, batch_retries = await self._fetch_bulk_batch(
                    gateway_id, batch
                )
            results.update(batch_results)
            retry_paths.extend(batch_retries)

        # Retry 504 paths once (unless caller opted out)
        if retry_paths and not skip_retries:
            _LOGGER.info("Retrying %d timed-out paths after %ds", len(retry_paths), BULK_RETRY_DELAY)
            await asyncio.sleep(BULK_RETRY_DELAY)

            retry_batches = [
                retry_paths[i : i + BULK_BATCH_SIZE]
                for i in range(0, len(retry_paths), BULK_BATCH_SIZE)
            ]
            for batch_idx, batch in enumerate(retry_batches):
                if batch_idx > 0:
                    await asyncio.sleep(BULK_INTER_BATCH_DELAY)
                batch_results, _ = await self._fetch_bulk_batch(
                    gateway_id, batch, is_retry=True
                )
                results.update(batch_results)
        elif retry_paths:
            # Retries skipped — mark timed-out paths as errors
            _LOGGER.debug("Skipping retry for %d timed-out paths", len(retry_paths))
            for p in retry_paths:
                results[p] = {
                    "_error": True,
                    "type": "error",
                    "value": "[gateway timeout]",
                }

        return results

    async def _fetch_bulk_batch(
        self,
        gateway_id: str,
        paths: list[str],
        *,
        is_retry: bool = False,
    ) -> tuple[dict[str, Any], list[str]]:
        """Execute a single bulk batch request.

        Returns ``(results_dict, retry_paths_list)``.
        """
        results: dict[str, Any] = {}
        retry: list[str] = []

        body = [{"gatewayId": gateway_id, "resourcePaths": paths}]
        url = f"{POINTT_BASE_URL}bulk"

        try:
            async with self._session.post(
                url, json=body, headers=self._auth_headers(), timeout=aiohttp.ClientTimeout(total=60)
            ) as resp:
                if resp.status == 401:
                    raise PointtAuthError("Unauthorized (401) on bulk request")
                if resp.status != 200:
                    text = await resp.text()
                    _LOGGER.warning("Bulk POST returned %d: %s", resp.status, text[:200])
                    for p in paths:
                        results[p] = {"_error": True, "type": "error", "value": f"[HTTP {resp.status}]"}
                    return results, retry

                data = await resp.json(content_type=None)

        except PointtAuthError:
            raise
        except (aiohttp.ClientError, asyncio.TimeoutError) as err:
            _LOGGER.warning("Bulk request failed: %s", err)
            for p in paths:
                results[p] = {"_error": True, "type": "error", "value": f"[{err}]"}
            return results, retry

        # Parse per-path responses
        for rp in data[0].get("resourcePaths", []):
            path = rp.get("resourcePath")
            gw_resp = rp.get("gatewayResponse") or {}
            gw_status = gw_resp.get("status")
            payload = gw_resp.get("payload")

            if gw_status == 200 and payload:
                results[path] = payload
            elif gw_status == 404:
                results[path] = None
            elif gw_status == 504 and not is_retry:
                retry.append(path)
            elif gw_status == 403:
                results[path] = {"_error": True, "type": "error", "value": "[forbidden]"}
            else:
                results[path] = {
                    "_error": True,
                    "type": "error",
                    "value": f"[gateway status {gw_status}]",
                }

        return results, retry
