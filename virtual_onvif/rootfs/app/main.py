#!/usr/bin/env python3
"""
Virtual ONVIF Device - Home Assistant Add-on
Creates virtual ONVIF cameras with custom event injection
"""

import os
import json
import logging
import threading
import time
from flask import Flask, render_template, request, jsonify
from flask_cors import CORS

from onvif_server import ONVIFServer
from discovery_server import DiscoveryServer
from ha_integration import HomeAssistantClient
from config_manager import ConfigManager

# Set up logging
LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO').upper()
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/var/log/virtual-onvif/app.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Global instances
config_manager = None
onvif_server = None
discovery_server = None
ha_client = None

def create_app():
    """Create Flask application"""
    app = Flask(__name__, 
                template_folder='/app/templates',
                static_folder='/app/static')
    CORS(app)
    
    @app.route('/')
    def index():
        """Main configuration page"""
        devices = config_manager.get_devices()
        return render_template('index.html', devices=devices)
    
    @app.route('/health')
    def health():
        """Health check endpoint"""
        return jsonify({'status': 'healthy', 'services': {
            'onvif': onvif_server.is_running() if onvif_server else False,
            'discovery': discovery_server.is_running() if discovery_server else False
        }})
    
    @app.route('/api/devices', methods=['GET'])
    def get_devices():
        """Get all configured devices"""
        return jsonify(config_manager.get_devices())
    
    @app.route('/api/devices', methods=['POST'])
    def add_device():
        """Add new virtual device"""
        data = request.json
        try:
            device = config_manager.add_device(data)
            onvif_server.add_device(device)
            return jsonify({'success': True, 'device': device})
        except Exception as e:
            logger.error(f"Error adding device: {e}")
            return jsonify({'success': False, 'error': str(e)}), 400
    
    @app.route('/api/devices/<device_id>', methods=['PUT'])
    def update_device(device_id):
        """Update existing device"""
        data = request.json
        try:
            device = config_manager.update_device(device_id, data)
            onvif_server.update_device(device)
            return jsonify({'success': True, 'device': device})
        except Exception as e:
            logger.error(f"Error updating device: {e}")
            return jsonify({'success': False, 'error': str(e)}), 400
    
    @app.route('/api/devices/<device_id>', methods=['DELETE'])
    def delete_device(device_id):
        """Delete device"""
        try:
            config_manager.delete_device(device_id)
            onvif_server.remove_device(device_id)
            return jsonify({'success': True})
        except Exception as e:
            logger.error(f"Error deleting device: {e}")
            return jsonify({'success': False, 'error': str(e)}), 400
    
    @app.route('/api/trigger-event', methods=['POST'])
    def trigger_event():
        """Manually trigger an event"""
        data = request.json
        device_id = data.get('device_id')
        event_type = data.get('event_type')
        state = data.get('state', True)
        
        try:
            onvif_server.trigger_event(device_id, event_type, state)
            return jsonify({'success': True})
        except Exception as e:
            logger.error(f"Error triggering event: {e}")
            return jsonify({'success': False, 'error': str(e)}), 400
    
    @app.route('/api/ha-entities')
    def get_ha_entities():
        """Get available Home Assistant entities"""
        try:
            entities = ha_client.get_entities() if ha_client else []
            return jsonify(entities)
        except Exception as e:
            logger.error(f"Error getting HA entities: {e}")
            return jsonify([])
    
    return app

def main():
    """Main application entry point"""
    global config_manager, onvif_server, discovery_server, ha_client
    
    logger.info("Starting Virtual ONVIF Device Add-on")
    
    try:
        # Initialize configuration manager
        config_manager = ConfigManager('/app/config')
        
        # Initialize Home Assistant client
        ha_client = HomeAssistantClient()
        
        # Initialize ONVIF server
        onvif_server = ONVIFServer(config_manager, ha_client)
        
        # Initialize discovery server
        discovery_server = DiscoveryServer(onvif_server)
        
        # Start services in threads
        threading.Thread(target=onvif_server.start, daemon=True).start()
        threading.Thread(target=discovery_server.start, daemon=True).start()
        
        # Start Home Assistant integration
        if ha_client.is_available():
            threading.Thread(target=ha_client.start_monitoring, daemon=True).start()
            logger.info("Home Assistant integration enabled")
        else:
            logger.warning("Home Assistant API not available")
        
        # Give services time to start
        time.sleep(2)
        
        # Start Flask app
        app = create_app()
        logger.info("Starting web interface on port 8080")
        app.run(host='0.0.0.0', port=8080, debug=(LOG_LEVEL == 'DEBUG'))
        
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        raise

if __name__ == '__main__':
    main()