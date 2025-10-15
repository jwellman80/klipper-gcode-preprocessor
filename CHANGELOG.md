# Changelog

All notable changes to the Klipper G-code Preprocessor will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2024-XX-XX

### Added
- Initial release of Klipper G-code Preprocessor
- Tool Thermal Manager processor for automatic tool cooldown
- Metadata Extractor processor for slicer metadata extraction
- Placeholder Replacer processor for dynamic G-code values
- Extensible plugin architecture
- Three-pass processing system (pre-process, line-by-line, post-process)
- Moonraker integration for automatic file preprocessing
- Manual preprocessing via `PREPROCESS_GCODE_FILE` command
- `LIST_GCODE_PROCESSORS` command to view loaded processors
- Comprehensive configuration system
- Support for PrusaSlicer, SuperSlicer, OrcaSlicer, BambuStudio
- Automated installation script
- Complete documentation and examples

### Features
- **Tool Thermal Manager**
  - Automatically cool down tools after last usage
  - Configurable tool exclusion list
  - Optional explanatory comments
  - Immediate or delayed cooldown modes

- **Metadata Extractor**
  - Extract tools used
  - Extract filament colors
  - Extract filament materials
  - Extract temperatures
  - Extract purge volumes (optional)
  - Extract filament names (optional)

- **Placeholder Replacer**
  - Replace !tool_count! with number of tools
  - Replace !tools! with tool list
  - Replace !colors! with color codes
  - Replace !materials! with material types
  - Replace !temperatures! with temperature values
  - Replace !total_toolchanges! with toolchange count

### Security
- Atomic file replacement to prevent corruption
- Fingerprint tracking to prevent double-processing
- Safe error handling with detailed logging

## [Unreleased]

### Planned
- Web UI for processor configuration
- Real-time preview of preprocessing changes
- Statistics and analytics processor
- Print time estimation adjustments
- Additional slicer support (Cura, Simplify3D)
- Processor marketplace/registry
