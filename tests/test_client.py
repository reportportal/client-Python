#  Copyright (c) 2022 https://reportportal.io .
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#  https://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License

import pickle
from io import StringIO
from unittest import mock

# noinspection PyPackageRequirements
import pytest
from conftest import DummyResponse
from requests import Response
from requests.exceptions import ReadTimeout

from reportportal_client import RPClient
from reportportal_client.core.rp_requests import RPRequestLog
from reportportal_client.helpers import timestamp


def connection_error(*args, **kwargs):
    raise ReadTimeout()


def response_error(*args, **kwargs):
    result = Response()
    result._content = "502 Gateway Timeout".encode("ASCII")
    result.status_code = 502
    return result


def invalid_response(*args, **kwargs):
    result = Response()
    result._content = "<html><head><title>Hello World!</title></head></html>".encode("ASCII")
    result.status_code = 200
    return result


@pytest.mark.parametrize(
    "requests_method, client_method, client_params",
    [
        ("put", "finish_launch", [timestamp()]),
        ("put", "finish_test_item", ["test_item_id", timestamp()]),
        ("get", "get_item_id_by_uuid", ["test_item_uuid"]),
        ("get", "get_launch_info", []),
        ("get", "get_launch_ui_id", []),
        ("get", "get_launch_ui_url", []),
        ("get", "get_project_settings", []),
        ("post", "start_launch", ["Test Launch", timestamp()]),
        ("post", "start_test_item", ["Test Item", timestamp(), "STEP"]),
        ("put", "update_test_item", ["test_item_id"]),
    ],
)
def test_connection_errors(rp_client, requests_method, client_method, client_params):
    rp_client._RPClient__launch_uuid = "test_launch_id"
    rp_client.session.get.return_value = DummyResponse()
    getattr(rp_client.session, requests_method).side_effect = connection_error
    result = getattr(rp_client, client_method)(*client_params)
    assert result is None

    getattr(rp_client.session, requests_method).side_effect = response_error
    result = getattr(rp_client, client_method)(*client_params)
    assert result is None

    getattr(rp_client.session, requests_method).side_effect = invalid_response
    result = getattr(rp_client, client_method)(*client_params)
    assert result is None


LAUNCH_ID = 333
EXPECTED_DEFAULT_URL = "http://endpoint/ui/#project/launches/all/" + str(LAUNCH_ID)
EXPECTED_DEBUG_URL = "http://endpoint/ui/#project/userdebug/all/" + str(LAUNCH_ID)


@pytest.mark.parametrize(
    "launch_mode, project_name, expected_url",
    [
        ("DEFAULT", "project", EXPECTED_DEFAULT_URL),
        ("DEBUG", "project", EXPECTED_DEBUG_URL),
        ("DEFAULT", "PROJECT", EXPECTED_DEFAULT_URL),
        ("debug", "PROJECT", EXPECTED_DEBUG_URL),
    ],
)
def test_launch_url_get(rp_client, launch_mode, project_name, expected_url):
    rp_client._RPClient__launch_uuid = "test_launch_id"
    rp_client._RPClient__project = project_name

    response = mock.Mock()
    response.is_success = True
    response.json.side_effect = lambda: {"mode": launch_mode, "id": LAUNCH_ID}

    def get_call(*args, **kwargs):
        return response

    rp_client.session.get.side_effect = get_call

    assert rp_client.get_launch_ui_url() == expected_url


@mock.patch("reportportal_client.client.getenv")
@mock.patch("reportportal_client.client.send_event")
def test_skip_statistics(send_event, getenv, rp_client):
    getenv.return_value = "1"
    client = RPClient("http://endpoint", "project", "api_key")
    client.session = rp_client.session
    client.start_launch("Test Launch", timestamp())
    assert mock.call("start_launch", None, None) not in send_event.mock_calls


@mock.patch("reportportal_client.client.getenv")
@mock.patch("reportportal_client.client.send_event")
def test_statistics(send_event, getenv, rp_client):
    getenv.return_value = ""
    client = RPClient("http://endpoint", "project", "api_key")
    client.session = rp_client.session
    client.start_launch("Test Launch", timestamp())
    assert mock.call("start_launch", None, None) in send_event.mock_calls


