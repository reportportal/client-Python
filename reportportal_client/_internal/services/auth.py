#  Copyright 2025 EPAM Systems
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#      https://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.

"""This module handles authentication for ReportPortal."""

import logging
import time
from abc import abstractmethod
from typing import Optional

import aiohttp
import requests

from reportportal_client._internal.static.abstract import AbstractBaseClass

logger = logging.getLogger(__name__)


# noinspection PyAbstractClass
class Auth(metaclass=AbstractBaseClass):
    """Abstract base class for synchronous authentication.

    This class defines the interface for all synchronous authentication methods.
    """

    __metaclass__ = AbstractBaseClass

    @abstractmethod
    def get(self) -> Optional[str]:
        """Get valid Authorization header value.

        :return: Authorization header value or None if authentication failed.
        """
        raise NotImplementedError('"get" method is not implemented!')

    @abstractmethod
    def refresh(self) -> Optional[str]:
        """Refresh the access token and return Authorization header value.

        :return: Authorization header value or None if refresh failed.
        """
        raise NotImplementedError('"refresh" method is not implemented!')


# noinspection PyAbstractClass
class AuthAsync(metaclass=AbstractBaseClass):
    """Abstract base class for asynchronous authentication.

    This class defines the interface for all asynchronous authentication methods.
    """

    __metaclass__ = AbstractBaseClass

    @abstractmethod
    async def get(self) -> Optional[str]:
        """Get valid Authorization header value.

        :return: Authorization header value or None if authentication failed.
        """
        raise NotImplementedError('"get" method is not implemented!')

    @abstractmethod
    async def refresh(self) -> Optional[str]:
        """Refresh the access token and return Authorization header value.

        :return: Authorization header value or None if refresh failed.
        """
        raise NotImplementedError('"refresh" method is not implemented!')


class ApiKeyAuthSync(Auth):
    """Synchronous API key authentication.

    This class provides simple key-based authentication that always returns
    the provided API key.
    """

    api_key: str

    def __init__(self, api_key: str) -> None:
        """Initialize API key authentication.

        :param api_key: API key for authentication.
        """
        self.api_key = api_key

    def get(self) -> Optional[str]:
        """Get valid Authorization header value.

        :return: Authorization header value with Bearer token.
        """
        return f"Bearer {self.api_key}"

    def refresh(self) -> None:
        """Refresh the access key and return Authorization header value.

        For API keys, this simply returns None as there's no refresh mechanism.

        :return: None
        """
        return None


class ApiKeyAuthAsync(AuthAsync):
    """Asynchronous API key authentication.

    This class provides simple key-based authentication that always returns
    the provided API key.
    """

    api_key: str

    def __init__(self, api_key: str) -> None:
        """Initialize API key authentication.

        :param api_key: API key for authentication.
        """
        self.api_key = api_key

    async def get(self) -> Optional[str]:
        """Get valid Authorization header value.

        :return: Authorization header value with Bearer token.
        """
        return f"Bearer {self.api_key}"

    async def refresh(self) -> None:
        """Refresh the access key and return Authorization header value.

        For API keys, this simply returns None as there's no refresh mechanism.

        :return: None
        """
        return None


