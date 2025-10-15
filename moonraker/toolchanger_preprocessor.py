# Toolchanger G-code Preprocessor - Moonraker Component
# Hooks into Moonraker's file upload/metadata system to preprocess G-code files

import os
import sys
import logging


class ToolchangerPreprocessor:
    """
    Moonraker component that integrates G-code preprocessing into file upload
    """

    def __init__(self, config):
        self.config = config
        self.server = config.get_server()

        # Configuration
        self.enabled = config.getboolean('enable_preprocessing', True)

        # Setup the preprocessor hook
        if self.enabled:
            self.setup_preprocessor_hook(config)

        logging.info("toolchanger_preprocessor: Component initialized")

    def setup_preprocessor_hook(self, config):
        """
        Setup the preprocessor to run on file uploads
        Similar to Happy Hare's approach
        """
        args = ""

        # Enable preprocessing
        if config.getboolean('enable_preprocessing', True):
            args += " -x"

        # Set the metadata script to this file
        # When Moonraker processes uploaded files, it will call this script
        try:
            from .file_manager import file_manager
            file_manager.METADATA_SCRIPT = os.path.abspath(__file__) + args
            logging.info(f"toolchanger_preprocessor: Set METADATA_SCRIPT to {file_manager.METADATA_SCRIPT}")
        except ImportError:
            logging.warning("toolchanger_preprocessor: Could not import file_manager - preprocessing may not work")

    async def component_init(self):
        """Initialize component after server is ready"""
        logging.info("toolchanger_preprocessor: Component initialization complete")


def load_component(config):
    return ToolchangerPreprocessor(config)


# ==============================================================================
# Command-line interface for when this script is invoked as a standalone script
# This is called by Moonraker when processing uploaded files
# ==============================================================================

