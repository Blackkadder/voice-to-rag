# Frontend - Voice-to-RAG Streamlit Application

This is a standalone Streamlit application designed to be hosted on Databricks Apps.

## Features

### 1. Voice Recording & Upload
- Record or upload audio files
- Upload voice data to Databricks Unity Catalog volumes
- Track uploaded recordings with metadata

### 2. Chat Interface
- Interactive chat interface backed by Databricks model serving endpoint
- Query the RAG system about your voice data
- Real-time responses from the AI model

### 3. Graph Visualization
- Display graph data from Databricks Delta tables
- Interactive graph visualization with customizable layouts
- Graph statistics and metrics

## Setup

### Prerequisites
- Python 3.10+
- [uv](https://docs.astral.sh/uv/) (recommended) or pip
- Databricks workspace with:
  - Unity Catalog enabled
  - Model serving endpoint deployed
  - Delta table with graph data

### Installation with uv (Recommended)

1. Install uv if you haven't already:
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

2. Create virtual environment and install dependencies:
```bash
uv sync
```

3. Install optional dependencies for enhanced features:
```bash
# For graph visualization
uv sync --extra graph

# For audio recording
uv sync --extra audio

# For all optional features
uv sync --all-extras
```

4. Configure environment variables:
```bash
export DATABRICKS_HOST="https://your-workspace.cloud.databricks.com"
export DATABRICKS_TOKEN="your-token"
export UC_CATALOG="voice_rag"
export UC_SCHEMA="default"
export UC_VOLUME="voice_data"
export MODEL_ENDPOINT="chatbot-endpoint"
export DELTA_TABLE="voice_rag.default.graph_data"
```

### Alternative: Installation with pip

```bash
pip install -r requirements.txt
```

### Running Locally

```bash
# With uv
uv run streamlit run app.py

# Or activate the virtual environment first
source .venv/bin/activate
streamlit run app.py
```

### Deploying to Databricks Apps

This app includes an `app.yaml` configuration file for Databricks Apps deployment.

1. **Set up secrets in Databricks Apps**:
   
   Before deploying, configure the required environment variables as secrets in your Databricks Apps settings:
   
   | Secret Name | Description |
   |-------------|-------------|
   | `UC_CATALOG` | Unity Catalog catalog name |
   | `UC_SCHEMA` | Unity Catalog schema name |
   | `UC_VOLUME` | Unity Catalog volume name for voice data |
   | `MODEL_ENDPOINT` | Model serving endpoint name |
   | `DELTA_TABLE` | Full path to Delta table (e.g., `main.default.graph_data`) |

2. **Deploy the app**:
   - Upload the frontend directory to your Databricks workspace
   - Go to Databricks Apps in your workspace
   - Click "Create App"
   - Point to the directory containing `app.yaml`
   - The app will automatically use the configuration from `app.yaml`

3. **Permissions required for the app service principal**:
   - `USE CATALOG` on the Unity Catalog catalog
   - `USE SCHEMA` on the schema
   - `READ VOLUME` and `WRITE VOLUME` on the volume
   - Access to the model serving endpoint

The `app.yaml` configures:
- The Streamlit command to run (`streamlit run app.py --server.port 8000`)
- Environment variables referenced from Databricks secrets

## Configuration

All configuration can be done through:
- Environment variables (recommended for production)
- The sidebar in the Streamlit UI (for development/testing)

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `DATABRICKS_HOST` | Databricks workspace URL | - |
| `DATABRICKS_TOKEN` | Databricks personal access token | - |
| `UC_CATALOG` | Unity Catalog catalog name | `main` |
| `UC_SCHEMA` | Unity Catalog schema name | `default` |
| `UC_VOLUME` | Unity Catalog volume name | `voice_data` |
| `MODEL_ENDPOINT` | Model serving endpoint name | `chatbot-endpoint` |
| `DELTA_TABLE` | Delta table with graph data | `main.default.graph_data` |

## Usage

### Recording and Uploading Voice Data

1. Navigate to the "Voice Recording" tab
2. Upload an audio file (WAV, MP3, M4A, or OGG)
3. Click "Upload to Unity Catalog"
4. The file will be stored in the configured Unity Catalog volume

### Chatting with the RAG System

1. Navigate to the "Chat Interface" tab
2. Type your question in the chat input
3. The system will query the Databricks model serving endpoint
4. Responses will appear in the chat interface

### Viewing Graph Data

1. Navigate to the "Graph Visualization" tab
2. Select layout and display options
3. Click "Refresh Data" to load latest graph data from Delta table
4. View interactive graph and statistics

## Development

### Adding Audio Recording Support

To enable in-browser audio recording, install the audio extras:
```bash
uv sync --extra audio
```

This includes:
- `streamlit-webrtc` for WebRTC audio recording
- `audio-recorder-streamlit` for simple audio recording widget

### Adding Graph Visualization

For enhanced graph visualization, install the graph extras:
```bash
uv sync --extra graph
```

This includes:
- `streamlit-agraph` for network graphs
- `pyvis` for interactive network visualizations

### Development Setup

Install all dependencies including dev tools:
```bash
uv sync --all-extras
```

Run linting:
```bash
uv run ruff check .
uv run ruff format .
```

## Troubleshooting

### Connection Issues
- Ensure `DATABRICKS_HOST` and `DATABRICKS_TOKEN` are correctly set
- Verify your token has appropriate permissions for Unity Catalog and model serving

### Upload Failures
- Check that the Unity Catalog volume exists and is accessible
- Verify the catalog/schema/volume path is correct

### Model Query Failures
- Ensure the model serving endpoint is deployed and running
- Verify the endpoint name matches your configuration

## Security Notes

- Never commit `DATABRICKS_TOKEN` to version control
- Use Databricks secrets for production deployments
- Restrict Unity Catalog volume permissions appropriately
