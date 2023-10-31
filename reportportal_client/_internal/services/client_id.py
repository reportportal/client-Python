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

"""This module generates and store unique client ID of an instance."""

import configparser
import io
import logging
import os
from uuid import uuid4

from .constants import CLIENT_ID_PROPERTY, RP_FOLDER_PATH, \
    RP_PROPERTIES_FILE_PATH

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())


class __NoSectionConfigParser(configparser.ConfigParser):
    DEFAULT_SECTION = 'DEFAULT'

    def __preprocess_file(self, fp):
        content = u'[' + self.DEFAULT_SECTION + ']\n' + fp.read()
        return io.StringIO(content)

    def read(self, filenames, encoding=None):
        if isinstance(filenames, str):
            filenames = [filenames]
        for filename in filenames:
            with open(filename, 'r') as fp:
                preprocessed_fp = self.__preprocess_file(fp)
                self.read_file(
                    preprocessed_fp,
                    filename)

    def write(self, fp, space_around_delimiters=True):
        for key, value in self.items(self.DEFAULT_SECTION):
            delimiter = ' = ' if space_around_delimiters else '='
            fp.write(u'{}{}{}\n'.format(key, delimiter, value))


def __read_config():
    config = __NoSectionConfigParser()
    if os.path.exists(RP_PROPERTIES_FILE_PATH):
        config.read(RP_PROPERTIES_FILE_PATH)
    return config


def _read_client_id():
    config = __read_config()
    if config.has_option(__NoSectionConfigParser.DEFAULT_SECTION,
                         CLIENT_ID_PROPERTY):
        return config.get(__NoSectionConfigParser.DEFAULT_SECTION,
                          CLIENT_ID_PROPERTY)


def _store_client_id(client_id):
    config = __read_config()
    if not os.path.exists(RP_FOLDER_PATH):
        os.makedirs(RP_FOLDER_PATH)
    config.set(__NoSectionConfigParser.DEFAULT_SECTION, CLIENT_ID_PROPERTY,
               client_id)
    with open(RP_PROPERTIES_FILE_PATH, 'w') as fp:
        config.write(fp)


def get_client_id():
    """Return unique client ID of the instance, generate new if not exists."""
    client_id = None
    try:
        client_id = _read_client_id()
    except (PermissionError, IOError) as error:
        logger.exception('[%s] Unknown exception has occurred. '
                         'Skipping client ID reading.', error)
    if not client_id:
        client_id = str(uuid4())
        try:
            _store_client_id(client_id)
        except (PermissionError, IOError) as error:
            logger.exception('[%s] Unknown exception has occurred. '
                             'Skipping client ID saving.', error)
    return client_id
