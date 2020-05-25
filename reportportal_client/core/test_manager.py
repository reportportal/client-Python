"""This module contains functional for test items management.

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

from pprint import pprint
from random import randint
from time import time
from weakref import ref

import six


# todo: add logging
# todo: update logic for log items
# todo: add type hinting (pyi)
# todo: remove testing code
# todo: [optional] add unittests


def _convert_string(value):
    """Support and convert strings in py2 and py3.

    :param value: input string
    :return value: convert string
    """
    if isinstance(value, six.text_type):
        # Don't try to encode 'unicode' in Python 2.
        return value
    return str(value)


def _dict_to_payload(dictionary):
    """Convert dict to list of dicts.

    :param dictionary: initial dict
    :return list: list of dicts
    """
    system = dictionary.pop("system", False)
    return [
        {"key": key, "value": _convert_string(value), "system": system}
        for key, value in sorted(dictionary.items())
    ]


# Todo: draft class for testing purpose
class BaseItem(object):
    def __init__(self, weight, data):
        self.uuid = str(randint(0, 1000))
        self.data = data
        self.weight = weight

        self.parent = None

        self.request = None
        self.response = None

    def set_parent(self, parent):
        self.parent = ref(parent)


# Todo: draft class for testing purpose
class TestItem(BaseItem):
    def __init__(self, name, item_type, data):
        super(TestItem, self).__init__(weight=None, data=data)
        self.name = name
        self.type = item_type

        self.children = []

        self.request = None
        self.response = None

    def add_child(self, child):
        child.set_parent(self)
        self.children.append(child)

    def update(self, data):
        self.data.update(data)

    def finish(self, data):
        self.data.update(data)

    def remove(self):
        # Todo: Remove children chain
        self.parent and self.parent().children.remove(self)


# Todo: draft class for testing purpose
class LogItem(BaseItem):
    def __init__(self, data):
        super(LogItem, self).__init__(weight=None, data=data)


class TestManager(object):
    """Manage test items during single launch.

    Test item types (item_type) can be:
        (SUITE, STORY, TEST, SCENARIO, STEP, BEFORE_CLASS,
        BEFORE_GROUPS, BEFORE_METHOD, BEFORE_SUITE, BEFORE_TEST, AFTER_CLASS,
        AFTER_GROUPS, AFTER_METHOD, AFTER_SUITE, AFTER_TEST).

    'attributes' and 'parameters' should be a dictionary
        with the following format:
            {
                "<key1>": "<value1>",
                "<key2>": "<value2>",
                ...
            }
    """

    def __init__(self, launch_id):
        self.launch_id = launch_id
        self.__storage = []

    def __add_test_item(self, test_item, parent_item_id=None):
        """Create test item with given params.

        :param test_item:       test item or log object
        :param parent_item_id:  parent item uuid for given test item
        :return: test item uuid
        """
        if not parent_item_id:
            self.__storage.append(test_item)
        else:
            self.get_test_item(parent_item_id).add_child(test_item)

        # Todo: wait for response to get item uuid
        return test_item.uuid

    def start_test_item(self,
                        name,
                        start_time,
                        item_type,
                        description=None,
                        attributes=None,
                        parameters=None,
                        parent_item_id=None,
                        has_stats=True,
                        **kwargs):
        """Start new test item.

        :param name:            test item name
        :param start_time:      test item execution start time
        :param item_type:       test item type (see class doc string)
        :param description:     test item description
        :param attributes:      test item attributes(tags)
                                Pairs of key and value (see class doc string)
        :param parameters:      test item set of parameters
                                (for parametrized tests) (see class doc string)
        :param parent_item_id:  UUID of parent test item
        :param has_stats:       True - regular test item, False - test item
                                without statistics (nested step)
        :param kwargs:          other parameters
        :return:                test item UUID
        """
        if attributes and isinstance(attributes, dict):
            attributes = _dict_to_payload(attributes)
        if parameters:
            parameters = _dict_to_payload(parameters)

        data = {
            "name": name,
            "description": description,
            "attributes": attributes,
            "startTime": start_time,
            "launchUuid": self.launch_id,
            "type": item_type,
            "parameters": parameters,
            "hasStats": has_stats
        }
        kwargs and data.update(kwargs)
        new_test_item = TestItem(name, item_type, data)
        return self.__add_test_item(new_test_item, parent_item_id)

    def update_test_item(self, item_uuid, attributes=None, description=None,
                         **kwargs):
        """Update existing test item at the Report Portal.

        :param str item_uuid:   test item UUID returned on the item start
        :param str description: test item description
        :param list attributes: test item attributes(tags)
                                Pairs of key and value (see class doc string)
        """
        data = {
            "description": description,
            "attributes": attributes,
        }
        self.get_test_item(item_uuid).update(data)

    def finish_test_item(self,
                         item_uuid,
                         end_time,
                         status,
                         issue=None,
                         attributes=None,
                         **kwargs):
        """Finish the test item.

        :param item_uuid:  id of the test item
        :param end_time:   time in UTC format
        :param status:     status of the test
        :param issue:      description of an issue
        :param attributes: list of attributes
        :param kwargs:     other parameters
        """
        # check if skipped test should not be marked as "TO INVESTIGATE"
        if issue is None and status == "SKIPPED":
            issue = {"issue_type": "NOT_ISSUE"}

        if attributes and isinstance(attributes, dict):
            attributes = _dict_to_payload(attributes)

        data = {
            "endTime": end_time,
            "status": status,
            "issue": issue,
            "launchUuid": self.launch_id,
            "attributes": attributes
        }
        kwargs and data.update(kwargs)
        self.get_test_item(item_uuid).finish(data)

    def remove_test_item(self, item_uuid):
        """Remove test item by uuid.

        :param item_uuid: test item uuid
        """
        test_item = self.get_test_item(item_uuid)
        if test_item.parent:
            test_item.remove()
        else:
            self.__storage.remove(test_item)

    def log(self, time, message, level=None, attachment=None, item_id=None):
        """Log message. Can be added to test item in any state.

        :param time:        log time
        :param message:     log message
        :param level:       log level
        :param attachment:  attachments t o log (images,files,etc.)
        :param item_id:     parent item UUID
        :return:            log item UUID
        """
        data = {
            "launchUuid": self.launch_id,
            "time": time,
            "message": message,
            "level": level,
        }
        if item_id:
            data["itemUuid"] = item_id
        elif attachment:
            data["attachment"] = attachment

        return self.__add_test_item(LogItem(data), parent_item_id=item_id)

    def get_test_item(self, item_uuid):
        """Get test item by its uuid in the storage.

        :param item_uuid: test item uuid
        :return: test item object if found else None
        """
        # Todo: add 'force' parameter to get item from report portal server
        #  instead of cache and update cache data according to this request
        return self._find_item(item_uuid, self.__storage)

    def _find_item(self, item_uuid, storage):
        """Find test item by its uuid in given storage.

        :param item_uuid: test item uuid
        :param storage: list with test item objects
        :return: test item object if found else None
        """
        for test_item in storage:
            if item_uuid == test_item.uuid:
                return test_item
            else:
                if hasattr(test_item, "children") and test_item.children:
                    found_item = self._find_item(item_uuid,
                                                 test_item.children)
                    if found_item:
                        return found_item


if __name__ == '__main__':
    # Testing

    def timestamp():
        return str(int(time() * 1000))


    launch_id = 'Lola launch'
    tm = TestManager(launch_id)
    ids = list()

    print("\n\nCreate")
    print("Test items structure:\n\\a\n\\b\n\t\\c\n\t\t\\d\n\\e\n")

    ids.append(tm.start_test_item(name="Test Case a",
                                  description="First Test Case",
                                  tags=["Image", "Smoke"],
                                  start_time=timestamp(),
                                  item_type="SUITE",
                                  parameters={"key1": "val1",
                                              "key2": "val2"}))

    ids.append(tm.start_test_item(name="Test Case b",
                                  description="Test Case",
                                  tags=["Image", "Smoke"],
                                  start_time=timestamp(),
                                  item_type="STEP",
                                  parameters={"key1": "val1",
                                              "key2": "val2"}))

    ids.append(tm.start_test_item(name="Test Case c",
                                  description="Test Case",
                                  tags=["Image", "Smoke"],
                                  start_time=timestamp(),
                                  item_type="STEP",
                                  parent_item_id=ids[1],
                                  parameters={"key1": "val1",
                                              "key2": "val2"}))

    ids.append(tm.start_test_item(name="Test Case d",
                                  description="Test Case",
                                  tags=["Image", "Smoke"],
                                  start_time=timestamp(),
                                  item_type="STEP",
                                  parent_item_id=ids[2],
                                  parameters={"key1": "val1",
                                              "key2": "val2"}))

    ids.append(tm.start_test_item(name="Test Case e",
                                  description="First Test Case",
                                  tags=["Image", "Smoke"],
                                  start_time=timestamp(),
                                  item_type="SUITE",
                                  parameters={"key1": "val1",
                                              "key2": "val2"}))

    print("ids:", [x for x in ids], "\n")


    def foo(aaa):
        print("\n")
        print(aaa, aaa.uuid, aaa.name)
        print(aaa.parent)
        print(aaa.children)
        pprint(aaa.data)


    for x in ids:
        foo(tm.get_test_item(x))

    # Negative check:
    assert tm.get_test_item('dsdsd') is None

    print("\n\nUpdate")
    tm.update_test_item(ids[1])
    tm.update_test_item(ids[3])

    foo(tm.get_test_item(ids[1]))
    foo(tm.get_test_item(ids[3]))

    print("\n\nFinish")
    tm.finish_test_item(ids[3], timestamp(), "SKIPPED")
    tm.finish_test_item(ids[2], timestamp(), "PASS")

    foo(tm.get_test_item(ids[2]))
    foo(tm.get_test_item(ids[3]))

    print("\n\nLogs")
    log_id_1 = tm.log(timestamp(), "running processes", "INFO")
    log_id_2 = tm.log(timestamp(), "running processes", "ERROR", item_id=ids[3])

    foo(tm.get_test_item(ids[3]))
    log1 = tm.get_test_item(log_id_1)
    print(log1, log1.uuid, log1.parent)
    log2 = tm.get_test_item(log_id_2)
    print(log2, log2.uuid, log2.parent)

    print("\n\nRemove")
    foo(tm.get_test_item(ids[2]))
    tm.remove_test_item(ids[3])
    assert tm.get_test_item(ids[3]) is None
    foo(tm.get_test_item(ids[2]))

    foo(tm.get_test_item(ids[0]))
    tm.remove_test_item(ids[0])
    assert tm.get_test_item(ids[0]) is None
