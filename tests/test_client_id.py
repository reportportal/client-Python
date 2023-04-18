#  Copyright (c) 2023 EPAM Systems
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

import os
import re
from uuid import UUID, uuid4

from reportportal_client.services.client_id import get_client_id
from reportportal_client.services.constants import RP_PROPERTIES_FILE_PATH


def test_get_client_id_should_return_the_id_for_two_calls():
    client_id_1 = get_client_id()
    client_id_2 = get_client_id()

    assert client_id_2 == client_id_1


def test_get_client_id_should_return_different_ids_if_store_file_removed():
    client_id_1 = get_client_id()
    os.remove(RP_PROPERTIES_FILE_PATH)
    client_id_2 = get_client_id()

    assert client_id_2 != client_id_1


def test_get_client_id_should_return_uuid():
    client_id = get_client_id()

    UUID(client_id, version=4)


def test_get_client_id_should_save_id_to_property_file():
    os.remove(RP_PROPERTIES_FILE_PATH)
    client_id = get_client_id()
    with open(RP_PROPERTIES_FILE_PATH) as fp:
        content = fp.read()
        test_pattern = re.compile(
            '^client\\.id\\s*=\\s*' + client_id + '\\s*(?:$|\\n)')
        assert test_pattern.match(content)


def test_get_client_id_should_read_id_from_property_file():
    os.remove(RP_PROPERTIES_FILE_PATH)
    client_id = str(uuid4())
    with open(RP_PROPERTIES_FILE_PATH, 'w') as fp:
        fp.write('client.id=' + client_id + '\n')

    assert get_client_id() == client_id


def test_get_client_id_should_read_id_from_property_file_if_not_empty_and_id_is_the_first_line():  # noqa: E501
    os.remove(RP_PROPERTIES_FILE_PATH)
    client_id = str(uuid4())
    with open(RP_PROPERTIES_FILE_PATH, 'w') as fp:
        fp.write('client.id=' + client_id + '\ntest.property=555\n')

    assert get_client_id() == client_id


def test_get_client_id_should_read_id_from_property_file_if_not_empty_and_id_is_not_the_first_line():  # noqa: E501
    os.remove(RP_PROPERTIES_FILE_PATH)
    client_id = str(uuid4())
    with open(RP_PROPERTIES_FILE_PATH, 'w') as fp:
        fp.write('test.property=555\nclient.id=' + client_id + '\n')

    assert get_client_id() == client_id


def test_get_client_id_should_write_id_to_property_file_if_it_is_not_empty():
    os.remove(RP_PROPERTIES_FILE_PATH)
    with open(RP_PROPERTIES_FILE_PATH, 'w') as fp:
        fp.write('test.property=555\n')

    client_id = get_client_id()
    with open(RP_PROPERTIES_FILE_PATH) as fp:
        content = fp.read()
        id_test_pattern = re.compile(
            '(?:^|\\n)client\\.id\\s*=\\s*' + client_id + '\\s*(?:$|\\n)')
        content_test_pattern = re.compile(
            '(?:^|\\n)test\\.property\\s*=\\s*555(?:$|\\n)')

    assert next(id_test_pattern.finditer(content))
    assert next(content_test_pattern.finditer(content))
