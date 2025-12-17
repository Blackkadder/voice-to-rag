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
from dotenv import load_dotenv

from databricks.sdk import WorkspaceClient
from audio_recorder_streamlit import audio_recorder

# Load environment variables from .env file (for local development)
load_dotenv()

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
    initial_sidebar_state="expanded",
    menu_items={
        'Get Help': None,
        'Report a bug': None,
        'About': "Voice-to-RAG: Transform voice data into intelligent RAG-powered insights"
    }
)

# Custom CSS for better styling
st.markdown("""
<style>
    /* Main styling */
    .main .block-container {
        padding-top: 2rem;
        padding-bottom: 2rem;
    }
    
    /* Header styling */
    h1 {
        color: #1f77b4;
        border-bottom: 3px solid #1f77b4;
        padding-bottom: 0.5rem;
    }
    
    h2 {
        color: #2c3e50;
        margin-top: 1.5rem;
    }
    
    h3 {
        color: #34495e;
    }
    
    /* Card-like containers */
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
    }
    
    .stTabs [data-baseweb="tab"] {
        padding: 10px 20px;
        border-radius: 8px 8px 0 0;
    }
    
    /* Sidebar styling */
    .css-1d391kg {
        padding-top: 2rem;
    }
    
    /* Metrics styling */
    [data-testid="stMetricValue"] {
        font-size: 2rem;
    }
    
    /* Button styling */
    .stButton > button {
        border-radius: 8px;
        border: none;
        padding: 0.5rem 1.5rem;
        font-weight: 500;
        transition: all 0.3s;
    }
    
    .stButton > button:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 8px rgba(0,0,0,0.1);
    }
    
    /* Success/Error messages */
    .stSuccess {
        border-radius: 8px;
        padding: 1rem;
    }
    
    .stError {
        border-radius: 8px;
        padding: 1rem;
    }
    
    /* Info boxes */
    .stInfo {
        border-radius: 8px;
        padding: 1rem;
    }
    
    /* Expander styling */
    .streamlit-expanderHeader {
        font-weight: 500;
    }
    
    /* Chat message styling */
    .stChatMessage {
        padding: 1rem;
        border-radius: 12px;
        margin-bottom: 1rem;
    }
    
    /* File uploader styling */
    .uploadedFile {
        border-radius: 8px;
        padding: 1rem;
        background-color: #f8f9fa;
        margin: 0.5rem 0;
    }
    
    /* Footer styling */
    footer {
        visibility: hidden;
    }
    
    /* Custom divider */
    hr {
        margin: 2rem 0;
        border: none;
        border-top: 2px solid #e0e0e0;
    }
    
    /* Connection status badge */
    .connection-badge {
        padding: 0.5rem 1rem;
        border-radius: 20px;
        display: inline-block;
        font-weight: 500;
        margin-bottom: 1rem;
    }
</style>
""", unsafe_allow_html=True)

# Initialize session state
if 'messages' not in st.session_state:
    st.session_state.messages = []
if 'recordings' not in st.session_state:
    st.session_state.recordings = []

# Sidebar for configuration
with st.sidebar:
    st.markdown("## 🎤 Voice-to-RAG")
    st.markdown("---")
    
    # Connection status
    if databricks_connected:
        st.success("🟢 **Connected to Databricks**")
    else:
        st.warning("🟡 **Not Connected**")
        st.caption("Set DATABRICKS_HOST and DATABRICKS_TOKEN in .env")
    
    st.markdown("---")
    
    with st.expander("📦 Unity Catalog Settings", expanded=True):
        uc_catalog = st.text_input("Catalog", value=os.getenv("UC_CATALOG", "voice_graph_rag"), key="uc_catalog")
        uc_schema = st.text_input("Schema", value=os.getenv("UC_SCHEMA", "default"), key="uc_schema")
        uc_volume = st.text_input("Volume", value=os.getenv("UC_VOLUME", "voice_data"), key="uc_volume")
    
    with st.expander("🤖 Model Serving Settings"):
        model_endpoint = st.text_input(
            "Model Endpoint", 
            value=os.getenv("MODEL_ENDPOINT", "chatbot-endpoint"),
            key="model_endpoint"
        )
    
    with st.expander("📊 Graph Data Settings"):
        delta_table = st.text_input(
            "Delta Table", 
            value=os.getenv("DELTA_TABLE", "voice_graph_rag.default.graph_data"),
            key="delta_table"
        )
    
    st.markdown("---")
    st.caption("💡 Configure settings above to customize your workspace")

