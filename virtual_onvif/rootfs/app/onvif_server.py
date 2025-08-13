#!/usr/bin/env python3
"""
ONVIF Server Implementation
Handles ONVIF device services, media profiles, and event notifications
"""

import json
import logging
import socket
import threading
import time
import uuid
from datetime import datetime, timezone
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from xml.etree import ElementTree as ET

logger = logging.getLogger(__name__)

class ONVIFRequestHandler(BaseHTTPRequestHandler):
    """HTTP request handler for ONVIF services"""
    
    def __init__(self, onvif_server, *args):
        self.onvif_server = onvif_server
        super().__init__(*args)
    
    def do_POST(self):
        """Handle ONVIF SOAP requests"""
        try:
            content_length = int(self.headers.get('content-length', 0))
            body = self.rfile.read(content_length).decode('utf-8')
            
            logger.debug(f"ONVIF Request to {self.path}: {body[:200]}...")
            
            # Route based on path
            if self.path.startswith('/onvif/device_service'):
                response = self.handle_device_service(body)
            elif self.path.startswith('/onvif/media_service'):
                response = self.handle_media_service(body)
            elif self.path.startswith('/onvif/event_service'):
                response = self.handle_event_service(body)
            else:
                response = self.create_fault("Unknown service")
            
            self.send_response(200)
            self.send_header('Content-Type', 'application/soap+xml; charset=utf-8')
            self.send_header('Content-Length', str(len(response)))
            self.end_headers()
            self.wfile.write(response.encode('utf-8'))
            
        except Exception as e:
            logger.error(f"Error handling request: {e}")
            self.send_error(500)
    
    def handle_device_service(self, body):
        """Handle device management requests"""
        if 'GetDeviceInformation' in body:
            return self.get_device_information()
        elif 'GetCapabilities' in body:
            return self.get_capabilities()
        elif 'GetServices' in body:
            return self.get_services()
        elif 'GetScopes' in body:
            return self.get_scopes()
        else:
            return self.create_fault("Unsupported device operation")
    
    def handle_media_service(self, body):
        """Handle media service requests"""
        if 'GetProfiles' in body:
            return self.get_profiles()
        elif 'GetStreamUri' in body:
            return self.get_stream_uri(body)
        elif 'GetSnapshotUri' in body:
            return self.get_snapshot_uri(body)
        else:
            return self.create_fault("Unsupported media operation")
    
    def handle_event_service(self, body):
        """Handle event service requests"""
        if 'Subscribe' in body:
            return self.handle_subscription(body)
        elif 'Unsubscribe' in body:
            return self.handle_unsubscription(body)
        elif 'GetEventProperties' in body:
            return self.get_event_properties()
        else:
            return self.create_fault("Unsupported event operation")
    
    def get_device_information(self):
        """Return device information"""
        device = self.onvif_server.get_current_device()
        return f"""<?xml version="1.0" encoding="UTF-8"?>
<soap:Envelope xmlns:soap="http://www.w3.org/2003/05/soap-envelope">
    <soap:Body>
        <tds:GetDeviceInformationResponse xmlns:tds="http://www.onvif.org/ver10/device/wsdl">
            <tds:Manufacturer>{device.get('manufacturer', 'Virtual ONVIF')}</tds:Manufacturer>
            <tds:Model>{device.get('model', 'Virtual Camera')}</tds:Model>
            <tds:FirmwareVersion>{device.get('firmware_version', '1.0.0')}</tds:FirmwareVersion>
            <tds:SerialNumber>{device.get('uuid', 'unknown')}</tds:SerialNumber>
            <tds:HardwareId>VirtualONVIF-{device.get('uuid', 'unknown')[:8]}</tds:HardwareId>
        </tds:GetDeviceInformationResponse>
    </soap:Body>
</soap:Envelope>"""
    
    def get_capabilities(self):
        """Return device capabilities"""
        server_ip = self.onvif_server.get_server_ip()
        return f"""<?xml version="1.0" encoding="UTF-8"?>
<soap:Envelope xmlns:soap="http://www.w3.org/2003/05/soap-envelope">
    <soap:Body>
        <tds:GetCapabilitiesResponse xmlns:tds="http://www.onvif.org/ver10/device/wsdl">
            <tds:Capabilities>
                <tt:Analytics xmlns:tt="http://www.onvif.org/ver10/schema">
                    <tt:XAddr>http://{server_ip}:8081/onvif/analytics_service</tt:XAddr>
                </tt:Analytics>
                <tt:Device xmlns:tt="http://www.onvif.org/ver10/schema">
                    <tt:XAddr>http://{server_ip}:8081/onvif/device_service</tt:XAddr>
                    <tt:Network>
                        <tt:IPFilter>false</tt:IPFilter>
                        <tt:ZeroConfiguration>false</tt:ZeroConfiguration>
                        <tt:IPVersion6>false</tt:IPVersion6>
                        <tt:DynDNS>false</tt:DynDNS>
                    </tt:Network>
                    <tt:System>
                        <tt:DiscoveryResolve>false</tt:DiscoveryResolve>
                        <tt:DiscoveryBye>false</tt:DiscoveryBye>
                        <tt:RemoteDiscovery>false</tt:RemoteDiscovery>
                    </tt:System>
                </tt:Device>
                <tt:Events xmlns:tt="http://www.onvif.org/ver10/schema">
                    <tt:XAddr>http://{server_ip}:8081/onvif/event_service</tt:XAddr>
                    <tt:WSSubscriptionPolicySupport>true</tt:WSSubscriptionPolicySupport>
                    <tt:WSPullPointSupport>false</tt:WSPullPointSupport>
                </tt:Events>
                <tt:Media xmlns:tt="http://www.onvif.org/ver10/schema">
                    <tt:XAddr>http://{server_ip}:8082/onvif/media_service</tt:XAddr>
                    <tt:StreamingCapabilities>
                        <tt:RTPMulticast>false</tt:RTPMulticast>
                        <tt:RTP_TCP>true</tt:RTP_TCP>
                        <tt:RTP_RTSP_TCP>true</tt:RTP_RTSP_TCP>
                    </tt:StreamingCapabilities>
                </tt:Media>
            </tds:Capabilities>
        </tds:GetCapabilitiesResponse>
    </soap:Body>
</soap:Envelope>"""
    
    def get_profiles(self):
        """Return media profiles"""
        device = self.onvif_server.get_current_device()
        profiles_xml = ""
        
        # Main stream profile
        if device.get('main_stream_url'):
            profiles_xml += f"""
                <trt:Profiles token="Profile_1" fixed="true">
                    <tt:Name>MainStream</tt:Name>
                    <tt:VideoSourceConfiguration token="VideoSource_1">
                        <tt:Name>VideoSource_1</tt:Name>
                        <tt:UseCount>1</tt:UseCount>
                        <tt:SourceToken>VideoSource_1</tt:SourceToken>
                        <tt:Bounds x="0" y="0" width="1920" height="1080"/>
                    </tt:VideoSourceConfiguration>
                    <tt:VideoEncoderConfiguration token="VideoEncoder_1">
                        <tt:Name>VideoEncoder_1</tt:Name>
                        <tt:UseCount>1</tt:UseCount>
                        <tt:Encoding>H264</tt:Encoding>
                        <tt:Resolution>
                            <tt:Width>1920</tt:Width>
                            <tt:Height>1080</tt:Height>
                        </tt:Resolution>
                        <tt:Quality>5</tt:Quality>
                        <tt:RateControl>
                            <tt:FrameRateLimit>30</tt:FrameRateLimit>
                            <tt:EncodingInterval>1</tt:EncodingInterval>
                            <tt:BitrateLimit>8000</tt:BitrateLimit>
                        </tt:RateControl>
                        <tt:H264>
                            <tt:GovLength>30</tt:GovLength>
                            <tt:H264Profile>Main</tt:H264Profile>
                        </tt:H264>
                    </tt:VideoEncoderConfiguration>
                </trt:Profiles>"""
        
        # Sub stream profile
        if device.get('sub_stream_url'):
            profiles_xml += f"""
                <trt:Profiles token="Profile_2" fixed="true">
                    <tt:Name>SubStream</tt:Name>
                    <tt:VideoSourceConfiguration token="VideoSource_1">
                        <tt:Name>VideoSource_1</tt:Name>
                        <tt:UseCount>1</tt:UseCount>
                        <tt:SourceToken>VideoSource_1</tt:SourceToken>
                        <tt:Bounds x="0" y="0" width="704" height="576"/>
                    </tt:VideoSourceConfiguration>
                    <tt:VideoEncoderConfiguration token="VideoEncoder_2">
                        <tt:Name>VideoEncoder_2</tt:Name>
                        <tt:UseCount>1</tt:UseCount>
                        <tt:Encoding>H264</tt:Encoding>
                        <tt:Resolution>
                            <tt:Width>704</tt:Width>
                            <tt:Height>576</tt:Height>
                        </tt:Resolution>
                        <tt:Quality>3</tt:Quality>
                        <tt:RateControl>
                            <tt:FrameRateLimit>15</tt:FrameRateLimit>
                            <tt:EncodingInterval>1</tt:EncodingInterval>
                            <tt:BitrateLimit>1000</tt:BitrateLimit>
                        </tt:RateControl>
                        <tt:H264>
                            <tt:GovLength>15</tt:GovLength>
                            <tt:H264Profile>Baseline</tt:H264Profile>
                        </tt:H264>
                    </tt:VideoEncoderConfiguration>
                </trt:Profiles>"""
        
        return f"""<?xml version="1.0" encoding="UTF-8"?>
<soap:Envelope xmlns:soap="http://www.w3.org/2003/05/soap-envelope"
               xmlns:trt="http://www.onvif.org/ver10/media/wsdl"
               xmlns:tt="http://www.onvif.org/ver10/schema">
    <soap:Body>
        <trt:GetProfilesResponse>
            {profiles_xml}
        </trt:GetProfilesResponse>
    </soap:Body>
</soap:Envelope>"""
    
    def get_stream_uri(self, body):
        """Return stream URI for requested profile"""
        device = self.onvif_server.get_current_device()
        
        # Parse profile token from request
        profile_token = "Profile_1"  # Default
        if 'ProfileToken' in body:
            # Simple extraction - could be improved with proper XML parsing
            start = body.find('<ProfileToken>') + len('<ProfileToken>')
            end = body.find('</ProfileToken>')
            if start > 0 and end > start:
                profile_token = body[start:end]
        
        # Return appropriate stream URL
        stream_url = ""
        if profile_token == "Profile_1" and device.get('main_stream_url'):
            stream_url = device['main_stream_url']
        elif profile_token == "Profile_2" and device.get('sub_stream_url'):
            stream_url = device['sub_stream_url']
        else:
            stream_url = device.get('main_stream_url', '')
        
        return f"""<?xml version="1.0" encoding="UTF-8"?>
<soap:Envelope xmlns:soap="http://www.w3.org/2003/05/soap-envelope">
    <soap:Body>
        <trt:GetStreamUriResponse xmlns:trt="http://www.onvif.org/ver10/media/wsdl">
            <trt:MediaUri>
                <tt:Uri xmlns:tt="http://www.onvif.org/ver10/schema">{stream_url}</tt:Uri>
                <tt:InvalidAfterConnect xmlns:tt="http://www.onvif.org/ver10/schema">false</tt:InvalidAfterConnect>
                <tt:InvalidAfterReboot xmlns:tt="http://www.onvif.org/ver10/schema">false</tt:InvalidAfterReboot>
                <tt:Timeout xmlns:tt="http://www.onvif.org/ver10/schema">PT60S</tt:Timeout>
            </trt:MediaUri>
        </trt:GetStreamUriResponse>
    </soap:Body>
</soap:Envelope>"""
    
    def handle_subscription(self, body):
        """Handle event subscription"""
        # Extract consumer reference from request
        consumer_ref = "http://unknown/notify"
        if 'ConsumerReference' in body:
            # Simple extraction - could be improved
            start = body.find('<Address>') + len('<Address>')
            end = body.find('</Address>')
            if start > 0 and end > start:
                consumer_ref = body[start:end]
        
        # Create subscription
        subscription_id = str(uuid.uuid4())
        self.onvif_server.add_subscription(subscription_id, consumer_ref)
        
        return f"""<?xml version="1.0" encoding="UTF-8"?>
<soap:Envelope xmlns:soap="http://www.w3.org/2003/05/soap-envelope">
    <soap:Body>
        <wsnt:SubscribeResponse xmlns:wsnt="http://docs.oasis-open.org/wsn/b-2">
            <wsnt:SubscriptionReference>
                <wsa:Address xmlns:wsa="http://www.w3.org/2005/08/addressing">http://{self.onvif_server.get_server_ip()}:8081/subscription/{subscription_id}</wsa:Address>
            </wsnt:SubscriptionReference>
        </wsnt:SubscribeResponse>
    </soap:Body>
</soap:Envelope>"""
    
    def create_fault(self, error_msg):
        """Create SOAP fault response"""
        return f"""<?xml version="1.0" encoding="UTF-8"?>
<soap:Envelope xmlns:soap="http://www.w3.org/2003/05/soap-envelope">
    <soap:Body>
        <soap:Fault>
            <soap:Code>
                <soap:Value>soap:Sender</soap:Value>
            </soap:Code>
            <soap:Reason>
                <soap:Text xml:lang="en">{error_msg}</soap:Text>
            </soap:Reason>
        </soap:Fault>
    </soap:Body>
</soap:Envelope>"""


