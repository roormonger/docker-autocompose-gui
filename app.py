from flask import Flask, render_template, request, session, redirect, url_for, flash, jsonify, send_from_directory, send_file
import docker
import subprocess
import shlex
import os
from datetime import datetime
from github import Github, UnknownObjectException, GithubException
import secrets
import logging
import urllib.parse 
import io
import zipfile # For creating ZIP files
import shutil # For removing directories

app = Flask(__name__)
app.secret_key = os.getenv('FLASK_SECRET_KEY', secrets.token_hex(16))

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = app.logger

# --- SCRIPT VERSION MARKER ---
SCRIPT_VERSION = "v10.2 - Simplified flash message for generation"

# --- Configuration ---
AUTOCOMPOSE_SCRIPT_PATH = "./autocompose.py" 
GENERATED_FILES_BASE_OUTPUT_DIR = os.path.abspath(os.getenv('OUTPUT_DIR', "/generated_compose_files")) 
TEMP_COMPOSE_DIR = os.path.abspath("./compose_temp") 
logger.info(f"GENERATED_FILES_BASE_OUTPUT_DIR set to: {GENERATED_FILES_BASE_OUTPUT_DIR}")
logger.info(f"TEMP_COMPOSE_DIR set to: {TEMP_COMPOSE_DIR}")

# GitHub Configuration from Environment Variables
GITHUB_TOKEN_FROM_ENV = os.getenv('GITHUB_TOKEN') 
GITHUB_TARGET_REPO_ENV = os.getenv('GITHUB_TARGET_REPO') 
GITHUB_UPLOAD_PATH_ENV = os.getenv('GITHUB_UPLOAD_PATH', "") 
GITHUB_UPLOAD_BRANCH_ENV = os.getenv('GITHUB_UPLOAD_BRANCH', "main") 
USER_SET_GITHUB_COMMIT_MSG = os.getenv('GITHUB_UPLOAD_COMMIT_MSG') 
ENABLE_GITHUB_UPLOAD = os.getenv('ENABLE_GITHUB_UPLOAD', 'false').lower() == 'true'

logger.info(f"GitHub Upload Feature Enabled by ENV: {ENABLE_GITHUB_UPLOAD}")
logger.info(f"GitHub Token Provided via ENV: {bool(GITHUB_TOKEN_FROM_ENV)}")
logger.info(f"GitHub Target Repo via ENV: {GITHUB_TARGET_REPO_ENV}")

# --- Helper Function to clear and recreate TEMP_COMPOSE_DIR ---
def clear_and_recreate_temp_dir():
    if os.path.exists(TEMP_COMPOSE_DIR):
        try:
            shutil.rmtree(TEMP_COMPOSE_DIR)
            logger.info(f"Successfully removed temporary directory: {TEMP_COMPOSE_DIR}")
        except Exception as e:
            logger.error(f"Error removing temporary directory {TEMP_COMPOSE_DIR}: {e}")
    try:
        os.makedirs(TEMP_COMPOSE_DIR, exist_ok=True)
        logger.info(f"Ensured temporary compose directory exists: {TEMP_COMPOSE_DIR}")
    except OSError as e:
        logger.error(f"Could not create temporary compose directory {TEMP_COMPOSE_DIR}: {e}")

# --- Initial Cleanup on Application Start ---
clear_and_recreate_temp_dir()


# --- Helper Functions ---
def get_docker_client():
    try:
        client = docker.from_env()
        client.ping() 
        logger.info("Successfully connected to Docker daemon.")
        return client
    except docker.errors.DockerException as e:
        logger.error(f"Could not connect to Docker daemon: {e}")
        return None

