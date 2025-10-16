# Unused Tool Shutdown Preprocessor
# Automatically shuts down tools after their last usage

from typing import Dict, List, Optional, Set
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


class UnusedToolShutdown(GcodePreprocessorPlugin):
    """
    Processor that automatically inserts shutdown commands for tools
    after their last usage in the G-code file.
    """

    def __init__(self, config, logger):
        super().__init__(config, logger)

        # Configuration options
        self.exclude_tools_str = config.get('exclude_tools', '')
        self.exclude_tools: Set[int] = set()

        # Parse exclude_tools
        if self.exclude_tools_str:
            for tool_str in str(self.exclude_tools_str).split(','):
                try:
                    self.exclude_tools.add(int(tool_str.strip()))
                except ValueError:
                    pass

        # Internal state
        self.tool_usage_map: Dict[int, List[int]] = {}  # tool_number -> [line_numbers]
        self.tool_last_usage: Dict[int, int] = {}  # tool_number -> last_line_number
        self.tools_to_cooldown: Set[int] = set()  # Tools that need cooldown
        self.current_tool: Optional[int] = None
        self.pending_cooldown: Optional[int] = None  # Tool to cool after current line

    def get_name(self) -> str:
        return "unused_tool_shutdown"

    def get_description(self) -> str:
        return "Automatically shuts down tools after their last usage"

    def pre_process(self, file_path: str, context: PreprocessorContext) -> bool:
        """
        First pass: Scan entire file to build tool usage map
        """
        self.logger.info(f"unused_tool_shutdown: Scanning file for tool usage")

        self.tool_usage_map.clear()
        self.tool_last_usage.clear()
        self.tools_to_cooldown.clear()

        lines = PreprocessorUtilities.read_file_lines(file_path)

        for line_num, line in enumerate(lines):
            # Extract tool number from any tool change command
            tool_number = GcodePatterns.extract_tool_number(line)

            if tool_number is not None:
                # Record this usage
                if tool_number not in self.tool_usage_map:
                    self.tool_usage_map[tool_number] = []
                self.tool_usage_map[tool_number].append(line_num)

        # Determine last usage for each tool
        for tool_number, usage_lines in self.tool_usage_map.items():
            if usage_lines:
                self.tool_last_usage[tool_number] = max(usage_lines)

        # Determine which tools should be cooled down
        for tool_number in self.tool_usage_map.keys():
            if tool_number not in self.exclude_tools:
                self.tools_to_cooldown.add(tool_number)

        self.logger.info(f"unused_tool_shutdown: Found {len(self.tool_usage_map)} tools used in file")
        self.logger.info(f"unused_tool_shutdown: Tools to manage: {sorted(self.tool_usage_map.keys())}")
        self.logger.info(f"unused_tool_shutdown: Excluded tools: {sorted(self.exclude_tools)}")
        self.logger.info(f"unused_tool_shutdown: Last usage map: {self.tool_last_usage}")

        # Store metadata for other processors
        context.set_metadata('tools_used', sorted(self.tool_usage_map.keys()))
        context.set_metadata('tool_last_usage', self.tool_last_usage)

        return True

    def process_line(self, line: str, context: PreprocessorContext) -> List[str]:
        """
        Process each line and insert cooldown commands when appropriate
        """
        output_lines = []

        # Check if we have a pending cooldown to insert
        if self.pending_cooldown is not None:
            cooldown_tool = self.pending_cooldown
            self.pending_cooldown = None

            # Insert cooldown command with comment
            output_lines.append(f"; T{cooldown_tool} no longer needed - cooling down\n")
            cooldown_cmd = PreprocessorUtilities.format_tool_temp_command(cooldown_tool, 0)
            output_lines.append(cooldown_cmd)

            self.logger.info(f"unused_tool_shutdown: Inserted cooldown for T{cooldown_tool} at line {context.current_line}")

        # Now process the current line
        tool_number = GcodePatterns.extract_tool_number(line)

        if tool_number is not None:
            # This is a tool change
            previous_tool = self.current_tool
            self.current_tool = tool_number

            # Check if this is the last usage of the previous tool
            if previous_tool is not None and previous_tool in self.tools_to_cooldown:
                if context.current_line >= self.tool_last_usage.get(previous_tool, -1):
                    # This is the last time we'll use the previous tool
                    # Schedule it for cooldown after this tool change line
                    self.pending_cooldown = previous_tool

        # Output the current line unchanged
        output_lines.append(line)

        return output_lines

    def post_process(self, file_path: str, context: PreprocessorContext) -> bool:
        """
        Final pass: Add summary comment
        """
        # Check if there's still a pending cooldown (shouldn't happen, but be safe)
        if self.pending_cooldown is not None:
            self.logger.warning(f"unused_tool_shutdown: Tool T{self.pending_cooldown} had pending cooldown at end of file")

        self.logger.info(f"unused_tool_shutdown: Processing complete")
        return True


def create_processor(config, logger):
    """Factory function to create processor instance"""
    return UnusedToolShutdown(config, logger)
