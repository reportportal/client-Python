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

"""This module contains ReportPortal Client interface and synchronous implementation class."""

import logging
import queue
import sys
import warnings
from abc import abstractmethod
from os import getenv
from typing import Union, Tuple, Any, Optional, TextIO, List, Dict

import aenum
import requests
from requests.adapters import HTTPAdapter, Retry, DEFAULT_RETRIES

# noinspection PyProtectedMember
from reportportal_client._internal.local import set_current
# noinspection PyProtectedMember
from reportportal_client._internal.logs.batcher import LogBatcher
# noinspection PyProtectedMember
from reportportal_client._internal.services.statistics import send_event
# noinspection PyProtectedMember
from reportportal_client._internal.static.abstract import AbstractBaseClass
# noinspection PyProtectedMember
from reportportal_client._internal.static.defines import NOT_FOUND
from reportportal_client.core.rp_issues import Issue
from reportportal_client.core.rp_requests import (HttpRequest, ItemStartRequest, ItemFinishRequest, RPFile,
                                                  LaunchStartRequest, LaunchFinishRequest, RPRequestLog,
                                                  RPLogBatch)
from reportportal_client.helpers import uri_join, verify_value_length, agent_name_version, LifoQueue
from reportportal_client.logs import MAX_LOG_BATCH_PAYLOAD_SIZE
from reportportal_client.steps import StepReporter

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())


class OutputType(aenum.Enum):
    """Enum of possible print output types."""

    STDOUT = aenum.auto()
    STDERR = aenum.auto()

    def get_output(self) -> Optional[TextIO]:
        """Return TextIO based on the current type."""
        if self == OutputType.STDOUT:
            return sys.stdout
        if self == OutputType.STDERR:
            return sys.stderr


