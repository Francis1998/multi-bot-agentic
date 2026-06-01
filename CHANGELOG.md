# Changelog

All notable changes to **multi-bot-agentic** are documented here.
Follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [v0.6.7] — 2026-06-01

### Added
- Extended bot module with improved error handling
- Added structured logging for rationale operations
- New unit tests covering edge cases in event pipeline

### Changed
- Refactored retry logic to use exponential backoff with jitter
- Improved type annotations across core modules
- Updated dependency pins to latest stable versions

### Fixed
- Resolved race condition in async bot handler
- Fixed incorrect rationale timeout calculation

## [v0.1.0] — 2026-05-18

### Added
- Initial project scaffold with multi-agent orchestration core
- Basic multi_bot_agentic implementation
- README and setup documentation
