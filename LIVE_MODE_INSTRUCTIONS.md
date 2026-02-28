# Live Mode Testing Instructions for CCTV Power Supply Unit

## Equipment Setup

### Required Equipment
- **CCTV Power Supply Unit (Model: SP-80M / CCTV-PSU-24W-V1)**
- **USB Multimeter (Silicon Labs CP210x chipset)**
- **Multimeter Test Leads**
- **AC Power Cord**
- **Computer with Python 3.8+**

### Connection Diagram
```
AC Power Outlet
    |
    v
[CCTV Power Supply]
    |
    +-- TP2 (12V Output Rail) --> Red Test Lead --> USB Multimeter Red
    +-- GND --> Black Test Lead --> USB Multimeter Black
    +-- Other Test Points (TP1, TP3, etc.) for additional measurements
```

## Step-by-Step Setup

### 1. Install Drivers (if needed)
- **Windows**: The CP210x driver is automatically installed on Windows 10/11
- **Linux**: Run `sudo apt-get install python3-serial` or install via package manager
- **macOS**: Drivers available from Silicon Labs website

### 2. Verify USB Multimeter Connection
```bash
# Run connection test
python test_usb_multimeter.py

# Expected Output:
# ============================================================
# USB MULTIMETER CONNECTION TEST
# ============================================================
# Step 1: Listing available COM ports...
# ----------------------------------------
#   Found 5 COM port(s):
#   [ ] COM8: Silicon Labs CP210x USB to UART Bridge
#   [OK] Auto-detected multimeter on: COM8
#   [OK] Connected to multimeter!
#   Port: COM8
#   Baud Rate: 2400
```

### 3. Check Environment Configuration
```bash
# Verify dependencies are installed
pip install -r requirements.txt

# Check .env file
cat .env
```

**Required .env settings:**
```
# APPLICATION MODE
APP_MODE=mock                      # Will be overridden by --usb flag
USB_PORT=COM8                      # Auto-detected or set manually
USB_BAUD_RATE=2400
USB_TIMEOUT=2.0

# LLM Configuration (required for diagnostic reasoning)
GROQ_API_KEY=gsk_your_key_here
LLM_PROVIDER=groq
LLM_MODEL=llama-3.3-70b-versatile

# Embeddings (Local - no API key needed)
EMBEDDING_PROVIDER=local
EMBEDDING_MODEL=all-MiniLM-L6-v2

# ChromaDB (RAG system)
CHROMADB_HOST=localhost
CHROMADB_PORT=8000
CHROMADB_COLLECTION=biomed_equipment

# LangSmith (Observability)
LANGCHAIN_API_KEY=lsv2_your_key_here
LANGCHAIN_PROJECT=biomed-troubleshooter
LANGCHAIN_TRACING=true
```

### 4. Start ChromaDB (RAG System)
```bash
# For Docker installation
docker run -d -p 8000:8000 chromadb/chroma

# Verify ChromaDB is running
python test_retrieval.py
```

## Running Live Mode Test

### Option 1: Using --usb Flag (Recommended)
```bash
# Run agent with USB multimeter
python -m src.interfaces.cli --usb CCTV-PSU-24W-V1

# Expected Output:
# ============================================================
# USB MULTIMETER MODE - Biomedical Troubleshooting Agent
# ============================================================
# Equipment: CCTV-PSU-24W-V1
# Timeout: 60 seconds
#
# Press Ctrl+C to exit
#
# Detecting USB multimeter...
# Connected to multimeter!
#
# Taking measurements...
# Connect probes to test points and press Enter after each measurement.
#
# Press Enter to take measurement 1 (or 'q' to finish): 
```

### Option 2: Setting APP_MODE=usb in .env
```bash
# Edit .env file
APP_MODE=usb

# Run without flags
python -m src.interfaces.cli --status
```

## Taking Measurements

### Test Points and Measurements

#### Primary Input (TP1 - Bridge Rectifier Output)
```
Location: Near AC input connector
Type: DC Voltage
Expected Normal: 280-380V
Safety: HIGH VOLTAGE - Disconnect AC power first!
```

#### 12V Output Rail (TP2 - Main Output)
```
Location: Near output connectors
Type: DC Voltage
Expected Normal: 11.4-12.6V
```

