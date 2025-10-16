# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

This is a Klipper G-code preprocessor system that automatically optimizes and enhances G-code files for multi-tool 3D printing. It integrates as Klipper modules and optionally as a Moonraker component to preprocess uploaded files.

## Key Commands

### Installation
```bash
# Install the preprocessor system
./install.sh

# Manual linking of Klipper modules
ln -sf ~/klipper-gcode-preprocessor/klipper/extras/gcode_preprocessor*.py ~/klipper/klippy/extras/
ln -sf ~/klipper-gcode-preprocessor/klipper/extras/preprocessors ~/klipper/klippy/extras/

# Restart Klipper
sudo systemctl restart klipper

# Restart Moonraker (if using Moonraker integration)
sudo systemctl restart moonraker
```

### Testing & Development
```bash
# View Klipper logs for debugging
tail -f ~/printer_data/logs/klippy.log

# Test preprocessing manually (via Klipper console)
PREPROCESS_GCODE_FILE FILE=/path/to/file.gcode

# List loaded processors (via Klipper console)
LIST_GCODE_PROCESSORS
```

## Architecture

### Three-Pass Plugin System

The preprocessor uses a three-phase pipeline where each processor gets three passes:

1. **Pre-process Pass** (`pre_process()`): Scan entire file, gather metadata, build usage maps
   - Example: `token_replacer` scans for slicer comments
   - Example: `unused_tool_shutdown` builds tool usage map to find last usages

2. **Line-by-line Pass** (`process_line()`): Transform individual G-code lines
   - Each processor receives each line and returns a list of output lines (0, 1, or many)
   - Processors run in list order for each line
   - Example: `token_replacer` replaces `!tool_count!` with actual count

3. **Post-process Pass** (`post_process()`): Finalization and cleanup
   - Used for summary generation or final validation

### Component Structure

**Core Components:**
- `gcode_preprocessor_base.py` - Base classes (`GcodePreprocessorPlugin`, `PreprocessorContext`, `GcodePatterns`, `PreprocessorUtilities`)
- `gcode_preprocessor.py` - Main orchestrator that loads plugins, manages pipeline, and registers Klipper commands

**Klipper Integration:**
- Lives in `klipper/extras/` (symlinked to `~/klipper/klippy/extras/`)
- Loaded as Klipper module via `load_config()` function
- Registers G-code commands: `PREPROCESS_GCODE_FILE`, `LIST_GCODE_PROCESSORS`
- Processors live in `klipper/extras/preprocessors/` subdirectory

**Moonraker Integration (Optional):**
- `moonraker/gcode_preprocessor.py` - Hooks into Moonraker's file upload system
- Can be invoked standalone as a script when files are uploaded
- Sets `METADATA_SCRIPT` to intercept file processing

### Built-in Processors

1. **token_replacer**
   - Extracts slicer metadata from comments (colors, materials, temperatures)
   - Detects slicer type (PrusaSlicer, OrcaSlicer, BambuStudio, SuperSlicer)
   - Stores extracted data in `PreprocessorContext` for other processors
   - Replaces token placeholders like `!tool_count!`, `!colors!`, `!materials!`, `!temperatures!`
   - Processes non-comment lines only for replacements (preserves slicer metadata)
   - See `klipper/extras/preprocessors/token_replacer.py`

2. **unused_tool_shutdown**
   - Automatically inserts `M104 T{n} S0` shutdown commands after last tool usage
   - Scans entire file to build tool usage map, identifies last usage for each tool
   - By default, all tools are shut down (no exclusions)
   - Can exclude specific tools via `exclude_tools` config (e.g., `exclude_tools: 0` to skip T0)
   - See `klipper/extras/preprocessors/unused_tool_shutdown.py`

### Key Patterns

**Tool Change Detection:**
The system recognizes multiple tool change formats via regex patterns in `GcodePatterns`:
- Standard: `T0`, `T1`, etc.
- Klipper: `SELECT_TOOL TOOL=0` or `SELECT_TOOL T=0`
- Happy Hare MMU: `MMU_CHANGE_TOOL TOOL=0`

**Processing Fingerprint:**
Files are marked with `; processed by klipper-gcode-preprocessor` on first line to prevent reprocessing.

**Context Sharing:**
`PreprocessorContext.metadata` dict allows processors to share data between the pre-process and line-by-line phases. For example, `token_replacer` scans the file in `pre_process()` and uses the gathered data in `process_line()` to replace token placeholders.

## Writing Custom Processors

Create a new file in `klipper/extras/preprocessors/my_processor.py`:

```python
from gcode_preprocessor_base import (
    GcodePreprocessorPlugin,
    PreprocessorContext,
    GcodePatterns,
    PreprocessorUtilities
)

class MyProcessor(GcodePreprocessorPlugin):
    def __init__(self, config, logger):
        super().__init__(config, logger)
        # Load config options: config.get('my_option', default_value)

    def get_name(self) -> str:
        return "my_processor"

    def get_description(self) -> str:
        return "What this processor does"

    def pre_process(self, file_path: str, context: PreprocessorContext) -> bool:
        # First pass - scan file, gather data
        lines = PreprocessorUtilities.read_file_lines(file_path)
        # ... analyze lines ...
        context.set_metadata('my_data', data)  # Share with other processors
        return True

    def process_line(self, line: str, context: PreprocessorContext) -> List[str]:
        # Transform line - return list of output lines
        # Return [] to skip line, [line] to keep unchanged, [line1, line2] to insert
        return [line]

    def post_process(self, file_path: str, context: PreprocessorContext) -> bool:
        # Final pass - cleanup, validation
        return True

def create_processor(config, logger):
    """Factory function - must be present"""
    return MyProcessor(config, logger)
```

Then configure in `printer.cfg` or config file:
```ini
[gcode_preprocessor]
processors: token_replacer, unused_tool_shutdown, my_processor

[preprocessor my_processor]
my_option: value
```

## Configuration System

**Default Config:** `config/gcode-preprocessor.cfg` (or installed to `~/printer_data/config/gcode-preprocessor/preprocessor.cfg`)

**Config Sections:**
- `[gcode_preprocessor]` - Main settings (enabled, processors list)
- `[preprocessor {name}]` - Per-processor settings (processor-specific options)
- Moonraker component settings (in moonraker.conf): `[gcode_preprocessor]`

**Execution Order:**
Processors execute in the order they appear in the `processors` list. Typical order:
1. token_replacer - gather data first and replace token placeholders
2. unused_tool_shutdown - insert shutdown commands

## File Locations

- **Source:** `/home/pi/klipper-gcode-preprocessor/`
- **Klipper Modules:** Symlinked to `~/klipper/klippy/extras/`
- **Moonraker Component:** Symlinked to `~/moonraker/moonraker/components/`
- **Configuration:** `~/printer_data/config/gcode-preprocessor/preprocessor.cfg`
- **Logs:** `~/printer_data/logs/klippy.log` (Klipper) or `~/printer_data/logs/moonraker.log`

## Important Development Notes

- **Atomic File Operations:** The system writes to `.preprocessing` temp file, then uses `os.replace()` for atomic swap
- **Config Access:** Processor configs use dict-like access: `config.get('key', default)`
- **Line Preservation:** Lines read with `readlines()` include `\n`, preserve this in output
- **Error Handling:** Return `False` from `pre_process()` or `post_process()` to abort processing
- **Import Path:** Processors must handle import paths (see `sys.path.insert(0, ...)` in existing processors)
- **Klipper Module Loading:** Use `self.printer.try_load_module(config, module_name)` pattern
- **Context Metadata:** Use `context.set_metadata()` and `context.get_metadata()` for processor communication
