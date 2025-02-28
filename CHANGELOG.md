# Changelog

## [Unreleased]

## [5.6.2]
### Fixed
- Issue [#246](https://github.com/reportportal/client-Python/issues/246): Invalid return type, by @HardNorth
### Changed
- `helpers.common_helpers.gen_attributes` function now accepts refactored, by @HardNorth

## [5.6.1]
### Added
- `markdown_helpers` module in `reportportal_client.helpers` package, by @HardNorth
### Changed
- `helpers.is_binary` function to improve binary content detection, by @HardNorth
- `helpers` module moved to `reportportal_client.helpers` package, by @HardNorth

## [5.6.0]
### Added
- `match_pattern` and `translate_glob_to_regex`, `normalize_caseless`, `caseless_equal` functions in `helpers` module, by @HardNorth
- `client.RP.start_test_item` method and all its children now accept `uuid` argument, by @HardNorth
### Removed
- `Python 3.7` support, by @HardNorth

## [5.5.10]
### Added
- Official `Python 3.13` support, by @HardNorth
### Fixed
- Issue [#244](https://github.com/reportportal/client-Python/issues/244): Client crash on different error responses, by @HardNorth

## [5.5.9]
### Fixed
- Empty parameter Dict conversion, by @HardNorth

## [5.5.8]
### Removed
- Retries of requests ended with `504` HTTP status code, since it's not clear if the request was delivered or not, by @HardNorth
### Changed
- `client.RP.start_test_item` method and all its children now accept `retry_of` argument, by @HardNorth
- `client.RP.finish_test_item` method and all its children now accept `retry_of` argument, by @HardNorth
- `client.RP.finish_test_item` method and all its children now accept `test_case_id` argument, by @HardNorth

## [5.5.7]
### Added
- `helpers.to_bool` function, by @HardNorth
- Official `Python 3.12` support, by @HardNorth
### Fixed
- SSL context when certificate is provided, by @JLBIZ
- Log Record pathnames are incorrect on python3.11, by @dagansandler

## [5.5.6]
### Added
- `CONTENT_TYPE_TO_EXTENSIONS` constant in `helpers` module, by @HardNorth
### Fixed
- Issue [#228](https://github.com/reportportal/client-Python/issues/228): AttributeError on very large request, by @HardNorth
### Changed
- `helpers.gen_attributes` now accepts `Iterable[str]` argument instead of `List[str]`, by @HardNorth

## [5.5.5]
### Added
- `is_binary` method in `helpers` module, by @HardNorth
- `guess_content_type_from_bytes` method in `helpers` module, by @HardNorth

## [5.5.4]
### Added
- Issue [#225](https://github.com/reportportal/client-Python/issues/225): JSON decoding error logging, by @HardNorth
### Fixed
- Issue [#226](https://github.com/reportportal/client-Python/issues/226): Logging batch flush on client close, by @HardNorth

## [5.5.3]
### Fixed
- Python 3.7 support, by @HardNorth
- Launch UUID attribute for AIO clients, by @HardNorth
- Http timeout bypass for Sync Client, by @HardNorth

## [5.5.2]
### Fixed
- Attribute truncation for every method with attributes, by @HardNorth

## [5.5.1]
### Fixed
- Multipart file upload for Async clients, by @HardNorth

## [5.5.0]
### Added
- `RP` class in `reportportal_client.client` module as common interface for all ReportPortal clients, by @HardNorth
- `reportportal_client.aio` with asynchronous clients and auxiliary classes, by @HardNorth
- Dependency on `aiohttp` and `certifi`, by @HardNorth
### Changed
- RPClient class does not use separate Thread for log processing anymore, by @HardNorth
- Use `importlib.metadata` package for distribution data extraction for Python versions starting 3.8, by @HardNorth
- `helpers.verify_value_length` function updated to truncate attribute keys also and reveal attributes were truncated, by @HardNorth
### Removed
- Dependency on `six`, by @HardNorth

## [5.4.1]
### Changed
- Unified ReportPortal product naming, by @HardNorth
- `RPClient` internal item stack implementation changed to `LifoQueue` to maintain concurrency better, by @HardNorth
### Removed
- Unused `delayed_assert` dependency, by @HardNorth

## [5.4.0]
### Added
- `launch_uuid_print` and `print_output` arguments in `RPClient` class constructor, by @HardNorth
### Removed
- Python 2.7, 3.6 support, by @HardNorth

## [5.3.5]
### Added
- `__getstate__` and `__setstate__` methods in `RPClient` class to make it possible to pickle it, by @HardNorth
### Changed
- `token` field of `RPClient` class was renamed to `api_key` to maintain common convention, by @HardNorth
### Fixed
- Issue [#214](https://github.com/reportportal/client-Python/issues/214): HTTP RFC compliance fix for getting project settings, by @hanikhan

## [5.3.4]
### Added
- Check for parent `RPClient` object in thread before logging, by @HardNorth

## [5.3.3]
### Added
- `RPClient.clone()` method, by @HardNorth
### Fixed
- Client crash in case of Client ID reading error, by @HardNorth

## [5.3.2]
### Fixed
- Client crash in case of Client ID saving error, by @HardNorth

## [5.3.1]
### Added
- `MAX_LOG_BATCH_SIZE` constant into `log_manager` module, by @HardNorth
### Fixed
- Missed `verify_ssl` argument passing to `LogManager` class, by @rplevka
### Changed
- Statistics service was refactored, by @HardNorth

## [5.3.0]
### Fixed
- Issue [#198](https://github.com/reportportal/client-Python/issues/198): Python 3.8+ logging issue, by @HardNorth
- Issue [#200](https://github.com/reportportal/client-Python/issues/200): max_pool_size not worked without retries setting, by @ericscobell
- Issue [#202](https://github.com/reportportal/client-Python/issues/202): TypeError on request make, by @HardNorth
### Changed
- Statistics service rewrite, by @HardNorth
### Removed
- Deprecated code, `service.py` and `LogManager` in `core` package, by @HardNorth

## [5.2.5]
### Fixed
- Issue [#194](https://github.com/reportportal/client-Python/issues/194): logging URL generation, by @HardNorth
- Issue [#195](https://github.com/reportportal/client-Python/issues/195): `None` mode exception, by @HardNorth

## [5.2.4]
### Changed
- `LogManager` class moved from `core` package to `logs` package, by @HardNorth
### Fixed
- Issue [#192](https://github.com/reportportal/client-Python/issues/192): launch URL generation, by @HardNorth

## [5.2.3]
### Added
- Ability to pass client instance in `RPLogHandler` constructor, by @HardNorth
- Issue [#179](https://github.com/reportportal/client-Python/issues/179): batch logging request payload size tracking, by @HardNorth
### Fixed
- Issue [#184](https://github.com/reportportal/client-Python/issues/184): early logger initialization exception, by @dagansandler

## [5.2.2]
### Fixed
- Issue [#182](https://github.com/reportportal/client-Python/issues/182): logger crash on empty client, by @HardNorth

## [5.2.1]
### Fixed
- Issue [#180](https://github.com/reportportal/client-Python/issues/180): logger crash on attachments, by @HardNorth
### Changed
- Log processing does not stop on the first error now, by @HardNorth

## [5.2.0]
### Changed
- Client fixes, by @HardNorth