# noinspection PyAbstractClass
class OAuthPasswordGrant:
    """Base class for OAuth 2.0 password grant authentication.

    This class provides common logic for obtaining and refreshing access tokens using
    the OAuth 2.0 password grant flow. This class should not be used directly, use
    OAuthPasswordGrantSync or OAuthPasswordGrantAsync instead.
    """

    oauth_uri: str
    username: str
    password: str
    client_id: str
    client_secret: Optional[str]
    scope: Optional[str]
    _access_token: Optional[str]
    _refresh_token: Optional[str]
    _token_expires_at: Optional[float]
    _last_attempt_time: Optional[float]

    def __init__(
        self,
        oauth_uri: str,
        username: str,
        password: str,
        client_id: str,
        client_secret: Optional[str] = None,
        scope: Optional[str] = None,
    ) -> None:
        """Initialize OAuth 2.0 password grant authentication.

        :param oauth_uri:      OAuth 2.0 token endpoint URI.
        :param username:       Username for authentication.
        :param password:       Password for authentication.
        :param client_id:      OAuth client ID.
        :param client_secret:  Optional OAuth client secret.
        :param scope:          Optional OAuth scope.
        """
        self.oauth_uri = oauth_uri
        self.username = username
        self.password = password
        self.client_id = client_id
        self.client_secret = client_secret
        self.scope = scope
        self._access_token = None
        self._refresh_token = None
        self._token_expires_at = None
        self._last_attempt_time = None

    def _should_skip_request(self) -> bool:
        """Check if token request should be skipped due to throttling.

        :return: True if request should be skipped, False otherwise.
        """
        if self._last_attempt_time is None:
            return False
        current_time = time.time()
        return int(current_time) == int(self._last_attempt_time)

    def _is_token_expired(self) -> bool:
        """Check if the current access token is expired.

        :return: True if token is expired or not set, False otherwise.
        """
        if not self._access_token or self._token_expires_at is None:
            return True
        return time.time() >= self._token_expires_at

    def _update_last_attempt_time(self) -> None:
        """Update the last attempt time to current time."""
        self._last_attempt_time = time.time()

    def _clear_token(self) -> None:
        """Clear the current access token."""
        self._access_token = None
        self._token_expires_at = None

    def _parse_token_response(self, response_data: dict) -> bool:
        """Parse OAuth token response and store tokens.

        :param response_data: Response JSON data from OAuth server.
        :return:              True if parsing was successful, False otherwise.
        """
        try:
            access_token = response_data.get("access_token")
            if not access_token:
                logger.warning("OAuth token response missing 'access_token' field")
                return False

            self._access_token = access_token
            self._refresh_token = response_data.get("refresh_token")

            expires_in = response_data.get("expires_in")
            if expires_in:
                # Set expiration time with 30 seconds buffer to avoid edge cases
                self._token_expires_at = time.time() + int(expires_in) - 30
            else:
                # If expires_in is not provided, assume token is valid for a reasonable time
                self._token_expires_at = time.time() + 3600  # 1 hour default

            return True
        except (ValueError, TypeError) as e:
            logger.warning(f"Failed to parse OAuth token response: {e}")
            return False

    def _build_token_request_data(self, grant_type: str, **extra_params) -> dict:
        """Build request data for OAuth token request.

        :param grant_type:    OAuth grant type.
        :param extra_params:  Additional parameters for the request.
        :return:              Dictionary with request data.
        """
        data = {"grant_type": grant_type, "client_id": self.client_id}

        if self.client_secret:
            data["client_secret"] = self.client_secret

        if self.scope:
            data["scope"] = self.scope

        data.update(extra_params)
        return data


class OAuthPasswordGrantSync(OAuthPasswordGrant, Auth):
    """Synchronous implementation of OAuth 2.0 password grant authentication."""

    _session: Optional[requests.Session]

    def __init__(
        self,
        oauth_uri: str,
        username: str,
        password: str,
        client_id: str,
        client_secret: Optional[str] = None,
        scope: Optional[str] = None,
        session: Optional[requests.Session] = None,
    ) -> None:
        """Initialize OAuth 2.0 password grant authentication.

        :param oauth_uri:      OAuth 2.0 token endpoint URI.
        :param username:       Username for authentication.
        :param password:       Password for authentication.
        :param client_id:      OAuth client ID.
        :param client_secret:  Optional OAuth client secret.
        :param scope:          Optional OAuth scope.
        :param session:        Optional requests.Session instance to use.
        """
        super().__init__(oauth_uri, username, password, client_id, client_secret, scope)
        self._session = session

    def _get_session(self) -> requests.Session:
        """Get or create requests.Session.

        :return: Session instance.
        """
        if self._session is None:
            self._session = requests.Session()
        return self._session

    def _execute_token_request(self, data: dict) -> bool:
        """Execute token request to OAuth server.

        :param data: Request data.
        :return:     True if request was successful, False otherwise.
        """
        self._update_last_attempt_time()

        try:
            session = self._get_session()
            response = session.post(
                self.oauth_uri,
                data=data,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )

            if not response.ok:
                logger.warning(f"OAuth token request failed with status {response.status_code}")
                return False

            return self._parse_token_response(response.json())

        except requests.exceptions.RequestException as e:
            logger.warning(f"OAuth token request failed: {e}")
            return False

    def _obtain_new_token(self) -> bool:
        """Obtain new access token using password grant.

        :return: True if token was obtained successfully, False otherwise.
        """
        data = self._build_token_request_data(
            grant_type="password",
            username=self.username,
            password=self.password,
        )
        return self._execute_token_request(data)

    def _refresh_access_token(self) -> bool:
        """Refresh access token using refresh token.

        :return: True if token was refreshed successfully, False otherwise.
        """
        if not self._refresh_token:
            return False

        data = self._build_token_request_data(
            grant_type="refresh_token",
            refresh_token=self._refresh_token,
        )
        return self._execute_token_request(data)

    def get(self) -> Optional[str]:
        """Get valid Authorization header value.

        :return: Authorization header value or None if authentication failed.
        """
        # If token is valid, return it (no need to check throttling for cached token)
        if not self._is_token_expired():
            return f"Bearer {self._access_token}"

        # Check if we should skip new request due to throttling
        if self._should_skip_request():
            return None

        # Try to refresh token first
        if self._refresh_access_token():
            return f"Bearer {self._access_token}"

        # If refresh failed, try to obtain new token
        if self._obtain_new_token():
            return f"Bearer {self._access_token}"

        return None

    def refresh(self) -> Optional[str]:
        """Refresh the access token and return Authorization header value.

        :return: Authorization header value or None if refresh failed.
        """
        self._clear_token()
        return self.get()

    def close(self) -> None:
        """Close the session and release resources."""
        if self._session:
            self._session.close()


