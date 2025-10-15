#!/bin/bash
# Klipper G-code Preprocessor Installation Script
#
# This script installs the G-code preprocessor system for Klipper
# It can be used standalone or integrated with klipper-toolchanger

KLIPPER_PATH="${HOME}/klipper"
MOONRAKER_PATH="${HOME}/moonraker"
INSTALL_PATH="${HOME}/klipper-gcode-preprocessor"
CONFIG_PATH="${HOME}/printer_data/config"

set -eu
export LC_ALL=C

function preflight_checks {
    if [ "$EUID" -eq 0 ]; then
        echo "[PRE-CHECK] This script must not be run as root!"
        exit -1
    fi

    if [ "$(sudo systemctl list-units --full -all -t service --no-legend | grep -F 'klipper.service')" ]; then
        printf "[PRE-CHECK] Klipper service found! Continuing...\n\n"
    else
        echo "[ERROR] Klipper service not found, please install Klipper first!"
        exit -1
    fi
}

function check_download {
    local installdirname installbasename
    installdirname="$(dirname ${INSTALL_PATH})"
    installbasename="$(basename ${INSTALL_PATH})"

    if [ ! -d "${INSTALL_PATH}" ]; then
        echo "[DOWNLOAD] Downloading repository..."
        if git -C $installdirname clone https://github.com/jwellman80/klipper-gcode-preprocessor.git $installbasename; then
            chmod +x ${INSTALL_PATH}/install.sh
            printf "[DOWNLOAD] Download complete!\n\n"
        else
            echo "[ERROR] Download of git repository failed!"
            echo "[INFO] Continuing with local installation..."
        fi
    else
        printf "[DOWNLOAD] Repository already found locally. Continuing...\n\n"
    fi
}

function link_klipper_modules {
    echo "[INSTALL] Linking G-code preprocessor modules to Klipper..."

    # Link main modules
    ln -sfn "${INSTALL_PATH}"/klipper/extras/gcode_preprocessor_base.py "${KLIPPER_PATH}/klippy/extras/"
    ln -sfn "${INSTALL_PATH}"/klipper/extras/gcode_preprocessor.py "${KLIPPER_PATH}/klippy/extras/"

    # Link preprocessor plugins
    mkdir -p "${KLIPPER_PATH}/klippy/extras/preprocessors"
    for file in "${INSTALL_PATH}"/klipper/extras/preprocessors/*.py; do
        ln -sfn "${file}" "${KLIPPER_PATH}/klippy/extras/preprocessors/"
    done

    echo "[INSTALL] Klipper modules linked successfully!"
}

function install_config {
    echo "[INSTALL] Installing configuration files..."

    mkdir -p "${CONFIG_PATH}"/gcode-preprocessor

    # Copy config file if it doesn't exist, otherwise show diff
    if [ ! -f "${CONFIG_PATH}/gcode-preprocessor/preprocessor.cfg" ]; then
        cp "${INSTALL_PATH}"/config/gcode-preprocessor.cfg "${CONFIG_PATH}"/gcode-preprocessor/preprocessor.cfg
        echo "[INSTALL] Configuration file installed to ${CONFIG_PATH}/gcode-preprocessor/preprocessor.cfg"
    else
        echo "[INFO] Configuration file already exists at ${CONFIG_PATH}/gcode-preprocessor/preprocessor.cfg"
        echo "[INFO] Review ${INSTALL_PATH}/config/gcode-preprocessor.cfg for any new settings"
    fi

    echo ""
    echo "[INFO] Add the following line to your printer.cfg to enable the preprocessor:"
    echo ""
    echo "    [include gcode-preprocessor/preprocessor.cfg]"
    echo ""
}

function install_moonraker_component {
    echo -e "\n\nInstall Moonraker component for automatic G-code preprocessing?"
    echo "This enables automatic preprocessing when files are uploaded via Mainsail/Fluidd."
    echo "You can skip this and use manual preprocessing with PREPROCESS_GCODE_FILE instead."
    echo ""
    echo "1. Yes, install Moonraker component (recommended)"
    echo "2. No, skip Moonraker integration"
    read -rp "Select an option [1-2]: " moonraker_choice

    case $moonraker_choice in
        1)
            if [ -d "${MOONRAKER_PATH}/moonraker/components" ]; then
                echo "[INSTALL] Installing Moonraker component..."
                ln -sfn "${INSTALL_PATH}"/moonraker/toolchanger_preprocessor.py "${MOONRAKER_PATH}"/moonraker/components/
                echo "[INSTALL] Moonraker component installed!"
                echo ""
                echo "[INFO] Add the following to your moonraker.conf to enable automatic preprocessing:"
                echo ""
                echo "[toolchanger_preprocessor]"
                echo "enable_preprocessing: True"
                echo ""
                echo "[INFO] Then restart Moonraker: sudo systemctl restart moonraker"
            else
                echo "[WARNING] Moonraker components directory not found at ${MOONRAKER_PATH}/moonraker/components"
                echo "[WARNING] Moonraker component installation skipped."
                echo "[INFO] You can still use manual preprocessing with PREPROCESS_GCODE_FILE"
            fi
            ;;
        2)
            echo "[INSTALL] Skipping Moonraker component installation."
            echo "[INFO] You can use manual preprocessing with PREPROCESS_GCODE_FILE"
            ;;
        *)
            echo "[ERROR] Invalid option selected!"
            exit -1
            ;;
    esac
}

function restart_klipper {
    echo -e "\n[POST-INSTALL] Restart Klipper now?"
    echo "1. Yes, restart Klipper"
    echo "2. No, I'll restart manually later"
    read -rp "Select an option [1-2]: " restart_choice

    case $restart_choice in
        1)
            echo "[POST-INSTALL] Restarting Klipper..."
            sudo systemctl restart klipper
            echo "[POST-INSTALL] Klipper restarted!"
            ;;
        2)
            echo "[POST-INSTALL] Please restart Klipper manually when ready:"
            echo "    sudo systemctl restart klipper"
            ;;
        *)
            echo "[WARNING] Invalid option, skipping restart"
            ;;
    esac
}

function show_completion_message {
    echo ""
    echo "========================================"
    echo "Installation Complete!"
    echo "========================================"
    echo ""
    echo "Next steps:"
    echo "1. Add to your printer.cfg:"
    echo "   [include gcode-preprocessor/preprocessor.cfg]"
    echo ""
    echo "2. Restart Klipper if you haven't already:"
    echo "   sudo systemctl restart klipper"
    echo ""
    echo "3. Test the preprocessor with:"
    echo "   PREPROCESS_GCODE_FILE FILE=/path/to/file.gcode"
    echo ""
    echo "4. List available processors:"
    echo "   LIST_GCODE_PROCESSORS"
    echo ""
    echo "Documentation: ${INSTALL_PATH}/docs/README.md"
    echo "Example test file: ${INSTALL_PATH}/examples/test_sample.gcode"
    echo ""
}

# Main installation flow
printf "\n============================================\n"
echo "  Klipper G-code Preprocessor Installer"
printf "============================================\n\n"

# Run steps
preflight_checks
check_download
link_klipper_modules
install_config
install_moonraker_component
restart_klipper
show_completion_message
