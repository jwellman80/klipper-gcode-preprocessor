# G-code Preprocessor System

import os
import logging
from typing import Dict, List, Optional, Any
from . import gcode_preprocessor_base


class PreprocessorConfigSection:
    """Dummy class to register [preprocessor ...] config sections with Klipper"""
    def __init__(self, config):
        self.name = config.get_name()


class ProcessorConfig:
    """Config helper for processors to read their settings"""
    def __init__(self, section_name, parent_config):
        self.section_name = section_name
        self.parent_config = parent_config

        # Try to load the actual config section if it exists
        self.config_section = None
        try:
            # Get the printer's configfile object
            printer = parent_config.get_printer()
            configfile = printer.lookup_object('configfile')
            # Try to get this section from the raw config
            if hasattr(configfile, 'fileconfig'):
                if configfile.fileconfig.has_section(section_name):
                    self.config_section = configfile.fileconfig[section_name]
        except:
            pass

    def get(self, key, default=None):
        """Get a config value as string"""
        if self.config_section and key in self.config_section:
            return self.config_section[key]
        return default

    def getboolean(self, key, default=False):
        """Get a config value as boolean"""
        value = self.get(key, None)
        if value is None:
            return default
        value_str = str(value).lower()
        return value_str in ['true', '1', 'yes', 'on']

    def getint(self, key, default=0):
        """Get a config value as int"""
        value = self.get(key, None)
        if value is None:
            return default
        try:
            return int(value)
        except:
            return default

    def getfloat(self, key, default=0.0):
        """Get a config value as float"""
        value = self.get(key, None)
        if value is None:
            return default
        try:
            return float(value)
        except:
            return default