#### Feedback Reference (TP3)
```
Location: Near U5 (Buck Converter IC)
Type: DC Voltage
Expected Normal: 2.4-2.6V
```

#### Input Fuse (F1)
```
Location: Input side near AC connector
Type: Resistance
Expected Normal: <0.1Ω (continuity)
```

#### Output Current (I_OUT)
```
Location: Series with output rail
Type: DC Current
Expected Normal: <2.0A
```

#### Feedback Resistor (R2)
```
Location: Near TP3
Type: Resistance
Expected Normal: 465-475Ω
```

#### Output Capacitor ESR (C12)
```
Location: Output side
Type: Resistance (ESR)
Expected Normal: <0.2Ω
```

#### U5 Temperature (Buck Converter IC)
```
Location: U5 package
Type: Temperature
Expected Normal: <60°C
```

### Measurement Procedure
1. Connect USB multimeter to computer
2. Connect multimeter test leads to test point
3. Press Enter to record measurement
4. Continue for all test points
5. Type 'q' or press Ctrl+C to finish

## Sample Measurement Sequence
```
Press Enter to take measurement 1 (or 'q' to finish): 

  Recorded: 12.2 V (DC_VOLTAGE)

Press Enter to take measurement 2 (or 'q' to finish): 

  Recorded: 2.5 V (DC_VOLTAGE)

Press Enter to take measurement 3 (or 'q' to finish): 

  Recorded: 310.5 V (DC_VOLTAGE)

Press Enter to take measurement 4 (or 'q' to finish): q

--- RUNNING DIAGNOSIS ---

--- Diagnosis Result ---
  Primary Cause: Output Rail Collapse
  Confidence: 0.85
  Severity: high

  Recommended Actions:
    1. Check input fuse F1 continuity
    2. Measure bridge output TP1
    3. Replace buck converter IC U5
```

## Troubleshooting Tips

### Common Issues

#### No Reading Received
```
[!] No measurement received within timeout
```
**Possible Causes & Fixes:**
- Multimeter not measuring anything - connect to voltage source
- Loose test leads - check connections
- Wrong COM port - specify with --usb-port parameter
- Baud rate mismatch - try 9600 or 19200 baud

#### Connection Failed
```
[ERROR] Failed to connect to USB multimeter
```
**Possible Causes & Fixes:**
- USB cable disconnected - check physical connection
- Drivers not installed - reinstall CP210x drivers
- Permission issues (Linux) - run with sudo or add user to dialout group

#### Parser Error
```
Raw value contains unexpected characters
```
**Possible Causes & Fixes:**
- Incorrect baud rate - try different values
- Multimeter protocol not supported - contact developer with raw data log
- Electrical interference - move away from power sources

## Advanced Testing

### Logging Raw Data for Debugging
```bash
python log_raw_data.py

# This will log binary data to help debug parsing issues
```

### Custom Baud Rate Test
```bash
python -m src.interfaces.cli --usb CCTV-PSU-24W-V1 --baud 9600

# Or test all baud rates
python test_baud_rates.py
```

## Safety Precautions

1. **High Voltage**: The primary side operates at 310V DC - always disconnect AC power before measuring.
2. **Capacitor Discharge**: Capacitors may retain charge even after power is disconnected - discharge properly.
3. **Insulation**: Use insulated test leads and ensure your body is insulated from ground.
4. **Safety Gear**: Wear appropriate PPE including safety glasses and insulated gloves.

## Results Interpretation

### Normal Operation
```
All readings within specified ranges
```
**Result**: No fault detected. Equipment is operating normally.

### Fault Detection
```
Output rail TP2: 0.5V (expected 11.4-12.6V)
Feedback ref TP3: 0.0V (expected 2.4-2.6V)
```
**Result**: Output Rail Collapse fault detected.

## Next Steps

1. If you encounter any issues, check the troubleshooting guide
2. Collect all measurements and review the diagnosis
3. Follow recommended recovery steps
4. Retest after repairs

## Technical Support

If you need assistance:
1. Run `python test_usb_multimeter.py` and save the output
2. Run `python log_raw_data.py` and save the raw data log
3. Contact technical support with these logs and a description of the issue
