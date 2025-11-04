"""This module contains unit tests for authentication."""

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
#  limitations under the License

import time
from unittest import mock

# noinspection PyPackageRequirements
import pytest

# noinspection PyProtectedMember
from reportportal_client._internal.services.auth import (
    ApiTokenAuthAsync,
    ApiTokenAuthSync,
    OAuthPasswordGrantAsync,
    OAuthPasswordGrantSync,
)

OAUTH_URI = "https://example.com/oauth/token"
USERNAME = "testuser"
PASSWORD = "testpass"
CLIENT_ID = "test_client_id"
CLIENT_SECRET = "test_client_secret"
SCOPE = "test_scope"
ACCESS_TOKEN = "test_access_token"
REFRESH_TOKEN = "test_refresh_token"
EXPIRES_IN = 3600


def create_token_response(access_token=ACCESS_TOKEN, refresh_token=REFRESH_TOKEN, expires_in=EXPIRES_IN):
    """Create a mock OAuth token response."""
    return {"access_token": access_token, "refresh_token": refresh_token, "expires_in": expires_in}


class TestOAuthPasswordGrantSync:
    """Tests for synchronous OAuth 2.0 password grant authentication."""

    def test_happy_path_fresh_start(self):
        """Test successful token acquisition on fresh start."""
        mock_response = mock.Mock()
        mock_response.ok = True
        mock_response.json.return_value = create_token_response()

        mock_session = mock.Mock()
        mock_session.post.return_value = mock_response

        oauth = OAuthPasswordGrantSync(
            OAUTH_URI, USERNAME, PASSWORD, CLIENT_ID, CLIENT_SECRET, SCOPE, session=mock_session
        )
        result = oauth.get()

        assert result == f"Bearer {ACCESS_TOKEN}"
        assert oauth._access_token == ACCESS_TOKEN
        assert oauth._refresh_token == REFRESH_TOKEN
        mock_session.post.assert_called_once()

        # Verify request data
        call_args = mock_session.post.call_args
        assert call_args[0][0] == OAUTH_URI
        data = call_args[1]["data"]
        assert data["grant_type"] == "password"
        assert data["username"] == USERNAME
        assert data["password"] == PASSWORD
        assert data["client_id"] == CLIENT_ID
        assert data["client_secret"] == CLIENT_SECRET
        assert data["scope"] == SCOPE

    def test_happy_path_token_refresh(self):
        """Test successful token refresh after expiration."""
        mock_response = mock.Mock()
        mock_response.ok = True
        mock_response.json.return_value = create_token_response(expires_in=1)

        mock_session = mock.Mock()
        mock_session.post.return_value = mock_response

        oauth = OAuthPasswordGrantSync(OAUTH_URI, USERNAME, PASSWORD, CLIENT_ID, session=mock_session)

        # First call - obtain token
        result1 = oauth.get()
        assert result1 == f"Bearer {ACCESS_TOKEN}"
        assert mock_session.post.call_count == 1

        # Wait for token to expire
        time.sleep(1)

        # Second call - token expired, should refresh
        new_access_token = "new_access_token"
        mock_response.json.return_value = create_token_response(access_token=new_access_token)

        result2 = oauth.get()
        assert result2 == f"Bearer {new_access_token}"
        assert oauth._access_token == new_access_token
        assert mock_session.post.call_count == 2

        # Verify refresh token was used
        call_args = mock_session.post.call_args_list[1]
        data = call_args[1]["data"]
        assert data["grant_type"] == "refresh_token"
        assert data["refresh_token"] == REFRESH_TOKEN

    def test_token_refresh_throttling(self):
        """Test that token requests are throttled within the same second after failure."""
        mock_response_fail = mock.Mock()
        mock_response_fail.ok = False
        mock_response_fail.status_code = 401

        mock_session = mock.Mock()
        mock_session.post.return_value = mock_response_fail

        oauth = OAuthPasswordGrantSync(OAUTH_URI, USERNAME, PASSWORD, CLIENT_ID, session=mock_session)

        # First call - should fail
        result1 = oauth.get()
        assert result1 is None
        assert mock_session.post.call_count == 1

        # Second call in the same second - should be throttled
        result2 = oauth.get()
        assert result2 is None
        assert mock_session.post.call_count == 1  # No additional call

    def test_initial_request_401_response(self):
        """Test 401 response from server on initial request."""
        mock_response = mock.Mock()
        mock_response.ok = False
        mock_response.status_code = 401

        mock_session = mock.Mock()
        mock_session.post.return_value = mock_response

        oauth = OAuthPasswordGrantSync(OAUTH_URI, USERNAME, PASSWORD, CLIENT_ID, session=mock_session)
        result = oauth.get()

        assert result is None
        assert oauth._access_token is None

    def test_initial_request_403_response(self):
        """Test 403 response from server on initial request."""
        mock_response = mock.Mock()
        mock_response.ok = False
        mock_response.status_code = 403

        mock_session = mock.Mock()
        mock_session.post.return_value = mock_response

        oauth = OAuthPasswordGrantSync(OAUTH_URI, USERNAME, PASSWORD, CLIENT_ID, session=mock_session)
        result = oauth.get()

        assert result is None
        assert oauth._access_token is None

    def test_refresh_request_401_fallback_to_password_grant(self):
        """Test 401 response on refresh request falls back to password grant."""
        # First obtain a token
        initial_response = mock.Mock()
        initial_response.ok = True
        initial_response.json.return_value = create_token_response(expires_in=1)

        mock_session = mock.Mock()
        mock_session.post.return_value = initial_response

        oauth = OAuthPasswordGrantSync(OAUTH_URI, USERNAME, PASSWORD, CLIENT_ID, session=mock_session)
        result1 = oauth.get()
        assert result1 == f"Bearer {ACCESS_TOKEN}"

        # Wait for token to expire
        time.sleep(1)

        # Simulate refresh failure and password grant success
        refresh_response = mock.Mock()
        refresh_response.ok = False
        refresh_response.status_code = 401

        password_response = mock.Mock()
        password_response.ok = True
        new_token = "new_password_token"
        password_response.json.return_value = create_token_response(access_token=new_token)

        mock_session.post.side_effect = [refresh_response, password_response]

        result2 = oauth.get()
        assert result2 == f"Bearer {new_token}"
        assert oauth._access_token == new_token
        assert mock_session.post.call_count == 3  # Initial + refresh attempt + password grant

    def test_refresh_request_403_fallback_to_password_grant(self):
        """Test 403 response on refresh request falls back to password grant."""
        # First obtain a token
        initial_response = mock.Mock()
        initial_response.ok = True
        initial_response.json.return_value = create_token_response(expires_in=1)

        mock_session = mock.Mock()
        mock_session.post.return_value = initial_response

        oauth = OAuthPasswordGrantSync(OAUTH_URI, USERNAME, PASSWORD, CLIENT_ID, session=mock_session)
        result1 = oauth.get()
        assert result1 == f"Bearer {ACCESS_TOKEN}"

        # Wait for token to expire
        time.sleep(1)

        # Simulate refresh failure with 403 and password grant success
        refresh_response = mock.Mock()
        refresh_response.ok = False
        refresh_response.status_code = 403

        password_response = mock.Mock()
        password_response.ok = True
        new_token = "new_password_token"
        password_response.json.return_value = create_token_response(access_token=new_token)

        mock_session.post.side_effect = [refresh_response, password_response]

        result2 = oauth.get()
        assert result2 == f"Bearer {new_token}"
        assert oauth._access_token == new_token

    def test_refresh_method_on_valid_token(self):
        """Test refresh method call on existing and not expired access token."""
        initial_response = mock.Mock()
        initial_response.ok = True
        initial_response.json.return_value = create_token_response()

        mock_session = mock.Mock()
        mock_session.post.return_value = initial_response

        oauth = OAuthPasswordGrantSync(OAUTH_URI, USERNAME, PASSWORD, CLIENT_ID, session=mock_session)

        # Get initial token
        result1 = oauth.get()
        assert result1 == f"Bearer {ACCESS_TOKEN}"
        assert oauth._access_token == ACCESS_TOKEN

        # Call refresh on valid token
        new_token = "refreshed_token"
        refreshed_response = mock.Mock()
        refreshed_response.ok = True
        refreshed_response.json.return_value = create_token_response(access_token=new_token)
        mock_session.post.return_value = refreshed_response

        # Wait to avoid throttling
        time.sleep(1)

        result2 = oauth.refresh()
        assert result2 == f"Bearer {new_token}"
        assert oauth._access_token == new_token

        # Verify it tried to use refresh token (since refresh clears the access token but refresh token is still available)
        call_args = mock_session.post.call_args
        data = call_args[1]["data"]
        # After refresh() clears the access token, it should try to use refresh_token grant since refresh token is still available
        assert data["grant_type"] == "refresh_token"
        assert data["refresh_token"] == REFRESH_TOKEN


