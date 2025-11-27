# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Documentation compliance updates for Overseer standards
- FEATURES.md with comprehensive feature documentation
- CHANGELOG.md to track version history
- CONTRIBUTING.md with contribution guidelines

### Changed

- Updated ROADMAP.md to quarterly format with completion status
- Updated TASKS.md with proper section structure (Done, In Progress, Todo)
- Updated METRICS.md with accurate project metrics

## [1.0.0] - 2024-12-01

### Added

- Initial release of Google Drive API script
- OAuth2 authentication and authorization flow
- Assessment 1: Root folder file and folder counting
- Assessment 2: Recursive child object counting with detailed CSV reports
- Assessment 3: Folder copying with validation
- Recursive folder copying with structure preservation
- Retry mechanism for file copy failures
- Comprehensive error handling and logging system
- CSV-based validation comparing source and destination
- Environment variable configuration for folder IDs and client credentials
- CI/CD workflows: Pylint, Bandit, CodeQL, Dependency Review
- README.md with setup instructions and badges
- ABOUT.md with detailed implementation documentation
- Support for trashed file filtering

### Fixed

- Error handling for failed file copy operations with parent folder URL retrieval