def test_clone():
    args = ["http://endpoint", "project"]
    kwargs = {
        "api_key": "api_key",
        "log_batch_size": 30,
        "is_skipped_an_issue": False,
        "verify_ssl": False,
        "retries": 5,
        "max_pool_size": 30,
        "launch_id": "test-123",
        "http_timeout": (30, 30),
        "log_batch_payload_limit": 1000000,
        "mode": "DEBUG",
    }
    client = RPClient(*args, **kwargs)
    client._add_current_item("test-321")
    client._add_current_item("test-322")
    cloned = client.clone()
    assert cloned is not None and client is not cloned
    assert cloned.endpoint == args[0] and cloned.project == args[1]
    assert (
        cloned.api_key == kwargs["api_key"]
        and cloned.log_batch_size == kwargs["log_batch_size"]
        and cloned.is_skipped_an_issue == kwargs["is_skipped_an_issue"]
        and cloned.verify_ssl == kwargs["verify_ssl"]
        and cloned.retries == kwargs["retries"]
        and cloned.max_pool_size == kwargs["max_pool_size"]
        and cloned.launch_uuid == kwargs["launch_id"]
        and cloned.launch_id == kwargs["launch_id"]
        and cloned.http_timeout == kwargs["http_timeout"]
        and cloned.log_batch_payload_limit == kwargs["log_batch_payload_limit"]
        and cloned.mode == kwargs["mode"]
    )
    assert cloned._item_stack.qsize() == 1 and client.current_item() == cloned.current_item()


@mock.patch("reportportal_client.client.warnings.warn")
def test_deprecated_token_argument(warn):
    api_key = "api_key"
    client = RPClient(endpoint="http://endpoint", project="project", token=api_key)

    assert warn.call_count == 1
    assert client.api_key == api_key


@mock.patch("reportportal_client.client.warnings.warn")
def test_api_key_argument(warn):
    api_key = "api_key"
    client = RPClient(endpoint="http://endpoint", project="project", api_key=api_key)

    assert warn.call_count == 0
    assert client.api_key == api_key


def test_empty_api_key_argument():
    """Test that empty api_key raises ValueError."""
    api_key = ""
    with pytest.raises(ValueError) as exc_info:
        RPClient(endpoint="http://endpoint", project="project", api_key=api_key)

    assert "Authentication credentials are required" in str(exc_info.value)


def test_launch_uuid_print(rp_client):
    str_io = StringIO()
    output_mock = mock.Mock()
    output_mock.get_output.side_effect = lambda: str_io
    client = RPClient(
        endpoint="http://endpoint", project="project", api_key="test", launch_uuid_print=True, print_output=output_mock
    )
    client.session = rp_client.session
    client._skip_analytics = "True"
    client.start_launch("Test Launch", timestamp())
    assert "ReportPortal Launch UUID: " in str_io.getvalue()


def test_no_launch_uuid_print(rp_client):
    str_io = StringIO()
    output_mock = mock.Mock()
    output_mock.get_output.side_effect = lambda: str_io
    client = RPClient(
        endpoint="http://endpoint",
        project="project",
        api_key="test",
        launch_uuid_print=False,
        print_output=output_mock,
    )
    client.session = rp_client.session
    client._skip_analytics = "True"
    client.start_launch("Test Launch", timestamp())
    assert "ReportPortal Launch UUID: " not in str_io.getvalue()


@mock.patch("reportportal_client.client.sys.stdout", new_callable=StringIO)
def test_launch_uuid_print_default_io(mock_stdout, rp_client):
    client = RPClient(endpoint="http://endpoint", project="project", api_key="test", launch_uuid_print=True)
    client.session = rp_client.session
    client._skip_analytics = "True"
    client.start_launch("Test Launch", timestamp())

    assert "ReportPortal Launch UUID: " in mock_stdout.getvalue()


@mock.patch("reportportal_client.client.sys.stdout", new_callable=StringIO)
def test_launch_uuid_print_default_print(mock_stdout, rp_client):
    client = RPClient(endpoint="http://endpoint", project="project", api_key="test")
    client.session = rp_client.session
    client._skip_analytics = "True"
    client.start_launch("Test Launch", timestamp())

    assert "ReportPortal Launch UUID: " not in mock_stdout.getvalue()


def test_client_pickling():
    client = RPClient("http://localhost:8080", "default_personal", api_key="test_key")
    pickled_client = pickle.dumps(client)
    unpickled_client = pickle.loads(pickled_client)
    assert unpickled_client is not None


@pytest.mark.parametrize(
    "method, call_method, arguments",
    [
        ("start_launch", "post", ["Test Launch", timestamp()]),
        ("start_test_item", "post", ["Test Item", timestamp(), "SUITE"]),
        ("finish_test_item", "put", ["test_item_uuid", timestamp()]),
        ("finish_launch", "put", [timestamp()]),
        ("update_test_item", "put", ["test_item_uuid"]),
    ],
)
def test_attribute_truncation(rp_client: RPClient, method, call_method, arguments):
    # noinspection PyTypeChecker
    session: mock.Mock = rp_client.session
    session.get.return_value = DummyResponse()
    if method != "start_launch":
        rp_client._RPClient__launch_uuid = "test_launch_id"

    getattr(rp_client, method)(*arguments, **{"attributes": {"key": "value" * 26}})
    getattr(session, call_method).assert_called_once()
    kwargs = getattr(session, call_method).call_args_list[0][1]
    assert "attributes" in kwargs["json"]
    assert kwargs["json"]["attributes"]
    assert len(kwargs["json"]["attributes"][0]["value"]) == 128