if __name__ == "__main__":
    import argparse
    import json
    import traceback
    import sys

    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # Parse arguments
    parser = argparse.ArgumentParser(description="G-code Preprocessing Script")
    parser.add_argument("-c", "--config", metavar='<config_file>',
                       default=None,
                       help="Optional JSON configuration file")
    parser.add_argument("-f", "--filename", metavar='<filename>',
                       help="Name of G-code file to process")
    parser.add_argument("-p", "--path", metavar='<path>',
                       default=os.path.abspath(os.path.dirname(__file__)),
                       help="Optional absolute path for file")
    parser.add_argument("-u", "--ufp", metavar="<ufp file>",
                       default=None,
                       help="Optional path of UFP file to extract")
    parser.add_argument("-o", "--check-objects", dest='check_objects',
                       action='store_true',
                       help="Process G-code file for exclude object functionality")
    parser.add_argument("-x", "--preprocess", dest='preprocess',
                       action='store_true',
                       help="Enable toolchanger preprocessing")

    args = parser.parse_args()

    # Load configuration
    config = {}
    if args.config is None:
        if args.filename is None:
            logging.error("The '--filename' (-f) option must be specified when --config is not set")
            sys.exit(-1)
        config["filename"] = args.filename
        config["gcode_dir"] = args.path
        config["ufp_path"] = args.ufp
        config["check_objects"] = args.check_objects
        config["preprocess"] = args.preprocess
    else:
        try:
            with open(args.config, "r") as f:
                config = json.load(f)
        except Exception:
            logging.error(traceback.format_exc())
            sys.exit(-1)

        if config.get("filename") is None:
            logging.error("The 'filename' field must be present in the configuration")
            sys.exit(-1)

        # Merge command-line args into config (command-line takes precedence)
        if args.preprocess:
            config["preprocess"] = True
        if args.check_objects:
            config["check_objects"] = True

    if config.get("gcode_dir") is None:
        config["gcode_dir"] = os.path.abspath(os.path.dirname(__file__))

    # Build file path
    file_path = os.path.join(config["gcode_dir"], config["filename"])

    if not os.path.isfile(file_path):
        logging.error(f"File not found: {file_path}")
        sys.exit(-1)

    # Perform preprocessing if enabled
    if config.get("preprocess", False):
        try:
            logging.info(f"toolchanger_preprocessor: Pre-processing file: {file_path}")

            # Check if file is a G-code file
            if not file_path.endswith(".gcode"):
                logging.info(f"toolchanger_preprocessor: Skipping non-G-code file: {file_path}")
            else:
                # Check if already processed
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    first_line = f.readline()
                    if 'processed by toolchanger_preprocessor' in first_line:
                        logging.info(f"toolchanger_preprocessor: File already preprocessed: {file_path}")
                    else:
                        # Import and run the preprocessor directly
                        logging.info(f"toolchanger_preprocessor: File needs preprocessing: {file_path}")

                        # Add the Klipper extras directory to Python path
                        klipper_extras_path = os.path.expanduser('~/klipper/klippy/extras')
                        if os.path.exists(klipper_extras_path) and klipper_extras_path not in sys.path:
                            sys.path.insert(0, klipper_extras_path)

                        try:
                            # Import the preprocessor modules
                            import importlib
                            import configparser
                            from gcode_preprocessor_base import PreprocessorContext, PreprocessorUtilities

                            # Load configuration
                            config_file = os.path.expanduser('~/printer_data/config/gcode-preprocessor/preprocessor.cfg')
                            parser = configparser.ConfigParser()
                            parser.read(config_file)

                            # Get processor list
                            processors_str = parser.get('gcode_preprocessor', 'processors', fallback='')
                            processors_list = [p.strip() for p in processors_str.split(',') if p.strip()]

                            # Create a simple config helper
                            class SimpleProcessorConfig:
                                def __init__(self, section_name, config_parser):
                                    self.section_name = section_name
                                    self.parser = config_parser

                                def get(self, key, default=None):
                                    try:
                                        return self.parser.get(self.section_name, key)
                                    except:
                                        return default

                                def getboolean(self, key, default=False):
                                    try:
                                        return self.parser.getboolean(self.section_name, key)
                                    except:
                                        return default

                                def getint(self, key, default=0):
                                    try:
                                        return self.parser.getint(self.section_name, key)
                                    except:
                                        return default

                            # Load processors
                            loaded_processors = []
                            for proc_name in processors_list:
                                try:
                                    module = importlib.import_module(f'preprocessors.{proc_name}')
                                    section_name = f'preprocessor {proc_name}'
                                    proc_config = SimpleProcessorConfig(section_name, parser)
                                    processor = module.create_processor(proc_config, logging)
                                    loaded_processors.append(processor)
                                    logging.info(f"toolchanger_preprocessor: Loaded processor '{proc_name}'")
                                except Exception as e:
                                    logging.warning(f"toolchanger_preprocessor: Failed to load processor '{proc_name}': {e}")

                            if not loaded_processors:
                                logging.warning("toolchanger_preprocessor: No processors loaded, skipping")
                            else:
                                # Create context
                                context = PreprocessorContext()
                                context.file_path = file_path
                                context.filename = os.path.basename(file_path)

                                # Filter processors that can process this file
                                active_processors = [p for p in loaded_processors if p.can_process(file_path, context)]

                                if not active_processors:
                                    logging.info("toolchanger_preprocessor: No applicable processors for this file")
                                else:
                                    # Pass 1: Pre-processing
                                    for processor in active_processors:
                                        if not processor.pre_process(file_path, context):
                                            logging.error(f"toolchanger_preprocessor: Pre-processing failed in {processor.get_name()}")
                                            raise Exception(f"Pre-processing failed in {processor.get_name()}")

                                    # Pass 2: Line-by-line processing
                                    input_lines = PreprocessorUtilities.read_file_lines(file_path)
                                    output_lines = []

                                    # Add fingerprint
                                    output_lines.append(PreprocessorUtilities.add_fingerprint(
                                        context.get_metadata('slicer')))

                                    context.total_lines = len(input_lines)

                                    for line_num, line in enumerate(input_lines):
                                        context.current_line = line_num
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
                                            logging.error(f"toolchanger_preprocessor: Post-processing failed in {processor.get_name()}")
                                            raise Exception(f"Post-processing failed in {processor.get_name()}")

                                    # Write output atomically
                                    temp_path = file_path + '.preprocessing'
                                    PreprocessorUtilities.write_file_lines(temp_path, output_lines)
                                    os.replace(temp_path, file_path)

                                    logging.info(f"toolchanger_preprocessor: Successfully preprocessed {file_path} with {len(active_processors)} processors")

                        except Exception as e:
                            logging.error(f"toolchanger_preprocessor: Error during preprocessing: {e}")
                            logging.error(traceback.format_exc())

        except Exception as e:
            logging.error(f"toolchanger_preprocessor: Error during preprocessing: {e}")
            logging.error(traceback.format_exc())
            # Don't exit with error - allow metadata extraction to continue

    # Now call the original metadata extraction
    # This maintains compatibility with Moonraker's file processing
    try:
        # Import and run the metadata module
        directory = os.path.dirname(os.path.abspath(__file__))
        target_dir = os.path.join(directory, "file_manager")

        if os.path.exists(target_dir):
            sys.path.insert(0, target_dir)
            import metadata
            metadata.main(config)
        else:
            logging.warning(f"toolchanger_preprocessor: file_manager directory not found at {target_dir}")
            logging.info("toolchanger_preprocessor: Metadata extraction skipped")

    except Exception as e:
        logging.error(f"toolchanger_preprocessor: Error during metadata extraction: {e}")
        logging.error(traceback.format_exc())
        sys.exit(-1)
