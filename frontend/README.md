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
- Python 3.8+
- Databricks workspace with:
  - Unity Catalog enabled
  - Model serving endpoint deployed
  - Delta table with graph data

### Installation

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Configure environment variables:
```bash
export DATABRICKS_HOST="https://your-workspace.cloud.databricks.com"
export DATABRICKS_TOKEN="your-token"
export UC_CATALOG="main"
export UC_SCHEMA="default"
export UC_VOLUME="voice_data"
export MODEL_ENDPOINT="chatbot-endpoint"
export DELTA_TABLE="main.default.graph_data"
```

### Running Locally

```bash
streamlit run app.py
```

### Deploying to Databricks Apps

1. Upload the frontend directory to your Databricks workspace
2. Create a new Databricks App:
   - Go to Databricks Apps in your workspace
   - Click "Create App"
   - Select the app.py file
   - Configure environment variables in the app settings
3. Deploy the app

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

To enable in-browser audio recording, uncomment the optional dependencies in `requirements.txt`:
- `streamlit-webrtc` for WebRTC audio recording
- `audio-recorder-streamlit` for simple audio recording widget

### Adding Graph Visualization

For enhanced graph visualization, uncomment these optional dependencies:
- `streamlit-agraph` for network graphs
- `pyvis` for interactive network visualizations

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