@pytest.mark.parametrize(
    "method, call_method, arguments",
    [
        ("start_launch", "post", ["Test Launch", timestamp()]),
        ("start_test_item", "post", ["Test Item", timestamp(), "SUITE"]),
        ("finish_test_item", "put", ["test_item_uuid", timestamp()]),
        ("finish_launch", "put", [timestamp()]),
        ("update_test_item", "put", ["test_item_uuid"]),
        ("get_launch_info", "get", []),
        ("get_project_settings", "get", []),
        ("get_item_id_by_uuid", "get", ["test_item_uuid"]),
        ("log", "post", [timestamp(), "Test Message"]),
    ],
)
def test_http_timeout_bypass(method, call_method, arguments):
    http_timeout = (35.1, 33.3)
    rp_client = RPClient("http://endpoint", "project", "api_key", http_timeout=http_timeout, log_batch_size=1)
    session: mock.Mock = mock.Mock()
    session.get.return_value = DummyResponse()
    session.post.return_value = DummyResponse()
    session.put.return_value = DummyResponse()
    rp_client.session = session
    rp_client._skip_analytics = "True"

    if method != "start_launch":
        rp_client._RPClient__launch_uuid = "test_launch_id"

    getattr(rp_client, method)(*arguments)
    getattr(session, call_method).assert_called_once()
    kwargs = getattr(session, call_method).call_args_list[0][1]
    assert "timeout" in kwargs
    assert kwargs["timeout"] == http_timeout


def test_logs_flush_on_close(rp_client: RPClient):
    # noinspection PyTypeChecker
    session: mock.Mock = rp_client.session
    batcher: mock.Mock = mock.Mock()
    batcher.flush.return_value = [RPRequestLog("test_launch_uuid", timestamp(), message="test_message")]
    rp_client._log_batcher = batcher

    rp_client.close()

    batcher.flush.assert_called_once()
    session.post.assert_called_once()
    session.close.assert_called_once()


def test_oauth_authentication_parameters():
    """Test that OAuth 2.0 authentication parameters work correctly."""
    client = RPClient(
        endpoint="http://endpoint",
        project="project",
        oauth_uri="https://example.com/oauth/token",
        oauth_username="test_user",
        oauth_password="test_password",
        oauth_client_id="test_client_id",
        oauth_client_secret="test_client_secret",
        oauth_scope="read write",
    )

    assert client is not None
    assert client.oauth_uri == "https://example.com/oauth/token"
    assert client.oauth_username == "test_user"
    assert client.oauth_password == "test_password"
    assert client.oauth_client_id == "test_client_id"
    assert client.oauth_client_secret == "test_client_secret"
    assert client.oauth_scope == "read write"
    assert client.api_key is None


def test_oauth_authentication_without_optional_parameters():
    """Test OAuth authentication with only required parameters."""
    client = RPClient(
        endpoint="http://endpoint",
        project="project",
        oauth_uri="https://example.com/oauth/token",
        oauth_username="test_user",
        oauth_password="test_password",
        oauth_client_id="test_client_id",
    )

    assert client is not None
    assert client.oauth_uri == "https://example.com/oauth/token"
    assert client.oauth_username == "test_user"
    assert client.oauth_password == "test_password"
    assert client.oauth_client_id == "test_client_id"
    assert client.oauth_client_secret is None
    assert client.oauth_scope is None
    assert client.api_key is None


def test_no_authentication_parameters():
    """Test that missing authentication parameters raises ValueError."""
    with pytest.raises(ValueError) as exc_info:
        RPClient(endpoint="http://endpoint", project="project")

    assert "Authentication credentials are required" in str(exc_info.value)
    assert "OAuth 2.0 parameters" in str(exc_info.value)
    assert "api_key parameter" in str(exc_info.value)


def test_partial_oauth_parameters():
    """Test that missing authentication parameters raises ValueError."""
    with pytest.raises(ValueError) as exc_info:
        RPClient(
            endpoint="http://endpoint",
            project="project",
            oauth_uri="https://example.com/oauth/token",
            oauth_username="test_user",
            oauth_password="test_password",
        )

    assert "Authentication credentials are required" in str(exc_info.value)
    assert "OAuth 2.0 parameters" in str(exc_info.value)
    assert "api_key parameter" in str(exc_info.value)