class OAuthPasswordGrantAsync(OAuthPasswordGrant, AuthAsync):
    """Asynchronous implementation of OAuth 2.0 password grant authentication."""

    _session: Optional[aiohttp.ClientSession]

    def __init__(
        self,
        oauth_uri: str,
        username: str,
        password: str,
        client_id: str,
        client_secret: Optional[str] = None,
        scope: Optional[str] = None,
        session: Optional[aiohttp.ClientSession] = None,
    ) -> None:
        """Initialize OAuth 2.0 password grant authentication.

        :param oauth_uri:      OAuth 2.0 token endpoint URI.
        :param username:       Username for authentication.
        :param password:       Password for authentication.
        :param client_id:      OAuth client ID.
        :param client_secret:  Optional OAuth client secret.
        :param scope:          Optional OAuth scope.
        :param session:        Optional aiohttp.ClientSession instance to use.
        """
        super().__init__(oauth_uri, username, password, client_id, client_secret, scope)
        self._session = session

    def _get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp ClientSession.

        :return: ClientSession instance.
        """
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    async def _execute_token_request(self, data: dict) -> bool:
        """Execute token request to OAuth server.

        :param data: Request data.
        :return:     True if request was successful, False otherwise.
        """
        self._update_last_attempt_time()

        try:
            session = self._get_session()
            async with session.post(
                self.oauth_uri,
                data=data,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            ) as response:
                if not response.ok:
                    logger.warning(f"OAuth token request failed with status {response.status}")
                    return False

                response_data = await response.json()
                return self._parse_token_response(response_data)

        except aiohttp.ClientError as e:
            logger.warning(f"OAuth token request failed: {e}")
            return False

    async def _obtain_new_token(self) -> bool:
        """Obtain new access token using password grant.

        :return: True if token was obtained successfully, False otherwise.
        """
        data = self._build_token_request_data(
            grant_type="password",
            username=self.username,
            password=self.password,
        )
        return await self._execute_token_request(data)

    async def _refresh_access_token(self) -> bool:
        """Refresh access token using refresh token.

        :return: True if token was refreshed successfully, False otherwise.
        """
        if not self._refresh_token:
            return False

        data = self._build_token_request_data(
            grant_type="refresh_token",
            refresh_token=self._refresh_token,
        )
        return await self._execute_token_request(data)

    async def get(self) -> Optional[str]:
        """Get valid Authorization header value.

        :return: Authorization header value or None if authentication failed.
        """
        # If token is valid, return it (no need to check throttling for cached token)
        if not self._is_token_expired():
            return f"Bearer {self._access_token}"

        # Check if we should skip new request due to throttling
        if self._should_skip_request():
            return None

        # Try to refresh token first
        if await self._refresh_access_token():
            return f"Bearer {self._access_token}"

        # If refresh failed, try to obtain new token
        if await self._obtain_new_token():
            return f"Bearer {self._access_token}"

        return None

    async def refresh(self) -> Optional[str]:
        """Refresh the access token and return Authorization header value.

        :return: Authorization header value or None if refresh failed.
        """
        self._clear_token()
        return await self.get()

    async def close(self) -> None:
        """Close the session and release resources."""
        if self._session and not self._session.closed:
            await self._session.close()