class GcodePreprocessor:
    """Main G-code preprocessor that manages and orchestrates plugins"""

    def __init__(self, config):
        self.printer = config.get_printer()
        self.gcode = self.printer.lookup_object('gcode')
        self.config = config
        self.name = config.get_name()

        # Load configuration
        self.enabled = config.getboolean('enabled', True)
        self.processors_list = config.get('processors', '').split(',')
        self.processors_list = [p.strip() for p in self.processors_list if p.strip()]

        # Registry of available processors
        self.processors: List[gcode_preprocessor_base.GcodePreprocessorPlugin] = []

        # Register for klippy events
        self.printer.register_event_handler("klippy:connect", self._handle_connect)

        # Register remote methods for Moonraker integration
        self.printer.register_event_handler("klippy:ready", self._handle_ready)

    def _handle_connect(self):
        """Handle Klipper connect event"""
        # Load processors
        if self.enabled:
            self._load_processors()

    def _handle_ready(self):
        """Handle Klipper ready event - register remote methods"""
        # Register remote methods that Moonraker can call
        self.gcode.register_command("PREPROCESS_GCODE_FILE",
                                   self.cmd_PREPROCESS_GCODE_FILE,
                                   desc="Preprocess a G-code file")
        self.gcode.register_command("LIST_GCODE_PROCESSORS",
                                   self.cmd_LIST_GCODE_PROCESSORS,
                                   desc="List available G-code processors")

    def _load_processors(self):
        """Load and initialize all configured processors"""
        for index, processor_name in enumerate(self.processors_list):
            try:
                # Try to load the processor module
                module_name = f"preprocessors.{processor_name}"
                try:
                    # Import the processor module dynamically
                    import importlib
                    module = importlib.import_module(f".{module_name}", package="extras")
                except ImportError as e:
                    logging.warning(f"gcode_preprocessor: Could not load processor '{processor_name}': {e}")
                    continue

                # Create a config helper for the processor
                # This allows processors to read their config with .get() method
                section_name = f"preprocessor {processor_name}"
                proc_config = ProcessorConfig(section_name, self.config)

                # Instantiate the processor
                processor_class = getattr(module, 'create_processor', None)
                if processor_class:
                    processor = processor_class(proc_config, logging)
                    self.processors.append(processor)
                    logging.info(f"gcode_preprocessor: Loaded processor '{processor.get_name()}' (order: {index + 1})")
                else:
                    logging.warning(f"gcode_preprocessor: Processor module '{processor_name}' missing create_processor() function")

            except Exception as e:
                logging.error(f"gcode_preprocessor: Error loading processor '{processor_name}': {e}")
                import traceback
                logging.error(traceback.format_exc())

        # Processors are already in the correct order based on list position
        # No need to sort
        logging.info(f"gcode_preprocessor: Loaded {len(self.processors)} processors")

    def process_file(self, file_path: str) -> Dict[str, Any]:
        """
        Process a G-code file through all enabled processors

        Args:
            file_path: Path to the G-code file to process

        Returns:
            Dictionary with processing results and metadata
        """
        if not self.enabled:
            return {'success': True, 'processed': False, 'message': 'Preprocessor disabled'}

        if not os.path.exists(file_path):
            return {'success': False, 'processed': False, 'message': f'File not found: {file_path}'}

        # Check if file was already processed
        if self._is_already_processed(file_path):
            return {'success': True, 'processed': False, 'message': 'File already preprocessed'}

        # Create context
        context = gcode_preprocessor_base.PreprocessorContext()
        context.file_path = file_path
        context.filename = os.path.basename(file_path)

        # Get toolchanger if available
        try:
            toolchanger = self.printer.lookup_object('toolchanger')
            if toolchanger:
                status = toolchanger.get_status(self.printer.get_reactor().monotonic())
                context.toolchanger_config = status
                context.tools = status.get('tool_numbers', [])
        except:
            pass

        try:
            # Filter processors that can process this file
            active_processors = [p for p in self.processors if p.can_process(file_path, context)]

            if not active_processors:
                return {'success': True, 'processed': False, 'message': 'No processors applicable'}

            logging.info(f"gcode_preprocessor: Processing '{context.filename}' with {len(active_processors)} processors")

            # Pass 1: Pre-processing (metadata gathering)
            for processor in active_processors:
                if not processor.pre_process(file_path, context):
                    return {'success': False, 'processed': False,
                           'message': f'Pre-processing failed in {processor.get_name()}'}

            # Pass 2: Line-by-line processing
            input_lines = gcode_preprocessor_base.PreprocessorUtilities.read_file_lines(file_path)
            output_lines = []

            # Add fingerprint
            output_lines.append(gcode_preprocessor_base.PreprocessorUtilities.add_fingerprint(
                context.get_metadata('slicer')))

            context.total_lines = len(input_lines)

            for line_num, line in enumerate(input_lines):
                context.current_line = line_num

                # Run line through all processors
                processed_lines = [line]
                for processor in active_processors:
                    new_lines = []
                    for proc_line in processed_lines:
                        result = processor.process_line(proc_line, context)
                        new_lines.extend(result)
                    processed_lines = new_lines

                output_lines.extend(processed_lines)

            # Pass 3: Post-processing
            for processor in active_processors:
                if not processor.post_process(file_path, context):
                    return {'success': False, 'processed': False,
                           'message': f'Post-processing failed in {processor.get_name()}'}

            # Write output to temp file, then atomically replace original
            temp_path = file_path + '.preprocessing'
            gcode_preprocessor_base.PreprocessorUtilities.write_file_lines(temp_path, output_lines)

            # Atomic replacement
            os.replace(temp_path, file_path)

            logging.info(f"gcode_preprocessor: Successfully processed '{context.filename}'")

            return {
                'success': True,
                'processed': True,
                'message': f'Processed by {len(active_processors)} processors',
                'processors': [p.get_name() for p in active_processors],
                'metadata': context.metadata
            }

        except Exception as e:
            logging.error(f"gcode_preprocessor: Error processing file: {e}")
            import traceback
            logging.error(traceback.format_exc())
            return {'success': False, 'processed': False, 'message': str(e)}

    def _is_already_processed(self, file_path: str) -> bool:
        """Check if file was already processed by looking for fingerprint"""
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                first_line = f.readline()
                return 'processed by klipper-gcode-preprocessor' in first_line
        except:
            return False

    cmd_PREPROCESS_GCODE_FILE_help = "Manually preprocess a G-code file"
    def cmd_PREPROCESS_GCODE_FILE(self, gcmd):
        """Command to manually trigger file preprocessing"""
        file_path = gcmd.get('FILE')

        if not file_path:
            gcmd.respond_info("Usage: PREPROCESS_GCODE_FILE FILE=<path>")
            return

        result = self.process_file(file_path)

        if result['success']:
            if result['processed']:
                gcmd.respond_info(f"File preprocessed successfully: {result['message']}")
                if 'processors' in result:
                    gcmd.respond_info(f"Processors used: {', '.join(result['processors'])}")
            else:
                gcmd.respond_info(f"File not processed: {result['message']}")
        else:
            gcmd.respond_info(f"Error preprocessing file: {result['message']}")

    cmd_LIST_GCODE_PROCESSORS_help = "List available G-code processors"
    def cmd_LIST_GCODE_PROCESSORS(self, gcmd):
        """Command to list all loaded processors"""
        if not self.processors:
            gcmd.respond_info("No processors loaded")
            return

        gcmd.respond_info(f"Loaded {len(self.processors)} processors:")
        for i, proc in enumerate(self.processors, 1):
            gcmd.respond_info(f"  {i}. {proc.get_name()}")
            gcmd.respond_info(f"     {proc.get_description()}")

    def get_status(self, eventtime):
        """Return status for queries"""
        return {
            'enabled': self.enabled,
            'processors': [
                {
                    'name': p.get_name(),
                    'description': p.get_description()
                }
                for p in self.processors
            ]
        }


def load_config(config):
    return GcodePreprocessor(config)

def load_config_prefix(config):
    """Allow [preprocessor ...] config sections to be defined"""
    # This function registers the config sections so Klipper doesn't complain
    # Return a dummy object that Klipper can register
    # The actual config values are read by GcodePreprocessor._load_processors()
    return PreprocessorConfigSection(config)
