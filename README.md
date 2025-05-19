# Docker Autocompose GUI

A web-based GUI wrapper for the `docker-autocompose` script, packaged in a Docker container. This tool allows you to interactively select running Docker containers and generate `docker-compose.yml` configurations for them.

## Features

* Lists running Docker containers for easy selection.
* Generates `docker-compose.yml` for single or multiple containers.
* Option for combined (stack) or separate compose files for multiple selections.
* Saves generated compose files to a user-specified volume on the host.
* Provides direct download links for generated files.
* `gui_app.py` (the GUI) is pulled from GitHub during the image build.
* `autocompose.py` (the core script by Red5d) is included in the Docker image from this repository.

## Prerequisites

* **Git:** To clone the repository.
* **Docker:** Must be installed and running on your system.
* **Docker Compose:** (Recommended for easy execution) Must be installed if you plan to use the `docker-compose.yml` file.

## Setup and Installation

1.  **Clone the Repository:**
    First, clone this repository to your local machine:
    ```bash
    git clone [https://github.com/roormonger/docker-autocompose-gui.git](https://github.com/roormonger/docker-autocompose-gui.git)
    cd docker-autocompose-gui
    ```

2.  **Ensure `autocompose.py` is Present:**
    This project includes `autocompose.py` (the script by Red5d) in the root of the repository. This file will be copied into the Docker image during the build process. Make sure it is present in the root directory if you've made any changes.

3.  **Build the Docker Image:**
    Navigate into the cloned `docker-autocompose-gui` directory. Then, build the Docker image using the provided `Dockerfile`:
    ```bash
    docker build -t autocompose-gui .
    ```
    This command builds the image and tags it as `autocompose-gui`.

## Running the Application

You have two main ways to run the application:

### Option 1: Using Docker Compose (Recommended)

This is the easiest way to run the application with the correct configurations.

1.  **Review `docker-compose.yml`:**
    A `docker-compose.yml` file is provided in the root of this repository:
    ```yaml
    version: '3.8'

    services:
      autocompose-gui:
        image: autocompose-gui
        container_name: autocompose-gui
        restart: unless-stopped
        ports:
          - "8501:8501"
        volumes:
          - /var/run/docker.sock:/var/run/docker.sock
          - ./my_compose_outputs:/generated_compose_files
    ```
    This file defines the `autocompose-gui` service, maps the necessary port, and sets up volumes for Docker socket access and persisting generated compose files.

2.  **Create Output Directory:**
    The `docker-compose.yml` file is configured to save generated compose files to a `./my_compose_outputs` directory on your host (relative to where the `docker-compose.yml` file is). Create this directory:
    ```bash
    mkdir my_compose_outputs
    ```
    Alternatively, you can modify the `docker-compose.yml` file to point to any existing directory on your host.

3.  **Start the Application:**
    Navigate to the directory containing `docker-compose.yml` (the root of this project) and run:
    ```bash
    docker-compose up -d
    ```
    The `-d` flag runs the container in detached mode (in the background).

4.  **Stop the Application:**
    To stop the container launched by Docker Compose:
    ```bash
    docker-compose down
    ```

### Option 2: Using `docker run`

If you prefer not to use Docker Compose, you can run the container directly.

1.  **Create Output Directory (if not already done):**
    Ensure you have a directory on your host to store the generated compose files. For example:
    ```bash
    mkdir -p /path/on/your/host/my_compose_outputs
    ```
    (Replace `/path/on/your/host/my_compose_outputs` with your desired path.)

2.  **Run the Container:**
    ```bash
    docker run -d \
        -p 8501:8501 \
        -v /var/run/docker.sock:/var/run/docker.sock \
        -v /path/on/your/host/my_compose_outputs:/generated_compose_files \
        --name autocompose-gui \
        autocompose-gui
    ```
    **Important:** Replace `/path/on/your/host/my_compose_outputs` with the actual absolute path to your chosen output directory.

3.  **Stop the Container:**
    ```bash
    docker stop autocompose-gui
    docker rm autocompose-gui
    ```

## Accessing the GUI

Once the container is running (using either Docker Compose or `docker run`), open your web browser and navigate to:

`http://localhost:8501`

You should see the GUI. Select your running containers, choose your generation options, and the generated `docker-compose.yml` files will be:
* Displayed in the GUI.
* Available for direct download from the GUI.
* Saved to your host machine in the directory you mounted to `/generated_compose_files` (e.g., `./my_compose_outputs` or your custom path).

## Project Structure

* `Dockerfile`: Defines how the Docker image is built.
* `gui_app.py`: The Streamlit Python application providing the GUI (pulled from GitHub during image build).
* `autocompose.py`: The core script by Red5d for generating compose files (included in the image from this repository).
* `docker-compose.yml`: For easy application startup and management.
* `README.md`: This file.

## Troubleshooting

* **"Cannot connect to Docker daemon" / Permission Denied on Docker Socket:**
    * Ensure Docker is running.
    * If on Linux, you might need to run `docker-compose` or `docker` commands with `sudo`, or [add your user to the `docker` group](https://docs.docker.com/engine/install/linux-postinstall/#manage-docker-as-a-non-root-user).
* **Files not saving to host:** Double-check the host path in the `volumes` section of your `docker-compose.yml` or `docker run` command. Ensure the directory exists and Docker has permission to write to it.
* **`gui_app.py` or `autocompose.py` not found inside container:** Verify the `Dockerfile` build process. The `wget` command for `gui_app.py` should complete successfully, and the `COPY autocompose.py` command should find the file in the repository root during the build.

## Contributing

(Optional: Add guidelines if you are open to contributions.)

## License

(Optional: Add a `LICENSE` file to your repository and reference it here, e.g., MIT, Apache 2.0.)
