# Idle Tool Shutdown Preprocessor
# Automatically shuts down tools after their last usage or when idle for too long

from typing import Dict, List, Optional, Set, Tuple
import sys
import os
import re
import math

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from gcode_preprocessor_base import (
    GcodePreprocessorPlugin,
    PreprocessorContext,
    GcodePatterns,
    PreprocessorUtilities
)


class IdleToolShutdown(GcodePreprocessorPlugin):
    """
    Processor that automatically inserts shutdown commands for tools either:
    1. After their last usage in the G-code file (default behavior)
    2. When they've been idle for a specified time period (optional)
    """

    def __init__(self, config, logger):
        super().__init__(config, logger)

        # Configuration options
        self.exclude_tools_str = config.get('exclude_tools', '')
        self.exclude_tools: Set[int] = set()

        # Idle timeout feature (disabled by default)
        self.idle_timeout_minutes = float(config.get('idle_timeout_minutes', 0))
        self.idle_timeout_seconds = self.idle_timeout_minutes * 60.0
        self.idle_timeout_enabled = self.idle_timeout_minutes > 0

        # Initial feedrate for time estimation before any F parameter is seen (mm/min)
        self.initial_feedrate = float(config.get('initial_feedrate', 3000.0))

        # Parse exclude_tools
        if self.exclude_tools_str:
            for tool_str in str(self.exclude_tools_str).split(','):
                try:
                    self.exclude_tools.add(int(tool_str.strip()))
                except ValueError:
                    pass

        # Internal state for end-of-use tracking
        self.tool_usage_map: Dict[int, List[int]] = {}  # tool_number -> [line_numbers]
        self.tool_last_usage: Dict[int, int] = {}  # tool_number -> last_line_number
        self.tools_to_cooldown: Set[int] = set()  # Tools that need cooldown
        self.current_tool: Optional[int] = None
        self.pending_cooldown: Optional[int] = None  # Tool to cool after current line

        # Internal state for idle timeout tracking
        self.line_times: Dict[int, float] = {}  # line_number -> estimated_time_seconds
        self.line_cumulative_times: Dict[int, float] = {}  # line_number -> cumulative_time_seconds
        self.tool_usage_timeline: Dict[int, List[Tuple[int, float]]] = {}  # tool_number -> [(line_num, time)]
        self.current_time: float = 0.0  # Estimated current print time in seconds
        self.tools_shutdown_idle: Set[int] = set()  # Tools shutdown due to idle timeout

        # Position tracking for movement estimation (idle timeout only)
        self.current_position: Dict[str, float] = {'X': 0.0, 'Y': 0.0, 'Z': 0.0, 'E': 0.0}
        self.current_feedrate: float = self.initial_feedrate

    def get_name(self) -> str:
        return "idle_tool_shutdown"

    def get_description(self) -> str:
        desc = "Automatically shuts down tools after their last usage"
        if self.idle_timeout_enabled:
            desc += f" or when idle > {self.idle_timeout_minutes} minutes"
        return desc

    def _parse_gcode_params(self, line: str) -> Dict[str, float]:
        """
        Parse G-code parameters from a line
        Returns dict of parameter: value (e.g., {'X': 100.5, 'Y': 50.0, 'F': 3000})
        """
        params = {}
        # Strip comments
        command_part, _ = GcodePatterns.strip_comment(line)

        # Match parameter patterns like X100.5 or F3000
        param_pattern = re.compile(r'([A-Z])([-\d.]+)', re.IGNORECASE)
        for match in param_pattern.finditer(command_part):
            param_name = match.group(1).upper()
            param_value = float(match.group(2))
            params[param_name] = param_value

        return params

    def _estimate_move_time(self, line: str, position: Dict[str, float], feedrate: float) -> Tuple[float, Dict[str, float], float]:
        """
        Estimate time for a G0/G1 movement command in seconds
        Returns: (time_seconds, new_position, new_feedrate)
        """
        if not GcodePatterns.G0_G1.match(line):
            return 0.0, position, feedrate

        params = self._parse_gcode_params(line)

        # Update feedrate if specified
        new_feedrate = params.get('F', feedrate)

        # Calculate distance moved
        new_position = position.copy()
        for axis in ['X', 'Y', 'Z', 'E']:
            if axis in params:
                new_position[axis] = params[axis]

        # Calculate Euclidean distance (ignoring E axis for time calculation)
        dx = new_position['X'] - position['X']
        dy = new_position['Y'] - position['Y']
        dz = new_position['Z'] - position['Z']
        distance = math.sqrt(dx*dx + dy*dy + dz*dz)

        # Calculate time: distance (mm) / feedrate (mm/min) * 60 (s/min)
        if new_feedrate > 0 and distance > 0:
            time_seconds = (distance / new_feedrate) * 60.0
            return time_seconds, new_position, new_feedrate

        return 0.0, new_position, new_feedrate

    def pre_process(self, file_path: str, context: PreprocessorContext) -> bool:
        """
        First pass: Scan entire file to build tool usage map and estimate print times
        """
        self.logger.info(f"idle_tool_shutdown: Scanning file for tool usage")

        self.tool_usage_map.clear()
        self.tool_last_usage.clear()
        self.tools_to_cooldown.clear()
        self.tool_usage_timeline.clear()
        self.line_cumulative_times.clear()

        lines = PreprocessorUtilities.read_file_lines(file_path)

        # For idle timeout, we need to estimate print times
        temp_position = {'X': 0.0, 'Y': 0.0, 'Z': 0.0, 'E': 0.0}
        temp_feedrate = self.initial_feedrate
        temp_current_time = 0.0

        for line_num, line in enumerate(lines):
            # Store cumulative time at this line (before processing the line)
            if self.idle_timeout_enabled:
                self.line_cumulative_times[line_num] = temp_current_time

            # Extract tool number from any tool change command
            tool_number = GcodePatterns.extract_tool_number(line)

            if tool_number is not None:
                # Record this usage
                if tool_number not in self.tool_usage_map:
                    self.tool_usage_map[tool_number] = []
                self.tool_usage_map[tool_number].append(line_num)

                # For idle timeout, build timeline with timestamps
                if self.idle_timeout_enabled:
                    if tool_number not in self.tool_usage_timeline:
                        self.tool_usage_timeline[tool_number] = []
                    self.tool_usage_timeline[tool_number].append((line_num, temp_current_time))

            # If idle timeout is enabled, estimate print times
            if self.idle_timeout_enabled:
                # Estimate time for movements
                if GcodePatterns.G0_G1.match(line):
                    move_time, temp_position, temp_feedrate = self._estimate_move_time(
                        line, temp_position, temp_feedrate
                    )
                    if move_time > 0:
                        temp_current_time += move_time
                        self.line_times[line_num] = move_time

                # Track time for dwell commands (G4)
                dwell_match = re.match(r'^G4\s+[PS]([\d.]+)', line, re.IGNORECASE)
                if dwell_match:
                    dwell_time = float(dwell_match.group(1))
                    # G4 P is in milliseconds, G4 S is in seconds
                    if 'P' in line.upper():
                        dwell_time = dwell_time / 1000.0
                    temp_current_time += dwell_time
                    self.line_times[line_num] = dwell_time

        # Determine last usage for each tool
        for tool_number, usage_lines in self.tool_usage_map.items():
            if usage_lines:
                self.tool_last_usage[tool_number] = max(usage_lines)

        # Determine which tools should be cooled down (at end of use)
        for tool_number in self.tool_usage_map.keys():
            if tool_number not in self.exclude_tools:
                self.tools_to_cooldown.add(tool_number)

        self.logger.info(f"idle_tool_shutdown: Found {len(self.tool_usage_map)} tools used in file")
        self.logger.info(f"idle_tool_shutdown: Tools to manage: {sorted(self.tool_usage_map.keys())}")
        self.logger.info(f"idle_tool_shutdown: Excluded tools: {sorted(self.exclude_tools)}")
        self.logger.info(f"idle_tool_shutdown: Last usage map: {self.tool_last_usage}")

        if self.idle_timeout_enabled:
            self.logger.info(f"idle_tool_shutdown: Idle timeout enabled: {self.idle_timeout_minutes} minutes")
            self.logger.info(f"idle_tool_shutdown: Estimated total print time: {temp_current_time / 60.0:.2f} minutes")

        # Store metadata for other processors
        context.set_metadata('tools_used', sorted(self.tool_usage_map.keys()))
        context.set_metadata('tool_last_usage', self.tool_last_usage)

        return True

    def _get_next_tool_usage_time(self, tool_num: int, current_line: int) -> Optional[float]:
        """
        Get the time when the tool will be used next (after current line)
        Returns None if tool won't be used again
        """
        if tool_num not in self.tool_usage_timeline:
            return None

        # Find the next usage after the current line
        for line_num, usage_time in self.tool_usage_timeline[tool_num]:
            if line_num > current_line:
                return usage_time

        return None  # No future usage

    def process_line(self, line: str, context: PreprocessorContext) -> List[str]:
        """
        Process each line and insert cooldown commands when appropriate
        """
        output_lines = []
        line_num = context.current_line

        # Get current time from the cumulative times map
        if self.idle_timeout_enabled and line_num in self.line_cumulative_times:
            self.current_time = self.line_cumulative_times[line_num]

        # Check if this line heats up a tool (M104/M109 with temp > 0)
        # If so, remove from shutdown set to allow future predictive cooldowns
        if re.match(r'^M10[49]\s+', line, re.IGNORECASE):
            params = self._parse_gcode_params(line)
            # Check if both T and S parameters exist, and S > 0
            if 'T' in params and 'S' in params:
                tool_num = int(params['T'])
                temp = params['S']

                # If temp > 0, this is a heating command (not cooling)
                if temp > 0:
                    if tool_num in self.tools_shutdown_idle:
                        self.tools_shutdown_idle.remove(tool_num)
                        self.logger.info(f"idle_tool_shutdown: T{tool_num} reheated to {temp}C at line {line_num}, allowing future predictive cooldown")

        # Check if we have a pending cooldown to insert (end-of-use feature)
        if self.pending_cooldown is not None:
            cooldown_tool = self.pending_cooldown
            self.pending_cooldown = None

            # Only insert if not already shutdown by idle timeout
            if cooldown_tool not in self.tools_shutdown_idle:
                output_lines.append(f"; T{cooldown_tool} no longer needed - cooling down\n")
                cooldown_cmd = PreprocessorUtilities.format_tool_temp_command(cooldown_tool, 0)
                output_lines.append(cooldown_cmd)

                self.logger.info(f"idle_tool_shutdown: Inserted end-of-use cooldown for T{cooldown_tool} at line {line_num}")

        # Now process the current line
        tool_number = GcodePatterns.extract_tool_number(line)

        if tool_number is not None:
            # This is a tool change
            previous_tool = self.current_tool
            self.current_tool = tool_number

            self.logger.info(f"idle_tool_shutdown: Tool change to T{tool_number} at line {line_num}, "
                           f"time={self.current_time/60.0:.2f}min")

            # PREDICTIVE IDLE TIMEOUT: Check if the previous tool will be idle too long
            if (self.idle_timeout_enabled and
                previous_tool is not None and
                previous_tool not in self.exclude_tools and
                previous_tool not in self.tools_shutdown_idle):

                # Find when the previous tool will be used next
                next_usage_time = self._get_next_tool_usage_time(previous_tool, line_num)

                if next_usage_time is None:
                    # Tool won't be used again - let end-of-use feature handle it
                    pass
                else:
                    # Calculate predicted idle time
                    predicted_idle_time = next_usage_time - self.current_time

                    # If tool will be idle longer than threshold, shut it down NOW
                    if predicted_idle_time >= self.idle_timeout_seconds:
                        output_lines.append(f"; T{previous_tool} will be idle for {predicted_idle_time/60.0:.2f} minutes - cooling down\n")
                        cooldown_cmd = PreprocessorUtilities.format_tool_temp_command(previous_tool, 0)
                        output_lines.append(cooldown_cmd)

                        self.tools_shutdown_idle.add(previous_tool)
                        self.logger.info(f"idle_tool_shutdown: Inserted predictive cooldown for T{previous_tool} at line {line_num}, "
                                       f"predicted_idle={predicted_idle_time/60.0:.2f}min")

            # Check if this is the last usage of the previous tool (end-of-use feature)
            if previous_tool is not None and previous_tool in self.tools_to_cooldown:
                if line_num >= self.tool_last_usage.get(previous_tool, -1):
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
            self.logger.warning(f"idle_tool_shutdown: Tool T{self.pending_cooldown} had pending cooldown at end of file")

        self.logger.info(f"idle_tool_shutdown: Processing complete")
        if self.idle_timeout_enabled:
            self.logger.info(f"idle_tool_shutdown: Shutdown {len(self.tools_shutdown_idle)} tools due to idle timeout")
            if self.tools_shutdown_idle:
                self.logger.info(f"idle_tool_shutdown: Idle shutdown tools: {sorted(self.tools_shutdown_idle)}")

        return True


def create_processor(config, logger):
    """Factory function to create processor instance"""
    return IdleToolShutdown(config, logger)
