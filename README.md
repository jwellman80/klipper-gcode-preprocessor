# Klipper G-code Preprocessor

A powerful, extensible G-code preprocessing system for Klipper that automatically optimizes and enhances G-code files for multi-tool 3D printing.

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

## Installation

### Quick Install

```bash
cd ~
git clone https://github.com/jwellman80/klipper-gcode-preprocessor.git
cd klipper-gcode-preprocessor
./install.sh
```

### Manual Install

1. Clone the repository:
```bash
cd ~
git clone https://github.com/jwellman80/klipper-gcode-preprocessor.git
```

2. Link Klipper modules:
```bash
ln -sf ~/klipper-gcode-preprocessor/klipper/extras/gcode_preprocessor*.py ~/klipper/klippy/extras/
ln -sf ~/klipper-gcode-preprocessor/klipper/extras/preprocessors ~/klipper/klippy/extras/
```

3. Install configuration:
```bash
mkdir -p ~/printer_data/config/gcode-preprocessor
cp ~/klipper-gcode-preprocessor/config/gcode-preprocessor.cfg ~/printer_data/config/gcode-preprocessor/preprocessor.cfg
```

4. Add to your `printer.cfg`:
```ini
[include gcode-preprocessor/preprocessor.cfg]
```

5. Restart Klipper:
```bash
sudo systemctl restart klipper
```

### Optional: Moonraker Integration

For automatic preprocessing on file upload:

1. Link Moonraker component:
```bash
ln -sf ~/klipper-gcode-preprocessor/moonraker/toolchanger_preprocessor.py ~/moonraker/moonraker/components/
```

2. Add to `moonraker.conf`:
```ini
[toolchanger_preprocessor]
enable_preprocessing: True
```

3. Restart Moonraker:
```bash
sudo systemctl restart moonraker
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

### Tool Thermal Manager Settings
```ini
[preprocessor tool_thermal_manager]
enabled: True
immediate_cooldown: True
exclude_tools:                # Empty by default (all tools cooled)
                             # Example: exclude_tools: 0  (don't cool T0)
add_cooldown_comments: True
```

### Metadata Extractor Settings
```ini
[preprocessor metadata_extractor]
enabled: True
extract_tools: True
extract_colors: True
extract_materials: True
extract_temperatures: True
```

### Placeholder Replacer Settings
```ini
[preprocessor placeholder_replacer]
enabled: True
placeholders: !tool_count!, !colors!, !materials!, !temperatures!
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
processors: metadata_extractor, tool_thermal_manager, my_processor
processor_order: metadata_extractor=10, tool_thermal_manager=20, my_processor=30

[preprocessor my_processor]
enabled: True
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
│       ├── tool_thermal_manager.py    # Tool cooldown
│       ├── metadata_extractor.py      # Extract metadata
│       └── placeholder_replacer.py    # Replace placeholders
├── moonraker/
│   └── toolchanger_preprocessor.py    # Moonraker component
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
; processed by toolchanger_preprocessor
```

To reprocess, delete this line or re-upload the file.

### Tool Not Cooling Down
- Check `exclude_tools` setting (empty by default - all tools cooled)
- Verify tool is used multiple times (needs "last usage")
- Check logs for `tool_thermal_manager` messages

### Placeholders Not Replaced
- Ensure `metadata_extractor` runs before `placeholder_replacer`
- Check `processor_order` setting
- Verify slicer is supported

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
