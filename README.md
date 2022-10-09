# ReportPortal python client

[![PyPI](https://img.shields.io/pypi/v/reportportal-client.svg?maxAge=259200)](https://pypi.python.org/pypi/reportportal-client)
[![Python versions](https://img.shields.io/pypi/pyversions/reportportal-client.svg)](https://pypi.org/project/reportportal-client)
[![Build Status](https://github.com/reportportal/client-Python/actions/workflows/tests.yml/badge.svg)](https://github.com/reportportal/client-Python/actions/workflows/tests.yml)
[![codecov.io](https://codecov.io/gh/reportportal/client-Python/branch/master/graph/badge.svg)](https://codecov.io/gh/reportportal/client-Python)
[![Join Slack chat!](https://reportportal-slack-auto.herokuapp.com/badge.svg)](https://reportportal-slack-auto.herokuapp.com)
[![stackoverflow](https://img.shields.io/badge/reportportal-stackoverflow-orange.svg?style=flat)](http://stackoverflow.com/questions/tagged/reportportal)
[![Build with Love](https://img.shields.io/badge/build%20with-❤%EF%B8%8F%E2%80%8D-lightgrey.svg)](http://reportportal.io?style=flat)

Library used only for implementors of custom listeners for ReportPortal


## Already implemented listeners:

- [PyTest Framework](https://github.com/reportportal/agent-python-pytest)
- [Robot Framework](https://github.com/reportportal/agent-Python-RobotFramework)
- [Behave Framework](https://github.com/reportportal/agent-python-behave)
- [Nose Framework](https://github.com/reportportal/agent-python-nosetests)


## Installation

The latest stable version is available on PyPI:

```
pip install reportportal-client
```

**IMPORTANT!**
The latest client version **does** not support Report Portal versions below
5.0.0.

Version 3 is the latest one which supports Report Portal versions below 5.0.0
to install it:

```
pip install reportportal-client~=3.0
```


## Contribution

All the fixes for the client that supports Report Portal versions below 5.0.0
should go into the v3 branch. The master branch will store the code base for
the client for Report Portal versions 5 and above.


## Usage

Main classes are:

- reportportal_client.ReportPortalService
- reportportal_client.ReportPortalServiceAsync(Client version 3.x only)

Basic usage example:

```python
import os
import subprocess
import traceback
from mimetypes import guess_type
from time import time

# Report Portal versions below 5.0.0:
from reportportal_client import ReportPortalServiceAsync

# Report Portal versions >= 5.0.0:
from reportportal_client import ReportPortalService


def timestamp():
    return str(int(time() * 1000))


endpoint = "http://10.6.40.6:8080"
project = "default"
# You can get UUID from user profile page in the Report Portal.
token = "1adf271d-505f-44a8-ad71-0afbdf8c83bd"
launch_name = "Test launch"
launch_doc = "Testing logging with attachment."


def my_error_handler(exc_info):
    """
    This callback function will be called by async service client when error occurs.
    Return True if error is not critical and you want to continue work.
    :param exc_info: result of sys.exc_info() -> (type, value, traceback)
    :return:
    """
    print("Error occurred: {}".format(exc_info[1]))
    traceback.print_exception(*exc_info)


# Report Portal versions below 5.0.0:
service = ReportPortalServiceAsync(endpoint=endpoint, project=project,
                                   token=token, error_handler=my_error_handler)

# Report Portal versions >= 5.0.0:
service = ReportPortalService(endpoint=endpoint, project=project,
                                   token=token)

# Start launch.
launch = service.start_launch(name=launch_name,
                              start_time=timestamp(),
                              description=launch_doc)

# Start test item Report Portal versions below 5.0.0:
test = service.start_test_item(name="Test Case",
                               description="First Test Case",
                               tags=["Image", "Smoke"],
                               start_time=timestamp(),
                               item_type="STEP",
                               parameters={"key1": "val1",
                                           "key2": "val2"})

# Start test item Report Portal versions >= 5.0.0:
item_id = service.start_test_item(name="Test Case",
                                  description="First Test Case",
                                  start_time=timestamp(),
                                  item_type="STEP",
                                  parameters={"key1": "val1",
                                              "key2": "val2"})


# Create text log message with INFO level.
service.log(time=timestamp(),
            message="Hello World!",
            level="INFO")

# Create log message with attached text output and WARN level.
service.log(time=timestamp(),
            message="Too high memory usage!",
            level="WARN",
            attachment={
                "name": "free_memory.txt",
                "data": subprocess.check_output("free -h".split()),
                "mime": "text/plain"
            })

# Create log message with binary file, INFO level and custom mimetype.
image = "/tmp/image.png"
with open(image, "rb") as fh:
    attachment = {
        "name": os.path.basename(image),
        "data": fh.read(),
        "mime": guess_type(image)[0] or "application/octet-stream"
    }
    service.log(timestamp(), "Screen shot of issue.", "INFO", attachment)

# Create log message supplying only contents
service.log(
    timestamp(),
    "running processes",
    "INFO",
    attachment=subprocess.check_output("ps aux".split()))

# Finish test item Report Portal versions below 5.0.0.
service.finish_test_item(end_time=timestamp(), status="PASSED")

# Finish test item Report Portal versions >= 5.0.0.
service.finish_test_item(item_id=item_id, end_time=timestamp(), status="PASSED")

# Finish launch.
service.finish_launch(end_time=timestamp())

# Due to async nature of the service we need to call terminate() method which
# ensures all pending requests to server are processed.
# Failure to call terminate() may result in lost data.
service.terminate()
```


# Send attachment (screenshots)

[python-client](https://github.com/reportportal/client-Python/blob/64550693ec9c198b439f8f6e8b23413812d9adf1/reportportal_client/service.py#L259) uses `requests` library for working with RP and the same semantics to work with attachments (data).

There are two ways to pass data as attachment:

### Case 1 - pass file-like object
```
with open(screenshot_file_path, "rb") as image_file:
    rp_logger.info("Some Text Here",
                   attachment={"name": "test_name_screenshot.png",
                               "data": image_file,
                               "mime": "image/png"})
```

### Case 2 - pass file content itself (like you did)
```
with open(screenshot_file_path, "rb") as image_file:
        file_data = image_file.read()

rp_logger.info("Some Text Here",
               attachment={"name": "test_name_screenshot.png",
                           "data": file_data,
                           "mime": "image/png"})
```


# Copyright Notice

Licensed under the [Apache 2.0](https://www.apache.org/licenses/LICENSE-2.0)
license (see the LICENSE.txt file).
