import streamlit as st
import subprocess
import shlex
import docker
import os # Crucial for path operations and file saving
from datetime import datetime

# --- Configuration ---
AUTOCOMPOSE_SCRIPT_PATH = "/app/autocompose.py"
GENERATED_FILES_OUTPUT_DIR = "/generated_compose_files" # Must match volume mount in `docker run`

# --- Page Config and Basic Styling (similar to previous) ---
st.set_page_config(layout="wide", page_title="Docker Autocompose GUI")
st.markdown("""
<style>
    /* ... (keep existing styles or add new ones as desired) ... */
    .stButton>button { border-radius: 5px; padding: 8px 15px; }
    .stDownloadButton>button { width: 100%; background-color: #28a745; color: white; border-radius: 5px; padding: 8px 15px; }
    .stDownloadButton>button:hover { background-color: #218838; color: white; }
    .streamlit-expanderContent { overflow: visible !important; }
</style>
""", unsafe_allow_html=True)


# --- Helper function to run autocompose ---
def run_autocompose(container_ids, full_output_flag, log_area=st):
    if not os.path.exists(AUTOCOMPOSE_SCRIPT_PATH):
        log_area.error(
            f"**CRITICAL ERROR:** `autocompose.py` not found at `{AUTOCOMPOSE_SCRIPT_PATH}`. "
            "Please ensure it's correctly mounted via a volume."
        )
        return None, f"`autocompose.py` not found at {AUTOCOMPOSE_SCRIPT_PATH}", -2, ""

    if not container_ids:
        return "", "No container IDs provided.", -1, ""

    command = ["python", AUTOCOMPOSE_SCRIPT_PATH] # Use the defined path
    if full_output_flag:
        command.append("--full")
    command.extend(container_ids)

    display_command = ' '.join(shlex.quote(c) for c in command)
    log_area.info(f"⚙️ Executing: `{display_command}`")

    try:
        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding='utf-8'
        )
        stdout, stderr = process.communicate(timeout=90)
        return stdout, stderr, process.returncode, display_command
    except subprocess.TimeoutExpired:
        log_area.error("⏳ Script execution timed out after 90 seconds.")
        return None, "Script execution timed out.", -1, display_command
    except Exception as e: # Catch other potential Popen errors
        log_area.error(f"🔥 An unexpected error occurred while trying to run autocompose: {str(e)}")
        return None, f"Unexpected error during Popen: {str(e)}", -3, display_command

# --- Helper function to sanitize filename ---
def sanitize_filename(name):
    name = name.replace(" ", "_")
    valid_chars = "-_.abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
    sanitized_name = ''.join(c for c in name if c in valid_chars)
    if not sanitized_name:
        return "unnamed_compose"
    return sanitized_name

# --- Helper function to save file and provide download ---
def save_and_download(content, base_filename, container_name_for_log, log_area=st, download_key_prefix="dl_"):
    """Saves content to the volume and offers a download button."""
    if not content:
        log_area.warning(f"No content to save for {container_name_for_log}.")
        return

    # Ensure the target directory for saving exists
    try:
        os.makedirs(GENERATED_FILES_OUTPUT_DIR, exist_ok=True)
    except OSError as e:
        log_area.error(f"🔥 Error creating output directory `{GENERATED_FILES_OUTPUT_DIR}`: {e}")
        # Still offer download if directory creation fails
        log_area.download_button(
            label=f"⚠️ Download {base_filename} (Save to volume failed)",
            data=content,
            file_name=base_filename,
            mime="text/yaml",
            key=f"{download_key_prefix}_{base_filename}_fail"
        )
        return

    save_path = os.path.join(GENERATED_FILES_OUTPUT_DIR, base_filename)
    try:
        with open(save_path, "w", encoding="utf-8") as f:
            f.write(content)
        log_area.success(f"✅ Saved: `{save_path}` (in container). Access it via your host's mounted volume.")
    except IOError as e:
        log_area.error(f"🔥 Error saving file to `{save_path}`: {e}")

    log_area.download_button(
        label=f"📥 Download {base_filename}",
        data=content,
        file_name=base_filename,
        mime="text/yaml",
        key=f"{download_key_prefix}_{base_filename}"
    )

