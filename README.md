# ReportPortal python client

[![PyPI](https://img.shields.io/pypi/v/reportportal-client.svg?maxAge=259200)](https://pypi.python.org/pypi/reportportal-client)
[![Python versions](https://img.shields.io/pypi/pyversions/reportportal-client.svg)](https://pypi.org/project/reportportal-client)
[![Build Status](https://github.com/reportportal/client-Python/actions/workflows/tests.yml/badge.svg)](https://github.com/reportportal/client-Python/actions/workflows/tests.yml)
[![codecov.io](https://codecov.io/gh/reportportal/client-Python/branch/develop/graph/badge.svg)](https://codecov.io/gh/reportportal/client-Python)
[![Join Slack chat!](https://img.shields.io/badge/slack-join-brightgreen.svg)](https://slack.epmrpp.reportportal.io/)
[![stackoverflow](https://img.shields.io/badge/reportportal-stackoverflow-orange.svg?style=flat)](http://stackoverflow.com/questions/tagged/reportportal)
[![Build with Love](https://img.shields.io/badge/build%20with-❤%EF%B8%8F%E2%80%8D-lightgrey.svg)](http://reportportal.io?style=flat)

Library used only for implementors of custom listeners for ReportPortal

## Already implemented listeners:

- [PyTest Framework](https://github.com/reportportal/agent-python-pytest)
- [Robot Framework](https://github.com/reportportal/agent-Python-RobotFramework)
- [Behave Framework](https://github.com/reportportal/agent-python-behave)
- [Nose Framework (archived)](https://github.com/reportportal/agent-python-nosetests)

## Installation

The latest stable version is available on PyPI:

```
pip install reportportal-client
```

## Usage

Basic usage example:

```python
import os
import subprocess
from mimetypes import guess_type

from reportportal_client import RPClient
from reportportal_client.helpers import timestamp

endpoint = "http://docker.local:8080"
project = "default"
# You can get UUID from user profile page in the ReportPortal.
api_key = "1adf271d-505f-44a8-ad71-0afbdf8c83bd"
launch_name = "Test launch"
launch_doc = "Testing logging with attachment."


client = RPClient(endpoint=endpoint, project=project,
                  api_key=api_key)

# Start log upload thread
client.start()

# Start launch.
launch = client.start_launch(name=launch_name,
                             start_time=timestamp(),
                             description=launch_doc)

item_id = client.start_test_item(name="Test Case",
                                 description="First Test Case",
                                 start_time=timestamp(),
                                 attributes=[{"key": "key", "value": "value"},
                                             {"value", "tag"}],
                                 item_type="STEP",
                                 parameters={"key1": "val1",
                                             "key2": "val2"})

# Create text log message with INFO level.
client.log(time=timestamp(),
           message="Hello World!",
           level="INFO")

# Create log message with attached text output and WARN level.
client.log(time=timestamp(),
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
    client.log(timestamp(), "Screen shot of issue.", "INFO", attachment)

client.finish_test_item(item_id=item_id, end_time=timestamp(), status="PASSED")

# Finish launch.
client.finish_launch(end_time=timestamp())

# Due to async nature of the service we need to call terminate() method which
# ensures all pending requests to server are processed.
# Failure to call terminate() may result in lost data.
client.terminate()
```

# Send attachment (screenshots)

The client uses `requests` library for working with RP and the same semantics
to work with attachments (data).

To log an attachment you need to pass file content and metadata to ``

```python
import logging

from reportportal_client import RPLogger, RPLogHandler

logging.setLoggerClass(RPLogger)
rp_logger = logging.getLogger(__name__)
rp_logger.setLevel(logging.DEBUG)
rp_logger.addHandler(RPLogHandler())

screenshot_file_path = 'path/to/file.png'

with open(screenshot_file_path, "rb") as image_file:
    file_data = image_file.read()

    # noinspection PyArgumentList
    rp_logger.info(
        "Some Text Here",
        attachment={"name": "test_name_screenshot.png",
                    "data": file_data,
                    "mime": "image/png"}
    )
```

# Copyright Notice

Licensed under the [Apache 2.0](https://www.apache.org/licenses/LICENSE-2.0)
license (see the LICENSE.txt file).
