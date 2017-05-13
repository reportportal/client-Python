# ReportPortal python client

[![PyPI](https://img.shields.io/pypi/v/reportportal-client.svg?maxAge=2592000)](https://pypi.python.org/pypi/reportportal-client)
[![Build Status](https://travis-ci.org/reportportal/client-Python.svg?branch=master)](https://travis-ci.org/reportportal/client-Python)

Library used only for implementors of custom listeners for ReportPortal


## Allready implemented listeners:

- [Robot Framework](https://github.com/reportportal/agent-Python-RobotFramework)
- [PyTest Framework](https://github.com/reportportal/agent-python-pytest)


## Installation

The latest stable version is available on PyPI:

```
pip install reportportal-client
```


## Usage

Main classes are:

- reportportal_client.ReportPortalService
- reportportal_client.StartLaunchRQ
- reportportal_client.StartTestItemRQ
- reportportal_client.FinishTestItemRQ
- reportportal_client.FinishExecutionRQ
- reportportal_client.SaveLogRQ

Basic usage example:

```python
import os
import subprocess
from time import time
from mimetypes import guess_type

from reportportal_client import (ReportPortalService,
                                 FinishExecutionRQ,
                                 StartLaunchRQ, StartTestItemRQ,
                                 FinishTestItemRQ, SaveLogRQ)


def timestamp():
    return str(int(time() * 1000))


endpoint = "http://10.6.40.6:8080"
project = "default"
# You can get UUID from user profile page in the Report Portal.
token = "1adf271d-505f-44a8-ad71-0afbdf8c83bd"
launch_name = "Test launch"
launch_doc = "Testing logging with attachment."

service = ReportPortalService(endpoint=endpoint, project=project, token=token)

# Create start launch request.
sl_rq = StartLaunchRQ(name=launch_name,
                      start_time=timestamp(),
                      description=launch_doc)

# Start launch.
launch = service.start_launch(sl_rq)

# Create start test item request.
sti_rq = StartTestItemRQ(name="Test Case",
                         description="First Test Case",
                         tags=["Image", "Smoke"],
                         start_time=timestamp(),
                         launch_id=launch.id,
                         type="TEST")

# Start test item.
test = service.start_test_item(parent_item_id=None, start_test_item_rq=sti_rq)

# Create text log message with INFO level.
service.log(SaveLogRQ(item_id=test.id,
                      time=timestamp(),
                      message="Hello World!",
                      level="INFO"))

# Create log message with attached text output and WARN level.
service.attach(SaveLogRQ(item_id=test.id,
                         time=timestamp(),
                         message="Too high memory usage!",
                         level="WARN"),
               name="free_memory.txt",
               data=subprocess.check_output("free -h".split()))

# Create log message with piped binary file, INFO level and custom mimetype.
image = "/tmp/image.png"
sl_rq = SaveLogRQ(test.id, timestamp(), "Screen shot of issue.", "INFO")
with open(image, "rb") as fh:
    service.attach(save_log_rq=sl_rq,
                   name=os.path.basename(image),
                   data=fh,
                   mime=guess_type(image)[0] or "application/octet-stream")

# Create log message with binary data and INFO level.
filebin = "/tmp/file.bin"
with open(filebin, "rb") as fd:
    bindata = fd.read()
# Note here that we pass binary data instead of file handle.
service.attach(SaveLogRQ(item_id=test.id,
                         time=timestamp(),
                         message="Binary data file.",
                         level="INFO"),
               name="file.bin",
               data=bindata,
               mime="application/octet-stream")

# Create finish test item request.
fti_rq = FinishTestItemRQ(end_time=timestamp(), status="PASSED")

# Finish test item.
service.finish_test_item(item_id=test.id, finish_test_item_rq=fti_rq)

# Create finish launch request.
fl_rq = FinishExecutionRQ(end_time=timestamp(), status="PASSED")
# Finish launch.
service.finish_launch(launch.id, fl_rq)
```


# Copyright Notice

Licensed under the [GPLv3](https://www.gnu.org/licenses/quick-guide-gplv3.html)
license (see the LICENSE.txt file).