# --- Initialize session state (as before) ---
if 'selected_container_info' not in st.session_state:
    st.session_state.selected_container_info = {}

# --- Sidebar (Updated instructions) ---
st.sidebar.title("About & Options")
st.sidebar.info(
    "Select running containers to generate `docker-compose.yml` files. "
    "Files will be saved to a mounted volume and offered for download."
)
st.sidebar.markdown("Original `autocompose.py` script: [Red5d/docker-autocompose](https://github.com/Red5d/docker-autocompose)")
st.sidebar.markdown("---")
st.sidebar.subheader("Volume Mounts Required:")
st.sidebar.markdown(f"1. **Output Files**: Mount a host directory to `{GENERATED_FILES_OUTPUT_DIR}` in the container to persist generated files.")
st.sidebar.markdown("---")
st.sidebar.header("Global Autocompose Options")
full_output_globally = st.sidebar.checkbox(
    "Include default values (`--full`)", value=False, help="Applies `--full` to `autocompose.py`."
)

# --- Main Application ---
st.title("🚢 Docker Autocompose GUI")

# --- Pre-flight check for autocompose.py ---
if not os.path.exists(AUTOCOMPOSE_SCRIPT_PATH):
    st.error(
        f"**CRITICAL SETUP ERROR:** The script `autocompose.py` was not found at the expected path `{AUTOCOMPOSE_SCRIPT_PATH}` inside the container. "
        "Please ensure you have downloaded `autocompose.py` from its official repository and are correctly mounting it as a volume when running this Docker container. "
        "The application will not be able to generate compose files without it."
    )
    st.code(f"Example mount: -v /path/on/your/host/autocompose.py:{AUTOCOMPOSE_SCRIPT_PATH}", language="bash")
    st.stop() # Stop further execution if critical script is missing


st.markdown("Interactively generate `docker-compose.yml` configurations from your running Docker containers. Generated files are saved to a mounted volume.")

# (The rest of the UI for listing containers and generation logic is largely the same,
# but calls `save_and_download` after getting output from `run_autocompose`)

# --- Section 1: List and Select Containers (Same as before) ---
st.header("1. Select Running Containers")
try:
    docker_client = docker.from_env()
    running_containers = docker_client.containers.list(all=False)
except docker.errors.DockerException as e:
    st.error(f"🚨 Could not connect to Docker daemon: {e}")
    st.caption("Ensure Docker is running and the Docker socket (`/var/run/docker.sock`) is correctly mounted.")
    running_containers = []

if not running_containers:
    st.warning("No running containers found, or the Docker daemon is inaccessible.")
