# Changelog

## [Unreleased]
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
