# Knowledge Base Documentation

This folder contains technical documentation for the AI Agent's RAG (Retrieval Augmented Generation) system.

## How to Add Documentation

1. **Supported Formats**: `.md`, `.txt`, `.pdf` (text extraction)

2. **Document Structure Best Practices**:
   - Use clear headers and sections
   - Include equipment model in filename or content
   - Structure with: Symptoms, Causes, Test Procedures, Resolution

3. **Example Document Structure**:
   ```markdown
   # Equipment Model: CCTV-PSU-24W-V1
   
   ## Issue: Output Voltage Collapse
   
   ### Symptoms
   - Output reads 12V instead of 24V
   - LED indicator dim
   
   ### Root Causes
   1. Failed bridge rectifier (70% probability)
   2. Shorted filter capacitor (20% probability)
   
   ### Test Procedure
   1. Measure voltage at TP2
   2. Check diode forward voltage
   
   ### Resolution
   Replace bridge rectifier D1-D4
   ```

4. **After Adding Documents**:
   Run the ingestion script to update the vector database:
   ```bash
   python scripts/ingest_knowledge.py
   ```

## Folder Structure

```
data/knowledge/
├── equipment/          # Equipment-specific documentation
│   ├── cctv-psu/       # CCTV Power Supply docs
│   └── ...             # Other equipment
├── general/            # General troubleshooting guides
├── safety/             # Safety procedures
└── README.md           # This file
```

## Metadata Tags

When creating documents, consider including these metadata tags:
- `equipment_model`: The equipment model ID
- `component`: Affected component
- `fault_type`: Type of fault (electrical, mechanical, etc.)
- `severity`: low, medium, high, critical
- `revision_date`: Document version date
