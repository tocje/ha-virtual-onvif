# Virtual ONVIF Device - Home Assistant Add-on

Create virtual ONVIF cameras that proxy existing RTSP streams and inject custom events triggered by Home Assistant entities.

## Features

- 🎥 **Virtual ONVIF Cameras**: Create virtual cameras that appear as real ONVIF devices
- 🔗 **RTSP Proxy**: Forward existing camera streams (main + sub streams)
- ⚡ **Event Injection**: Trigger ONVIF motion/contact events from Home Assistant entities
- 🔍 **Auto Discovery**: Devices are automatically discovered by ONVIF clients
- 🌐 **Web Interface**: Easy configuration through built-in web UI
- 🏠 **HA Integration**: Deep integration with Home Assistant automations

## Use Cases

- **Legacy Camera Integration**: Make non-ONVIF cameras appear as ONVIF devices
- **Event Simulation**: Inject motion events from PIR sensors, door contacts, etc.
- **Testing & Development**: Create test ONVIF devices for NVR/VMS testing
- **Enhanced Triggers**: Use HA's advanced detection logic for camera events

## Installation

1. Add this repository to your Home Assistant add-on store
2. Install the "Virtual ONVIF Device" add-on
3. Start the add-on
4. Configure devices through the web interface

## Configuration

### Basic Add-on Configuration

```yaml
devices:
  - name: "Living Room Camera"
    main_stream_url: "rtsp://192.168.1.100:554/stream1"
    sub_stream_url: "rtsp://192.168.1.100:554/stream2"
    motion_trigger_entity: "binary_sensor.living_room_motion"
    manufacturer: "Virtual ONVIF"
    model: "Virtual Camera v1"

discovery_enabled: true
log_level: "info"
```

### Configuration Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `devices` | list | `[]` | List of virtual devices to create |
| `discovery_enabled` | bool | `true` | Enable WS-Discovery for auto-detection |
| `log_level` | string | `info` | Logging level (debug, info, warning, error) |

### Device Configuration

| Option | Type | Required | Description |
|--------|------|----------|-------------|
| `name` | string | Yes | Display name for the device |
| `main_stream_url` | string | Yes | Primary RTSP stream URL |
| `sub_stream_url` | string | No | Secondary/low-res stream URL |
| `motion_trigger_entity` | string | No | HA entity to trigger motion events |
| `door_trigger_entity` | string | No | HA entity to trigger door/contact events |
| `manufacturer` | string | No | Device manufacturer name |
| `model` | string | No | Device model name |
| `firmware_version` | string | No | Firmware version string |
| `uuid` | string | No | Device UUID (auto-generated if not provided) |

## Web Interface

Access the configuration web interface at: `http://your-ha-ip:8080`

### Features:
- **Device Management**: Add, edit, delete virtual cameras
- **Live Testing**: Manually trigger events for testing
- **Entity Browser**: Browse available Home Assistant entities
- **System Status**: Monitor service health and connections

## ONVIF Compliance

### Supported Services:
- **Device Management**: GetDeviceInformation, GetCapabilities, GetServices
- **Media Services**: GetProfiles, GetStreamUri, GetSnapshotUri
- **Event Services**: Subscribe, Unsubscribe, GetEventProperties
- **Discovery**: WS-Discovery probe/match responses

### Supported Events:
- `tns1:VideoSource/MotionAlarm` - Motion detection
- `tns1:Device/TriggerRelay` - Door/contact triggers
- `tns1:VideoSource/ImageTooBlurry` - Tamper detection
- Custom events (configurable)

### Stream Profiles:
- **Profile_1**: Main/high resolution stream
- **Profile_2**: Sub/low resolution stream

## Home Assistant Integration

### Entity Monitoring
The add-on automatically monitors configured Home Assistant entities and triggers corresponding ONVIF events:

```yaml
# Example: Motion sensor triggers camera motion event
binary_sensor.pir_sensor: on -> Motion event (state=true)
binary_sensor.pir_sensor: off -> Motion event (state=false)
```

