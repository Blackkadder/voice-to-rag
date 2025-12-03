# voice-to-rag

Full stack project to convert voice data to a (graph) RAG pipeline

## Project Structure

This repository contains two main components:

### Frontend

The `frontend/` directory contains a standalone Streamlit application designed to be hosted on Databricks Apps.

**Features:**
1. **Voice Recording & Upload** - Record or upload voice data and save it to Databricks Unity Catalog volumes
2. **Chat Interface** - Interactive chat backed by a Databricks model serving endpoint for querying the RAG system
3. **Graph Visualization** - Display and interact with graph data from Databricks Delta tables

**Tech Stack:** Streamlit, Databricks SDK, Python

See [frontend/README.md](frontend/README.md) for detailed documentation.

### Backend

The `backend/` directory contains configuration files that define parameters for the graph RAG pipeline.

**Features:**
- Comprehensive configuration system using Python dataclasses
- Support for Unity Catalog, audio processing, graph construction, retrieval, and Databricks service settings
- JSON/YAML configuration file support
- Environment variable overrides

**Tech Stack:** Python, Databricks SDK

See [backend/README.md](backend/README.md) for detailed documentation.

## Quick Start

### Frontend Setup

```bash
cd frontend
pip install -r requirements.txt

# Set environment variables
export DATABRICKS_HOST="https://your-workspace.cloud.databricks.com"
export DATABRICKS_TOKEN="your-token"
export UC_CATALOG="main"
export UC_SCHEMA="default"
export UC_VOLUME="voice_data"
export MODEL_ENDPOINT="chatbot-endpoint"
export DELTA_TABLE="main.default.graph_data"

# Run the application
streamlit run app.py
```

### Backend Configuration

```python
from backend.config import get_config

# Use default configuration
config = get_config()

# Or load from file
from backend.config import load_config_from_file
config = load_config_from_file("backend/config.example.json")

# Access configuration values
print(config.graph_rag.entity_extraction_model)
print(config.unity_catalog.volume_path)
```

## Architecture

```
voice-to-rag/
├── frontend/               # Streamlit application
│   ├── app.py             # Main application file
│   ├── requirements.txt   # Python dependencies
│   └── README.md          # Frontend documentation
│
├── backend/               # Configuration system
│   ├── config.py          # Configuration module
│   ├── config.example.json # Example configuration
│   ├── requirements.txt   # Python dependencies
│   └── README.md          # Backend documentation
│
└── README.md              # This file
```

## Workflow

1. **Voice Upload**: Users upload or record voice data through the Streamlit frontend
2. **Storage**: Audio files are stored in Databricks Unity Catalog volumes
3. **Processing**: Backend pipeline (configured via backend/config.py) processes audio:
   - Transcribes speech to text
   - Extracts entities and relationships
   - Builds knowledge graph
   - Generates embeddings
4. **Storage**: Graph data and embeddings are stored in Delta tables
5. **Retrieval**: Users query via chat interface
6. **Response**: System retrieves relevant context and generates responses
7. **Visualization**: Graph data is displayed interactively

## Prerequisites

- Python 3.8 or higher
- Databricks workspace with:
  - Unity Catalog enabled
  - Model serving endpoint deployed
  - Delta tables for storing graph data

## Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `DATABRICKS_HOST` | Databricks workspace URL | Yes |
| `DATABRICKS_TOKEN` | Personal access token | Yes |
| `UC_CATALOG` | Unity Catalog catalog name | No (default: main) |
| `UC_SCHEMA` | Unity Catalog schema name | No (default: default) |
| `UC_VOLUME` | Unity Catalog volume name | No (default: voice_data) |
| `MODEL_ENDPOINT` | Model serving endpoint name | No (default: chatbot-endpoint) |
| `DELTA_TABLE` | Delta table for graph data | No (default: main.default.graph_data) |

## Development

### Running Tests

```bash
# Frontend
cd frontend
pytest

# Backend
cd backend
pytest
```

### Code Style

This project follows PEP 8 style guidelines. Use tools like `black` and `flake8` for formatting and linting.

### Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## Deployment

### Deploying Frontend to Databricks Apps

1. Navigate to your Databricks workspace
2. Go to "Apps" section
3. Click "Create App"
4. Select `frontend/app.py`
5. Configure environment variables
6. Deploy

### Running Backend Pipeline

The backend configuration can be used in Databricks notebooks or jobs:

```python
# In a Databricks notebook
from backend.config import get_config

config = get_config()

# Use config in your pipeline
# ... your pipeline code ...
```

## Security

- Never commit `DATABRICKS_TOKEN` to version control
- Use Databricks secrets for production deployments
- Restrict Unity Catalog permissions appropriately
- Review and audit model serving endpoint access

## Troubleshooting

### Connection Issues
- Verify `DATABRICKS_HOST` and `DATABRICKS_TOKEN` are correct
- Check network connectivity to Databricks workspace
- Ensure token has necessary permissions

### Upload Failures
- Verify Unity Catalog volume exists
- Check volume permissions
- Ensure catalog/schema/volume path is correct

### Model Query Failures
- Confirm model serving endpoint is running
- Verify endpoint name matches configuration
- Check endpoint has sufficient capacity

## License

[Add your license here]

## Contact

[Add contact information]