class TestOAuthPasswordGrantAsync:
    """Tests for asynchronous OAuth 2.0 password grant authentication."""

    @pytest.mark.asyncio
    async def test_happy_path_fresh_start(self):
        """Test successful token acquisition on fresh start."""
        mock_response = mock.AsyncMock()
        mock_response.ok = True
        mock_response.json.return_value = create_token_response()
        mock_response.__aenter__.return_value = mock_response
        mock_response.__aexit__.return_value = None

        mock_session = mock.Mock()
        mock_session.post = mock.Mock(return_value=mock_response)
        mock_session.closed = False

        oauth = OAuthPasswordGrantAsync(
            OAUTH_URI, USERNAME, PASSWORD, CLIENT_ID, CLIENT_SECRET, SCOPE, session=mock_session
        )
        result = await oauth.get()

        assert result == f"Bearer {ACCESS_TOKEN}"
        assert oauth._access_token == ACCESS_TOKEN
        assert oauth._refresh_token == REFRESH_TOKEN
        mock_session.post.assert_called_once()

        # Verify request data
        call_args = mock_session.post.call_args
        data = call_args[1]["data"]
        assert data["grant_type"] == "password"
        assert data["username"] == USERNAME
        assert data["password"] == PASSWORD
        assert data["client_id"] == CLIENT_ID
        assert data["client_secret"] == CLIENT_SECRET
        assert data["scope"] == SCOPE

    @pytest.mark.asyncio
    async def test_happy_path_token_refresh(self):
        """Test successful token refresh after expiration."""
        mock_response = mock.AsyncMock()
        mock_response.ok = True
        mock_response.json.return_value = create_token_response(expires_in=1)
        mock_response.__aenter__.return_value = mock_response
        mock_response.__aexit__.return_value = None

        mock_session = mock.Mock()
        mock_session.post = mock.Mock(return_value=mock_response)
        mock_session.closed = False

        oauth = OAuthPasswordGrantAsync(OAUTH_URI, USERNAME, PASSWORD, CLIENT_ID, session=mock_session)

        # First call - obtain token
        result1 = await oauth.get()
        assert result1 == f"Bearer {ACCESS_TOKEN}"
        assert mock_session.post.call_count == 1

        # Wait for token to expire
        time.sleep(1)

        # Second call - token expired, should refresh
        new_access_token = "new_access_token"
        mock_response.json.return_value = create_token_response(access_token=new_access_token)

        result2 = await oauth.get()
        assert result2 == f"Bearer {new_access_token}"
        assert oauth._access_token == new_access_token
        assert mock_session.post.call_count == 2

        # Verify refresh token was used
        call_args = mock_session.post.call_args_list[1]
        data = call_args[1]["data"]
        assert data["grant_type"] == "refresh_token"
        assert data["refresh_token"] == REFRESH_TOKEN

    @pytest.mark.asyncio
    async def test_token_refresh_throttling(self):
        """Test that token requests are throttled within the same second after failure."""
        mock_response_fail = mock.AsyncMock()
        mock_response_fail.ok = False
        mock_response_fail.status = 401
        mock_response_fail.__aenter__.return_value = mock_response_fail
        mock_response_fail.__aexit__.return_value = None

        mock_session = mock.Mock()
        mock_session.post = mock.Mock(return_value=mock_response_fail)
        mock_session.closed = False

        oauth = OAuthPasswordGrantAsync(OAUTH_URI, USERNAME, PASSWORD, CLIENT_ID, session=mock_session)

        # First call - should fail
        result1 = await oauth.get()
        assert result1 is None
        assert mock_session.post.call_count == 1

        # Second call in the same second - should be throttled
        result2 = await oauth.get()
        assert result2 is None
        assert mock_session.post.call_count == 1  # No additional call

    @pytest.mark.asyncio
    async def test_initial_request_401_response(self):
        """Test 401 response from server on initial request."""
        mock_response = mock.AsyncMock()
        mock_response.ok = False
        mock_response.status = 401
        mock_response.__aenter__.return_value = mock_response
        mock_response.__aexit__.return_value = None

        mock_session = mock.Mock()
        mock_session.post = mock.Mock(return_value=mock_response)
        mock_session.closed = False

        oauth = OAuthPasswordGrantAsync(OAUTH_URI, USERNAME, PASSWORD, CLIENT_ID, session=mock_session)
        result = await oauth.get()

        assert result is None
        assert oauth._access_token is None

    @pytest.mark.asyncio
    async def test_initial_request_403_response(self):
        """Test 403 response from server on initial request."""
        mock_response = mock.AsyncMock()
        mock_response.ok = False
        mock_response.status = 403
        mock_response.__aenter__.return_value = mock_response
        mock_response.__aexit__.return_value = None

        mock_session = mock.Mock()
        mock_session.post = mock.Mock(return_value=mock_response)
        mock_session.closed = False

        oauth = OAuthPasswordGrantAsync(OAUTH_URI, USERNAME, PASSWORD, CLIENT_ID, session=mock_session)
        result = await oauth.get()

        assert result is None
        assert oauth._access_token is None

    @pytest.mark.asyncio
    async def test_refresh_request_401_fallback_to_password_grant(self):
        """Test 401 response on refresh request falls back to password grant."""
        # First obtain a token
        initial_response = mock.AsyncMock()
        initial_response.ok = True
        initial_response.json.return_value = create_token_response(expires_in=1)
        initial_response.__aenter__.return_value = initial_response
        initial_response.__aexit__.return_value = None

        mock_session = mock.Mock()
        mock_session.post = mock.Mock(return_value=initial_response)
        mock_session.closed = False

        oauth = OAuthPasswordGrantAsync(OAUTH_URI, USERNAME, PASSWORD, CLIENT_ID, session=mock_session)
        result1 = await oauth.get()
        assert result1 == f"Bearer {ACCESS_TOKEN}"

        # Wait for token to expire
        time.sleep(1)

        # Simulate refresh failure and password grant success
        refresh_response = mock.AsyncMock()
        refresh_response.ok = False
        refresh_response.status = 401
        refresh_response.__aenter__.return_value = refresh_response
        refresh_response.__aexit__.return_value = None

        password_response = mock.AsyncMock()
        password_response.ok = True
        new_token = "new_password_token"
        password_response.json.return_value = create_token_response(access_token=new_token)
        password_response.__aenter__.return_value = password_response
        password_response.__aexit__.return_value = None

        mock_session.post.side_effect = [refresh_response, password_response]

        result2 = await oauth.get()
        assert result2 == f"Bearer {new_token}"
        assert oauth._access_token == new_token
        assert mock_session.post.call_count == 3  # Initial + refresh attempt + password grant

    @pytest.mark.asyncio
    async def test_refresh_request_403_fallback_to_password_grant(self):
        """Test 403 response on refresh request falls back to password grant."""
        # First obtain a token
        initial_response = mock.AsyncMock()
        initial_response.ok = True
        initial_response.json.return_value = create_token_response(expires_in=1)
        initial_response.__aenter__.return_value = initial_response
        initial_response.__aexit__.return_value = None

        mock_session = mock.Mock()
        mock_session.post = mock.Mock(return_value=initial_response)
        mock_session.closed = False

        oauth = OAuthPasswordGrantAsync(OAUTH_URI, USERNAME, PASSWORD, CLIENT_ID, session=mock_session)
        result1 = await oauth.get()
        assert result1 == f"Bearer {ACCESS_TOKEN}"

        # Wait for token to expire
        time.sleep(1)

        # Simulate refresh failure with 403 and password grant success
        refresh_response = mock.AsyncMock()
        refresh_response.ok = False
        refresh_response.status = 403
        refresh_response.__aenter__.return_value = refresh_response
        refresh_response.__aexit__.return_value = None

        password_response = mock.AsyncMock()
        password_response.ok = True
        new_token = "new_password_token"
        password_response.json.return_value = create_token_response(access_token=new_token)
        password_response.__aenter__.return_value = password_response
        password_response.__aexit__.return_value = None

        mock_session.post.side_effect = [refresh_response, password_response]

        result2 = await oauth.get()
        assert result2 == f"Bearer {new_token}"
        assert oauth._access_token == new_token

    @pytest.mark.asyncio
    async def test_refresh_method_on_valid_token(self):
        """Test refresh method call on existing and not expired access token."""
        initial_response = mock.AsyncMock()
        initial_response.ok = True
        initial_response.json.return_value = create_token_response()
        initial_response.__aenter__.return_value = initial_response
        initial_response.__aexit__.return_value = None

        mock_session = mock.Mock()
        mock_session.post = mock.Mock(return_value=initial_response)
        mock_session.closed = False

        oauth = OAuthPasswordGrantAsync(OAUTH_URI, USERNAME, PASSWORD, CLIENT_ID, session=mock_session)

        # Get initial token
        result1 = await oauth.get()
        assert result1 == f"Bearer {ACCESS_TOKEN}"
        assert oauth._access_token == ACCESS_TOKEN

        # Call refresh on valid token
        new_token = "refreshed_token"
        refreshed_response = mock.AsyncMock()
        refreshed_response.ok = True
        refreshed_response.json.return_value = create_token_response(access_token=new_token)
        refreshed_response.__aenter__.return_value = refreshed_response
        refreshed_response.__aexit__.return_value = None
        mock_session.post.return_value = refreshed_response

        # Wait to avoid throttling
        time.sleep(1)

        result2 = await oauth.refresh()
        assert result2 == f"Bearer {new_token}"
        assert oauth._access_token == new_token

        # Verify it tried to use refresh token (since refresh clears the access token but refresh token is still available)
        call_args = mock_session.post.call_args
        data = call_args[1]["data"]
        # After refresh() clears the access token, it should try to use refresh_token grant since refresh token is still available
        assert data["grant_type"] == "refresh_token"
        assert data["refresh_token"] == REFRESH_TOKEN


