# Completed Tasks

## ✅ Add file processing fingerprint
**Status:** Already implemented
- File fingerprint check exists (line 144 of toolchanger_preprocessor.py)
- Files marked with `; processed by toolchanger_preprocessor` on first line
- Prevents reprocessing of already-processed files

## ✅ Change tool cooldown default behavior
**Status:** Completed
- Changed default from `exclude_tools='0'` to `exclude_tools=''` in tool_thermal_manager.py
- **All tools now receive cooldown commands by default**
- Users can still exclude specific tools by setting `exclude_tools: 0` in config

## ✅ Clean up documentation
**Status:** Completed
- **README.md**
  - Fixed exclude_tools default documentation (now shows empty default)
  - Updated troubleshooting section with correct default behavior

- **docs/README.md**
  - Removed all klipper-toolchanger-easy path references
  - Changed `~/klipper-toolchanger-easy` → `~/klipper-gcode-preprocessor`
  - Changed `toolchanger/readonly-configs/` → `gcode-preprocessor/`
  - Updated configuration section to reflect actual file locations
  - Fixed exclude_tools documentation

- **QUICKSTART.md**
  - Updated exclude_tools example to show it's optional
  - Verified all paths and instructions are accurate

- **CLAUDE.md**
  - Updated tool_thermal_manager description
  - Changed from "Excludes configured tools (typically T0 as reference tool)"
  - To "By default, all tools are cooled down (no exclusions)"

## ✅ Fix Moonraker integration bugs
**Status:** Completed
- **Bug #1:** Duplicate `-p` argument in argparse
  - Changed preprocess flag from `-p` to `-x`

- **Bug #2:** Command-line args not merged with JSON config
  - Added merge logic so `-x` flag properly sets `config["preprocess"] = True`

- Files now automatically preprocess on upload via Moonraker

## Summary
All requested tasks have been completed. The system now:
1. ✅ Prevents duplicate processing via fingerprint check
2. ✅ Cools down all tools by default (not just non-T0 tools)
3. ✅ Has clean, accurate documentation without outdated references
4. ✅ Automatically preprocesses files on upload
