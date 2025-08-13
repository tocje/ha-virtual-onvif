#!/usr/bin/with-contenv bashio

# Set log level
LOG_LEVEL=$(bashio::config 'log_level')
export LOG_LEVEL=${LOG_LEVEL}

# Create config directory if it doesn't exist
mkdir -p /app/config

# Get configuration from Home Assistant
CONFIG_PATH="/data/options.json"
if bashio::fs.file_exists "${CONFIG_PATH}"; then
    cp "${CONFIG_PATH}" /app/config/addon_config.json
    bashio::log.info "Configuration loaded from Home Assistant"
else
    bashio::log.warning "No configuration found, using defaults"
    echo '{"devices": [], "discovery_enabled": true}' > /app/config/addon_config.json
fi

# Set environment variables for Home Assistant API
export SUPERVISOR_TOKEN=${SUPERVISOR_TOKEN}
export HASSIO_TOKEN=${HASSIO_TOKEN}

# Start the application
bashio::log.info "Starting Virtual ONVIF Device server..."

cd /app
python3 -u main.py