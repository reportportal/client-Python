#ReportPortal python client 

[![PyPI](https://img.shields.io/pypi/v/reportportal-client.svg?maxAge=2592000)](https://pypi.python.org/pypi/reportportal-client)

Library used only for implementors of custom listeners for ReportPortal

## Allready implemented listeners:
* [Robot Framework](https://github.com/reportportal/agent-Python-RobotFramework)


## Installation

The latest stable version is available on PyPI:

    pip install reportportal-client


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
from time import time
from reportportal_client import (ReportPortalService, 
                                 FinishExecutionRQ,
                                 StartLaunchRQ, StartTestItemRQ,
                                 FinishTestItemRQ, SaveLogRQ)

def timestamp():
    return str(int(time() * 1000))

endpoint = "https://urlpreportportal"
project = "ProjectName"
token = "uuid" #you can get it from profile page in ReportPortal
launch_name = "name for launch"
launch_doc = "Some text documentation for launch"

service = ReportPortalService(endpoint=endpoint,
                              project=project,
                              token=token)

#Start Launch
sl_rq = StartLaunchRQ(name=launch_name,
                      start_time=timestamp(),
                      description=launch_doc)                  
r = service.start_launch(sl_rq)
launch_id = r.id

#Finish Launch
fl_rq = FinishExecutionRQ(end_time=timestamp(),
                          status="PASSED")
service.finish_launch(launch_id, fl_rq)
```

# Copyright Notice
Licensed under the [GPLv3](https://www.gnu.org/licenses/quick-guide-gplv3.html)
license (see the LICENSE.txt file).