class RP(metaclass=AbstractBaseClass):
    """Common interface for ReportPortal clients.

    This abstract class serves as common interface for different ReportPortal clients. It's implemented to
    ease migration from version to version and to ensure that each particular client has the same methods.
    """

    __metaclass__ = AbstractBaseClass

    @property
    @abstractmethod
    def launch_uuid(self) -> Optional[str]:
        """Return current Launch UUID.

        :return: UUID string.
        """
        raise NotImplementedError('"launch_uuid" property is not implemented!')

    @property
    def launch_id(self) -> Optional[str]:
        """Return current Launch UUID.

        :return: UUID string.
        """
        warnings.warn(
            message='`launch_id` property is deprecated since 5.5.0 and will be subject for removing in the'
                    ' next major version. Use `launch_uuid` property instead.',
            category=DeprecationWarning,
            stacklevel=2
        )
        return self.launch_uuid

    @property
    @abstractmethod
    def endpoint(self) -> str:
        """Return current base URL.

        :return: base URL string.
        """
        raise NotImplementedError('"endpoint" property is not implemented!')

    @property
    @abstractmethod
    def project(self) -> str:
        """Return current Project name.

        :return: Project name string.
        """
        raise NotImplementedError('"project" property is not implemented!')

    @property
    @abstractmethod
    def step_reporter(self) -> StepReporter:
        """Return StepReporter object for the current launch.

        :return: StepReporter to report steps.
        """
        raise NotImplementedError('"step_reporter" property is not implemented!')

    @abstractmethod
    def start_launch(self,
                     name: str,
                     start_time: str,
                     description: Optional[str] = None,
                     attributes: Optional[Union[list, dict]] = None,
                     rerun: bool = False,
                     rerun_of: Optional[str] = None,
                     **kwargs) -> Optional[str]:
        """Start a new Launch with the given arguments.

        :param name:        Launch name.
        :param start_time:  Launch start time.
        :param description: Launch description.
        :param attributes:  Launch attributes.
        :param rerun:       Start launch in rerun mode.
        :param rerun_of:    For rerun mode specifies which launch will be re-run. Should be used with the
                            'rerun' option.
        :return:            Launch UUID if successfully started or None.
        """
        raise NotImplementedError('"start_launch" method is not implemented!')

    @abstractmethod
    def start_test_item(self,
                        name: str,
                        start_time: str,
                        item_type: str,
                        description: Optional[str] = None,
                        attributes: Optional[Union[List[dict], dict]] = None,
                        parameters: Optional[dict] = None,
                        parent_item_id: Optional[str] = None,
                        has_stats: bool = True,
                        code_ref: Optional[str] = None,
                        retry: bool = False,
                        test_case_id: Optional[str] = None,
                        **kwargs: Any) -> Optional[str]:
        """Start Test Case/Suite/Step/Nested Step Item.

        :param name:           Name of the Test Item.
        :param start_time:     The Item start time.
        :param item_type:      Type of the Test Item. Allowed values:
                               "suite", "story", "test", "scenario", "step", "before_class", "before_groups",
                               "before_method", "before_suite", "before_test", "after_class", "after_groups",
                               "after_method", "after_suite", "after_test".
        :param description:    The Item description.
        :param attributes:     Test Item attributes.
        :param parameters:     Set of parameters (for parametrized Test Items).
        :param parent_item_id: A UUID of a parent SUITE / STEP.
        :param has_stats:      Set to False if test item is a Nested Step.
        :param code_ref:       Physical location of the Test Item.
        :param retry:          Used to report retry of the test. Allowed values: "True" or "False".
        :param test_case_id:   A unique ID of the current Step.
        :return:               Test Item UUID if successfully started or None.
        """
        raise NotImplementedError('"start_test_item" method is not implemented!')

    @abstractmethod
    def finish_test_item(self,
                         item_id: str,
                         end_time: str,
                         status: str = None,
                         issue: Optional[Issue] = None,
                         attributes: Optional[Union[list, dict]] = None,
                         description: str = None,
                         retry: bool = False,
                         **kwargs: Any) -> Optional[str]:
        """Finish Test Suite/Case/Step/Nested Step Item.

        :param item_id:     ID of the Test Item.
        :param end_time:    The Item end time.
        :param status:      Test status. Allowed values:
                            PASSED, FAILED, STOPPED, SKIPPED, INTERRUPTED, CANCELLED, INFO, WARN or None.
        :param issue:       Issue which will be attached to the current Item.
        :param attributes:  Test Item attributes(tags). Pairs of key and value. These attributes override
                            attributes on start Test Item call.
        :param description: Test Item description. Overrides description from start request.
        :param retry:       Used to report retry of the test. Allowed values: "True" or "False".
        :return:            Response message.
        """
        raise NotImplementedError('"finish_test_item" method is not implemented!')

    @abstractmethod
    def finish_launch(self,
                      end_time: str,
                      status: str = None,
                      attributes: Optional[Union[list, dict]] = None,
                      **kwargs: Any) -> Optional[str]:
        """Finish a Launch.

        :param end_time:   Launch end time.
        :param status:     Launch status. Can be one of the followings:
                           PASSED, FAILED, STOPPED, SKIPPED, INTERRUPTED, CANCELLED.
        :param attributes: Launch attributes. These attributes override attributes on Start Launch call.
        :return:           Response message or None.
        """
        raise NotImplementedError('"finish_launch" method is not implemented!')

    @abstractmethod
    def update_test_item(self,
                         item_uuid: Optional[str],
                         attributes: Optional[Union[list, dict]] = None,
                         description: Optional[str] = None) -> Optional[str]:
        """Update existing Test Item at the ReportPortal.

        :param item_uuid:   Test Item UUID returned on the item start.
        :param attributes:  Test Item attributes: [{'key': 'k_name', 'value': 'k_value'}, ...].
        :param description: Test Item description.
        :return:            Response message or None.
        """
        raise NotImplementedError('"update_test_item" method is not implemented!')

    @abstractmethod
    def get_launch_info(self) -> Optional[dict]:
        """Get current Launch information.

        :return: Launch information in dictionary.
        """
        raise NotImplementedError('"get_launch_info" method is not implemented!')

    @abstractmethod
    def get_item_id_by_uuid(self, item_uuid: str) -> Optional[str]:
        """Get Test Item ID by the given Item UUID.

        :param item_uuid: String UUID returned on the Item start.
        :return:          Test Item ID.
        """
        raise NotImplementedError('"get_item_id_by_uuid" method is not implemented!')

    @abstractmethod
    def get_launch_ui_id(self) -> Optional[int]:
        """Get Launch ID of the current Launch.

        :return: Launch ID of the Launch. None if not found.
        """
        raise NotImplementedError('"get_launch_ui_id" method is not implemented!')

    @abstractmethod
    def get_launch_ui_url(self) -> Optional[str]:
        """Get full quality URL of the current Launch.

        :return: Launch URL string.
        """
        raise NotImplementedError('"get_launch_ui_id" method is not implemented!')

    @abstractmethod
    def get_project_settings(self) -> Optional[dict]:
        """Get settings of the current Project.

        :return: Settings response in Dictionary.
        """
        raise NotImplementedError('"get_project_settings" method is not implemented!')

    @abstractmethod
    def log(self,
            time: str, message: str,
            level: Optional[Union[int, str]] = None,
            attachment: Optional[dict] = None,
            item_id: Optional[str] = None) -> Optional[Tuple[str, ...]]:
        """Send Log message to the ReportPortal and attach it to a Test Item or Launch.

        This method stores Log messages in internal batch and sent it when batch is full, so not every method
        call will return any response.

        :param time:       Time in UTC.
        :param message:    Log message text.
        :param level:      Message's Log level.
        :param attachment: Message's attachments(images,files,etc.).
        :param item_id:    UUID of the ReportPortal Item the message belongs to.
        :return:           Response message Tuple if Log message batch was sent or None.
        """
        raise NotImplementedError('"log" method is not implemented!')

    @abstractmethod
    def current_item(self) -> Optional[str]:
        """Retrieve the last Item reported by the client (based on the internal FILO queue).

        :return: Item UUID string.
        """
        raise NotImplementedError('"current_item" method is not implemented!')

    @abstractmethod
    def clone(self) -> 'RP':
        """Clone the Client object, set current Item ID as cloned Item ID.

        :return: Cloned client object.
        :rtype: RP
        """
        raise NotImplementedError('"clone" method is not implemented!')

    @abstractmethod
    def close(self) -> None:
        """Close current client connections."""
        raise NotImplementedError('"clone" method is not implemented!')

    def start(self) -> None:
        """Start the client."""
        warnings.warn(
            message='`start` method is deprecated since 5.5.0 and will be subject for removing in the'
                    ' next major version. There is no any necessity to call this method anymore.',
            category=DeprecationWarning,
            stacklevel=2
        )

    def terminate(self, *_: Any, **__: Any) -> None:
        """Call this to terminate the client."""
        warnings.warn(
            message='`terminate` method is deprecated since 5.5.0 and will be subject for removing in the'
                    ' next major version. There is no any necessity to call this method anymore.',
            category=DeprecationWarning,
            stacklevel=2
        )
        self.close()