def run_autocompose_script(container_ids): 
    if not os.path.exists(AUTOCOMPOSE_SCRIPT_PATH):
        logger.error(f"CRITICAL ERROR: autocompose.py not found at {AUTOCOMPOSE_SCRIPT_PATH}.")
        return None, f"autocompose.py not found at {AUTOCOMPOSE_SCRIPT_PATH}", -2
    if not container_ids: 
        logger.warning("run_autocompose_script called with no container IDs.")
        return "", "No container IDs provided.", -1
    
    command = ["python3", AUTOCOMPOSE_SCRIPT_PATH]
    command.extend(container_ids)
    display_command = ' '.join(shlex.quote(c) for c in command)
    logger.info(f"Executing: {display_command}")
    try:
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding='utf-8')
        stdout, stderr = process.communicate(timeout=90)
        if stderr: 
            logger.info(f"autocompose.py stderr:\n{stderr.strip()}")
        if process.returncode != 0:
            logger.error(f"autocompose.py script error (code {process.returncode}).")
        return stdout, stderr, process.returncode
    except subprocess.TimeoutExpired:
        logger.error("autocompose.py script execution timed out.")
        return None, "Script execution timed out.", -1
    except Exception as e:
        logger.error(f"Exception running autocompose.py: {str(e)}")
        return None, f"Error running autocompose: {str(e)}", -3

def sanitize_filename_base(name):
    name = name.replace(" ", "_")
    valid_chars = "-_.abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
    sanitized_name = ''.join(c for c in name if c in valid_chars)
    return sanitized_name if sanitized_name else "unnamed_compose"

def generate_timestamped_dirname(): 
    return f"Autocompose-GUI_{datetime.now().strftime('%m-%d-%Y_%H-%M-%S')}"

def _upload_to_github_internal(token, repo_name_str, base_remote_path, output_subdir_name, file_content_str, simple_filename, commit_message_template, branch_name):
    if not token: return "GitHub Token not available (GITHUB_TOKEN environment variable not set).", "danger"
    if not repo_name_str: return "GitHub Target Repository not configured (GITHUB_TARGET_REPO environment variable not set).", "danger"
    
    try:
        g = Github(token)
        repo = g.get_repo(repo_name_str)
    except GithubException as e:
        logger.error(f"GitHub Error accessing '{repo_name_str}': {e.status} {e.data}")
        return f"GitHub Error: Could not access repository '{repo_name_str}'. Check token and repo. Details: {e.status}", "danger"
    
    clean_base_remote_path = base_remote_path.strip("/")
    full_remote_path_dir = os.path.join(clean_base_remote_path, output_subdir_name).replace("\\", "/")
    if full_remote_path_dir.startswith("/"): full_remote_path_dir = full_remote_path_dir[1:]
    
    full_remote_path_file = os.path.join(full_remote_path_dir, simple_filename).replace("\\","/")

    commit_msg_to_use = commit_message_template
    if not commit_msg_to_use: 
        commit_msg_to_use = f"Autocompose GUI: Add/Update {simple_filename} in {output_subdir_name} ({datetime.now().strftime('%Y-%m-%d_%H-%M-%S')})"
    
    logger.info(f"Attempting to upload '{simple_filename}' to {repo_name_str}/{full_remote_path_file} on branch {branch_name}")
    try:
        contents = repo.get_contents(full_remote_path_file, ref=branch_name)
        repo.update_file(contents.path, commit_msg_to_use, file_content_str, contents.sha, branch=branch_name)
        return f"Successfully updated '{simple_filename}' in GitHub path '{full_remote_path_dir}' (branch: {branch_name}).", "success"
    except UnknownObjectException: 
        repo.create_file(full_remote_path_file, commit_msg_to_use, file_content_str, branch=branch_name)
        return f"Successfully created '{simple_filename}' in GitHub path '{full_remote_path_dir}' (branch: {branch_name}).", "success"
    except GithubException as e:
        logger.error(f"GitHub Error uploading/updating '{simple_filename}' to '{full_remote_path_file}': {e.status} {e.data}")
        msg = f"GitHub Error: Failed to upload/update '{simple_filename}'. Details: {e.status}"
        if hasattr(e, 'data') and e.data and "branch not found" in str(e.data).lower():
             msg += f" Warning: Branch '{branch_name}' might not exist in '{repo_name_str}'."
        return msg, "danger"
    except Exception as e:
        logger.error(f"Unexpected error during GitHub upload for '{simple_filename}' to '{full_remote_path_file}': {str(e)}")
        return f"An unexpected error occurred during GitHub upload for '{simple_filename}': {str(e)}", "danger"

