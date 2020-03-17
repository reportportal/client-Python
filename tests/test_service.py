try:
    from unittest.mock import create_autospec, Mock, patch, MagicMock
except ImportError:
    from mock import create_autospec, Mock, patch, MagicMock

from reportportal_client.service import _convert_string, _list_to_payload, \
    uri_join, _get_id, _get_msg, _get_data, _get_json, _get_messages, \
    ReportPortalService

import unittest
from datetime import datetime


class TestServiceFunctions(unittest.TestCase):
    """
    Test for main functions in service.py
    """
    def test_check_convert_to_string(self):
        """
        Test for support and convert strings to utf-8
        """
        self.assertEqual(_convert_string("Hello world"), 'Hello world')
        self.assertEqual(type(_convert_string("Hello world")), str)

    def test_list_to_payload(self):
        """
        Test for convert dict to list of dicts
        """
        initial_dict = {'key': "value", 'key1': 'value1'}
        expected_list = [{'key': 'key', 'value': 'value'},
                         {'key': 'key1', 'value': 'value1'}]
        self.assertEqual(_list_to_payload(initial_dict), expected_list)

    def test_get_id(self):
        """Test for get id from Response obj"""
        fake_json = {"id": 123}

        """
        Mocking Response obj
        :param status_code 200
        :param return JSON obj fake_json
        """
        with patch('requests.Response', new_callable=MagicMock()) as mock_get:
            mock_get.status_code = 200
            mock_get.json.return_value = fake_json

            obj = _get_id(mock_get)

        self.assertEqual(obj, 123)

    def test_get_msg(self):
        """Test  get_msg recieved from Response"""
        fake_json = {"id": 123}

        """
        Mocking Response object
        :param status_code int
        :param return_value json obj
        :return (dict) fake_json
        """
        with patch('requests.Response', new_callable=MagicMock()) as mock_get:
            mock_get.status_code = 200
            mock_get.json.return_value = fake_json

            obj = _get_msg(mock_get)

        self.assertEqual(obj, fake_json)

    def test_get_data(self):
        """
        Test for get data from Response
        :return: dict
        """
        fake_json = {"id": 123}

        """
        Mocking Response obj
        :param status_code int
        :param return_value dict
        :return (dict) fake_json
        """
        with patch('requests.Response', new_callable=MagicMock()) as mock_get:
            mock_get.status_code = 200
            mock_get.json.return_value = fake_json

            obj = _get_data(mock_get)

        self.assertEqual(obj, fake_json)

    def test_get_json(self):
        """Test get json from Response"""
        fake_json = {"id": 123}

        """
        Mocking Response obj
        :param status_code int
        :param return_value = dict
        :return (dict) fake_json
        """
        with patch('requests.Response', new_callable=MagicMock()) as mock_get:
            mock_get.status_code = 200
            mock_get.json.return_value = fake_json

            obj = _get_json(mock_get)

        self.assertEqual(obj, fake_json)

    def test_get_messages(self):
        """Test for get message from response
        :param: Response
        :return: list
        """
        data = {"responses": [{"errorCode": 422, "message": "error"}]}

        obj = _get_messages(data)

        self.assertEqual(obj, ['422: error'])


class ReportPortalServiceTest(unittest.TestCase):
    def setUp(self):
        """Creating ReportPortalService Instance and Mocking session"""
        self.rp = ReportPortalService('http://endpoint', 'project', 'token')
        self.rp.session = MagicMock()

    """Testing for start launch and sending request"""
    def test_start_launch(self):
        """
        Mocking _get_data function
        :param return_value dict
        :return: (int) id
        """
        with patch('reportportal_client.service._get_data',
                   new_callable=Mock()) as mock_get:
            mock_get.return_value = {"id": 111}
            launch_id = self.rp.start_launch('name',
                                             datetime.now().isoformat())
        self.assertEqual(launch_id, 111)

    """Testing for finish launch and sending request"""
    def test_finish_launch(self):
        """
        Mocking get_msg
        :param: return_value dict
        :return: (dict) json obj
        """
        with patch('reportportal_client.service._get_msg',
                   new_callable=Mock()) as mock_get:
            mock_get.return_value = {"id": 111}
            _get_msg = self.rp.finish_launch('name',
                                             datetime.now().isoformat())
        self.assertEqual(_get_msg, {"id": 111})
