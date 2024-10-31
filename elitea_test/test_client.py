import pytest
from unittest.mock import Mock, patch
from reportportal_client import RPClient, OutputType, StepReporter, Issue
from requests import Session
from requests.adapters import HTTPAdapter

@pytest.fixture
def rp_client():
    return RPClient(
        endpoint="http://example.com",
        project="test_project",
        api_key="test_api_key",
        log_batch_size=20,
        is_skipped_an_issue=True,
        verify_ssl=True,
        retries=3,
        max_pool_size=50,
        launch_uuid="test_launch_uuid",
        http_timeout=(10, 10),
        log_batch_payload_size=1024,
        mode="DEFAULT",
        launch_uuid_print=False,
        print_output=OutputType.STDOUT
    )

def test_launch_uuid(rp_client):
    assert rp_client.launch_uuid == "test_launch_uuid"

def test_endpoint(rp_client):
    assert rp_client.endpoint == "http://example.com"

def test_project(rp_client):
    assert rp_client.project == "test_project"

def test_step_reporter(rp_client):
    assert isinstance(rp_client.step_reporter, StepReporter)

def test_init_session(rp_client):
    rp_client._RPClient__init_session()
    assert isinstance(rp_client.session, Session)
    assert rp_client.session.headers['Authorization'] == 'Bearer test_api_key'

def test_start_launch(rp_client):
    with patch.object(rp_client, 'start_launch', return_value="launch_uuid") as mock_start_launch:
        result = rp_client.start_launch(
            name="Test Launch",
            start_time="2023-01-01T00:00:00.000Z",
            description="Test Description",
            attributes=[{"key": "value"}],
            rerun=False,
            rerun_of=None
        )
        assert result == "launch_uuid"
        mock_start_launch.assert_called_once()

def test_start_test_item(rp_client):
    with patch.object(rp_client, 'start_test_item', return_value="item_uuid") as mock_start_test_item:
        result = rp_client.start_test_item(
            name="Test Item",
            start_time="2023-01-01T00:00:00.000Z",
            item_type="test",
            description="Test Description",
            attributes=[{"key": "value"}],
            parameters={"param": "value"},
            parent_item_id=None,
            has_stats=True,
            code_ref=None,
            retry=False,
            test_case_id=None
        )
        assert result == "item_uuid"
        mock_start_test_item.assert_called_once()

def test_finish_test_item(rp_client):
    with patch.object(rp_client, 'finish_test_item', return_value="response") as mock_finish_test_item:
        result = rp_client.finish_test_item(
            item_id="item_uuid",
            end_time="2023-01-01T00:00:00.000Z",
            status="PASSED",
            issue=None,
            attributes=[{"key": "value"}],
            description="Test Description",
            retry=False
        )
        assert result == "response"
        mock_finish_test_item.assert_called_once()

def test_finish_launch(rp_client):
    with patch.object(rp_client, 'finish_launch', return_value="response") as mock_finish_launch:
        result = rp_client.finish_launch(
            end_time="2023-01-01T00:00:00.000Z",
            status="PASSED",
            attributes=[{"key": "value"}]
        )
        assert result == "response"
        mock_finish_launch.assert_called_once()

def test_update_test_item(rp_client):
    with patch.object(rp_client, 'update_test_item', return_value="response") as mock_update_test_item:
        result = rp_client.update_test_item(
            item_uuid="item_uuid",
            attributes=[{"key": "value"}],
            description="Updated Description"
        )
        assert result == "response"
        mock_update_test_item.assert_called_once()

def test_get_launch_info(rp_client):
    with patch.object(rp_client, 'get_launch_info', return_value={"info": "data"}) as mock_get_launch_info:
        result = rp_client.get_launch_info()
        assert result == {"info": "data"}
        mock_get_launch_info.assert_called_once()

def test_get_item_id_by_uuid(rp_client):
    with patch.object(rp_client, 'get_item_id_by_uuid', return_value="item_id") as mock_get_item_id_by_uuid:
        result = rp_client.get_item_id_by_uuid("item_uuid")
        assert result == "item_id"
        mock_get_item_id_by_uuid.assert_called_once()

def test_get_launch_ui_id(rp_client):
    with patch.object(rp_client, 'get_launch_ui_id', return_value=123) as mock_get_launch_ui_id:
        result = rp_client.get_launch_ui_id()
        assert result == 123
        mock_get_launch_ui_id.assert_called_once()

def test_get_launch_ui_url(rp_client):
    with patch.object(rp_client, 'get_launch_ui_url', return_value="http://example.com/launch") as mock_get_launch_ui_url:
        result = rp_client.get_launch_ui_url()
        assert result == "http://example.com/launch"
        mock_get_launch_ui_url.assert_called_once()

def test_get_project_settings(rp_client):
    with patch.object(rp_client, 'get_project_settings', return_value={"settings": "data"}) as mock_get_project_settings:
        result = rp_client.get_project_settings()
        assert result == {"settings": "data"}
        mock_get_project_settings.assert_called_once()