def save_to_temp_and_get_info(content, output_subdir_name, simple_filename):
    full_temp_dir = os.path.join(TEMP_COMPOSE_DIR, output_subdir_name)
    temp_save_path = os.path.join(full_temp_dir, simple_filename)
    
    logger.info(f"Attempting to save temporarily to: {temp_save_path}")
    try:
        os.makedirs(full_temp_dir, exist_ok=True)
        with open(temp_save_path, "w", encoding="utf-8") as f: f.write(content)
        logger.info(f"Successfully saved temporary file to {temp_save_path}")
        return temp_save_path, f"Generated: {output_subdir_name}/{simple_filename}", "info"
    except IOError as e:
        logger.error(f"IOError saving temporary file to {temp_save_path}: {e}")
        return None, f"🔥 Error saving temporary file: {e}", "error"
    except Exception as e_general:
        logger.error(f"Unexpected error saving temporary file to {temp_save_path}: {e_general}")
        return None, f"🔥 Unexpected error saving temporary file: {e_general}", "error"

def get_container_image_name(container_attrs, client):
    try:
        if not isinstance(container_attrs, dict): return "Invalid Attrs"
        config = container_attrs.get('Config', {})
        if not isinstance(config, dict): return "Invalid Config"
        image_name_from_config = config.get('Image', 'Unknown Image')
        if client and 'ImageID' in config and config['ImageID']:
            try:
                img_obj = client.images.get(config['ImageID'])
                if img_obj.tags: return img_obj.tags[0]
            except Exception: pass 
        return image_name_from_config
    except Exception: return "Error: Image Name"

def format_ports_info(ports_data):
    if not ports_data or not isinstance(ports_data, dict): return "No port data"
    bindings = []
    for port, host_cfgs in ports_data.items():
        if host_cfgs and isinstance(host_cfgs, list):
            for host_config in host_cfgs:
                if isinstance(host_config, dict):
                    host_port = host_config.get('HostPort')
                    if host_port: bindings.append(f"{host_port}:{port}")
        elif host_cfgs is None: 
            bindings.append(f"exposed {port}")
    return ", ".join(bindings) if bindings else "No exposed ports"

def toggle_container_selection_ajax(container_id, container_name_display): 
    if 'selected_containers' not in session:
        session['selected_containers'] = {}
    
    if container_id in session['selected_containers']:
        session['selected_containers'].pop(container_id, None)
        selected = False
    else:
        session['selected_containers'][container_id] = container_name_display
        selected = True
    session.modified = True
    return selected, len(session['selected_containers'])

def select_all_containers(all_running_containers):
    session['selected_containers'] = {c['id']: c['name'] for c in all_running_containers}
    session.modified = True

def deselect_all_containers(): 
    session['selected_containers'] = {}
    session.modified = True

def initialize_session_defaults():
    session.setdefault('selected_containers', {})
    session.setdefault('sort_by', 'name')
    session.setdefault('sort_order', 'asc')
    session.setdefault('num_cols', 3)
    session.setdefault('job_history', []) 
    session.setdefault('current_batch_files', []) 

@app.before_request
def ensure_session_defaults():
    initialize_session_defaults()

@app.route('/api/toggle_selection', methods=['POST'])
def api_toggle_selection():
    data = request.get_json()
    container_id = data.get('container_id')
    container_name = data.get('container_name')
    if not container_id or not container_name:
        return jsonify(success=False, error="Missing container_id or container_name"), 400
    is_selected, count = toggle_container_selection_ajax(container_id, container_name)
    return jsonify(success=True, id=container_id, name=container_name, selected=is_selected, selected_count=count)


