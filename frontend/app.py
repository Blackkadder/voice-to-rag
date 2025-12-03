"""
Voice-to-RAG Frontend Application

This Streamlit application provides:
1. Voice recording and upload to Databricks Unity Catalog volume
2. Chat interface backed by Databricks model serving endpoint
3. Interactive graph visualization from Databricks Delta table
"""

import streamlit as st
import os
import io
from datetime import datetime

from databricks.sdk import WorkspaceClient

# Initialize Databricks WorkspaceClient
# Auto-authenticates when running on Databricks Apps
# For local development, set DATABRICKS_HOST and DATABRICKS_TOKEN env vars
try:
    w = WorkspaceClient()
    databricks_connected = True
except Exception as e:
    w = None
    databricks_connected = False

# Configure page
st.set_page_config(
    page_title="Voice-to-RAG",
    page_icon="🎤",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Initialize session state
if 'messages' not in st.session_state:
    st.session_state.messages = []
if 'recordings' not in st.session_state:
    st.session_state.recordings = []

# Sidebar for configuration
with st.sidebar:
    st.title("⚙️ Configuration")
    
    st.subheader("Unity Catalog Settings")
    uc_catalog = st.text_input("Catalog", value=os.getenv("UC_CATALOG", "main"))
    uc_schema = st.text_input("Schema", value=os.getenv("UC_SCHEMA", "default"))
    uc_volume = st.text_input("Volume", value=os.getenv("UC_VOLUME", "voice_data"))
    
    st.subheader("Model Serving Settings")
    model_endpoint = st.text_input(
        "Model Endpoint", 
        value=os.getenv("MODEL_ENDPOINT", "chatbot-endpoint")
    )
    
    st.subheader("Graph Data Settings")
    delta_table = st.text_input(
        "Delta Table", 
        value=os.getenv("DELTA_TABLE", "main.default.graph_data")
    )

# Main application tabs
tab1, tab2, tab3 = st.tabs(["🎤 Voice Recording", "💬 Chat Interface", "📊 Graph Visualization"])

# Tab 1: Voice Recording and Upload
with tab1:
    st.header("Voice Recording & Upload")
    st.markdown("Record or upload voice data to Databricks Unity Catalog volume")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Upload Audio")
        
        # Show connection status
        if databricks_connected:
            st.success("✅ Connected to Databricks")
        else:
            st.warning("⚠️ Not connected to Databricks. Set DATABRICKS_HOST and DATABRICKS_TOKEN environment variables.")
        
        # File uploader for audio files
        audio_value = st.file_uploader(
            "Select an audio file to upload",
            type=["wav", "mp3", "m4a", "ogg", "webm"],
            key="audio_upload"
        )
        
        if audio_value is not None:
            # Preview the audio
            st.audio(audio_value)
            
            # Show file info
            st.caption(f"📄 **File:** {audio_value.name} | **Size:** {audio_value.size:,} bytes")
            
            upload_button = st.button("📤 Upload to Unity Catalog", key="upload_audio")
            
            if upload_button:
                if not databricks_connected:
                    st.error("❌ Cannot upload: Not connected to Databricks")
                else:
                    try:
                        with st.spinner("Uploading to Unity Catalog..."):
                            # Read file bytes and wrap in BytesIO
                            file_bytes = audio_value.read()
                            binary_data = io.BytesIO(file_bytes)
                            
                            # Generate unique filename with timestamp
                            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                            file_extension = audio_value.name.split('.')[-1]
                            filename = f"recording_{timestamp}.{file_extension}"
                            
                            # Construct Unity Catalog volume path
                            volume_file_path = f"/Volumes/{uc_catalog}/{uc_schema}/{uc_volume}/{filename}"
                            
                            # Upload using Databricks SDK
                            w.files.upload(volume_file_path, binary_data, overwrite=True)
                            
                            # Track uploaded recording in session state
                            st.session_state.recordings.append({
                                "filename": filename,
                                "path": volume_file_path,
                                "timestamp": timestamp,
                                "size": len(file_bytes),
                                "original_name": audio_value.name
                            })
                            
                            st.success(f"✅ Uploaded to: `{volume_file_path}`")
                            
                    except Exception as e:
                        st.error(f"❌ Upload failed: {str(e)}")
    
    with col2:
        st.subheader("Uploaded Recordings")
        
        if st.session_state.recordings:
            for idx, recording in enumerate(st.session_state.recordings):
                with st.expander(f"📁 {recording['filename']}", expanded=(idx == len(st.session_state.recordings) - 1)):
                    st.write(f"**Original Name:** {recording.get('original_name', 'N/A')}")
                    st.write(f"**Volume Path:** `{recording['path']}`")
                    st.write(f"**Uploaded:** {recording['timestamp']}")
                    st.write(f"**Size:** {recording['size']:,} bytes")
            
            # Clear recordings button
            if st.button("🗑️ Clear Upload History"):
                st.session_state.recordings = []
                st.rerun()
        else:
            st.info("No recordings uploaded yet")

# Tab 2: Chat Interface
with tab2:
    st.header("Chat Interface")
    st.markdown("Chat with the RAG system backed by Databricks model serving")
    
    # Display chat messages
    chat_container = st.container()
    with chat_container:
        for message in st.session_state.messages:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])
    
    # Chat input
    if prompt := st.chat_input("Ask a question about your voice data..."):
        # Add user message to chat history
        st.session_state.messages.append({"role": "user", "content": prompt})
        
        # Display user message
        with st.chat_message("user"):
            st.markdown(prompt)
        
        # Get bot response
        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                try:
                    # In production, call Databricks model serving endpoint
                    # from databricks.sdk import WorkspaceClient
                    # w = WorkspaceClient()
                    # response = w.serving_endpoints.query(
                    #     name=model_endpoint,
                    #     inputs=[{"query": prompt}]
                    # )
                    
                    # Simulated response
                    response_text = f"This is a simulated response to: '{prompt}'. In production, this would query the Databricks model serving endpoint '{model_endpoint}'."
                    
                    st.markdown(response_text)
                    st.session_state.messages.append({
                        "role": "assistant", 
                        "content": response_text
                    })
                    
                except Exception as e:
                    error_msg = f"Error querying model: {str(e)}"
                    st.error(error_msg)
                    st.session_state.messages.append({
                        "role": "assistant",
                        "content": error_msg
                    })
    
    # Clear chat button
    if st.button("Clear Chat History"):
        st.session_state.messages = []
        st.rerun()

