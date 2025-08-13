#!/usr/bin/env python3
"""
Home Assistant Integration
Connects with Home Assistant API to monitor entity states and trigger events
"""

import json
import logging
import os
import requests
import threading
import time
import websocket
from typing import Dict, List, Any, Callable

logger = logging.getLogger(__name__)

class HomeAssistantClient:
    """Client for Home Assistant API integration"""
    
    def __init__(self):
        self.base_url = self.get_ha_url()
        self.token = self.get_ha_token()
        self.ws_url = self.base_url.replace('http', 'ws') + '/api/websocket'
        self.headers = {
            'Authorization': f'Bearer {self.token}',
            'Content-Type': 'application/json'
        }
        
        self.ws = None
        self.ws_id = 1
        self.monitoring = False
        self.entity_callbacks = {}  # entity_id -> callback function
        self.entities_cache = {}
        
        # Test connection
        self.available = self.test_connection()
    
    def get_ha_url(self) -> str:
        """Get Home Assistant URL"""
        # Try different methods to get HA URL
        if os.getenv('HASSIO_TOKEN'):
            return 'http://supervisor/core'
        elif os.getenv('HA_URL'):
            return os.getenv('HA_URL')
        else:
            return 'http://localhost:8123'
    
    def get_ha_token(self) -> str:
        """Get Home Assistant access token"""
        # Try supervisor token first (add-on environment)
        token = os.getenv('SUPERVISOR_TOKEN') or os.getenv('HASSIO_TOKEN')
        if token:
            return token
        
        # Try long-lived access token
        token = os.getenv('HA_TOKEN')
        if token:
            return token
        
        logger.warning("No Home Assistant token found")
        return ""
    
    def test_connection(self) -> bool:
        """Test connection to Home Assistant"""
        if not self.token:
            logger.warning("No HA token available, API integration disabled")
            return False
        
        try:
            response = requests.get(
                f'{self.base_url}/api/config',
                headers=self.headers,
                timeout=5
            )
            
            if response.status_code == 200:
                config = response.json()
                logger.info(f"Connected to Home Assistant: {config.get('location_name', 'Unknown')}")
                return True
            else:
                logger.warning(f"HA API returned status {response.status_code}")
                return False
                
        except Exception as e:
            logger.warning(f"Failed to connect to Home Assistant: {e}")
            return False
    
    def is_available(self) -> bool:
        """Check if Home Assistant integration is available"""
        return self.available
    
    def get_entities(self) -> List[Dict[str, Any]]:
        """Get all available entities from Home Assistant"""
        if not self.available:
            return []
        
        try:
            response = requests.get(
                f'{self.base_url}/api/states',
                headers=self.headers,
                timeout=10
            )
            
            if response.status_code == 200:
                entities = response.json()
                
                # Filter for useful trigger entities
                filtered_entities = []
                trigger_domains = ['binary_sensor', 'input_boolean', 'switch', 'sensor', 'person']
                
                for entity in entities:
                    entity_id = entity.get('entity_id', '')
                    domain = entity_id.split('.')[0] if '.' in entity_id else ''
                    
                    if domain in trigger_domains:
                        filtered_entities.append({
                            'entity_id': entity_id,
                            'friendly_name': entity.get('attributes', {}).get('friendly_name', entity_id),
                            'state': entity.get('state', 'unknown'),
                            'domain': domain,
                            'device_class': entity.get('attributes', {}).get('device_class', '')
                        })
                
                # Cache entities
                self.entities_cache = {e['entity_id']: e for e in filtered_entities}
                logger.debug(f"Retrieved {len(filtered_entities)} entities from HA")
                
                return filtered_entities
            
        except Exception as e:
            logger.error(f"Error getting entities from HA: {e}")
        
        return []
    
    def get_entity_state(self, entity_id: str) -> Dict[str, Any]:
        """Get current state of specific entity"""
        if not self.available:
            return {}
        
        try:
            response = requests.get(
                f'{self.base_url}/api/states/{entity_id}',
                headers=self.headers,
                timeout=5
            )
            
            if response.status_code == 200:
                return response.json()
                
        except Exception as e:
            logger.error(f"Error getting entity state for {entity_id}: {e}")
        
        return {}
    
    def register_entity_callback(self, entity_id: str, callback: Callable):
        """Register callback for entity state changes"""
        self.entity_callbacks[entity_id] = callback
        logger.debug(f"Registered callback for entity: {entity_id}")
    
    def unregister_entity_callback(self, entity_id: str):
        """Unregister entity callback"""
        if entity_id in self.entity_callbacks:
            del self.entity_callbacks[entity_id]
            logger.debug(f"Unregistered callback for entity: {entity_id}")
    
    def start_monitoring(self):
        """Start monitoring Home Assistant entity changes via WebSocket"""
        if not self.available or self.monitoring:
            return
        
        self.monitoring = True
        logger.info("Starting Home Assistant entity monitoring")
        
        # Start WebSocket connection in separate thread
        threading.Thread(target=self._websocket_loop, daemon=True).start()
    
    def stop_monitoring(self):
        """Stop monitoring entity changes"""
        self.monitoring = False
        if self.ws:
            self.ws.close()
        logger.info("Stopped Home Assistant monitoring")
    
    def _websocket_loop(self):
        """WebSocket connection loop"""
        while self.monitoring:
            try:
                logger.debug("Connecting to Home Assistant WebSocket")
                
                # Create WebSocket connection
                self.ws = websocket.WebSocketApp(
                    self.ws_url,
                    on_open=self._on_ws_open,
                    on_message=self._on_ws_message,
                    on_error=self._on_ws_error,
                    on_close=self._on_ws_close
                )
                
                self.ws.run_forever()
                
            except Exception as e:
                logger.error(f"WebSocket error: {e}")
            
            if self.monitoring:
                logger.info("Reconnecting to Home Assistant in 10 seconds...")
                time.sleep(10)
    
    def _on_ws_open(self, ws):
        """WebSocket connection opened"""
        logger.debug("WebSocket connection opened")
        
        # Send authentication
        auth_message = {
            "type": "auth",
            "access_token": self.token
        }
        ws.send(json.dumps(auth_message))
    
    def _on_ws_message(self, ws, message):
        """Handle WebSocket message"""
        try:
            data = json.loads(message)
            msg_type = data.get('type')
            
            if msg_type == 'auth_ok':
                logger.info("WebSocket authenticated successfully")
                # Subscribe to state changes
                subscribe_message = {
                    "id": self.ws_id,
                    "type": "subscribe_events",
                    "event_type": "state_changed"
                }
                ws.send(json.dumps(subscribe_message))
                self.ws_id += 1
                
            elif msg_type == 'result':
                if data.get('success'):
                    logger.info("Subscribed to Home Assistant state changes")
                else:
                    logger.error(f"Subscription failed: {data}")
                    
            elif msg_type == 'event':
                self._handle_state_change(data)
                
        except Exception as e:
            logger.error(f"Error processing WebSocket message: {e}")
    
    def _on_ws_error(self, ws, error):
        """WebSocket error handler"""
        logger.error(f"WebSocket error: {error}")
    
    def _on_ws_close(self, ws, close_status_code, close_msg):
        """WebSocket connection closed"""
        logger.debug("WebSocket connection closed")
    
    def _handle_state_change(self, event_data):
        """Handle state change event from Home Assistant"""
        try:
            event = event_data.get('event', {})
            data = event.get('data', {})
            entity_id = data.get('entity_id')
            new_state = data.get('new_state', {})
            old_state = data.get('old_state', {})
            
            if not entity_id:
                return
            
            # Check if we have a callback for this entity
            if entity_id in self.entity_callbacks:
                try:
                    callback = self.entity_callbacks[entity_id]
                    callback(entity_id, new_state, old_state)
                    
                    logger.debug(f"Triggered callback for {entity_id}: {old_state.get('state')} -> {new_state.get('state')}")
                    
                except Exception as e:
                    logger.error(f"Error in entity callback for {entity_id}: {e}")
            
        except Exception as e:
            logger.error(f"Error handling state change: {e}")
    
    def call_service(self, domain: str, service: str, entity_id: str = None, service_data: Dict = None):
        """Call Home Assistant service"""
        if not self.available:
            return False
        
        try:
            url = f'{self.base_url}/api/services/{domain}/{service}'
            
            payload = service_data or {}
            if entity_id:
                payload['entity_id'] = entity_id
            
            response = requests.post(
                url,
                headers=self.headers,
                json=payload,
                timeout=10
            )
            
            if response.status_code == 200:
                logger.debug(f"Called service {domain}.{service} successfully")
                return True
            else:
                logger.error(f"Service call failed with status {response.status_code}")
                return False
                
        except Exception as e:
            logger.error(f"Error calling service {domain}.{service}: {e}")
            return False
    
    def create_persistent_notification(self, message: str, title: str = "Virtual ONVIF"):
        """Create persistent notification in Home Assistant"""
        return self.call_service(
            'persistent_notification',
            'create',
            service_data={
                'message': message,
                'title': title,
                'notification_id': f'virtual_onvif_{int(time.time())}'
            }
        )