else:
    # (Checkbox logic for selecting containers - same as previous version)
    st.write("Choose the containers you want to include:")
    num_cols = st.slider("Number of columns for container list:", 1, 5, 3, key="cols_slider")
    cols = st.columns(num_cols)
    current_selections = {}
    for i, container in enumerate(running_containers):
        container_name = container.name or container.attrs.get('Config', {}).get('Hostname', 'Unknown')
        display_label = f"{container_name} ({container.short_id})"
        is_selected = cols[i % num_cols].checkbox(
            display_label,
            value=(container.id in st.session_state.selected_container_info),
            key=f"cb_{container.id}"
        )
        if is_selected:
            current_selections[container.id] = container_name
    st.session_state.selected_container_info = current_selections
    num_selected = len(st.session_state.selected_container_info)
    selected_ids = list(st.session_state.selected_container_info.keys())
    selected_names = list(st.session_state.selected_container_info.values())

    if num_selected > 0:
        st.success(f"**{num_selected} container(s) selected:** {', '.join(selected_names)}")
        st.header("2. Choose Generation Mode & Generate")
        results_area = st.container()

        if num_selected == 1:
            st.info("A single compose file will be generated.")
            if st.button(f"🚀 Generate Compose for '{selected_names[0]}'", key="generate_single"):
                with results_area:
                    st.subheader(f"Compose for: {selected_names[0]} ({selected_ids[0][:12]})")
                    stdout, stderr, returncode, _ = run_autocompose([selected_ids[0]], full_output_globally, st)
                    if returncode == 0 and stdout:
                        st.code(stdout, language="yaml")
                        fname = sanitize_filename(f"{selected_names[0]}_compose.yml")
                        save_and_download(stdout, fname, selected_names[0], st, f"dl_s_{selected_ids[0]}")
                    else:
                        st.error(f"Error generating compose for {selected_names[0]}:")
                        if stdout: st.text_area("Stdout:", value=stdout, height=100, disabled=True, key=f"out_s_{selected_ids[0]}")
                        if stderr: st.text_area("Stderr:", value=stderr, height=100, disabled=True, key=f"err_s_{selected_ids[0]}")

        elif num_selected > 1:
            generation_mode = st.radio(
                "Generation mode for multiple containers:",
                ("Combined: Single `docker-compose.yml` (stack)",
                 "Separate: Individual `docker-compose.yml` files"),
                key="generation_mode_multiple", horizontal=True
            )
            if st.button(f"🚀 Generate Compose File(s) ({num_selected} containers)", key="generate_multiple"):
                with results_area:
                    if "Combined" in generation_mode:
                        st.subheader("Combined `docker-compose.yml` (Stack)")
                        stdout, stderr, returncode, _ = run_autocompose(selected_ids, full_output_globally, st)
                        if returncode == 0 and stdout:
                            st.code(stdout, language="yaml")
                            fname = sanitize_filename("docker_stack_compose.yml")
                            save_and_download(stdout, fname, "Combined Stack", st, "dl_stack")
                        else:
                            st.error("Error during combined stack generation:")
                            if stdout: st.text_area("Stdout:", value=stdout, height=100, disabled=True, key="out_stack")
                            if stderr: st.text_area("Stderr:", value=stderr, height=100, disabled=True, key="err_stack")
                    else: # Separate files
                        st.subheader("Individual `docker-compose.yml` Files")
                        success_count = 0
                        for container_id, container_name in st.session_state.selected_container_info.items():
                            exp_title = f"Compose for: {container_name} ({container_id[:12]})"
                            with st.expander(exp_title):
                                stdout_sep, stderr_sep, returncode_sep, _ = run_autocompose([container_id], full_output_globally, st)
                                if returncode_sep == 0 and stdout_sep:
                                    st.code(stdout_sep, language="yaml")
                                    fname_sep = sanitize_filename(f"{container_name}_compose.yml")
                                    save_and_download(stdout_sep, fname_sep, container_name, st, f"dl_sep_{container_id}")
                                    success_count += 1
                                else:
                                    st.error(f"Error generating compose for {container_name}:")
                                    if stdout_sep: st.text_area("Stdout:", value=stdout_sep, height=70, disabled=True, key=f"out_sep_{container_id}")
                                    if stderr_sep: st.text_area("Stderr:", value=stderr_sep, height=70, disabled=True, key=f"err_sep_{container_id}")
                        if success_count > 0: st.success(f"Processed {success_count} of {num_selected} separate compose files.")
                        if success_count < num_selected: st.warning(f"Failed for {num_selected - success_count} container(s). See details above.")
    else:
        st.info("☝️ Select one or more running containers to enable generation options.")

# --- Footer ---
st.markdown("---")
st.caption(f"Docker Autocompose GUI | Last refresh: {datetime.now().strftime('%Y-%m-%d %H:%M:%S %Z')}")