# Main application tabs
tab1, tab2, tab3 = st.tabs(["🎤 Voice Recording", "💬 Chat Interface", "📊 Graph Visualization"])

# Tab 1: Voice Recording and Upload
with tab1:
    st.markdown("## 🎙️ Voice Recording & Upload")
    st.markdown("Record or upload voice data to Databricks Unity Catalog volume")
    st.markdown("---")
    
    col1, col2 = st.columns([1.2, 1], gap="large")
    
    with col1:
        # Audio recorder section
        st.markdown("### 🎤 Record Audio")
        st.caption("Click the microphone button below to start recording")
        
        with st.container():
            audio_bytes = audio_recorder(
                text="🎙️ Click to Record",
                recording_color="#e74c3c",
                neutral_color="#1f77b4",
                icon_name="microphone",
                icon_size="2x",
            )
        
        # Handle recorded audio
        if audio_bytes:
            st.markdown("---")
            st.markdown("**🎵 Recording Preview**")
            st.audio(audio_bytes, format="audio/wav")
            
            # Store recorded audio in session state for upload
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"recording_{timestamp}.wav"
            st.session_state.current_recording = {
                "audio_bytes": audio_bytes,
                "filename": filename,
                "size": len(audio_bytes)
            }
            
            # File info in a nice container
            with st.container():
                col_info1, col_info2 = st.columns(2)
                with col_info1:
                    st.metric("File Name", filename)
                with col_info2:
                    st.metric("Size", f"{len(audio_bytes):,} bytes")
            
            upload_recorded_button = st.button("📤 Upload Recording to Unity Catalog", 
                                                key="upload_recorded",
                                                type="primary",
                                                use_container_width=True)
            
            if upload_recorded_button:
                if not databricks_connected:
                    st.error("❌ Cannot upload: Not connected to Databricks")
                else:
                    try:
                        with st.spinner("Uploading recording to Unity Catalog..."):
                            # Wrap recorded audio bytes in BytesIO
                            binary_data = io.BytesIO(audio_bytes)
                            
                            # Construct Unity Catalog volume path
                            volume_file_path = f"/Volumes/{uc_catalog}/{uc_schema}/{uc_volume}/{filename}"
                            
                            # Upload using Databricks SDK
                            w.files.upload(volume_file_path, binary_data, overwrite=True)
                            
                            # Track uploaded recording in session state
                            st.session_state.recordings.append({
                                "filename": filename,
                                "path": volume_file_path,
                                "timestamp": timestamp,
                                "size": len(audio_bytes),
                                "original_name": "Recorded Audio"
                            })
                            
                            # Clear current recording
                            if "current_recording" in st.session_state:
                                del st.session_state.current_recording
                            
                            st.success(f"✅ Uploaded to: `{volume_file_path}`")
                            st.rerun()
                            
                    except Exception as e:
                        st.error(f"❌ Upload failed: {str(e)}")
        
        st.markdown("---")
        st.markdown("### 📁 Or Upload Audio File")
        st.caption("Supported formats: WAV, MP3, M4A, OGG, WEBM")
        
        # File uploader for audio files
        audio_value = st.file_uploader(
            "Choose an audio file",
            type=["wav", "mp3", "m4a", "ogg", "webm"],
            key="audio_upload",
            label_visibility="collapsed"
        )
        
        if audio_value is not None:
            st.markdown("---")
            st.markdown("**🎵 Audio Preview**")
            st.audio(audio_value)
            
            # File info in a nice container
            with st.container():
                col_info1, col_info2 = st.columns(2)
                with col_info1:
                    st.metric("File Name", audio_value.name)
                with col_info2:
                    st.metric("Size", f"{audio_value.size:,} bytes")
            
            upload_button = st.button("📤 Upload File to Unity Catalog", 
                                     key="upload_audio",
                                     type="primary",
                                     use_container_width=True)
            
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
                            st.rerun()
                            
                    except Exception as e:
                        st.error(f"❌ Upload failed: {str(e)}")
    
    with col2:
        st.markdown("### 📚 Uploaded Recordings")
        
        if st.session_state.recordings:
            st.metric("Total Recordings", len(st.session_state.recordings))
            st.markdown("---")
            
            for idx, recording in enumerate(st.session_state.recordings):
                with st.expander(f"📁 {recording['filename']}", expanded=(idx == len(st.session_state.recordings) - 1)):
                    col_rec1, col_rec2 = st.columns(2)
                    with col_rec1:
                        st.caption("**Original Name**")
                        st.write(recording.get('original_name', 'N/A'))
                    with col_rec2:
                        st.caption("**Size**")
                        st.write(f"{recording['size']:,} bytes")
                    
                    st.caption("**Volume Path**")
                    st.code(recording['path'], language=None)
                    
                    st.caption("**Uploaded**")
                    st.write(recording['timestamp'])
            
            st.markdown("---")
            # Clear recordings button
            if st.button("🗑️ Clear Upload History", use_container_width=True):
                st.session_state.recordings = []
                st.rerun()
        else:
            st.info("📭 No recordings uploaded yet. Record or upload audio to get started!")

