#  Copyright (c) 2022 EPAM Systems
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

"""This module contains classes representing RP file object."""

import uuid


class RPFile(object):
    """Class representation for a file that will be attached to the log."""

    def __init__(self,
                 name=None,
                 content=None,
                 content_type=None,
                 data=None,
                 mime=None):
        """Initialize instance attributes.

        :param name:         File name
        :param content:      File content
        :param content_type: File content type (i.e. application/pdf)
        :param data:         File content
        :param mime:         File content type (i.e. application/pdf)
        """
        self.content = content or data
        self.content_type = content_type or mime
        self.name = name if name and name.strip() else str(uuid.uuid4())

    @property
    def payload(self):
        """Get HTTP payload for the request."""
        return {
            'content': self.content,
            'contentType': self.content_type,
            'name': self.name
        }
