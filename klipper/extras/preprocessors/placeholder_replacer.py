# Placeholder Replacer Preprocessor
# Replaces placeholders in G-code with actual values

from typing import Dict, List
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


class PlaceholderReplacer(GcodePreprocessorPlugin):
    """
    Processor that replaces placeholders in G-code with actual values
    Examples: !tool_count!, !colors!, !materials!, !temperatures!
    """

    def __init__(self, config, logger):
        super().__init__(config, logger)

        # Configuration options
        self.placeholders_str = config.get('placeholders',
            '!tool_count!, !colors!, !materials!, !temperatures!, !total_toolchanges!')
        self.placeholders = [p.strip() for p in self.placeholders_str.split(',')]

        # Internal state
        self.replacement_map: Dict[str, str] = {}

    def get_name(self) -> str:
        return "placeholder_replacer"

    def get_description(self) -> str:
        return "Replaces placeholders (!tool_count!, !colors!, etc.) with actual values"

    def pre_process(self, file_path: str, context: PreprocessorContext) -> bool:
        """
        Build replacement map from metadata
        """
        self.logger.info(f"placeholder_replacer: Building replacement map")

        # Get metadata from context (set by metadata_extractor)
        tools_used = context.get_metadata('tools_used', [])
        colors = context.get_metadata('colors', [])
        materials = context.get_metadata('materials', [])
        temperatures = context.get_metadata('temperatures', [])
        total_toolchanges = context.get_metadata('total_toolchanges', 0)
        filament_names = context.get_metadata('filament_names', [])

        # Build replacement map
        self.replacement_map = {
            '!tool_count!': str(len(tools_used)) if tools_used else '0',
            '!tools!': ','.join(map(str, tools_used)) if tools_used else '0',
            '!referenced_tools!': ','.join(map(str, tools_used)) if tools_used else '0',
            '!total_toolchanges!': str(total_toolchanges),
            '!colors!': ','.join(colors) if colors else '',
            '!materials!': ','.join(materials) if materials else '',
            '!temperatures!': ','.join(temperatures) if temperatures else '',
            '!filament_names!': ','.join(filament_names) if filament_names else '',
        }

        self.logger.info(f"placeholder_replacer: Replacement map: {self.replacement_map}")

        return True

    def process_line(self, line: str, context: PreprocessorContext) -> List[str]:
        """
        Replace placeholders in the line
        """
        # Don't process comment lines (preserve slicer metadata)
        if GcodePatterns.is_comment(line):
            return [line]

        # Check if line contains any placeholders
        modified_line = line
        for placeholder, replacement in self.replacement_map.items():
            if placeholder in modified_line:
                modified_line = modified_line.replace(placeholder, replacement)
                self.logger.info(f"placeholder_replacer: Replaced {placeholder} with {replacement} at line {context.current_line}")

        return [modified_line]

    def post_process(self, file_path: str, context: PreprocessorContext) -> bool:
        """
        Post-processing complete
        """
        return True


def create_processor(config, logger):
    """Factory function to create processor instance"""
    return PlaceholderReplacer(config, logger)