def test_log(rp_client):
    with patch.object(rp_client, 'log', return_value=("response",)) as mock_log:
        result = rp_client.log(
            time="2023-01-01T00:00:00.000Z",
            message="Test log message",
            level="INFO",
            attachment=None,
            item_id="item_uuid"
        )
        assert result == ("response",)
        mock_log.assert_called_once()

def test_current_item(rp_client):
    with patch.object(rp_client, 'current_item', return_value="item_uuid") as mock_current_item:
        result = rp_client.current_item()
        assert result == "item_uuid"
        mock_current_item.assert_called_once()

def test_clone(rp_client):
    with patch.object(rp_client, 'clone', return_value=rp_client) as mock_clone:
        result = rp_client.clone()
        assert result == rp_client
        mock_clone.assert_called_once()

def test_close(rp_client):
    with patch.object(rp_client, 'close') as mock_close:
        rp_client.close()
        mock_close.assert_called_once()

def test_is_skipped_an_issue(rp_client):
    assert rp_client.is_skipped_an_issue is True

def test_verify_ssl(rp_client):
    assert rp_client.verify_ssl is True

def test_retries(rp_client):
    assert rp_client.retries == 3

def test_max_pool_size(rp_client):
    assert rp_client.max_pool_size == 50

def test_http_timeout(rp_client):
    assert rp_client.http_timeout == (10, 10)

def test_log_batch_payload_size(rp_client):
    assert rp_client.log_batch_payload_size == 1024

def test_mode(rp_client):
    assert rp_client.mode == "DEFAULT"

def test_launch_uuid_print(rp_client):
    assert rp_client.launch_uuid_print is False

def test_print_output(rp_client):
    assert rp_client.print_output == OutputType.STDOUT

def test_log_batch_size(rp_client):
    assert rp_client.log_batch_size == 20


# Error Handling Tests

def test_start_launch_network_error(rp_client):
    with patch.object(rp_client.session, 'post', side_effect=requests.exceptions.ConnectionError):
        result = rp_client.start_launch(
            name="Test Launch",
            start_time="2023-01-01T00:00:00.000Z",
            description="Test Description",
            attributes=[{"key": "value"}],
            rerun=False,
            rerun_of=None
        )
        assert result is None


def test_start_test_item_network_error(rp_client):
    with patch.object(rp_client.session, 'post', side_effect=requests.exceptions.ConnectionError):
        result = rp_client.start_test_item(
            name="Test Item",
            start_time="2023-01-01T00:00:00.000Z",
            item_type="test",
            description="Test Description",
            attributes=[{"key": "value"}],
            parameters={"param": "value"},
            parent_item_id=None,
            has_stats=True,
            code_ref=None,
            retry=False,
            test_case_id=None
        )
        assert result is None


def test_finish_test_item_network_error(rp_client):
    with patch.object(rp_client.session, 'put', side_effect=requests.exceptions.ConnectionError):
        result = rp_client.finish_test_item(
            item_id="item_uuid",
            end_time="2023-01-01T00:00:00.000Z",
            status="PASSED",
            issue=None,
            attributes=[{"key": "value"}],
            description="Test Description",
            retry=False
        )
        assert result is None


def test_finish_launch_network_error(rp_client):
    with patch.object(rp_client.session, 'put', side_effect=requests.exceptions.ConnectionError):
        result = rp_client.finish_launch(
            end_time="2023-01-01T00:00:00.000Z",
            status="PASSED",
            attributes=[{"key": "value"}]
        )
        assert result is None


def test_update_test_item_network_error(rp_client):
    with patch.object(rp_client.session, 'put', side_effect=requests.exceptions.ConnectionError):
        result = rp_client.update_test_item(
            item_uuid="item_uuid",
            attributes=[{"key": "value"}],
            description="Updated Description"
        )
        assert result is None


def test_get_launch_info_network_error(rp_client):
    with patch.object(rp_client.session, 'get', side_effect=requests.exceptions.ConnectionError):
        result = rp_client.get_launch_info()
        assert result is None


def test_get_item_id_by_uuid_network_error(rp_client):
    with patch.object(rp_client.session, 'get', side_effect=requests.exceptions.ConnectionError):
        result = rp_client.get_item_id_by_uuid("item_uuid")
        assert result is None


def test_get_launch_ui_id_network_error(rp_client):
    with patch.object(rp_client.session, 'get', side_effect=requests.exceptions.ConnectionError):
        result = rp_client.get_launch_ui_id()
        assert result is None


def test_get_launch_ui_url_network_error(rp_client):
    with patch.object(rp_client.session, 'get', side_effect=requests.exceptions.ConnectionError):
        result = rp_client.get_launch_ui_url()
        assert result is None


def test_get_project_settings_network_error(rp_client):
    with patch.object(rp_client.session, 'get', side_effect=requests.exceptions.ConnectionError):
        result = rp_client.get_project_settings()
        assert result is None