def test_clone_with_oauth():
    """Test cloning a client with OAuth authentication."""
    args = ["http://endpoint", "project"]
    kwargs = {
        "oauth_uri": "https://example.com/oauth/token",
        "oauth_username": "test_user",
        "oauth_password": "test_password",
        "oauth_client_id": "test_client_id",
        "oauth_client_secret": "test_secret",
        "oauth_scope": "read write",
        "log_batch_size": 30,
        "is_skipped_an_issue": False,
        "verify_ssl": False,
        "retries": 5,
        "max_pool_size": 30,
        "launch_id": "test-123",
        "http_timeout": (30, 30),
        "log_batch_payload_limit": 1000000,
        "mode": "DEBUG",
    }
    client = RPClient(*args, **kwargs)
    client._add_current_item("test-321")
    client._add_current_item("test-322")
    cloned = client.clone()

    assert cloned is not None and client is not cloned
    assert cloned.endpoint == args[0] and cloned.project == args[1]
    assert (
        cloned.oauth_uri == kwargs["oauth_uri"]
        and cloned.oauth_username == kwargs["oauth_username"]
        and cloned.oauth_password == kwargs["oauth_password"]
        and cloned.oauth_client_id == kwargs["oauth_client_id"]
        and cloned.oauth_client_secret == kwargs["oauth_client_secret"]
        and cloned.oauth_scope == kwargs["oauth_scope"]
        and cloned.log_batch_size == kwargs["log_batch_size"]
        and cloned.is_skipped_an_issue == kwargs["is_skipped_an_issue"]
        and cloned.verify_ssl == kwargs["verify_ssl"]
        and cloned.retries == kwargs["retries"]
        and cloned.max_pool_size == kwargs["max_pool_size"]
        and cloned.launch_uuid == kwargs["launch_id"]
        and cloned.launch_id == kwargs["launch_id"]
        and cloned.http_timeout == kwargs["http_timeout"]
        and cloned.log_batch_payload_limit == kwargs["log_batch_payload_limit"]
        and cloned.mode == kwargs["mode"]
    )
    assert cloned._item_stack.qsize() == 1 and client.current_item() == cloned.current_item()


def test_api_key_authorization_header():
    """Test that API key authentication sets Authorization header correctly."""
    api_key = "test_api_key_12345"
    client = RPClient(endpoint="http://endpoint", project="project", api_key=api_key)

    # Mock the underlying requests.Session within ClientSession
    # noinspection PyProtectedMember
    underlying_session_mock = mock.Mock()
    underlying_session_mock.get.return_value = DummyResponse()
    underlying_session_mock.post.return_value = DummyResponse()
    underlying_session_mock.put.return_value = DummyResponse()
    # noinspection PyProtectedMember
    client.session._client = underlying_session_mock
    client._skip_analytics = "1"

    # Make a request
    client.get_project_settings()

    # Verify the underlying session.get was called
    underlying_session_mock.get.assert_called_once()
    call_kwargs = underlying_session_mock.get.call_args_list[0][1]

    # Verify Authorization header is set correctly
    assert "headers" in call_kwargs
    assert "Authorization" in call_kwargs["headers"]
    assert call_kwargs["headers"]["Authorization"] == f"Bearer {api_key}"


def test_oauth_authorization_header():
    """Test that OAuth authentication sets Authorization header correctly."""
    client = RPClient(
        endpoint="http://endpoint",
        project="project",
        oauth_uri="https://example.com/oauth/token",
        oauth_username="test_user",
        oauth_password="test_password",
        oauth_client_id="test_client_id",
    )

    # Mock the underlying requests.Session within ClientSession
    # noinspection PyProtectedMember
    underlying_session_mock = mock.Mock()
    underlying_session_mock.get.return_value = DummyResponse()
    underlying_session_mock.post.return_value = DummyResponse()
    underlying_session_mock.put.return_value = DummyResponse()
    # noinspection PyProtectedMember
    client.session._client = underlying_session_mock
    client._skip_analytics = "1"

    # Mock the Auth.get() method to return a test token
    test_token = "test_oauth_token_xyz"
    client.auth._access_token = test_token
    with mock.patch.object(client.auth, "_is_token_expired", return_value=False):
        # Make a request
        client.get_project_settings()

    # Verify the underlying session.get was called
    underlying_session_mock.get.assert_called_once()
    call_kwargs = underlying_session_mock.get.call_args_list[0][1]

    # Verify Authorization header is set correctly
    assert "headers" in call_kwargs
    assert "Authorization" in call_kwargs["headers"]
    assert call_kwargs["headers"]["Authorization"] == f"Bearer {test_token}"
