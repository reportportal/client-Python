"""This module contains common functions-helpers of the client and agents.

Copyright (c) 2018 http://reportportal.io .
Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at
http://www.apache.org/licenses/LICENSE-2.0
Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
"""

import logging

logger = logging.getLogger(__name__)


def gen_attributes(rp_attributes):
    """Generate list of attributes for the API request.

    Example of input list:
    ['tag_name:tag_value1', 'tag_value2']
    Output of the function for the given input list:
    [{'key': 'tag_name', 'value': 'tag_value1'}, {'value': 'tag_value2'}]

    :param rp_attributes: List of attributes(tags)
    :return:              Correctly created list of dictionaries
                          to be passed to RP
    """
    attrs = []
    for rp_attr in rp_attributes:
        try:
            key, value = rp_attr.split(':')
            attr_dict = {'key': key, 'value': value}
        except ValueError as exc:
            logger.exception(str(exc))
            attr_dict = {'value': rp_attr}

        if all(attr_dict.values()):
            attrs.append(attr_dict)
            continue
        logger.debug('Failed to process "{0}" attribute, attribute value'
                     ' should not be empty.'.format(rp_attr))
    return attrs
