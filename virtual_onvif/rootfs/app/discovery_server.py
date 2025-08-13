#!/usr/bin/env python3
"""
WS-Discovery Server
Handles ONVIF device discovery via UDP multicast
"""

import logging
import socket
import threading
import time
import uuid
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

class DiscoveryServer:
    """WS-Discovery server for ONVIF device discovery"""
    
    def __init__(self, onvif_server):
        self.onvif_server = onvif_server
        self.multicast_group = '239.255.255.250'
        self.multicast_port = 3702
        self.server_socket = None
        self.running = False
        
    def start(self):
        """Start discovery server"""
        try:
            logger.info("Starting WS-Discovery server")
            
            # Create UDP socket
            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            
            # Bind to multicast group
            self.server_socket.bind(('', self.multicast_port))
            
            # Join multicast group
            mreq = socket.inet_aton(self.multicast_group) + socket.inet_aton('0.0.0.0')
            self.server_socket.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
            
            self.running = True
            logger.info(f"WS-Discovery server listening on {self.multicast_group}:{self.multicast_port}")
            
            # Start listening loop
            while self.running:
                try:
                    data, addr = self.server_socket.recvfrom(4096)
                    message = data.decode('utf-8')
                    
                    logger.debug(f"Discovery request from {addr}: {message[:100]}...")
                    
                    # Handle probe requests
                    if 'Probe' in message and 'NetworkVideoTransmitter' in message:
                        self.send_probe_match(addr, message)
                    
                except socket.timeout:
                    continue
                except Exception as e:
                    if self.running:
                        logger.error(f"Discovery server error: {e}")
            
        except Exception as e:
            logger.error(f"Failed to start discovery server: {e}")
            self.running = False
    
    def stop(self):
        """Stop discovery server"""
        self.running = False
        if self.server_socket:
            self.server_socket.close()
        logger.info("WS-Discovery server stopped")
    
    def is_running(self):
        """Check if discovery server is running"""
        return self.running
    
    def send_probe_match(self, client_addr, probe_message):
        """Send probe match response"""
        try:
            # Get current device info
            device = self.onvif_server.get_current_device()
            if not device:
                return
            
            server_ip = self.onvif_server.get_server_ip()
            device_uuid = device.get('uuid', str(uuid.uuid4()))
            device_name = device.get('name', 'Virtual Camera')
            
            # Extract message ID from probe
            message_id = self.extract_message_id(probe_message)
            
            # Create probe match response
            response = f"""<?xml version="1.0" encoding="UTF-8"?>
<soap:Envelope xmlns:soap="http://www.w3.org/2003/05/soap-envelope"
               xmlns:wsa="http://www.w3.org/2005/08/addressing"
               xmlns:wsd="http://schemas.xmlsoap.org/ws/2005/04/discovery"
               xmlns:tns="http://www.onvif.org/ver10/network/wsdl">
    <soap:Header>
        <wsa:Action>http://schemas.xmlsoap.org/ws/2005/04/discovery/ProbeMatches</wsa:Action>
        <wsa:MessageID>urn:uuid:{str(uuid.uuid4())}</wsa:MessageID>
        <wsa:RelatesTo>{message_id}</wsa:RelatesTo>
        <wsa:To>http://www.w3.org/2005/08/addressing/anonymous</wsa:To>
    </soap:Header>
    <soap:Body>
        <wsd:ProbeMatches>
            <wsd:ProbeMatch>
                <wsa:EndpointReference>
                    <wsa:Address>urn:uuid:{device_uuid}</wsa:Address>
                </wsa:EndpointReference>
                <wsd:Types>tns:NetworkVideoTransmitter</wsd:Types>
                <wsd:Scopes>onvif://www.onvif.org/location/unknown onvif://www.onvif.org/name/{device_name} onvif://www.onvif.org/hardware/VirtualONVIF onvif://www.onvif.org/Profile/Streaming</wsd:Scopes>
                <wsd:XAddrs>http://{server_ip}:8081/onvif/device_service</wsd:XAddrs>
                <wsd:MetadataVersion>1</wsd:MetadataVersion>
            </wsd:ProbeMatch>
        </wsd:ProbeMatches>
    </soap:Body>
</soap:Envelope>"""
            
            # Send response
            response_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            response_socket.sendto(response.encode('utf-8'), client_addr)
            response_socket.close()
            
            logger.info(f"Sent probe match to {client_addr} for device {device_name}")
            
        except Exception as e:
            logger.error(f"Error sending probe match: {e}")
    
    def extract_message_id(self, message):
        """Extract message ID from probe request"""
        try:
            start = message.find('<wsa:MessageID>') + len('<wsa:MessageID>')
            end = message.find('</wsa:MessageID>')
            if start > 0 and end > start:
                return message[start:end]
        except:
            pass
        
        return f"urn:uuid:{str(uuid.uuid4())}"
    
    def send_hello(self):
        """Send hello announcement (when device comes online)"""
        try:
            device = self.onvif_server.get_current_device()
            if not device:
                return
            
            server_ip = self.onvif_server.get_server_ip()
            device_uuid = device.get('uuid', str(uuid.uuid4()))
            device_name = device.get('name', 'Virtual Camera')
            
            hello_message = f"""<?xml version="1.0" encoding="UTF-8"?>
<soap:Envelope xmlns:soap="http://www.w3.org/2003/05/soap-envelope"
               xmlns:wsa="http://www.w3.org/2005/08/addressing"
               xmlns:wsd="http://schemas.xmlsoap.org/ws/2005/04/discovery"
               xmlns:tns="http://www.onvif.org/ver10/network/wsdl">
    <soap:Header>
        <wsa:Action>http://schemas.xmlsoap.org/ws/2005/04/discovery/Hello</wsa:Action>
        <wsa:MessageID>urn:uuid:{str(uuid.uuid4())}</wsa:MessageID>
        <wsa:To>urn:schemas-xmlsoap-org:ws:2005:04:discovery</wsa:To>
    </soap:Header>
    <soap:Body>
        <wsd:Hello>
            <wsa:EndpointReference>
                <wsa:Address>urn:uuid:{device_uuid}</wsa:Address>
            </wsa:EndpointReference>
            <wsd:Types>tns:NetworkVideoTransmitter</wsd:Types>
            <wsd:Scopes>onvif://www.onvif.org/location/unknown onvif://www.onvif.org/name/{device_name} onvif://www.onvif.org/hardware/VirtualONVIF onvif://www.onvif.org/Profile/Streaming</wsd:Scopes>
            <wsd:XAddrs>http://{server_ip}:8081/onvif/device_service</wsd:XAddrs>
            <wsd:MetadataVersion>1</wsd:MetadataVersion>
        </wsd:Hello>
    </soap:Body>
</soap:Envelope>"""
            
            # Send to multicast group
            hello_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            hello_socket.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 2)
            hello_socket.sendto(
                hello_message.encode('utf-8'), 
                (self.multicast_group, self.multicast_port)
            )
            hello_socket.close()
            
            logger.info(f"Sent hello announcement for device {device_name}")
            
        except Exception as e:
            logger.error(f"Error sending hello: {e}")
    
    def send_bye(self):
        """Send bye announcement (when device goes offline)"""
        try:
            device = self.onvif_server.get_current_device()
            if not device:
                return
            
            device_uuid = device.get('uuid', str(uuid.uuid4()))
            device_name = device.get('name', 'Virtual Camera')
            
            bye_message = f"""<?xml version="1.0" encoding="UTF-8"?>
<soap:Envelope xmlns:soap="http://www.w3.org/2003/05/soap-envelope"
               xmlns:wsa="http://www.w3.org/2005/08/addressing"
               xmlns:wsd="http://schemas.xmlsoap.org/ws/2005/04/discovery"
               xmlns:tns="http://www.onvif.org/ver10/network/wsdl">
    <soap:Header>
        <wsa:Action>http://schemas.xmlsoap.org/ws/2005/04/discovery/Bye</wsa:Action>
        <wsa:MessageID>urn:uuid:{str(uuid.uuid4())}</wsa:MessageID>
        <wsa:To>urn:schemas-xmlsoap-org:ws:2005:04:discovery</wsa:To>
    </soap:Header>
    <soap:Body>
        <wsd:Bye>
            <wsa:EndpointReference>
                <wsa:Address>urn:uuid:{device_uuid}</wsa:Address>
            </wsa:EndpointReference>
            <wsd:Types>tns:NetworkVideoTransmitter</wsd:Types>
            <wsd:MetadataVersion>1</wsd:MetadataVersion>
        </wsd:Bye>
    </soap:Body>
</soap:Envelope>"""
            
            # Send to multicast group
            bye_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            bye_socket.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 2)
            bye_socket.sendto(
                bye_message.encode('utf-8'), 
                (self.multicast_group, self.multicast_port)
            )
            bye_socket.close()
            
            logger.info(f"Sent bye announcement for device {device_name}")
            
        except Exception as e:
            logger.error(f"Error sending bye: {e}")