# Changelog

All notable changes to **multi-bot-agentic** are documented here.
Follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [v0.5.0] — 2025-06-04

### Added
- Extended ODA module with improved error handling
- Added structured logging for safety operations
- New unit tests covering edge cases in rationale pipeline

### Changed
- Refactored retry logic to use exponential backoff with jitter
- Improved type annotations across core modules
- Updated dependency pins to latest stable versions

### Fixed
- Resolved race condition in async ODA handler
- Fixed incorrect safety timeout calculation

## [v0.1.0] — 2025-05-21

### Added
- Initial project scaffold with multi-agent orchestration core
- Basic multi_bot_agentic implementation
- README and setup documentation
