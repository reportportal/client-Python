"""This modules includes unit tests for the service.py module."""


from datetime import datetime
from six.moves import mock

from delayed_assert import expect, assert_expectations

from reportportal_client.service import (
    _convert_string,
    _get_data,
    _get_id,
    _get_json,
    _get_messages,
    _get_msg,
    _list_to_payload
)


class TestServiceFunctions:
    """This class contains test methods for helper functions."""

    def test_check_convert_to_string(self):
        """Test for support and convert strings to utf-8."""
        expect(_convert_string("Hello world") == 'Hello world')
        expect(lambda: isinstance(_convert_string("Hello world"), str))
        assert_expectations()

    def test_list_to_payload(self):
        """Test convert dict to list of dicts."""
        initial_dict = {'key': "value", 'key1': 'value1'}
        expected_list = [{'key': 'key', 'value': 'value'},
                         {'key': 'key1', 'value': 'value1'}]
        assert _list_to_payload(initial_dict) == expected_list

    def test_get_id(self, response):
        """Test for the get_id function."""
        assert _get_id(response(200, {"id": 123})) == 123

    def test_get_msg(self, response):
        """Test for the get_msg function."""
        fake_json = {"id": 123}
        assert _get_msg(response(200, fake_json)) == fake_json

    def test_get_data(self, response):
        """Test for the get_data function."""
        fake_json = {"id": 123}
        assert _get_data(response(200, fake_json)) == fake_json

    def test_get_json(self, response):
        """Test for the get_json function."""
        fake_json = {"id": 123}
        assert _get_json(response(200, fake_json)) == fake_json

    def test_get_messages(self):
        """Test for the get_messages function."""
        data = {"responses": [{"errorCode": 422, "message": "error"}]}
        assert _get_messages(data) == ['422: error']


class TestReportPortalService:
    """This class stores methods which test ReportPortalService."""

    @mock.patch('reportportal_client.service._get_data')
    def test_start_launch(self, mock_get, rp_service):
        """Test start launch and sending request.

        :param mock_get:   Mocked _get_data() function
        :param rp_service: Pytest fixture
        """
        mock_get.return_value = {"id": 111}
        launch_id = rp_service.start_launch('name', datetime.now().isoformat())
        assert launch_id == 111

    @mock.patch('reportportal_client.service._get_msg')
    def test_finish_launch(self, mock_get, rp_service):
        """Test finish launch and sending request.

        :param mock_get:   Mocked _get_msg() function
        :param rp_service: Pytest fixture
        """
        mock_get.return_value = {"id": 111}
        _get_msg = rp_service.finish_launch('name', datetime.now().isoformat())
        assert _get_msg == {"id": 111}