class ONVIFServer:
    """Main ONVIF server class"""
    
    def __init__(self, config_manager, ha_client):
        self.config_manager = config_manager
        self.ha_client = ha_client
        self.devices = {}
        self.subscriptions = {}
        self.current_device_id = None
        self.running = False
        self.server = None
        
    def start(self):
        """Start ONVIF server"""
        try:
            logger.info("Starting ONVIF server on port 8081")
            
            # Create request handler with server reference
            def handler(*args):
                return ONVIFRequestHandler(self, *args)
            
            # Start HTTP server
            self.server = HTTPServer(('0.0.0.0', 8081), handler)
            self.running = True
            
            # Load devices from config
            self.load_devices()
            
            logger.info("ONVIF server started successfully")
            self.server.serve_forever()
            
        except Exception as e:
            logger.error(f"Failed to start ONVIF server: {e}")
            self.running = False
    
    def stop(self):
        """Stop ONVIF server"""
        self.running = False
        if self.server:
            self.server.shutdown()
    
    def is_running(self):
        """Check if server is running"""
        return self.running
    
    def load_devices(self):
        """Load devices from configuration"""
        devices = self.config_manager.get_devices()
        for device in devices:
            self.devices[device['id']] = device
            if not self.current_device_id:
                self.current_device_id = device['id']
        logger.info(f"Loaded {len(devices)} virtual devices")
    
    def add_device(self, device_data):
        """Add new virtual device"""
        device_id = device_data.get('id', str(uuid.uuid4()))
        device_data['id'] = device_id
        self.devices[device_id] = device_data
        
        if not self.current_device_id:
            self.current_device_id = device_id
            
        logger.info(f"Added device: {device_data.get('name', device_id)}")
        return device_data
    
    def update_device(self, device_data):
        """Update existing device"""
        device_id = device_data['id']
        if device_id in self.devices:
            self.devices[device_id].update(device_data)
            logger.info(f"Updated device: {device_data.get('name', device_id)}")
        return device_data
    
    def remove_device(self, device_id):
        """Remove virtual device"""
        if device_id in self.devices:
            del self.devices[device_id]
            if self.current_device_id == device_id:
                self.current_device_id = next(iter(self.devices.keys()), None)
            logger.info(f"Removed device: {device_id}")
    
    def get_current_device(self):
        """Get current active device"""
        if self.current_device_id and self.current_device_id in self.devices:
            return self.devices[self.current_device_id]
        return {}
    
    def get_server_ip(self):
        """Get server IP address"""
        try:
            # Get local IP address
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except:
            return "127.0.0.1"
    
    def add_subscription(self, subscription_id, consumer_ref):
        """Add event subscription"""
        self.subscriptions[subscription_id] = {
            'consumer_ref': consumer_ref,
            'created': datetime.now(timezone.utc)
        }
        logger.info(f"Added event subscription: {subscription_id}")
    
    def remove_subscription(self, subscription_id):
        """Remove event subscription"""
        if subscription_id in self.subscriptions:
            del self.subscriptions[subscription_id]
            logger.info(f"Removed event subscription: {subscription_id}")
    
    def trigger_event(self, device_id, event_type, state):
        """Trigger ONVIF event to subscribers"""
        if not self.subscriptions:
            logger.debug("No event subscribers to notify")
            return
        
        device = self.devices.get(device_id, {})
        device_name = device.get('name', device_id)
        
        # Create ONVIF event message
        timestamp = datetime.now(timezone.utc).isoformat()
        
        # Map event types to ONVIF topics
        topic_mapping = {
            'motion': 'tns1:VideoSource/MotionAlarm',
            'door': 'tns1:Device/TriggerRelay',
            'tamper': 'tns1:VideoSource/ImageTooBlurry'
        }
        
        topic = topic_mapping.get(event_type, f'tns1:VideoSource/{event_type}')
        
        event_message = f"""<?xml version="1.0" encoding="UTF-8"?>
<wsnt:Notify xmlns:wsnt="http://docs.oasis-open.org/wsn/b-2"
             xmlns:tns1="http://www.onvif.org/ver10/topics"
             xmlns:tt="http://www.onvif.org/ver10/schema">
    <wsnt:NotificationMessage>
        <wsnt:Topic Dialect="http://www.onvif.org/ver10/tev/topicExpression/ConcreteSet">
            {topic}
        </wsnt:Topic>
        <wsnt:Message>
            <tt:Message UtcTime="{timestamp}" PropertyOperation="Changed">
                <tt:Source>
                    <tt:SimpleItem Name="VideoSourceConfigurationToken" Value="VideoSource_1"/>
                    <tt:SimpleItem Name="VideoSourceToken" Value="VideoSource_1"/>
                </tt:Source>
                <tt:Key>
                    <tt:SimpleItem Name="ObjectId" Value="{device_id}"/>
                </tt:Key>
                <tt:Data>
                    <tt:SimpleItem Name="State" Value="{str(state).lower()}"/>
                </tt:Data>
            </tt:Message>
        </wsnt:Message>
    </wsnt:NotificationMessage>
</wsnt:Notify>"""
        
        # Send to all subscribers
        for sub_id, subscription in self.subscriptions.items():
            try:
                self.send_event_notification(subscription['consumer_ref'], event_message)
                logger.info(f"Sent {event_type} event for device {device_name} to subscriber {sub_id}")
            except Exception as e:
                logger.error(f"Failed to send event to subscriber {sub_id}: {e}")
    
    def send_event_notification(self, consumer_ref, event_message):
        """Send event notification to subscriber endpoint"""
        import requests
        
        headers = {
            'Content-Type': 'application/soap+xml; charset=utf-8',
            'SOAPAction': 'http://docs.oasis-open.org/wsn/bw-2/NotificationConsumer/Notify'
        }
        
        try:
            response = requests.post(consumer_ref, data=event_message, headers=headers, timeout=10)
            if response.status_code == 200:
                logger.debug(f"Event notification sent successfully to {consumer_ref}")
            else:
                logger.warning(f"Event notification failed with status {response.status_code}")
        except requests.RequestException as e:
            logger.error(f"Failed to send event notification: {e}")