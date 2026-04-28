"""Medplum Webhook Service.

Sends processed wearable data to Medplum FHIR Conversion Bot via HTTP webhook.
Handles OAuth2 token management and retry logic.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any

import httpx

from app.config import settings

logger = logging.getLogger(__name__)


class MedplumWebhook:
    """Sends webhook payloads to Medplum FHIR Conversion Bot.

    Handles:
    - OAuth2 client credentials authentication
    - Token caching and refresh
    - Webhook delivery with retries
    """

    # Token cache
    _access_token: str | None = None
    _token_expires_at: datetime | None = None

    def __init__(self):
        self.webhook_url = settings.medplum_webhook_url
        self.webhook_secret = (
            settings.medplum_webhook_secret.get_secret_value()
            if settings.medplum_webhook_secret
            else None
        )
        self.client_id = settings.medplum_client_id
        self.client_secret = (
            settings.medplum_client_secret.get_secret_value()
            if settings.medplum_client_secret
            else None
        )

    def is_enabled(self) -> bool:
        """Check if Medplum integration is enabled and configured."""
        return (
            settings.medplum_enabled
            and self.webhook_url is not None
            and self.client_id is not None
            and self.client_secret is not None
        )

    async def send(
        self,
        payload: dict[str, Any],
        *,
        timeout: float = 30.0,
        retries: int = 2,
    ) -> bool:
        """Send payload to Medplum webhook endpoint.

        Returns True if successful, False otherwise.
        """
        if not self.is_enabled():
            logger.debug("Medplum integration not enabled, skipping webhook")
            return False

        # Get access token
        try:
            token = await self._get_access_token()
        except Exception:
            logger.error("Failed to get Medplum access token", exc_info=True)
            return False

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}",
        }

        # Add webhook secret if configured
        if self.webhook_secret:
            headers["X-Webhook-Secret"] = self.webhook_secret

        # Send with retries
        last_error: Exception | None = None
        for attempt in range(retries + 1):
            try:
                async with httpx.AsyncClient() as client:
                    response = await client.post(
                        self.webhook_url,  # type: ignore
                        json=payload,
                        headers=headers,
                        timeout=timeout,
                    )
                    response.raise_for_status()

                    logger.info(
                        "Successfully sent %s event to Medplum",
                        payload.get("event_type", "unknown"),
                    )
                    return True

            except httpx.HTTPStatusError as e:
                last_error = e
                if e.response.status_code == 401:
                    # Token might be expired, clear cache and retry
                    self._clear_token_cache()
                    try:
                        token = await self._get_access_token()
                        headers["Authorization"] = f"Bearer {token}"
                    except Exception:
                        pass
                logger.warning(
                    "Medplum webhook HTTP error (attempt %d/%d): %s",
                    attempt + 1,
                    retries + 1,
                    e,
                )

            except httpx.RequestError as e:
                last_error = e
                logger.warning(
                    "Medplum webhook request error (attempt %d/%d): %s",
                    attempt + 1,
                    retries + 1,
                    e,
                )

        logger.error(
            "Failed to send %s event to Medplum after %d attempts: %s",
            payload.get("event_type", "unknown"),
            retries + 1,
            last_error,
        )
        return False

    def send_sync(
        self,
        payload: dict[str, Any],
        *,
        timeout: float = 30.0,
        retries: int = 2,
    ) -> bool:
        """Synchronous version of send for use in Celery tasks.

        Returns True if successful, False otherwise.
        """
        if not self.is_enabled():
            logger.debug("Medplum integration not enabled, skipping webhook")
            return False

        # Get access token
        try:
            token = self._get_access_token_sync()
        except Exception:
            logger.error("Failed to get Medplum access token", exc_info=True)
            return False

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}",
        }

        # Add webhook secret if configured
        if self.webhook_secret:
            headers["X-Webhook-Secret"] = self.webhook_secret

        # Send with retries
        last_error: Exception | None = None
        for attempt in range(retries + 1):
            try:
                with httpx.Client() as client:
                    response = client.post(
                        self.webhook_url,  # type: ignore
                        json=payload,
                        headers=headers,
                        timeout=timeout,
                    )
                    response.raise_for_status()

                    # Log the bot response for debugging
                    try:
                        bot_response = response.json()
                        if not bot_response.get("success", True):
                            logger.warning(
                                "Medplum bot returned error for %s: %s",
                                payload.get("event_type", "unknown"),
                                bot_response.get("error", "unknown error"),
                            )
                        else:
                            logger.info(
                                "Successfully sent %s event to Medplum, observationId=%s",
                                payload.get("event_type", "unknown"),
                                bot_response.get("observationId", "none"),
                            )
                    except Exception:
                        logger.info(
                            "Successfully sent %s event to Medplum",
                            payload.get("event_type", "unknown"),
                        )
                    return True

            except httpx.HTTPStatusError as e:
                last_error = e
                if e.response.status_code == 401:
                    # Token might be expired, clear cache and retry
                    self._clear_token_cache()
                    try:
                        token = self._get_access_token_sync()
                        headers["Authorization"] = f"Bearer {token}"
                    except Exception:
                        pass
                logger.warning(
                    "Medplum webhook HTTP error (attempt %d/%d): %s",
                    attempt + 1,
                    retries + 1,
                    e,
                )

            except httpx.RequestError as e:
                last_error = e
                logger.warning(
                    "Medplum webhook request error (attempt %d/%d): %s",
                    attempt + 1,
                    retries + 1,
                    e,
                )

        logger.error(
            "Failed to send %s event to Medplum after %d attempts: %s",
            payload.get("event_type", "unknown"),
            retries + 1,
            last_error,
        )
        return False

    async def _get_access_token(self) -> str:
        """Get OAuth2 access token, using cache if valid."""
        # Return cached token if still valid (with 1 minute buffer)
        if (
            self._access_token
            and self._token_expires_at
            and datetime.now() < self._token_expires_at - timedelta(minutes=1)
        ):
            return self._access_token

        # Get new token
        token_url = self._get_token_url()

        async with httpx.AsyncClient() as client:
            response = await client.post(
                token_url,
                data={
                    "grant_type": "client_credentials",
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                timeout=30.0,
            )
            response.raise_for_status()

            data = response.json()
            self._access_token = data["access_token"]
            expires_in = data.get("expires_in", 3600)
            self._token_expires_at = datetime.now() + timedelta(seconds=expires_in)

            logger.debug("Obtained new Medplum access token, expires in %ds", expires_in)
            return self._access_token

    def _get_access_token_sync(self) -> str:
        """Synchronous version of _get_access_token."""
        # Return cached token if still valid (with 1 minute buffer)
        if (
            self._access_token
            and self._token_expires_at
            and datetime.now() < self._token_expires_at - timedelta(minutes=1)
        ):
            return self._access_token

        # Get new token
        token_url = self._get_token_url()

        with httpx.Client() as client:
            response = client.post(
                token_url,
                data={
                    "grant_type": "client_credentials",
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                timeout=30.0,
            )
            response.raise_for_status()

            data = response.json()
            self._access_token = data["access_token"]
            expires_in = data.get("expires_in", 3600)
            self._token_expires_at = datetime.now() + timedelta(seconds=expires_in)

            logger.debug("Obtained new Medplum access token, expires in %ds", expires_in)
            return self._access_token

    def _get_token_url(self) -> str:
        """Extract base URL from webhook URL and build token endpoint."""
        if not self.webhook_url:
            raise ValueError("Medplum webhook URL not configured")

        # webhook_url is like: http://localhost:8103/fhir/R4/Bot/{id}/$execute
        # token_url should be: http://localhost:8103/oauth2/token
        parts = self.webhook_url.split("/fhir/")
        if len(parts) >= 2:
            base_url = parts[0]
        else:
            # Fallback: assume standard Medplum structure
            base_url = "/".join(self.webhook_url.split("/")[:3])

        return f"{base_url}/oauth2/token"

    def _clear_token_cache(self) -> None:
        """Clear cached access token."""
        self._access_token = None
        self._token_expires_at = None


# Singleton instance
medplum_webhook = MedplumWebhook()
