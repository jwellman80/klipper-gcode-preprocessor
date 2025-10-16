# Klipper G-code Preprocessor

A powerful, extensible G-code preprocessing system for Klipper that automatically optimizes and enhances G-code files for multi-tool 3D printing.

## Installation

```bash
cd ~
git clone https://github.com/jwellman80/klipper-gcode-preprocessor.git
cd klipper-gcode-preprocessor
./install.sh
```

Add to `printer.cfg`
```ini
[include gcode-preprocessor/preprocessor.cfg]
```

Add to `moonraker.conf`:
```ini
[gcode_preprocessor]
enable_preprocessing: True
```

Restart Moonraker and Klipper:
```bash
sudo service moonraker restart
sudo service klipper restart
```

## Features

### 🔥 **Tool Thermal Manager** (Automatic Tool Cooldown)
Automatically inserts `M104 T{n} S0` commands to cool down tools after their last usage in the print. This saves energy, reduces wear, and prevents oozing from unused tools.

**Example:**
```gcode
T0          ; Print with T0
T1          ; Switch to T1
T0          ; Switch back to T0
M104 T1 S0  ; T1 no longer needed - cool down (INSERTED AUTOMATICALLY)
```

### 📊 **Metadata Extractor**
Extracts slicer metadata from G-code comments including:
- Tools used
- Filament colors
- Filament materials
- Print temperatures
- Purge volumes
- Filament names

Supports: PrusaSlicer, SuperSlicer, OrcaSlicer, BambuStudio

### 🔄 **Placeholder Replacer**
Replace placeholders in your G-code or macros with actual values:
- `!tool_count!` → Number of tools
- `!tools!` → Comma-separated tool list
- `!colors!` → Hex color codes
- `!materials!` → Material types
- `!temperatures!` → Temperature values

**Example Usage:**
```gcode
[gcode_macro START_PRINT]
gcode:
    M118 Print uses !tool_count! tools
    M118 Colors: !colors!
```

## Usage

### Automatic Processing
Files uploaded via Mainsail/Fluidd are automatically preprocessed (requires Moonraker integration).

### Manual Processing
```gcode
PREPROCESS_GCODE_FILE FILE=/path/to/file.gcode
```

### List Processors
```gcode
LIST_GCODE_PROCESSORS
```

## Configuration

### Default Settings
Located in `~/printer_data/config/gcode-preprocessor/preprocessor.cfg`

### Unused Tool Shutdown Settings
```ini
[preprocessor unused_tool_shutdown]
exclude_tools:                # Empty by default (all tools shut down)
                             # Example: exclude_tools: 0  (don't shut down T0)
                             # Example: exclude_tools: 0,1  (don't shut down T0 or T1)
```

### Token Replacer Settings
```ini
[preprocessor token_replacer]
extract_tools: True
extract_colors: True
extract_materials: True
extract_temperatures: True
replace_placeholders: True
```

## Writing Custom Processors

Create a new file in `~/klipper/klippy/extras/preprocessors/my_processor.py`:

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
        return [line]

    def post_process(self, file_path, context):
        # Final pass
        return True

def create_processor(config, logger):
    return MyProcessor(config, logger)
```

Then add to your config:
```ini
[gcode_preprocessor]
processors: token_replacer, unused_tool_shutdown, my_processor

[preprocessor my_processor]
# Custom settings
```

## Architecture

### Processing Pipeline
```
File Upload → Moonraker → Klipper Preprocessor
                              ↓
                 ┌────────────┴────────────┐
                 │  Pass 1: Pre-process    │
                 │  (gather metadata)      │
                 └────────────┬────────────┘
                              ↓
                 ┌────────────┴────────────┐
                 │  Pass 2: Line-by-line   │
                 │  (transform commands)   │
                 └────────────┬────────────┘
                              ↓
                 ┌────────────┴────────────┐
                 │  Pass 3: Post-process   │
                 │  (finalization)         │
                 └────────────┬────────────┘
                              ↓
                     Processed G-code
```

### Directory Structure
```
klipper-gcode-preprocessor/
├── install.sh                          # Installation script
├── README.md                           # This file
├── klipper/extras/
│   ├── gcode_preprocessor_base.py     # Base classes
│   ├── gcode_preprocessor.py          # Main registry
│   └── preprocessors/
│       ├── __init__.py
│       ├── token_replacer.py          # Extract metadata & replace tokens
│       ├── unused_tool_shutdown.py   # Auto shutdown unused tools
│       └── example_template.py       # Example processor template
├── moonraker/
│   └── gcode_preprocessor.py          # Moonraker component
├── config/
│   └── gcode-preprocessor.cfg         # Default configuration
├── docs/
│   └── README.md                       # Detailed documentation
└── examples/
    └── test_sample.gcode               # Test file
```

## Troubleshooting

### Preprocessor Not Running
- Check that `enabled: True` in `[gcode_preprocessor]`
- Verify Klipper logs: `tail -f ~/printer_data/logs/klippy.log`
- Ensure config is included in `printer.cfg`

### Files Already Preprocessed
Files are only preprocessed once. First line will contain:
```gcode
; processed by klipper-gcode-preprocessor
```

To reprocess, delete this line or re-upload the file.

### Tool Not Shutting Down
- Check `exclude_tools` setting (empty by default - all tools shut down)
- Verify tool is used multiple times (needs "last usage")
- Check logs for `unused_tool_shutdown` messages

### Placeholders Not Replaced
- Ensure `token_replacer` is in the processors list
- Verify slicer is supported (PrusaSlicer, OrcaSlicer, BambuStudio, SuperSlicer)

## Examples

See `docs/README.md` for comprehensive examples and use cases.

## Contributing

Contributions welcome! Please submit pull requests or open issues on GitHub.

## Credits

Inspired by the Happy Hare MMU preprocessor by moggieuk.

## License

GNU GPLv3

## Support

- Documentation: `docs/README.md`
- Issues: GitHub Issues
- Discussions: GitHub Discussions
