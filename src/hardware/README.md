# Biometric Access System Hardware Module

This module handles hardware integration for the Biometric Access Control System, supporting fingerprint scanners and facial recognition cameras.

## Installation

1. Install dependencies:
   ```bash
   pip install -r requirements.txt



   Supported Hardware
Fingerprint Scanners
Generic USB fingerprint scanners (using serial communication)

ZKTeco scanners (with custom protocol)

Suprema scanners (with custom protocol)

Cameras
USB webcams

IP cameras (RTSP streams)

Network cameras

Access Controllers
GPIO relays (Raspberry Pi)

Serial relays

Network controllers

Simulated controllers (for testing)

API Reference
HardwareManager
initialize_hardware(): Initialize all hardware devices

start_monitoring(): Start monitoring for biometric events

get_device_status(): Get status of all devices

enroll_fingerprint(user_id): Enroll new fingerprint

enroll_face(user_id): Enroll new face

run_diagnostics(): Run comprehensive diagnostics

Troubleshooting
Scanner not detected: Check port configuration and USB connection

Camera not working: Verify camera index or URL

Import errors: Install missing dependencies from requirements.txt