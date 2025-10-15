# Metadata Extractor Preprocessor
# Extracts slicer metadata from G-code comments

from typing import Dict, List, Optional
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from gcode_preprocessor_base import (
    GcodePreprocessorPlugin,
    PreprocessorContext,
    GcodePatterns,
    PreprocessorUtilities
)


class MetadataExtractor(GcodePreprocessorPlugin):
    """
    Processor that extracts metadata from slicer-generated comments
    including colors, materials, temperatures, and purge volumes
    """

    SUPPORTED_SLICERS = ['PrusaSlicer', 'SuperSlicer', 'OrcaSlicer', 'BambuStudio']

    def __init__(self, config, logger):
        super().__init__(config, logger)

        # Configuration options
        self.extract_tools = config.get('extract_tools', True)
        self.extract_colors = config.get('extract_colors', True)
        self.extract_materials = config.get('extract_materials', True)
        self.extract_temperatures = config.get('extract_temperatures', True)
        self.extract_purge_volumes = config.get('extract_purge_volumes', False)
        self.extract_filament_names = config.get('extract_filament_names', False)

        # Internal state
        self.slicer: Optional[str] = None
        self.colors: List[str] = []
        self.materials: List[str] = []
        self.temperatures: List[str] = []
        self.purge_volumes: List[str] = []
        self.filament_names: List[str] = []
        self.tools_used: set = set()
        self.total_toolchanges: int = 0

        # Flags to track if we've found metadata
        self.found_colors = False
        self.found_materials = False
        self.found_temperatures = False
        self.found_purge_volumes = False
        self.found_filament_names = False

    def get_name(self) -> str:
        return "metadata_extractor"

    def get_description(self) -> str:
        return "Extracts slicer metadata (colors, materials, temps) from G-code comments"

    def pre_process(self, file_path: str, context: PreprocessorContext) -> bool:
        """
        Scan file to extract all metadata from comments
        """
        self.logger.info(f"metadata_extractor: Scanning file for metadata")

        lines = PreprocessorUtilities.read_file_lines(file_path)

        for line in lines:
            # Detect slicer
            if not self.slicer and GcodePatterns.is_comment(line):
                match = GcodePatterns.SLICER_NAME.match(line)
                if match:
                    self.slicer = match.group(1) or match.group(2)
                    if self.slicer in self.SUPPORTED_SLICERS:
                        self.logger.info(f"metadata_extractor: Detected slicer: {self.slicer}")

            # Extract tool changes if enabled
            if self.extract_tools:
                tool_number = GcodePatterns.extract_tool_number(line)
                if tool_number is not None:
                    self.tools_used.add(tool_number)
                    self.total_toolchanges += 1

            # Extract colors if enabled and not found yet
            if self.extract_colors and not self.found_colors and GcodePatterns.is_comment(line):
                match = GcodePatterns.EXTRUDER_COLOR.match(line)
                if match:
                    colors_csv = PreprocessorUtilities.parse_csv_list(match.group(1), '#')
                    if not self.colors:
                        self.colors.extend(colors_csv)
                    else:
                        # Merge, preferring non-empty values
                        self.colors = [n if o == '' else o for o, n in zip(self.colors, colors_csv)]
                    self.found_colors = all(len(c) > 0 for c in self.colors)

            # Extract materials if enabled and not found yet
            if self.extract_materials and not self.found_materials and GcodePatterns.is_comment(line):
                match = GcodePatterns.FILAMENT_TYPE.match(line)
                if match:
                    materials_csv = match.group(1).strip().split(';')
                    self.materials.extend([m.strip() for m in materials_csv])
                    self.found_materials = True

            # Extract temperatures if enabled and not found yet
            if self.extract_temperatures and not self.found_temperatures and GcodePatterns.is_comment(line):
                match = GcodePatterns.TEMPERATURE.match(line)
                if match:
                    import re
                    temps_csv = re.split('[;,]', match.group(1).strip())
                    self.temperatures.extend([t.strip() for t in temps_csv])
                    self.found_temperatures = True

            # Extract purge volumes if enabled and not found yet
            if self.extract_purge_volumes and not self.found_purge_volumes and GcodePatterns.is_comment(line):
                match = GcodePatterns.PURGE_VOLUMES.match(line)
                if match:
                    purge_csv = match.group(1).strip().split(',')
                    self.purge_volumes.extend([p.strip() for p in purge_csv])
                    self.found_purge_volumes = True

            # Extract filament names if enabled and not found yet
            if self.extract_filament_names and not self.found_filament_names and GcodePatterns.is_comment(line):
                match = GcodePatterns.FILAMENT_NAMES.match(line)
                if match:
                    import re
                    names_csv = re.split('[;,]', match.group(2).strip())
                    self.filament_names.extend([n.strip() for n in names_csv])
                    self.found_filament_names = True

        # Log what we found
        self.logger.info(f"metadata_extractor: Slicer: {self.slicer}")
        if self.extract_tools:
            self.logger.info(f"metadata_extractor: Tools used: {sorted(self.tools_used)}")
            self.logger.info(f"metadata_extractor: Total tool changes: {self.total_toolchanges}")
        if self.extract_colors:
            self.logger.info(f"metadata_extractor: Colors: {self.colors}")
        if self.extract_materials:
            self.logger.info(f"metadata_extractor: Materials: {self.materials}")
        if self.extract_temperatures:
            self.logger.info(f"metadata_extractor: Temperatures: {self.temperatures}")

        # Store metadata in context for other processors
        context.set_metadata('slicer', self.slicer)
        context.set_metadata('tools_used', sorted(self.tools_used))
        context.set_metadata('total_toolchanges', self.total_toolchanges)
        context.set_metadata('colors', self.colors)
        context.set_metadata('materials', self.materials)
        context.set_metadata('temperatures', self.temperatures)
        context.set_metadata('purge_volumes', self.purge_volumes)
        context.set_metadata('filament_names', self.filament_names)

        return True

    def process_line(self, line: str, context: PreprocessorContext) -> List[str]:
        """
        This processor doesn't modify lines, just extracts metadata
        """
        return [line]

    def post_process(self, file_path: str, context: PreprocessorContext) -> bool:
        """
        Post-processing: Could add summary metadata as comments
        """
        return True


def create_processor(config, logger):
    """Factory function to create processor instance"""
    return MetadataExtractor(config, logger)