@app.route('/', methods=['GET', 'POST'])
def index():
    client = get_docker_client() 
    running_containers_data = []
    error_message = None
    docker_connected = bool(client)
    current_job_history = session.get('job_history', []) 
    
    generated_files_for_template = session.get('current_batch_files', [])

    if client:
        try:
            fetched_containers_sdk = client.containers.list(all=False)
            for c_sdk in fetched_containers_sdk:
                try:
                    if not hasattr(c_sdk, 'attrs') or not isinstance(c_sdk.attrs, dict): continue
                    attrs = c_sdk.attrs
                    created_str = attrs.get('Created')
                    if not created_str or not isinstance(created_str, str): continue
                    created_dt = datetime.fromisoformat(created_str.split('.')[0])
                    net_settings = attrs.get('NetworkSettings', {})
                    ports = net_settings.get('Ports', {}) if isinstance(net_settings, dict) else {}
                    name = c_sdk.name or attrs.get('Name', '').lstrip('/') or c_sdk.short_id
                    running_containers_data.append({
                        'id': c_sdk.id, 'short_id': c_sdk.short_id, 'name': name,
                        'image': get_container_image_name(attrs, client),
                        'ports': format_ports_info(ports), 
                        'created': created_dt.strftime('%Y-%m-%d %H:%M:%S') 
                    })
                except Exception as e_inner: logger.error(f"Error processing container {c_sdk.id if hasattr(c_sdk, 'id') else 'UnknownID'}: {e_inner}")
        except Exception as e: error_message = f"Error fetching list: {e}"; logger.error(error_message)
    else: error_message = "Could not connect to Docker."

    if request.method == 'POST':
        action_taken_this_post = False
        post_specific_job_history = [] 
        
        if 'apply_modal_settings_action' in request.form: 
            flash("Settings modal closed.", "info") 
            action_taken_this_post = True
        
        elif 'clear_job_history_action' in request.form:
            session['job_history'] = []
            current_job_history = [] 
            flash("Job history cleared.", "info")
            action_taken_this_post = True

        elif 'sort_by_select' in request.form or 'sort_order_radio' in request.form or \
             'num_cols_slider' in request.form or 'select_action' in request.form:
            if 'sort_by_select' in request.form: session['sort_by'] = request.form.get('sort_by_select')
            if 'sort_order_radio' in request.form: session['sort_order'] = request.form.get('sort_order_radio')
            if 'num_cols_slider' in request.form:
                try: session['num_cols'] = max(1, min(5, int(request.form.get('num_cols_slider'))))
                except (ValueError, TypeError): logger.warning("Invalid num_cols_slider value received.")
            if 'select_action' in request.form: 
                action = request.form.get('select_action')
                if action == 'select_all': select_all_containers(running_containers_data) 
                elif action == 'deselect_all': deselect_all_containers()
            action_taken_this_post = True
        
        session.modified = True 

        generate_button_value = request.form.get('generate_action') 

        if generate_button_value in ["generate_stack", "generate_individuals"]: 
            action_taken_this_post = True
            selected_ids = list(session.get('selected_containers', {}).keys()) 
            
            if not selected_ids:
                flash("No containers selected for generation.", "warning") 
            else:
                clear_and_recreate_temp_dir() # Clear entire temp dir before new generation
                session['current_batch_files'] = [] # Clear previous batch from session display
                
                temp_generated_files_info_for_session = [] 
                output_subdir_name = generate_timestamped_dirname()
                
                def handle_single_temp_generation(ids, base_name, subdir):
                    stdout, stderr, rc = run_autocompose_script(ids) 
                    if rc == 0 and stdout:
                        sanitized_base = sanitize_filename_base(base_name)
                        simple_filename = f"{sanitized_base}.yml" 
                        
                        temp_path, ls_msg, ls_cat = save_to_temp_and_get_info(stdout, subdir, simple_filename)
                        post_specific_job_history.append({'filename': f"{subdir}/{simple_filename}", 'operation': 'Temp Save', 'message': ls_msg, 'category': ls_cat, 'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')})
                        
                        if temp_path: 
                            temp_generated_files_info_for_session.append({
                                "filename": simple_filename, 
                                "content": stdout, 
                                "subdir_name": subdir, 
                                "temp_path": temp_path 
                            })
                    else: 
                        flash(f"Error generating compose for '{base_name}': {stderr or 'Unknown error'}", "danger")
                        post_specific_job_history.append({'filename': base_name, 'operation': 'Generation', 'message': f"Error generating compose: {stderr or 'Unknown error'}", 'category': 'danger', 'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')})

                if generate_button_value == "generate_stack":
                    base_name_for_combined = session['selected_containers'][selected_ids[0]] if len(selected_ids) == 1 else "docker_stack"
                    handle_single_temp_generation(selected_ids, base_name_for_combined, output_subdir_name)
                elif generate_button_value == "generate_individuals":
                    s_count = 0
                    for c_id, c_name in session['selected_containers'].items():
                        if c_id not in selected_ids: continue 
                        handle_single_temp_generation([c_id], c_name, output_subdir_name)
                        s_count +=1 
                    if s_count > 0 : 
                        flash(f"Generated {s_count} of {len(selected_ids)} files.", "info") # Simplified message
                
                session['current_batch_files'] = temp_generated_files_info_for_session 
        
        elif generate_button_value == "clear_generated": 
            action_taken_this_post = True
            session.pop('current_batch_files', None) 
            clear_and_recreate_temp_dir() 
            post_specific_job_history.append({'filename': 'N/A', 'operation': 'Clear Batch', 'message': "Generated files display and temporary storage cleared.", 'category': 'info', 'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')})
            flash("Generated files display and temporary storage cleared.", "info") 
                
        batch_action_value = request.form.get('batch_action')
        if batch_action_value:
            action_taken_this_post = True
            current_batch = session.get('current_batch_files', [])
            if not current_batch:
                flash("No files generated in the current batch to perform action on.", "warning")
            else:
                if batch_action_value == "save_all_local":
                    saved_count = 0
                    for file_info in current_batch:
                        final_output_dir_for_batch = os.path.join(GENERATED_FILES_BASE_OUTPUT_DIR, file_info['subdir_name'])
                        final_save_path = os.path.join(final_output_dir_for_batch, file_info['filename'])
                        try:
                            os.makedirs(final_output_dir_for_batch, exist_ok=True)
                            with open(file_info['temp_path'], 'r', encoding='utf-8') as src_f, \
                                 open(final_save_path, 'w', encoding='utf-8') as dest_f:
                                dest_f.write(src_f.read())
                            ls_msg = f"✅ Saved to local volume: `{file_info['subdir_name']}/{file_info['filename']}`."
                            ls_cat = "success"
                            saved_count +=1
                        except Exception as e:
                            ls_msg = f"🔥 Error saving {file_info['filename']} to local volume: {e}"
                            ls_cat = "error"
                            logger.error(ls_msg)
                        post_specific_job_history.append({'filename': f"{file_info['subdir_name']}/{file_info['filename']}", 'operation': 'Save to Volume', 'message': ls_msg, 'category': ls_cat, 'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')})
                    flash(f"Saved {saved_count}/{len(current_batch)} files to local volume.", "success" if saved_count == len(current_batch) else "warning")

                elif batch_action_value == "upload_all_github":
                    if not (ENABLE_GITHUB_UPLOAD and GITHUB_TOKEN_FROM_ENV and GITHUB_TARGET_REPO_ENV):
                        flash("GitHub upload is not enabled or fully configured via ENV variables.", "danger")
                    else:
                        uploaded_count = 0
                        for file_info in current_batch:
                            gh_msg, gh_category = _upload_to_github_internal(
                                GITHUB_TOKEN_FROM_ENV, GITHUB_TARGET_REPO_ENV, GITHUB_UPLOAD_PATH_ENV,
                                file_info['subdir_name'], file_info['content'], file_info['filename'], 
                                USER_SET_GITHUB_COMMIT_MSG, GITHUB_UPLOAD_BRANCH_ENV
                            )
                            post_specific_job_history.append({'filename': f"{file_info['subdir_name']}/{file_info['filename']}", 'operation': 'Batch GitHub Upload', 'message': gh_msg, 'category': gh_category, 'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')})
                            if gh_category == "success": uploaded_count += 1
                        flash(f"Uploaded {uploaded_count}/{len(current_batch)} files to GitHub.", "info" if uploaded_count == len(current_batch) else "warning")
                
                elif batch_action_value == "download_all_zip":
                    memory_file = io.BytesIO()
                    zip_subdir_name = current_batch[0]['subdir_name'] if current_batch else "compose_files"
                    zip_filename = f"{zip_subdir_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip"
                    with zipfile.ZipFile(memory_file, 'w', zipfile.ZIP_DEFLATED) as zf:
                        for file_item in current_batch:
                            zf.writestr(os.path.join(file_item['subdir_name'], file_item['filename']), file_item['content'])
                    memory_file.seek(0)
                    post_specific_job_history.append({'filename': zip_filename, 'operation': 'ZIP Download', 'message': f"ZIP file '{zip_filename}' prepared.", 'category': 'info', 'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')})
                    session['job_history'] = post_specific_job_history + session.get('job_history', [])[:49]
                    session.modified = True
                    return send_file(memory_file, download_name=zip_filename, as_attachment=True, mimetype='application/zip')

        if post_specific_job_history:
            updated_job_history = post_specific_job_history + session.get('job_history', [])
            session['job_history'] = updated_job_history[:50] 
            session.modified = True
        
        if action_taken_this_post and not (generate_button_value == "download_zip" or batch_action_value == "download_all_zip"): 
            return redirect(url_for('index', sort_by=session.get('sort_by'), sort_order=session.get('sort_order')))

    current_sort_by = session.get('sort_by', 'name')
    current_sort_order = session.get('sort_order', 'asc')
    reverse_sort = (current_sort_order == 'desc')
    if current_sort_by == 'name': running_containers_data.sort(key=lambda c: c.get('name', '').lower(), reverse=reverse_sort)
    elif current_sort_by == 'created': running_containers_data.sort(key=lambda c: datetime.strptime(c.get('created', '1970-01-01 00:00:00'), '%Y-%m-%d %H:%M:%S'), reverse=reverse_sort)
    elif current_sort_by == 'image': running_containers_data.sort(key=lambda c: c.get('image', '').lower(), reverse=reverse_sort)
    
    template_context = {
        "containers": running_containers_data,
        "selected_containers": session.get('selected_containers', {}),
        "error_message": error_message, "docker_connected": docker_connected,
        "current_sort_by": current_sort_by, "current_sort_order": current_sort_order,
        "num_cols": session.get('num_cols', 3), "SCRIPT_VERSION": SCRIPT_VERSION, 
        "GENERATED_FILES_OUTPUT_DIR": GENERATED_FILES_BASE_OUTPUT_DIR, 
        "TEMP_COMPOSE_DIR": TEMP_COMPOSE_DIR,
        "ENABLE_GITHUB_UPLOAD": ENABLE_GITHUB_UPLOAD, 
        "GITHUB_TOKEN_FROM_ENV_SET": bool(GITHUB_TOKEN_FROM_ENV), 
        "GITHUB_TARGET_REPO_ENV": GITHUB_TARGET_REPO_ENV, 
        "GITHUB_UPLOAD_PATH_ENV": GITHUB_UPLOAD_PATH_ENV,
        "GITHUB_UPLOAD_BRANCH_ENV": GITHUB_UPLOAD_BRANCH_ENV,
        "USER_SET_GITHUB_COMMIT_MSG": USER_SET_GITHUB_COMMIT_MSG, 
        "generated_files": generated_files_for_template, 
        "job_history": current_job_history, 
        "current_batch_files": session.get('current_batch_files', []) 
    }
    return render_template('index.html', **template_context)