# Tab 3: Graph Visualization
with tab3:
    st.header("Graph Visualization")
    st.markdown("Interactive visualization of graph data from Databricks Delta table")
    
    col1, col2 = st.columns([3, 1])
    
    with col2:
        st.subheader("Settings")
        layout_type = st.selectbox(
            "Layout",
            ["force", "circular", "hierarchical", "random"],
            index=0
        )
        
        show_labels = st.checkbox("Show Labels", value=True)
        show_edges = st.checkbox("Show Edges", value=True)
        
        refresh_button = st.button("🔄 Refresh Data")
    
    with col1:
        st.subheader(f"Graph from {delta_table}")
        
        try:
            # In production, query Delta table from Databricks
            # from databricks.sdk import WorkspaceClient
            # w = WorkspaceClient()
            # df = spark.table(delta_table).toPandas()
            
            # Simulated graph data
            graph_data = {
                "nodes": [
                    {"id": "1", "label": "Node 1", "group": "A"},
                    {"id": "2", "label": "Node 2", "group": "A"},
                    {"id": "3", "label": "Node 3", "group": "B"},
                    {"id": "4", "label": "Node 4", "group": "B"},
                    {"id": "5", "label": "Node 5", "group": "C"},
                ],
                "edges": [
                    {"from": "1", "to": "2"},
                    {"from": "1", "to": "3"},
                    {"from": "2", "to": "4"},
                    {"from": "3", "to": "4"},
                    {"from": "4", "to": "5"},
                ]
            }
            
            # Display graph using streamlit-agraph or pyvis
            st.info("📊 Graph visualization placeholder")
            st.json(graph_data)
            
            # In production, use a graph visualization library
            # from streamlit_agraph import agraph, Node, Edge, Config
            # nodes = [Node(id=n["id"], label=n["label"], size=25) for n in graph_data["nodes"]]
            # edges = [Edge(source=e["from"], target=e["to"]) for e in graph_data["edges"]]
            # config = Config(width=750, height=600, directed=True)
            # agraph(nodes=nodes, edges=edges, config=config)
            
            st.markdown("**Graph Statistics:**")
            metrics_cols = st.columns(3)
            metrics_cols[0].metric("Nodes", len(graph_data["nodes"]))
            metrics_cols[1].metric("Edges", len(graph_data["edges"]))
            metrics_cols[2].metric("Density", "0.40")
            
        except Exception as e:
            st.error(f"Error loading graph data: {str(e)}")

# Footer
st.markdown("---")
st.markdown(
    "**Voice-to-RAG** | Powered by Databricks | "
    "[Documentation](https://github.com/Blackkadder/voice-to-rag)"
)