### Service Calls
Trigger events programmatically:

```yaml
# Manual event trigger via automation
service: virtual_onvif.trigger_motion
data:
  device_name: "living_room_camera"
  state: true
```

### Automations
Create advanced triggering logic:

```yaml
automation:
  - alias: "AI Person Detection -> ONVIF Motion"
    trigger:
      - platform: state
        entity_id: binary_sensor.ai_person_detected
        to: 'on'
    action:
      - service: virtual_onvif.trigger_motion
        data:
          device_name: "front_door_camera"
          duration: 5  # seconds
```

## Network Requirements

### Ports Used:
- `8080/tcp`: Web configuration interface
- `8081/tcp`: ONVIF device and event services
- `8082/tcp`: ONVIF media services  
- `3702/udp`: WS-Discovery (multicast)

### Firewall:
Ensure ONVIF clients can reach your Home Assistant IP on the above ports.

## Troubleshooting

### Device Not Discovered
1. Check that discovery is enabled in configuration
2. Verify firewall allows UDP port 3702
3. Ensure client and HA are on same network segment
4. Check add-on logs for discovery messages

### Stream Issues
1. Verify RTSP URL is accessible from HA
2. Test stream URL directly with VLC/ffplay
3. Check camera authentication requirements
4. Ensure camera supports the specified resolution/codec

### Events Not Working
1. Verify Home Assistant entity exists and changes state
2. Check entity is properly configured in device settings
3. Monitor add-on logs for event triggers
4. Test with manual event triggers first

### Logs and Debugging
```bash
# View add-on logs
ha addons logs virtual_onvif

# Enable debug logging
# Set log_level: "debug" in configuration
```

## ONVIF Client Compatibility

### Tested Clients:
- ✅ **ONVIF Device Manager** - Full compatibility
- ✅ **Blue Iris** - Discovery and streaming
- ✅ **Milestone XProtect** - Events and streaming
- ✅ **Hikvision iVMS-4200** - Basic functionality
- ✅ **Dahua SmartPSS** - Discovery and streaming

### Known Issues:
- Some NVRs may require manual IP configuration
- PTZ commands are not supported (read-only virtual device)
- Audio streams not currently supported

## Advanced Configuration

### Multiple Devices
```yaml
devices:
  - name: "Front Door"
    main_stream_url: "rtsp://192.168.1.100:554/stream1"
    motion_trigger_entity: "binary_sensor.front_door_motion"
    
  - name: "Back Yard"  
    main_stream_url: "rtsp://192.168.1.101:554/stream1"
    motion_trigger_entity: "binary_sensor.back_yard_motion"
    door_trigger_entity: "binary_sensor.gate_contact"
```

### Custom Events
```yaml
devices:
  - name: "Smart Camera"
    main_stream_url: "rtsp://192.168.1.100:554/stream1"
    custom_events:
      - "person_detected"
      - "vehicle_detected"
      - "package_delivered"
```

## Development

### Building Locally
```bash
# Clone repository
git clone <repo-url>
cd virtual-onvif-addon

# Build for your architecture
docker build --build-arg BUILD_FROM="homeassistant/aarch64-base:latest" -t virtual-onvif .

# Test locally
docker run -p 8080:8080 -p 8081:8081 -p 3702:3702/udp virtual-onvif
```

### API Endpoints
The web interface exposes REST APIs for integration:

- `GET /api/devices` - List devices
- `POST /api/devices` - Create device  
- `PUT /api/devices/{id}` - Update device
- `DELETE /api/devices/{id}` - Delete device
- `POST /api/trigger-event` - Trigger event
- `GET /api/ha-entities` - List HA entities

## Support

- 📖 **Documentation**: [GitHub Wiki](link-to-wiki)
- 🐛 **Bug Reports**: [GitHub Issues](link-to-issues)
- 💬 **Community**: [Home Assistant Community](link-to-community-post)
- 📧 **Contact**: [Email](mailto:your-email)

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Acknowledgments

- ONVIF specification and community
- Home Assistant development team
- Python ONVIF libraries and contributors