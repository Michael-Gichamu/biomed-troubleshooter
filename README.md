# Biomedical Equipment Troubleshooting Agent

<div align="center">

**LangGraph-powered AI agent for biomedical equipment troubleshooting**

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![LangGraph](https://img.shields.io/badge/LangGraph-0.0.20+-green.svg)](https://langchain.com/)

</div>

---

## Features

- 🤖 **AI-Powered Diagnostics**: LangGraph-based workflow with LLM reasoning
- 🔍 **RAG Knowledge Base**: ChromaDB vector database for equipment documentation
- 📡 **ESP32 Integration**: Real-time signals via MQTT protocol
- 🎭 **Mock Mode**: Built-in simulation scenarios for testing/demo
- 📊 **LangSmith Tracing**: Full observability of agent behavior
- 🔄 **Mode Toggle**: Switch between mock and live modes instantly

---

## Quick Start

### Prerequisites

| Tool | Installation |
|------|--------------|
| **Python 3.10+** | https://python.org |
| **Docker Desktop** | https://docs.docker.com/desktop/ |
| **Git** | https://git-scm.com/ |

### 1. Clone and Setup

```bash
# Clone the repository
git clone https://github.com/Michael-Gichamu/biomed-troubleshooter.git
cd biomed-troubleshooter

# Copy environment file
cp .env.example .env
```

### 2. Start Infrastructure

```bash
# Windows
.\start-services.ps1

# Linux/macOS
chmod +x start-services.sh
./start-services.sh
```

This starts:
- **ChromaDB**: http://localhost:8000 (vector database)
- **Mosquitto**: localhost:1883 (MQTT broker)

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Run Demo

```bash
# Run mock mode with CCTV PSU output rail collapse scenario
python -m src.interfaces.cli --mock
```

Expected output:
```
============================================================
  MOCK MODE - Biomedical Troubleshooting Agent
============================================================
Mode: mock
Scenario: cctv-psu-output-rail

Generated Signals:
  TP1: 230.0 V (voltage)
  TP2: 12.3 V (voltage) ⚠️
  TP3: 0.52 A (current)

Diagnosis Result:
  Primary Cause: Output rail collapsed
  Confidence: high
  Severity: critical
```

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     Biomedical Troubleshooting Agent              │
├─────────────────────────────────────────────────────────────────┤
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────────────┐ │
│  │ Mock Mode   │    │ Live Mode   │    │ LangGraph Workflow  │ │
│  │ (Simulator) │    │ (MQTT/ESP32)│    │ (Diagnostic Logic)  │ │
│  └──────┬──────┘    └──────┬──────┘    └──────────┬──────────┘ │
│         │                  │                       │            │
│         └──────────────────┼───────────────────────┘            │
│                            ▼                                    │
│                 ┌─────────────────────┐                        │
│                 │    Mode Router      │                        │
│                 │  (Switch Handler)   │                        │
│                 └──────────┬──────────┘                        │
│                            ▼                                    │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                    ChromaDB                             │   │
│  │              (RAG Knowledge Base)                        │   │
│  └─────────────────────────────────────────────────────────┘   │
│                            │                                    │
│                            ▼                                    │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                    LangSmith                            │   │
│  │              (Observability & Tracing)                  │   │
│  └─────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

---

## Usage Modes

### Mock Mode (Default)

Run with simulated signals:

```bash
# Default scenario (output rail collapse)
python -m src.interfaces.cli --mock

# Specific scenario
python -m src.interfaces.cli --mock cctv-psu-overvoltage
python -m src.interfaces.cli --mock cctv-psu-ripple
python -m src.interfaces.cli --mock cctv-psu-thermal

# List all scenarios
python -m src.interfaces.cli --status
```

#### Available Scenarios

| Scenario | Description | Difficulty |
|----------|-------------|------------|
| `cctv-psu-output-rail` | Output voltage collapsed to 12V | Easy |
| `cctv-psu-overvoltage` | Output exceeded 24V spec | Medium |
| `cctv-psu-ripple` | Excessive ripple voltage | Medium |
| `cctv-psu-thermal` | Thermal shutdown condition | Easy |

### Live Mode (ESP32 Integration)

Run with real-time signals from ESP32:

```bash
# Set mode to live
export APP_MODE=live

# Listen for equipment signals
python -m src.interfaces.cli --live CCTV-PSU-24W-V1
```

#### ESP32 MQTT Message Format

```json
{
  "timestamp": "2026-02-04T14:30:00Z",
  "equipment_id": "CCTV-PSU-24W-V1",
  "signals": [
    {
      "test_point": "TP2",
      "value": 12.3,
      "unit": "V",
      "measurement_type": "voltage"
    }
  ]
}
```

### Interactive Mode

```bash
python -m src.interfaces.cli --interactive
```

---

## Configuration

### Environment Variables

Create a `.env` file from the example:

```env
# Application Mode
APP_MODE=mock  # or 'live'

# Mock Settings
MOCK_SCENARIO=cctv-psu-output-rail

# LLM (Free - Groq)
GROQ_API_KEY=your-groq-api-key
LLM_PROVIDER=groq
LLM_MODEL=llama-3.3-70b-versatile

# Embeddings (Local - Free)
EMBEDDING_PROVIDER=local
EMBEDDING_MODEL=all-MiniLM-L6-v2

# ChromaDB
CHROMADB_HOST=localhost
CHROMADB_PORT=8000

# LangSmith (Free tier)
LANGCHAIN_API_KEY=your-langsmith-api-key
LANGCHAIN_PROJECT=biomed-troubleshooter
LANGCHAIN_TRACING=true
```

### Getting Free API Keys

| Service | Purpose | Link |
|---------|---------|------|
| **Groq** | LLM Reasoning | https://console.groq.com |
| **LangSmith** | Tracing/Debugging | https://smith.langchain.com |

---

## Project Structure

```
biomed-troubleshooter/
├── docker-compose.yml          # Docker services (ChromaDB, Mosquitto)
├── start-services.ps1          # Windows startup script
├── start-services.sh          # Linux/macOS startup script
├── requirements.txt            # Python dependencies
├── .env.example               # Environment template
│
├── data/
│   ├── mock_signals/          # Mock scenario files
│   │   ├── cctv-psu-output-rail.json
│   │   ├── cctv-psu-overvoltage.json
│   │   ├── cctv-psu-ripple.json
│   │   └── cctv-psu-thermal.json
│   └── equipment/             # Equipment configurations
│       └── cctv-psu-24w-v1.yaml
│
├── mosquitto/
│   └── config/
│       └── mosquitto.conf     # MQTT broker config
│
├── src/
│   ├── application/
│   │   └── agent.py           # LangGraph workflow
│   ├── domain/
│   │   └── models.py          # Data models
│   ├── infrastructure/
│   │   ├── chromadb_client.py # Vector DB client
│   │   ├── config.py          # Configuration loader
│   │   ├── langsmith_client.py # Observability
│   │   ├── mode_config.py     # Mode configuration
│   │   ├── mqtt_client.py     # MQTT client
│   │   └── mock_generator.py   # Signal generator
│   └── interfaces/
│       ├── cli.py             # Command-line interface
│       └── mode_router.py      # Mode switching
│
└── docs/
    ├── agent_scope.md         # Agent responsibilities
    ├── agent_io_contract.md   # I/O specifications
    ├── signal_schema.md       # Signal format
    └── langgraph_design.md    # Workflow architecture
```

---

## Docker Services

### Start/Stop Services

```bash
# Windows
.\start-services.ps1          # Start
.\start-services.ps1 -stop    # Stop
.\start-services.ps1 -status  # Status

# Linux/macOS
./start-services.sh up        # Start
./start-services.sh stop     # Stop
./start-services.sh status   # Status
```

### Manual Docker Commands

```bash
# Start ChromaDB
docker run -d -p 8000:8000 --name biomed-chromadb chromadb/chroma

# Start Mosquitto
docker run -d -p 1883:1883 --name biomed-mosquitto eclipse-mosquitto

# Stop all
docker stop biomed-chromadb biomed-mosquitto
docker rm biomed-chromadb biomed-mosquitto
```

---

## Testing

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=src

# Run specific test
pytest tests/test_signal_processing.py -v
```

---

## LangSmith Dashboard

To visualize agent behavior:

1. Sign up at https://smith.langchain.com
2. Create API key
3. Add to `.env`: `LANGCHAIN_API_KEY=your-key`
4. Run agent and view traces at https://smith.langchain.com

---

## ESP32 Integration Guide

### Hardware Setup

1. ESP32 development board
2. Voltage divider circuit for analog measurements
3. WiFi connection

### Code Example

```cpp
#include <WiFi.h>
#include <PubSubClient.h>

const char* mqtt_server = "your-laptop-ip";
const int mqtt_port = 1883;
const char* topic = "biomed/signals/CCTV-PSU-24W-V1";

void publishSignals(float voltage, float current) {
    StaticJsonDocument<256> doc;
    doc["equipment_id"] = "CCTV-PSU-24W-V1";
    doc["signals"][0]["test_point"] = "TP2";
    doc["signals"][0]["value"] = voltage;
    doc["signals"][0]["unit"] = "V";
    // ... publish to MQTT
}
```

---

## Troubleshooting

### Common Issues

| Issue | Solution |
|-------|----------|
| ChromaDB not responding | Run `docker start biomed-chromadb` |
| MQTT connection failed | Check broker IP in `.env` |
| LangSmith not working | Verify API key in `.env` |
| LLM errors | Check Groq API key |

### Logs

```bash
# ChromaDB logs
docker logs biomed-chromadb

# Mosquitto logs
docker logs biomed-mosquitto
```

---

## Team Presentation Mode

For easy demo on any team member's laptop:

```bash
# 1. Clone
git clone https://github.com/Michael-Gichamu/biomed-troubleshooter.git

# 2. Setup
cp .env.example .env
./start-services.sh

# 3. Run demo
python -m src.interfaces.cli --mock
```

---

## License

MIT License - See LICENSE file for details.

---

## Author

**Michael Gichamu**
- GitHub: [@Michael-Gichamu](https://github.com/Michael-Gichamu)
- Project: https://github.com/Michael-Gichamu/biomed-troubleshooter
