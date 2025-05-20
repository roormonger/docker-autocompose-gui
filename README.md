# Docker Autocompose GUI

A web-based GUI wrapper for the `docker-autocompose` script by Red5d. Star their project if you like this.
https://github.com/Red5d/docker-autocompose

I liked the script but I am sucker for a GUI. 99.9% of this was made by Gemini (2.5 Pro). I have no idea what I am doing lol. It works well for what it is though.

## Features

* Lists running Docker containers for easy selection.
* Generates `docker-compose.yml` for single or multiple containers.
* Option for combined (stack) or separate compose files for multiple selections.
* Saves generated compose files to a user-specified volume on the host.
* Provides direct download links for generated files.
* `gui_app.py` (the GUI) is pulled from GitHub during the image build.
* `autocompose.py` (the core script by Red5d) is included in the Docker image from this repository.

## Running the Application

Make sure you have a folder bound for the compose files.

### Docker Compose

This is the easiest way to run the application with the correct configurations.

1.  **Review `docker-compose.yml`:**
    A `docker-compose.yml` file is provided in the root of this repository:
    ```yaml
    version: '3.8'

    services:
      autocompose-gui:
        image: roormonger/autocompose-gui:latest
        container_name: autocompose-gui
        restart: unless-stopped
        ports:
          - "8501:8501"
        volumes:
          - /var/run/docker.sock:/var/run/docker.sock
          - ./my_compose_outputs:/generated_compose_files
    ```