class TestApiTokenAuthSync:
    """Tests for synchronous API token authentication."""

    def test_get_returns_token(self):
        """Test that get() returns the API token."""
        api_token = "test_api_token_12345"
        auth = ApiTokenAuthSync(api_token)
        result = auth.get()

        assert result == f"Bearer {api_token}"

    def test_refresh_returns_token(self):
        """Test that refresh() returns the API token."""
        api_token = "test_api_token_67890"
        auth = ApiTokenAuthSync(api_token)
        result = auth.refresh()

        assert result == f"Bearer {api_token}"

    def test_multiple_calls_return_same_token(self):
        """Test that multiple calls return the same token."""
        api_token = "test_api_token_stable"
        auth = ApiTokenAuthSync(api_token)

        result1 = auth.get()
        result2 = auth.get()
        result3 = auth.refresh()

        assert result1 == f"Bearer {api_token}"
        assert result2 == f"Bearer {api_token}"
        assert result3 == f"Bearer {api_token}"


class TestApiTokenAuthAsync:
    """Tests for asynchronous API token authentication."""

    @pytest.mark.asyncio
    async def test_get_returns_token(self):
        """Test that get() returns the API token."""
        api_token = "test_api_token_async_12345"
        auth = ApiTokenAuthAsync(api_token)
        result = await auth.get()

        assert result == f"Bearer {api_token}"

    @pytest.mark.asyncio
    async def test_refresh_returns_token(self):
        """Test that refresh() returns the API token."""
        api_token = "test_api_token_async_67890"
        auth = ApiTokenAuthAsync(api_token)
        result = await auth.refresh()

        assert result == f"Bearer {api_token}"

    @pytest.mark.asyncio
    async def test_multiple_calls_return_same_token(self):
        """Test that multiple calls return the same token."""
        api_token = "test_api_token_async_stable"
        auth = ApiTokenAuthAsync(api_token)

        result1 = await auth.get()
        result2 = await auth.get()
        result3 = await auth.refresh()

        assert result1 == f"Bearer {api_token}"
        assert result2 == f"Bearer {api_token}"
        assert result3 == f"Bearer {api_token}"
