# G-code Preprocessor System

The G-code preprocessor system automatically processes uploaded G-code files to add toolchanger-specific optimizations and features.

## Features

### 1. **Unused Tool Shutdown**
Automatically inserts `M104 T{n} S0` commands to shut down tools after their last usage.

**Example:**
```gcode
T0          ; Print with T0
T1          ; Switch to T1, print
T0          ; Switch back to T0
M104 T1 S0  ; T1 no longer needed - cooling down (INSERTED AUTOMATICALLY)
T2          ; Switch to T2, print
T0          ; Switch back to T0
M104 T2 S0  ; T2 no longer needed - cooling down (INSERTED AUTOMATICALLY)
; Continue printing with T0
```

**Configuration:**
```ini
[preprocessor unused_tool_shutdown]
exclude_tools:  # Empty by default (all tools shut down)
                # Example: exclude_tools: 0  (don't shut down T0)
                # Example: exclude_tools: 0,1  (don't shut down T0 or T1)
```

### 2. **Token Replacer** (Metadata Extraction & Placeholder Replacement)
Extracts slicer metadata from G-code comments and replaces token placeholders with actual values:

**Metadata extracted:**
- Tools used
- Filament colors
- Filament materials
- Print temperatures
- Purge volumes (optional)
- Filament names (optional)

**Placeholders replaced:**
- `!tool_count!` → Number of tools used
- `!tools!` or `!referenced_tools!` → Comma-separated list of tool numbers
- `!total_toolchanges!` → Total number of tool changes
- `!colors!` → Comma-separated hex color codes
- `!materials!` → Comma-separated material types
- `!temperatures!` → Comma-separated temperatures

Supports PrusaSlicer, SuperSlicer, OrcaSlicer, and BambuStudio.

**Example Usage in START_PRINT Macro:**
```gcode
[gcode_macro START_PRINT]
gcode:
    M118 This print uses !tool_count! tools
    M118 Colors: !colors!
    M118 Materials: !materials!
```

After preprocessing:
```gcode
M118 This print uses 3 tools
M118 Colors: ff0000,00ff00,0000ff
M118 Materials: PLA,PETG,ABS
```

## Installation

1. Run the install script:
```bash
cd ~/klipper-gcode-preprocessor
./install.sh
```

2. Add to your `printer.cfg`:
```ini
[include gcode-preprocessor/preprocessor.cfg]
```

3. Restart Klipper:
```bash
sudo systemctl restart klipper
```

## Usage

### Automatic Processing (Moonraker Integration)
Files are automatically preprocessed when uploaded via Moonraker (Mainsail/Fluidd).

### Manual Processing
Process a file manually with:
```gcode
PREPROCESS_GCODE_FILE FILE=/path/to/file.gcode
```

### List Available Processors
```gcode
LIST_GCODE_PROCESSORS
```

## Configuration

### Default Configuration
Located in `~/printer_data/config/gcode-preprocessor/preprocessor.cfg`

### Custom Configuration
Edit the configuration file directly or override in your main `printer.cfg`:

```ini
# Customize unused tool shutdown
[preprocessor unused_tool_shutdown]
exclude_tools: 0,1  # Don't shut down T0 or T1 (optional)
```

## Writing Custom Processors

You can write custom processors as Python modules:

1. Create a new file in `~/klipper/klippy/extras/preprocessors/my_processor.py`:

```python
from gcode_preprocessor_base import (
    GcodePreprocessorPlugin,
    PreprocessorContext,
    GcodePatterns
)

class MyProcessor(GcodePreprocessorPlugin):
    def __init__(self, config, logger):
        super().__init__(config, logger)

    def get_name(self):
        return "my_processor"

    def get_description(self):
        return "My custom processor"

    def pre_process(self, file_path, context):
        # First pass - gather metadata
        return True

    def process_line(self, line, context):
        # Process each line
        return [line]  # Return list of output lines

    def post_process(self, file_path, context):
        # Final pass
        return True

def create_processor(config, logger):
    return MyProcessor(config, logger)
```

2. Add to your config:
```ini
[gcode_preprocessor]
processors: token_replacer, unused_tool_shutdown, my_processor

[preprocessor my_processor]
# Your custom settings here
```

## Architecture

### Processing Pipeline
```
File Upload → Moonraker → gcode_preprocessor.py
                              ↓
                    gcode_preprocessor.py (Klipper)
                              ↓
                    ┌─────────┴─────────┐
                    │   Processor 1     │ (token_replacer)
                    └─────────┬─────────┘
                              ↓
                    ┌─────────┴─────────┐
                    │   Processor 2     │ (unused_tool_shutdown)
                    └─────────┬─────────┘
                              ↓
                    Processed G-code File
```

### Three-Pass Processing
1. **Pre-process Pass**: Scan entire file, gather metadata, build maps
2. **Line-by-line Pass**: Transform each line, insert new commands
3. **Post-process Pass**: Finalization, summary generation

## Troubleshooting

### Preprocessor Not Running
- Check that `enabled: True` in `[gcode_preprocessor]`
- Verify Klipper logs: `tail -f ~/printer_data/logs/klippy.log`
- Ensure processors are listed in `processors:` setting

### Files Already Preprocessed
Files are only preprocessed once. The first line will contain:
```gcode
; processed by klipper-gcode-preprocessor
```

To reprocess, delete this line or re-upload the file.

### Tool Not Shutting Down
- Check `exclude_tools` setting (empty by default - all tools shut down)
- Verify the tool is actually used multiple times (needs a "last usage")
- Check logs for `unused_tool_shutdown` messages

### Placeholders Not Replaced
- Ensure `token_replacer` is in the processors list
- Verify slicer is supported (PrusaSlicer, OrcaSlicer, BambuStudio, SuperSlicer)

## Examples

### Example 1: Multi-Tool Print with Auto Cooldown
**Original G-code:**
```gcode
T0
G1 X100 Y100 E10
T1
G1 X100 Y100 E10
T2
G1 X100 Y100 E10
T0
G1 X100 Y100 E10
```

**After Preprocessing:**
```gcode
; processed by klipper-gcode-preprocessor
T0
G1 X100 Y100 E10
T1
G1 X100 Y100 E10
T2
; T1 no longer needed - cooling down
M104 T1 S0
G1 X100 Y100 E10
T0
; T2 no longer needed - cooling down
M104 T2 S0
G1 X100 Y100 E10
```

### Example 2: Using Placeholders in START_PRINT
**printer.cfg:**
```ini
[gcode_macro START_PRINT]
gcode:
    M118 Starting print with !tool_count! tools
    M118 Tools: !tools!
    M118 Colors: !colors!
    {% if '!tool_count!' == '1' %}
        M118 Single tool print
    {% else %}
        M118 Multi-tool print - preparing all tools
    {% endif %}
```

**After Preprocessing:**
```ini
M118 Starting print with 3 tools
M118 Tools: 0,1,2
M118 Colors: ff0000,00ff00,0000ff
M118 Multi-tool print - preparing all tools
```

## Credits

Inspired by the Happy Hare MMU preprocessor by moggieuk.

## License

GNU GPLv3