@app.route('/download_temp/<path:subdir>/<path:filename>') 
def download_temp_file(subdir, filename):
    if ".." in subdir or subdir.startswith("/") or ".." in filename or filename.startswith("/"):
        flash("Invalid file path for download.", "danger")
        return redirect(url_for('index'))
        
    directory = os.path.abspath(os.path.join(TEMP_COMPOSE_DIR, subdir))
    logger.info(f"Attempting to download temporary file '{filename}' from directory '{directory}'")
    try:
        return send_from_directory(directory, filename, as_attachment=True)
    except FileNotFoundError:
        logger.error(f"Temporary file not found for download: {os.path.join(directory, filename)}")
        flash(f"Error: File '{filename}' not found in temporary location '{subdir}'.", "danger")
        return redirect(url_for('index'))
    except Exception as e:
        logger.error(f"Error during temporary file download for '{filename}' from '{subdir}': {e}")
        flash(f"Error downloading file: {e}", "danger")
        return redirect(url_for('index'))

if __name__ == '__main__':
    if not os.path.exists(GENERATED_FILES_BASE_OUTPUT_DIR): 
        try: 
            os.makedirs(GENERATED_FILES_BASE_OUTPUT_DIR)
            logger.info(f"Created base output directory: {GENERATED_FILES_BASE_OUTPUT_DIR}")
        except OSError as e: 
            logger.error(f"Could not create base output directory {GENERATED_FILES_BASE_OUTPUT_DIR}: {e}")
    # Initial cleanup of TEMP_COMPOSE_DIR is handled at the top of the script now.
    app.run(debug=True, host='0.0.0.0', port=5000)
