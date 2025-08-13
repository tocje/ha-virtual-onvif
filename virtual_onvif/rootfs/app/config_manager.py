#!/usr/bin/env python3
"""
Configuration Manager
Handles device configuration, persistence, and validation
"""

import json
import logging
import os
import uuid
from typing import Dict, List, Any

logger = logging.getLogger(__name__)

class ConfigManager:
    """Manages configuration for virtual ONVIF devices"""
    
    def __init__(self, config_dir: str):
        self.config_dir = config_dir
        self.config_file = os.path.join(config_dir, 'devices.json')
        self.addon_config_file = os.path.join(config_dir, 'addon_config.json')
        self.devices = {}
        
        # Ensure config directory exists
        os.makedirs(config_dir, exist_ok=True)
        
        # Load existing configuration
        self.load_config()
    
    def load_config(self):
        """Load configuration from files"""
        # Load from Home Assistant add-on config first
        addon_config = self.load_addon_config()
        
        # Load saved devices configuration
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r') as f:
                    saved_devices = json.load(f)
                    self.devices = {dev['id']: dev for dev in saved_devices.get('devices', [])}
                logger.info(f"Loaded {len(self.devices)} devices from saved config")
            except Exception as e:
                logger.error(f"Error loading saved config: {e}")
        
        # Merge with add-on config devices
        addon_devices = addon_config.get('devices', [])
        for device_data in addon_devices:
            device_id = device_data.get('id')
            if not device_id:
                device_id = str(uuid.uuid4())
                device_data['id'] = device_id
            
            # Add or update device
            self.devices[device_id] = self.validate_device_config(device_data)
        
        if addon_devices:
            logger.info(f"Merged {len(addon_devices)} devices from add-on config")
            self.save_config()
    
    def load_addon_config(self) -> Dict[str, Any]:
        """Load configuration from Home Assistant add-on"""
        if os.path.exists(self.addon_config_file):
            try:
                with open(self.addon_config_file, 'r') as f:
                    config = json.load(f)
                    logger.debug("Loaded add-on configuration")
                    return config
            except Exception as e:
                logger.error(f"Error loading add-on config: {e}")
        
        return {'devices': [], 'discovery_enabled': True}
    
    def save_config(self):
        """Save current configuration to file"""
        try:
            config = {
                'devices': list(self.devices.values()),
                'last_updated': str(datetime.now())
            }
            
            with open(self.config_file, 'w') as f:
                json.dump(config, f, indent=2)
            
            logger.debug("Configuration saved successfully")
        except Exception as e:
            logger.error(f"Error saving configuration: {e}")
    
    def validate_device_config(self, device_data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate and normalize device configuration"""
        # Required fields with defaults
        validated = {
            'id': device_data.get('id', str(uuid.uuid4())),
            'name': device_data.get('name', 'Virtual Camera'),
            'uuid': device_data.get('uuid', str(uuid.uuid4())),
            'main_stream_url': device_data.get('main_stream_url', ''),
            'sub_stream_url': device_data.get('sub_stream_url', ''),
            'manufacturer': device_data.get('manufacturer', 'Virtual ONVIF'),
            'model': device_data.get('model', 'Virtual Camera'),
            'firmware_version': device_data.get('firmware_version', '1.0.0'),
            'motion_trigger_entity': device_data.get('motion_trigger_entity', ''),
            'door_trigger_entity': device_data.get('door_trigger_entity', ''),
            'custom_events': device_data.get('custom_events', []),
            'enabled': device_data.get('enabled', True),
            'created_at': device_data.get('created_at', str(datetime.now())),
            'updated_at': str(datetime.now())
        }
        
        # Validate URLs
        if validated['main_stream_url']:
            if not self.validate_rtsp_url(validated['main_stream_url']):
                logger.warning(f"Invalid main stream URL: {validated['main_stream_url']}")
        
        if validated['sub_stream_url']:
            if not self.validate_rtsp_url(validated['sub_stream_url']):
                logger.warning(f"Invalid sub stream URL: {validated['sub_stream_url']}")
        
        return validated
    
    def validate_rtsp_url(self, url: str) -> bool:
        """Validate RTSP URL format"""
        if not url:
            return True  # Empty URLs are allowed
        
        try:
            from urllib.parse import urlparse
            parsed = urlparse(url)
            return parsed.scheme.lower() in ['rtsp', 'rtmp', 'http', 'https']
        except:
            return False
    
    def get_devices(self) -> List[Dict[str, Any]]:
        """Get all configured devices"""
        return list(self.devices.values())
    
    def get_device(self, device_id: str) -> Dict[str, Any]:
        """Get specific device by ID"""
        return self.devices.get(device_id, {})
    
    def add_device(self, device_data: Dict[str, Any]) -> Dict[str, Any]:
        """Add new device"""
        device_id = device_data.get('id', str(uuid.uuid4()))
        device_data['id'] = device_id
        
        validated_device = self.validate_device_config(device_data)
        self.devices[device_id] = validated_device
        
        self.save_config()
        logger.info(f"Added device: {validated_device['name']} ({device_id})")
        
        return validated_device
    
    def update_device(self, device_id: str, device_data: Dict[str, Any]) -> Dict[str, Any]:
        """Update existing device"""
        if device_id not in self.devices:
            raise ValueError(f"Device {device_id} not found")
        
        device_data['id'] = device_id
        validated_device = self.validate_device_config(device_data)
        self.devices[device_id] = validated_device
        
        self.save_config()
        logger.info(f"Updated device: {validated_device['name']} ({device_id})")
        
        return validated_device
    
    def delete_device(self, device_id: str):
        """Delete device"""
        if device_id not in self.devices:
            raise ValueError(f"Device {device_id} not found")
        
        device_name = self.devices[device_id].get('name', device_id)
        del self.devices[device_id]
        
        self.save_config()
        logger.info(f"Deleted device: {device_name} ({device_id})")
    
    def get_enabled_devices(self) -> List[Dict[str, Any]]:
        """Get only enabled devices"""
        return [device for device in self.devices.values() if device.get('enabled', True)]
    
    def get_devices_with_motion_triggers(self) -> List[Dict[str, Any]]:
        """Get devices that have motion trigger entities configured"""
        return [
            device for device in self.devices.values() 
            if device.get('motion_trigger_entity') and device.get('enabled', True)
        ]
    
    def get_device_by_entity(self, entity_id: str) -> Dict[str, Any]:
        """Find device that uses specific Home Assistant entity"""
        for device in self.devices.values():
            if (device.get('motion_trigger_entity') == entity_id or 
                device.get('door_trigger_entity') == entity_id):
                return device
        return {}
    
    def export_config(self) -> Dict[str, Any]:
        """Export complete configuration"""
        return {
            'devices': list(self.devices.values()),
            'version': '1.0.0',
            'exported_at': str(datetime.now())
        }
    
    def import_config(self, config_data: Dict[str, Any]):
        """Import configuration from exported data"""
        try:
            devices = config_data.get('devices', [])
            imported_count = 0
            
            for device_data in devices:
                # Generate new ID to avoid conflicts
                old_id = device_data.get('id')
                device_data['id'] = str(uuid.uuid4())
                
                validated_device = self.validate_device_config(device_data)
                self.devices[validated_device['id']] = validated_device
                imported_count += 1
            
            self.save_config()
            logger.info(f"Imported {imported_count} devices")
            
            return imported_count
        except Exception as e:
            logger.error(f"Error importing configuration: {e}")
            raise


# Import datetime for timestamps
from datetime import datetime