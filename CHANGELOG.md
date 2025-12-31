# Changelog

All notable changes to this project will be documented in this file.

## [1.0.0] - 2025-12-31

### Added
- External Configuration: Settings are now loaded from `config.yaml`, allowing for user-specific configuration without modifying code.
- `config.example.yaml`: A template file with documentation for all configurable settings.
- Hardware Compatibility Disclaimer: Clarified that the software is optimized for AVKANS LV20N but compatible with other VISCA-over-IP cameras with calibration.

### Changed
- **Generalization**: Refactored `config.py` to support dynamic configuration loading.
- **Documentation**: Significant updates to `README.md` to guide new users through setup and configuration.
- **Cleanup**: Removed internal development notes and debug comments from core files (`skywatch_core.py`, `visca_control.py`, `app.py`, `adsb_client.py`, `main.js`).

### Fixed
- Fixed duplicate imports in `video_capture.py`.
