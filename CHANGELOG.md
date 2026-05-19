# Changelog

All notable changes to **multi-bot-agentic** are documented here.
Follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [v0.9.15] — 2026-05-18

### Added
- Extended bot module with improved error handling
- Added structured logging for ODA operations
- New unit tests covering edge cases in safety pipeline

### Changed
- Refactored retry logic to use exponential backoff with jitter
- Improved type annotations across core modules
- Updated dependency pins to latest stable versions

### Fixed
- Resolved race condition in async bot handler
- Fixed incorrect ODA timeout calculation

## [v0.1.0] — 2026-04-20

### Added
- Initial project scaffold with multi-agent orchestration core
- Basic multi_bot_agentic implementation
- README and setup documentation
