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
import re
from datetime import datetime
from dotenv import load_dotenv
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError

from databricks.sdk import WorkspaceClient
from audio_recorder_streamlit import audio_recorder

# Upload timeout in seconds
UPLOAD_TIMEOUT = 30

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

# Get UC settings from environment
UC_CATALOG = os.getenv("UC_CATALOG", "voice_rag")
UC_SCHEMA = os.getenv("UC_SCHEMA", "default")
UC_VOLUME = os.getenv("UC_VOLUME", "voice_data")
MODEL_ENDPOINT = os.getenv("MODEL_ENDPOINT", "chatbot-endpoint")
DELTA_TABLE = os.getenv("DELTA_TABLE", "voice_rag.default.graph_data")
DATABRICKS_HOST = os.getenv("DATABRICKS_HOST", "unknown")
# Configure page
st.set_page_config(
    page_title="Voice-to-RAG",
    page_icon="🎤",
    layout="wide",
    initial_sidebar_state="collapsed",
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
    
    /* Landing page styling */
    .landing-container {
        max-width: 600px;
        margin: 0 auto;
        padding: 2rem;
    }
    
    .session-card {
        padding: 1rem;
        border-radius: 8px;
        border: 1px solid #e0e0e0;
        margin: 0.5rem 0;
        cursor: pointer;
        transition: all 0.2s;
    }
    
    .session-card:hover {
        border-color: #1f77b4;
        background-color: #f8f9fa;
    }
</style>
""", unsafe_allow_html=True)

# Initialize session state
if 'messages' not in st.session_state:
    st.session_state.messages = []
if 'recordings' not in st.session_state:
    st.session_state.recordings = []
if 'current_session' not in st.session_state:
    st.session_state.current_session = None
if 'landing_view' not in st.session_state:
    st.session_state.landing_view = 'choose'  # 'choose', 'new', 'existing'


# ============================================================================
# Session Management Helper Functions
# ============================================================================

def get_volume_base_path():
    """Get the base path for the UC volume."""
    print(f"Getting volume base path: /Volumes/{UC_CATALOG}/{UC_SCHEMA}/{UC_VOLUME}")
    return f"/Volumes/{UC_CATALOG}/{UC_SCHEMA}/{UC_VOLUME}"


def list_existing_sessions():
    """List existing session folders from the UC volume."""
    if not databricks_connected or w is None:
        return []
    
    
    volume_path = get_volume_base_path()
    contents = w.files.list_directory_contents(volume_path)
    sessions = []
    for item in contents:
        # Extract folder name from path
        if item.is_directory:
            folder_name = item.path.rstrip('/').split('/')[-1]
            sessions.append(folder_name)
    return sorted(sessions)


def create_session_folder(session_name):
    """
    Validate session can be created. 
    The actual folder is created automatically on first file upload.
    """
    # We don't pre-create the folder - UC volumes create directories automatically
    # when uploading files with w.files.upload()
    session_path = f"{get_volume_base_path()}/{session_name}"
    return True, session_path


def validate_session_name(name):
    """Validate session name for use as a folder name."""
    if not name or not name.strip():
        return False, "Session name cannot be empty"
    
    name = name.strip()
    
    # Check for invalid characters
    if not re.match(r'^[a-zA-Z0-9_-]+$', name):
        return False, "Session name can only contain letters, numbers, underscores, and hyphens"
    
    if len(name) > 100:
        return False, "Session name must be 100 characters or less"
    
    return True, name


def switch_session():
    """Clear current session and return to landing page."""
    st.session_state.current_session = None
    st.session_state.landing_view = 'choose'
    st.session_state.messages = []
    st.session_state.recordings = []


def upload_file_with_timeout(file_path, binary_data, timeout=UPLOAD_TIMEOUT):
    """Upload file to UC volume with timeout."""
    if not databricks_connected or w is None:
        raise Exception("Not connected to Databricks")
    
    def do_upload():
        print(f"Uploading file to {file_path}")
        w.files.upload(file_path, binary_data, overwrite=True)
        print(f"Upload complete: {file_path}")
    
    # Don't use context manager - it waits for threads to finish even after timeout
    executor = ThreadPoolExecutor(max_workers=1)
    future = executor.submit(do_upload)
    try:
        future.result(timeout=timeout)
        executor.shutdown(wait=False)
        return True
    except FuturesTimeoutError:
        # Shutdown without waiting - let the thread die on its own
        executor.shutdown(wait=False)
        raise Exception(f"Upload timed out after {timeout} seconds")


# ============================================================================
# Landing Page
# ============================================================================

def render_landing_page():
    """Render the session selection landing page."""
    
    # Centered container
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col2:
        st.markdown("# 🎤 Voice-to-RAG")
        st.markdown("Transform voice data into intelligent RAG-powered insights")
        st.markdown("---")
        
        # Connection status
        if databricks_connected:
            st.success(f"🟢 Connected to Databricks {DATABRICKS_HOST}")
        else:
            st.warning("🟡 Not connected to Databricks")
            st.caption("Set DATABRICKS_HOST and DATABRICKS_TOKEN in .env for local development")
        
        st.markdown("---")
        
        # Landing view state machine
        if st.session_state.landing_view == 'choose':
            render_choice_view()
        elif st.session_state.landing_view == 'new':
            render_new_session_view()
        elif st.session_state.landing_view == 'existing':
            render_existing_sessions_view()


def render_choice_view():
    """Render the initial choice between new and existing session."""
    st.markdown("### Get Started")
    st.markdown("Choose how you'd like to begin:")
    
    st.markdown("")
    
    col_btn1, col_btn2 = st.columns(2)
    
    with col_btn1:
        if st.button("➕ Create New Session", use_container_width=True, type="primary"):
            st.session_state.landing_view = 'new'
            st.rerun()
    
    with col_btn2:
        if st.button("📂 Open Existing Session", use_container_width=True):
            st.session_state.landing_view = 'existing'
            st.rerun()


def render_new_session_view():
    """Render the new session creation form."""
    st.markdown("### Create New Session")
    st.markdown("Enter a name for your new session:")
    
    # Back button
    if st.button("← Back"):
        st.session_state.landing_view = 'choose'
        st.rerun()
    
    st.markdown("")
    
    # Session name input
    session_name = st.text_input(
        "Session Name",
        placeholder="e.g., interview_2024, meeting_notes, research_data",
        key="new_session_name",
        help="Use letters, numbers, underscores, and hyphens only"
    )
    
    st.markdown("")
    
    if st.button("Create Session", type="primary", use_container_width=True):
        if session_name:
            valid, result = validate_session_name(session_name)
            if valid:
                # Set session - folder will be created on first upload
                st.session_state.current_session = result
                st.session_state.landing_view = 'choose'
                st.rerun()
            else:
                st.error(f"❌ {result}")
        else:
            st.error("❌ Please enter a session name")


def render_existing_sessions_view():
    """Render the existing sessions list."""
    st.markdown("### Select Existing Session")
    
    # Back button
    if st.button("← Back"):
        st.session_state.landing_view = 'choose'
        st.rerun()
    
    st.markdown("")
    
    # Fetch existing sessions
    sessions = list_existing_sessions()
    
    if not sessions:
        st.info("📭 No existing sessions found. Create a new session to get started!")
        st.markdown("")
        if st.button("➕ Create New Session", type="primary"):
            st.session_state.landing_view = 'new'
            st.rerun()
    else:
        st.markdown(f"Found **{len(sessions)}** session(s):")
        st.markdown("")
        
        for session in sessions:
            col_name, col_btn = st.columns([3, 1])
            with col_name:
                st.markdown(f"📁 **{session}**")
            with col_btn:
                if st.button("Open", key=f"open_{session}", use_container_width=True):
                    st.session_state.current_session = session
                    st.rerun()


# ============================================================================
# Main Application (after session selected)
# ============================================================================

def render_main_app():
    """Render the main application after a session is selected."""
    
    current_session = st.session_state.current_session
    
    # Sidebar with session info and switch option
    with st.sidebar:
        st.markdown("## 🎤 Voice-to-RAG")
        st.markdown("---")
        
        # Current session display
        st.markdown("### 📁 Current Session")
        st.info(f"**{current_session}**")
        
        if st.button("🔄 Switch Session", use_container_width=True):
            switch_session()
            st.rerun()
        
        st.markdown("---")
        
        # Connection status
        if databricks_connected:
            st.success("🟢 **Connected**")
        else:
            st.warning("🟡 **Not Connected**")
        
        st.markdown("---")
        
        with st.expander("⚙️ Settings", expanded=False):
            st.caption("**Unity Catalog**")
            st.code(f"{UC_CATALOG}.{UC_SCHEMA}.{UC_VOLUME}", language=None)
            st.caption("**Model Endpoint**")
            st.code(MODEL_ENDPOINT, language=None)
            st.caption("**Delta Table**")
            st.code(DELTA_TABLE, language=None)
    
    # Main application tabs
    tab1, tab2, tab3 = st.tabs(["🎤 Voice Recording", "💬 Chat Interface", "📊 Graph Visualization"])
    
    # Tab 1: Voice Recording and Upload
    with tab1:
        render_voice_recording_tab(current_session)
    
    # Tab 2: Chat Interface
    with tab2:
        render_chat_tab()
    
    # Tab 3: Graph Visualization
    with tab3:
        render_graph_tab()


def render_voice_recording_tab(current_session):
    """Render the voice recording tab."""
    st.markdown("## 🎙️ Voice Recording & Upload")
    st.markdown(f"Recording to session: **{current_session}**")
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
        
        # Handle recorded audio - update session state if new recording
        if audio_bytes:
            # Store recorded audio in session state for upload
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"recording_{timestamp}.wav"
            st.session_state.current_recording = {
                "audio_bytes": audio_bytes,
                "filename": filename,
                "size": len(audio_bytes),
                "timestamp": timestamp
            }
        
        # Show recording UI if we have a recording (from audio_bytes OR session state)
        if st.session_state.get("current_recording"):
            recording = st.session_state.current_recording
            recording_bytes = recording["audio_bytes"]
            recording_filename = recording["filename"]
            recording_size = recording["size"]
            recording_timestamp = recording["timestamp"]
            
            st.markdown("---")
            st.markdown("**🎵 Recording Preview**")
            st.audio(recording_bytes, format="audio/wav")
            
            # File info in a nice container
            with st.container():
                col_info1, col_info2 = st.columns(2)
                with col_info1:
                    st.metric("File Name", recording_filename)
                with col_info2:
                    st.metric("Size", f"{recording_size:,} bytes")
            
            upload_recorded_button = st.button("📤 Upload Recording to Unity Catalog", 
                                                key="upload_recorded",
                                                type="primary",
                                                use_container_width=True)
            
            if upload_recorded_button:
                if not databricks_connected:
                    st.error("❌ Cannot upload: Not connected to Databricks")
                else:
                    try:
                        with st.spinner(f"Uploading recording to Unity Catalog (timeout: {UPLOAD_TIMEOUT}s)..."):
                            # Wrap recorded audio bytes in BytesIO
                            binary_data = io.BytesIO(recording_bytes)
                            
                            # Construct Unity Catalog volume path WITH session folder
                            volume_file_path = f"{get_volume_base_path()}/{current_session}/{recording_filename}"
                            
                            # Upload using Databricks SDK with timeout
                            upload_file_with_timeout(volume_file_path, binary_data)
                            
                            # Track uploaded recording in session state
                            st.session_state.recordings.append({
                                "filename": recording_filename,
                                "path": volume_file_path,
                                "timestamp": recording_timestamp,
                                "size": recording_size,
                                "original_name": "Recorded Audio"
                            })
                            
                            # Clear current recording
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
                        with st.spinner(f"Uploading to Unity Catalog (timeout: {UPLOAD_TIMEOUT}s)..."):
                            # Read file bytes and wrap in BytesIO
                            file_bytes = audio_value.read()
                            binary_data = io.BytesIO(file_bytes)
                            
                            # Generate unique filename with timestamp
                            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                            file_extension = audio_value.name.split('.')[-1]
                            filename = f"recording_{timestamp}.{file_extension}"
                            
                            # Construct Unity Catalog volume path WITH session folder
                            volume_file_path = f"{get_volume_base_path()}/{current_session}/{filename}"
                            
                            # Upload using Databricks SDK with timeout
                            upload_file_with_timeout(volume_file_path, binary_data)
                            
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


def render_chat_tab():
    """Render the chat interface tab."""
    st.markdown("## 💬 Chat Interface")
    st.markdown("Chat with the RAG system backed by Databricks model serving")
    st.markdown("---")
    
    # Display connection status
    if databricks_connected:
        st.success(f"🟢 Connected | Endpoint: `{MODEL_ENDPOINT}`")
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
                    # response = w.serving_endpoints.query(
                    #     name=MODEL_ENDPOINT,
                    #     inputs=[{"query": prompt}]
                    # )
                    
                    # Simulated response
                    response_text = f"This is a simulated response to: '{prompt}'. In production, this would query the Databricks model serving endpoint '{MODEL_ENDPOINT}'."
                    
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


def render_graph_tab():
    """Render the graph visualization tab."""
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
        st.markdown(f"### 📈 Graph from `{DELTA_TABLE}`")
        
        try:
            # In production, query Delta table from Databricks
            # df = spark.table(DELTA_TABLE).toPandas()
            
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
            
            st.markdown("---")
            st.markdown("### 📊 Graph Statistics")
            metrics_cols = st.columns(3)
            metrics_cols[0].metric("Nodes", len(graph_data["nodes"]))
            metrics_cols[1].metric("Edges", len(graph_data["edges"]))
            metrics_cols[2].metric("Density", "0.40")
            
        except Exception as e:
            st.error(f"Error loading graph data: {str(e)}")


# ============================================================================
# Main Entry Point
# ============================================================================

def main():
    """Main application entry point."""
    if st.session_state.current_session is None:
        render_landing_page()
    else:
        render_main_app()


# Run the app
main()