class RPClient(RP):
    """ReportPortal client.

    The class is supposed to use by ReportPortal agents: both custom and official, to make calls to
    ReportPortal. It handles HTTP request and response bodies generation and serialization, connection retries
    and log batching.
    """

    api_v1: str
    api_v2: str
    base_url_v1: str
    base_url_v2: str
    __endpoint: str
    is_skipped_an_issue: bool
    __launch_uuid: str
    use_own_launch: bool
    log_batch_size: int
    log_batch_payload_size: int
    __project: str
    api_key: str
    verify_ssl: Union[bool, str]
    retries: int
    max_pool_size: int
    http_timeout: Union[float, Tuple[float, float]]
    session: requests.Session
    __step_reporter: StepReporter
    mode: str
    launch_uuid_print: Optional[bool]
    print_output: OutputType
    truncate_attributes: bool
    _skip_analytics: str
    _item_stack: LifoQueue
    _log_batcher: LogBatcher[RPRequestLog]

    @property
    def launch_uuid(self) -> Optional[str]:
        """Return current launch UUID.

        :return: UUID string
        """
        return self.__launch_uuid

    @property
    def endpoint(self) -> str:
        """Return current base URL.

        :return: base URL string
        """
        return self.__endpoint

    @property
    def project(self) -> str:
        """Return current Project name.

        :return: Project name string
        """
        return self.__project

    @property
    def step_reporter(self) -> StepReporter:
        """Return StepReporter object for the current launch.

        :return: StepReporter to report steps
        """
        return self.__step_reporter

    def __init_session(self) -> None:
        retry_strategy = Retry(
            total=self.retries,
            backoff_factor=0.1,
            status_forcelist=[429, 500, 502, 503, 504]
        ) if self.retries else DEFAULT_RETRIES
        session = requests.Session()
        session.mount('https://', HTTPAdapter(
            max_retries=retry_strategy, pool_maxsize=self.max_pool_size))
        # noinspection HttpUrlsUsage
        session.mount('http://', HTTPAdapter(
            max_retries=retry_strategy, pool_maxsize=self.max_pool_size))
        if self.api_key:
            session.headers['Authorization'] = 'Bearer {0}'.format(
                self.api_key)
        self.session = session

    def __init__(
            self,
            endpoint: str,
            project: str,
            api_key: str = None,
            log_batch_size: int = 20,
            is_skipped_an_issue: bool = True,
            verify_ssl: Union[bool, str] = True,
            retries: int = None,
            max_pool_size: int = 50,
            launch_uuid: str = None,
            http_timeout: Union[float, Tuple[float, float]] = (10, 10),
            log_batch_payload_size: int = MAX_LOG_BATCH_PAYLOAD_SIZE,
            mode: str = 'DEFAULT',
            launch_uuid_print: bool = False,
            print_output: OutputType = OutputType.STDOUT,
            log_batcher: Optional[LogBatcher[RPRequestLog]] = None,
            truncate_attributes: bool = True,
            **kwargs: Any
    ) -> None:
        """Initialize the class instance with arguments.

        :param endpoint:               Endpoint of the ReportPortal service.
        :param project:                Project name to report to.
        :param api_key:                Authorization API key.
        :param log_batch_size:         Option to set the maximum number of logs that can be processed in one
                                       batch.
        :param is_skipped_an_issue:    Option to mark skipped tests as not 'To Investigate' items on the
                                       server side.
        :param verify_ssl:             Option to skip ssl verification.
        :param retries:                Number of retry attempts to make in case of connection / server errors.
        :param max_pool_size:          Option to set the maximum number of connections to save the pool.
        :param launch_uuid:            A launch UUID to use instead of starting own one.
        :param http_timeout:           A float in seconds for connect and read timeout. Use a Tuple to
                                       specific connect and read separately.
        :param log_batch_payload_size: Maximum size in bytes of logs that can be processed in one batch.
        :param mode:                   Launch mode, all Launches started by the client will be in that mode.
        :param launch_uuid_print:      Print Launch UUID into passed TextIO or by default to stdout.
        :param print_output:           Set output stream for Launch UUID printing.
        :param log_batcher:            Use existing LogBatcher instance instead of creation of own one.
        :param truncate_attributes:    Truncate test item attributes to default maximum length.
        """
        set_current(self)
        self.api_v1, self.api_v2 = 'v1', 'v2'
        self.__endpoint = endpoint
        self.__project = project
        self.base_url_v1 = uri_join(
            self.__endpoint, 'api/{}'.format(self.api_v1), self.__project)
        self.base_url_v2 = uri_join(
            self.__endpoint, 'api/{}'.format(self.api_v2), self.__project)
        self.is_skipped_an_issue = is_skipped_an_issue
        self.__launch_uuid = launch_uuid
        if not self.__launch_uuid:
            launch_id = kwargs.get('launch_id')
            if launch_id:
                warnings.warn(
                    message='`launch_id` property is deprecated since 5.5.0 and will be subject for removing'
                            ' in the next major version. Use `launch_uuid` property instead.',
                    category=DeprecationWarning,
                    stacklevel=2
                )
                self.__launch_uuid = launch_id
        self.use_own_launch = not bool(self.__launch_uuid)
        self.log_batch_size = log_batch_size
        self.log_batch_payload_size = log_batch_payload_size
        self._log_batcher = log_batcher or LogBatcher(self.log_batch_size, self.log_batch_payload_size)
        self.verify_ssl = verify_ssl
        self.retries = retries
        self.max_pool_size = max_pool_size
        self.http_timeout = http_timeout
        self.__step_reporter = StepReporter(self)
        self._item_stack = LifoQueue()
        self.mode = mode
        self._skip_analytics = getenv('AGENT_NO_ANALYTICS')
        self.launch_uuid_print = launch_uuid_print
        self.print_output = print_output
        self.truncate_attributes = truncate_attributes

        self.api_key = api_key
        if not self.api_key:
            if 'token' in kwargs:
                warnings.warn(
                    message='Argument `token` is deprecated since 5.3.5 and will be subject for removing in '
                            'the next major version. Use `api_key` argument instead.',
                    category=DeprecationWarning,
                    stacklevel=2
                )
                self.api_key = kwargs['token']

            if not self.api_key:
                warnings.warn(
                    message='Argument `api_key` is `None` or empty string, that is not supposed to happen '
                            'because ReportPortal is usually requires an authorization key. Please check '
                            'your code.',
                    category=RuntimeWarning,
                    stacklevel=2
                )

        self.__init_session()

    def start_launch(self,
                     name: str,
                     start_time: str,
                     description: Optional[str] = None,
                     attributes: Optional[Union[list, dict]] = None,
                     rerun: bool = False,
                     rerun_of: Optional[str] = None,
                     **kwargs) -> Optional[str]:
        """Start a new Launch with the given arguments.

        :param name:        Launch name.
        :param start_time:  Launch start time.
        :param description: Launch description.
        :param attributes:  Launch attributes.
        :param rerun:       Start launch in rerun mode.
        :param rerun_of:    For rerun mode specifies which launch will be re-run. Should be used with the
                            'rerun' option.
        :return:            Launch UUID if successfully started or None.
        """
        if not self.use_own_launch:
            return self.launch_uuid
        url = uri_join(self.base_url_v2, 'launch')
        request_payload = LaunchStartRequest(
            name=name,
            start_time=start_time,
            attributes=verify_value_length(attributes) if self.truncate_attributes else attributes,
            description=description,
            mode=self.mode,
            rerun=rerun,
            rerun_of=rerun_of
        ).payload
        response = HttpRequest(self.session.post, url=url, json=request_payload, verify_ssl=self.verify_ssl,
                               http_timeout=self.http_timeout).make()
        if not response:
            return

        if not self._skip_analytics:
            send_event('start_launch', *agent_name_version(attributes))

        self.__launch_uuid = response.id
        logger.debug('start_launch - ID: %s', self.launch_uuid)
        if self.launch_uuid_print and self.print_output:
            print(f'ReportPortal Launch UUID: {self.launch_uuid}', file=self.print_output.get_output())
        return self.launch_uuid

    def start_test_item(self,
                        name: str,
                        start_time: str,
                        item_type: str,
                        description: Optional[str] = None,
                        attributes: Optional[Union[List[dict], dict]] = None,
                        parameters: Optional[dict] = None,
                        parent_item_id: Optional[str] = None,
                        has_stats: bool = True,
                        code_ref: Optional[str] = None,
                        retry: bool = False,
                        test_case_id: Optional[str] = None,
                        **_: Any) -> Optional[str]:
        """Start Test Case/Suite/Step/Nested Step Item.

        :param name:           Name of the Test Item.
        :param start_time:     The Item start time.
        :param item_type:      Type of the Test Item. Allowed values:
                               "suite", "story", "test", "scenario", "step", "before_class", "before_groups",
                               "before_method", "before_suite", "before_test", "after_class", "after_groups",
                               "after_method", "after_suite", "after_test".
        :param description:    The Item description.
        :param attributes:     Test Item attributes.
        :param parameters:     Set of parameters (for parametrized Test Items).
        :param parent_item_id: A UUID of a parent SUITE / STEP.
        :param has_stats:      Set to False if test item is a Nested Step.
        :param code_ref:       Physical location of the Test Item.
        :param retry:          Used to report retry of the test. Allowed values: "True" or "False".
        :param test_case_id:   A unique ID of the current Step.
        :return:               Test Item UUID if successfully started or None.
        """
        if parent_item_id is NOT_FOUND:
            logger.warning('Attempt to start item for non-existent parent item.')
            return
        if parent_item_id:
            url = uri_join(self.base_url_v2, 'item', parent_item_id)
        else:
            url = uri_join(self.base_url_v2, 'item')
        request_payload = ItemStartRequest(
            name,
            start_time,
            item_type,
            self.launch_uuid,
            attributes=verify_value_length(attributes) if self.truncate_attributes else attributes,
            code_ref=code_ref,
            description=description,
            has_stats=has_stats,
            parameters=parameters,
            retry=retry,
            test_case_id=test_case_id
        ).payload

        response = HttpRequest(self.session.post, url=url, json=request_payload, verify_ssl=self.verify_ssl,
                               http_timeout=self.http_timeout).make()
        if not response:
            return
        item_id = response.id
        if item_id is not NOT_FOUND:
            logger.debug('start_test_item - ID: %s', item_id)
            self._add_current_item(item_id)
        else:
            logger.warning('start_test_item - invalid response: %s',
                           str(response.json))
        return item_id

    def finish_test_item(self,
                         item_id: str,
                         end_time: str,
                         status: str = None,
                         issue: Optional[Issue] = None,
                         attributes: Optional[Union[list, dict]] = None,
                         description: str = None,
                         retry: bool = False,
                         **kwargs: Any) -> Optional[str]:
        """Finish Test Suite/Case/Step/Nested Step Item.

        :param item_id:     ID of the Test Item.
        :param end_time:    The Item end time.
        :param status:      Test status. Allowed values:
                            PASSED, FAILED, STOPPED, SKIPPED, INTERRUPTED, CANCELLED, INFO, WARN or None.
        :param issue:       Issue which will be attached to the current Item.
        :param attributes:  Test Item attributes(tags). Pairs of key and value. These attributes override
                            attributes on start Test Item call.
        :param description: Test Item description. Overrides description from start request.
        :param retry:       Used to report retry of the test. Allowed values: "True" or "False".
        :return:            Response message.
        """
        if item_id is NOT_FOUND or not item_id:
            logger.warning('Attempt to finish non-existent item')
            return
        url = uri_join(self.base_url_v2, 'item', item_id)
        request_payload = ItemFinishRequest(
            end_time,
            self.launch_uuid,
            status,
            attributes=verify_value_length(attributes) if self.truncate_attributes else attributes,
            description=description,
            is_skipped_an_issue=self.is_skipped_an_issue,
            issue=issue,
            retry=retry
        ).payload
        response = HttpRequest(self.session.put, url=url, json=request_payload, verify_ssl=self.verify_ssl,
                               http_timeout=self.http_timeout).make()
        if not response:
            return
        self._remove_current_item()
        logger.debug('finish_test_item - ID: %s', item_id)
        logger.debug('response message: %s', response.message)
        return response.message

    def finish_launch(self,
                      end_time: str,
                      status: str = None,
                      attributes: Optional[Union[list, dict]] = None,
                      **kwargs: Any) -> Optional[str]:
        """Finish launch.

        :param end_time:    Launch end time
        :param status:      Launch status. Can be one of the followings:
                            PASSED, FAILED, STOPPED, SKIPPED, RESETED,
                            CANCELLED
        :param attributes:  Launch attributes
        """
        if self.use_own_launch:
            if self.launch_uuid is NOT_FOUND or not self.launch_uuid:
                logger.warning('Attempt to finish non-existent launch')
                return
            url = uri_join(self.base_url_v2, 'launch', self.launch_uuid, 'finish')
            request_payload = LaunchFinishRequest(
                end_time,
                status=status,
                attributes=verify_value_length(attributes) if self.truncate_attributes else attributes,
                description=kwargs.get('description')
            ).payload
            response = HttpRequest(self.session.put, url=url, json=request_payload,
                                   verify_ssl=self.verify_ssl, name='Finish Launch',
                                   http_timeout=self.http_timeout).make()
            if not response:
                return
            logger.debug('finish_launch - ID: %s', self.launch_uuid)
            logger.debug('response message: %s', response.message)
            message = response.message
        else:
            message = ""
        self._log(self._log_batcher.flush())
        return message

    def update_test_item(self, item_uuid: str, attributes: Optional[Union[list, dict]] = None,
                         description: Optional[str] = None) -> Optional[str]:
        """Update existing Test Item at the ReportPortal.

        :param item_uuid:   Test Item UUID returned on the item start.
        :param attributes:  Test Item attributes: [{'key': 'k_name', 'value': 'k_value'}, ...].
        :param description: Test Item description.
        :return:            Response message or None.
        """
        data = {
            'description': description,
            'attributes': verify_value_length(attributes) if self.truncate_attributes else attributes,
        }
        item_id = self.get_item_id_by_uuid(item_uuid)
        url = uri_join(self.base_url_v1, 'item', item_id, 'update')
        response = HttpRequest(self.session.put, url=url, json=data, verify_ssl=self.verify_ssl,
                               http_timeout=self.http_timeout).make()
        if not response:
            return
        logger.debug('update_test_item - Item: %s', item_id)
        return response.message

    def _log(self, batch: Optional[List[RPRequestLog]]) -> Optional[Tuple[str, ...]]:
        if batch:
            url = uri_join(self.base_url_v2, 'log')
            response = HttpRequest(self.session.post, url, files=RPLogBatch(batch).payload,
                                   verify_ssl=self.verify_ssl, http_timeout=self.http_timeout).make()
            if response:
                return response.messages

    def log(self,
            time: str,
            message: str,
            level: Optional[Union[int, str]] = None,
            attachment: Optional[dict] = None,
            item_id: Optional[str] = None) -> Optional[Tuple[str, ...]]:
        """Send Log message to the ReportPortal and attach it to a Test Item or Launch.

        This method stores Log messages in internal batch and sent it when batch is full, so not every method
        call will return any response.

        :param time:       Time in UTC.
        :param message:    Log message text.
        :param level:      Message's Log level.
        :param attachment: Message's attachments(images,files,etc.).
        :param item_id:    UUID of the ReportPortal Item the message belongs to.
        :return:           Response message Tuple if Log message batch was sent or None.
        """
        if item_id is NOT_FOUND:
            logger.warning("Attempt to log to non-existent item")
            return
        rp_file = RPFile(**attachment) if attachment else None
        rp_log = RPRequestLog(self.launch_uuid, time, rp_file, item_id, level, message)
        return self._log(self._log_batcher.append(rp_log))

    def get_item_id_by_uuid(self, item_uuid: str) -> Optional[str]:
        """Get Test Item ID by the given Item UUID.

        :param item_uuid: String UUID returned on the Item start.
        :return:          Test Item ID.
        """
        url = uri_join(self.base_url_v1, 'item', 'uuid', item_uuid)
        response = HttpRequest(self.session.get, url=url, verify_ssl=self.verify_ssl,
                               http_timeout=self.http_timeout).make()
        return response.id if response else None

    def get_launch_info(self) -> Optional[dict]:
        """Get current Launch information.

        :return: Launch information in dictionary.
        """
        if self.launch_uuid is None:
            return {}
        url = uri_join(self.base_url_v1, 'launch', 'uuid', self.launch_uuid)
        logger.debug('get_launch_info - ID: %s', self.launch_uuid)
        response = HttpRequest(self.session.get, url=url, verify_ssl=self.verify_ssl,
                               http_timeout=self.http_timeout).make()
        if not response:
            return
        launch_info = None
        if response.is_success:
            launch_info = response.json
            logger.debug(
                'get_launch_info - Launch info: %s', response.json)
        else:
            logger.warning('get_launch_info - Launch info: '
                           'Failed to fetch launch ID from the API.')
        return launch_info

    def get_launch_ui_id(self) -> Optional[int]:
        """Get Launch ID of the current Launch.

        :return: Launch ID of the Launch. None if not found.
        """
        launch_info = self.get_launch_info()
        return launch_info.get('id') if launch_info else None

    def get_launch_ui_url(self) -> Optional[str]:
        """Get full quality URL of the current Launch.

        :return: Launch URL string.
        """
        launch_info = self.get_launch_info()
        ui_id = launch_info.get('id') if launch_info else None
        if not ui_id:
            return
        mode = launch_info.get('mode') if launch_info else None
        if not mode:
            mode = self.mode

        launch_type = 'launches' if mode.upper() == 'DEFAULT' else 'userdebug'

        path = 'ui/#{project_name}/{launch_type}/all/{launch_id}'.format(
            project_name=self.__project.lower(), launch_type=launch_type,
            launch_id=ui_id)
        url = uri_join(self.__endpoint, path)
        logger.debug('get_launch_ui_url - UUID: %s', self.launch_uuid)
        return url

    def get_project_settings(self) -> Optional[dict]:
        """Get settings of the current Project.

        :return: Settings response in Dictionary.
        """
        url = uri_join(self.base_url_v1, 'settings')
        response = HttpRequest(self.session.get, url=url, verify_ssl=self.verify_ssl,
                               http_timeout=self.http_timeout).make()
        return response.json if response else None

    def _add_current_item(self, item: str) -> None:
        """Add the last item from the self._items queue."""
        self._item_stack.put(item)

    def _remove_current_item(self) -> Optional[str]:
        """Remove the last item from the self._items queue.

        :return: Item UUID string
        """
        try:
            return self._item_stack.get()
        except queue.Empty:
            return

    def current_item(self) -> Optional[str]:
        """Retrieve the last item reported by the client (based on the internal FILO queue).

        :return: Item UUID string.
        """
        return self._item_stack.last()

    def clone(self) -> 'RPClient':
        """Clone the Client object, set current Item ID as cloned Item ID.

        :return: Cloned client object.
        :rtype: RPClient
        """
        cloned = RPClient(
            endpoint=self.__endpoint,
            project=self.__project,
            api_key=self.api_key,
            log_batch_size=self.log_batch_size,
            is_skipped_an_issue=self.is_skipped_an_issue,
            verify_ssl=self.verify_ssl,
            retries=self.retries,
            max_pool_size=self.max_pool_size,
            launch_uuid=self.launch_uuid,
            http_timeout=self.http_timeout,
            log_batch_payload_size=self.log_batch_payload_size,
            mode=self.mode,
            log_batcher=self._log_batcher
        )
        current_item = self.current_item()
        if current_item:
            cloned._add_current_item(current_item)
        return cloned

    def close(self) -> None:
        """Close current client connections."""
        self._log(self._log_batcher.flush())
        self.session.close()

    def __getstate__(self) -> Dict[str, Any]:
        """Control object pickling and return object fields as Dictionary.

        :return: object state dictionary
        :rtype: dict
        """
        state = self.__dict__.copy()
        # Don't pickle 'session' field, since it contains unpickling 'socket'
        del state['session']
        return state

    def __setstate__(self, state: Dict[str, Any]) -> None:
        """Control object pickling, receives object state as Dictionary.

        :param dict state: object state dictionary
        """
        self.__dict__.update(state)
        # Restore 'session' field
        self.__init_session()
