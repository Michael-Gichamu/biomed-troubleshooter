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
- 🔌 **USB Multimeter Integration**: Direct measurement from Mastech MS8250D (CP210x)
- 🎭 **Mock Mode**: Built-in simulation scenarios for testing/demo
- 📊 **LangSmith Tracing**: Full observability of agent behavior

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

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Run Demo

```bash
# Run mock mode with CCTV PSU output rail collapse scenario
python -m src.interfaces.cli --mock
```

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     Biomedical Troubleshooting Agent              │
├─────────────────────────────────────────────────────────────────┤
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────────────┐ │
│  │ Mock Mode   │    │ USB Mode    │    │ LangGraph Workflow  │ │
│  │ (Simulator) │    │ (Multimeter)│    │ (Diagnostic Logic)  │ │
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
```

### USB Mode (Real Hardware)

Run with real-time signals from Mastech MS8250D:

```bash
# Connect multimeter and run
python -m src.interfaces.cli --usb CCTV-PSU-24W-V1
```

---

## Configuration

### Environment Variables

Create a `.env` file from the example:

```env
# LLM (Groq)
GROQ_API_KEY=your-groq-api-key
LLM_PROVIDER=groq
LLM_MODEL=llama-3.3-70b-versatile

# ChromaDB
CHROMADB_HOST=localhost
CHROMADB_PORT=8000

# LangSmith
LANGCHAIN_API_KEY=your-langsmith-api-key
LANGCHAIN_PROJECT=biomed-troubleshooter
LANGCHAIN_TRACING=true
```

---

## Project Structure

```
biomed-troubleshooter/
├── docker-compose.yml          # Docker services (ChromaDB)
├── start-services.ps1          # Windows startup script
├── start-services.sh          # Linux/macOS startup script
├── requirements.txt            # Python dependencies
├── .env.example               # Environment template
│
├── data/
│   ├── mock_signals/          # Mock scenario files
│   └── equipment/             # Equipment configurations
│
├── src/
│   ├── studio/                # LangGraph Studio components
│   │   ├── conversational_agent.py
│   │   ├── tools.py
│   │   └── background_usb_reader.py
│   ├── infrastructure/
│   │   ├── usb_multimeter.py  # Mastech 8250D logic
│   │   ├── chromadb_client.py # Vector DB client
│   │   └── equipment_config.py # YAML loader
│   └── interfaces/
│       └── cli.py             # Command-line interface
└── docs/
    └── PROJECT_AI_DOCUMENTATION.md
```

---

## License

MIT License - See LICENSE file for details.

---

## Author

**Michael Gichamu**
- GitHub: [@Michael-Gichamu](https://github.com/Michael-Gichamu)
- Project: https://github.com/Michael-Gichamu/biomed-troubleshooter