def test_log_network_error(rp_client):
    with patch.object(rp_client.session, 'post', side_effect=requests.exceptions.ConnectionError):
        result = rp_client.log(
            time="2023-01-01T00:00:00.000Z",
            message="Test log message",
            level="INFO",
            attachment=None,
            item_id="item_uuid"
        )
        assert result is None


# Parameterized Tests
@pytest.mark.parametrize("name, start_time, description, attributes, rerun, rerun_of", [
    ("Launch 1", "2023-01-01T00:00:00.000Z", "Description 1", [{"key": "value1"}], False, None),
    ("Launch 2", "2023-01-02T00:00:00.000Z", "Description 2", [{"key": "value2"}], True, "rerun_uuid")
])
def test_start_launch_param(rp_client, name, start_time, description, attributes, rerun, rerun_of):
    with patch.object(rp_client, 'start_launch', return_value="launch_uuid") as mock_start_launch:
        result = rp_client.start_launch(
            name=name,
            start_time=start_time,
            description=description,
            attributes=attributes,
            rerun=rerun,
            rerun_of=rerun_of
        )
        assert result == "launch_uuid"
        mock_start_launch.assert_called_once()


@pytest.mark.parametrize("name, start_time, item_type, description, attributes, parameters, parent_item_id, has_stats, code_ref, retry, test_case_id", [
    ("Item 1", "2023-01-01T00:00:00.000Z", "test", "Description 1", [{"key": "value1"}], {"param1": "value1"}, None, True, None, False, None),
    ("Item 2", "2023-01-02T00:00:00.000Z", "test", "Description 2", [{"key": "value2"}], {"param2": "value2"}, "parent_uuid", False, "code_ref", True, "test_case_id")
])
def test_start_test_item_param(rp_client, name, start_time, item_type, description, attributes, parameters, parent_item_id, has_stats, code_ref, retry, test_case_id):
    with patch.object(rp_client, 'start_test_item', return_value="item_uuid") as mock_start_test_item:
        result = rp_client.start_test_item(
            name=name,
            start_time=start_time,
            item_type=item_type,
            description=description,
            attributes=attributes,
            parameters=parameters,
            parent_item_id=parent_item_id,
            has_stats=has_stats,
            code_ref=code_ref,
            retry=retry,
            test_case_id=test_case_id
        )
        assert result == "item_uuid"
        mock_start_test_item.assert_called_once()


@pytest.mark.parametrize("item_id, end_time, status, issue, attributes, description, retry", [
    ("item_uuid_1", "2023-01-01T00:00:00.000Z", "PASSED", None, [{"key": "value1"}], "Description 1", False),
    ("item_uuid_2", "2023-01-02T00:00:00.000Z", "FAILED", Issue(), [{"key": "value2"}], "Description 2", True)
])
def test_finish_test_item_param(rp_client, item_id, end_time, status, issue, attributes, description, retry):
    with patch.object(rp_client, 'finish_test_item', return_value="response") as mock_finish_test_item:
        result = rp_client.finish_test_item(
            item_id=item_id,
            end_time=end_time,
            status=status,
            issue=issue,
            attributes=attributes,
            description=description,
            retry=retry
        )
        assert result == "response"
        mock_finish_test_item.assert_called_once()


@pytest.mark.parametrize("end_time, status, attributes", [
    ("2023-01-01T00:00:00.000Z", "PASSED", [{"key": "value1"}]),
    ("2023-01-02T00:00:00.000Z", "FAILED", [{"key": "value2"}])
])
def test_finish_launch_param(rp_client, end_time, status, attributes):
    with patch.object(rp_client, 'finish_launch', return_value="response") as mock_finish_launch:
        result = rp_client.finish_launch(
            end_time=end_time,
            status=status,
            attributes=attributes
        )
        assert result == "response"
        mock_finish_launch.assert_called_once()


@pytest.mark.parametrize("item_uuid, attributes, description", [
    ("item_uuid_1", [{"key": "value1"}], "Updated Description 1"),
    ("item_uuid_2", [{"key": "value2"}], "Updated Description 2")
])
def test_update_test_item_param(rp_client, item_uuid, attributes, description):
    with patch.object(rp_client, 'update_test_item', return_value="response") as mock_update_test_item:
        result = rp_client.update_test_item(
            item_uuid=item_uuid,
            attributes=attributes,
            description=description
        )
        assert result == "response"
        mock_update_test_item.assert_called_once()


@pytest.mark.parametrize("time, message, level, attachment, item_id", [
    ("2023-01-01T00:00:00.000Z", "Test log message 1", "INFO", None, "item_uuid_1"),
    ("2023-01-02T00:00:00.000Z", "Test log message 2", "ERROR", {"name": "attachment.txt", "data": b"data"}, "item_uuid_2")
])
def test_log_param(rp_client, time, message, level, attachment, item_id):
    with patch.object(rp_client, 'log', return_value=("response",)) as mock_log:
        result = rp_client.log(
            time=time,
            message=message,
            level=level,
            attachment=attachment,
            item_id=item_id
        )
        assert result == ("response",)
        mock_log.assert_called_once()