# Tab 2: Chat Interface
with tab2:
    st.markdown("## 💬 Chat Interface")
    st.markdown("Chat with the RAG system backed by Databricks model serving")
    st.markdown("---")
    
    # Display connection status
    if databricks_connected:
        st.success(f"🟢 Connected | Endpoint: `{model_endpoint}`")
    else:
        st.warning("🟡 Not connected to Databricks")
    
    st.markdown("---")
    
    # Display chat messages
    chat_container = st.container()
    with chat_container:
        if not st.session_state.messages:
            st.info("👋 Start a conversation! Ask questions about your voice data.")
        else:
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
    if st.session_state.messages:
        st.markdown("---")
        col_clear1, col_clear2, col_clear3 = st.columns([1, 1, 1])
        with col_clear2:
            if st.button("🗑️ Clear Chat History", use_container_width=True):
                st.session_state.messages = []
                st.rerun()

# Tab 3: Graph Visualization
with tab3:
    st.markdown("## 📊 Graph Visualization")
    st.markdown("Interactive visualization of graph data from Databricks Delta table")
    st.markdown("---")
    
    col1, col2 = st.columns([3, 1], gap="large")
    
    with col2:
        st.markdown("### ⚙️ Settings")
        st.markdown("---")
        
        layout_type = st.selectbox(
            "Layout Type",
            ["force", "circular", "hierarchical", "random"],
            index=0,
            help="Choose the graph layout algorithm"
        )
        
        st.markdown("---")
        
        show_labels = st.checkbox("Show Labels", value=True)
        show_edges = st.checkbox("Show Edges", value=True)
        
        st.markdown("---")
        
        refresh_button = st.button("🔄 Refresh Data", use_container_width=True, type="primary")
    
    with col1:
        st.markdown(f"### 📈 Graph from `{delta_table}`")
        
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
            st.info("📊 Graph visualization placeholder - Install graph extras for interactive visualization")
            
            with st.expander("📋 View Graph Data (JSON)", expanded=False):
                st.json(graph_data)
            
            # In production, use a graph visualization library
            # from streamlit_agraph import agraph, Node, Edge, Config
            # nodes = [Node(id=n["id"], label=n["label"], size=25) for n in graph_data["nodes"]]
            # edges = [Edge(source=e["from"], target=e["to"]) for e in graph_data["edges"]]
            # config = Config(width=750, height=600, directed=True)
            # agraph(nodes=nodes, edges=edges, config=config)
            
            st.markdown("---")
            st.markdown("### 📊 Graph Statistics")
            metrics_cols = st.columns(3)
            metrics_cols[0].metric("Nodes", len(graph_data["nodes"]))
            metrics_cols[1].metric("Edges", len(graph_data["edges"]))
            metrics_cols[2].metric("Density", "0.40")
            
        except Exception as e:
            st.error(f"Error loading graph data: {str(e)}")

# Footer
st.markdown("---")
footer_col1, footer_col2, footer_col3 = st.columns(3)
with footer_col2:
    st.markdown(
        """
        <div style='text-align: center; color: #666; padding: 1rem;'>
            <strong>Voice-to-RAG</strong> | Powered by Databricks<br>
            <a href='https://github.com/Blackkadder/voice-to-rag' style='color: #1f77b4; text-decoration: none;'>📚 Documentation</a>
        </div>
        """,
        unsafe_allow_html=True
    )
