# Docker Autocompose GUI

A web-based GUI wrapper for the `docker-autocompose` script by Red5d. Star their project if you like this.
https://github.com/Red5d/docker-autocompose

I found Red5d's docker-autocompose script very helpful to create docker-compose.yml files for my running containers. It's nice to have backups in case something bad happens. I am a sucker for a GUI though, so I put my free month of Gemini Pro to work lol. All compose files are saved in a timestamped folder. I chose this to avoid any conflicts with existing files. Hopefully you only need to use it once.

https://hub.docker.com/r/roormonger/autocompose-gui

## Features

* Uses Flask for the UI
* Lists running Docker containers for easy selection.
* Generates `docker-compose.yml` for single or multiple containers.
* Option for combined (stack) or separate compose files for multiple selections.
* Generates the compose files in the UI for easy with an option to download directly or you can copy the text.
* Saves generated compose files to a user-specified volume on the host.
* Upload compose files to Github.
* Save all generated compose files in a single zip.
* Resizable columns in container list.
* Sorting Options in container list.
* Light/Dark mode.
* Ability to add a label to any container to exclude any ENV variable from the output. ( Format - AUTOCOMPOSE_EXCLUDE=ENV_VAR_1,ENV_VAR_2,ENV_VAR_3 )

![alt text](https://github.com/roormonger/autocompose-gui/blob/main/images/main.png?raw=true)
![alt text](https://github.com/roormonger/autocompose-gui/blob/main/images/output.png?raw=true)
![alt text](https://github.com/roormonger/autocompose-gui/blob/main/images/history.png?raw=true)

## You know what to do

Make sure you have a folder bound for the compose files.

```yaml
services:
  autocompose-gui:
    image: roormonger/autocompose-gui:latest
    container_name: autocompose-gui
    restart: unless-stopped
    environment:
      - ENABLE_GITHUB_UPLOAD=false #Optional - Set to "true" to enable the "Upload to Github" button in the UI
      - GITHUB_TOKEN=YOUR_GITHUB_TOKEN #Optional - Your Github personal authorization token. Only needed for Github upload
      - GITHUB_TARGET_REPO=YOUR_GITHUB_REPO #Optional - The Github repo you want do dump your compose files into (NAME/REPO)
      - GITHUB_UPLOAD_PATH= #Optional - Path in the above repo. Leave blank for root
      - GITHUB_UPLOAD_BRANCH=BRANCH #Optional - Repo branch
      - GITHUB_UPLOAD_COMMIT_MSG= #Optional - The commit message. If blank default to "Autocompose-GUI_(TIMESTAMP)" 
      - FLASK_SECRET_KEY=YOUR_FLASK_KEY #Required - Make up whatever you want
    labels:
      - AUTOCOMPOSE_EXCLUDE=GITHUB_TOKEN,FLASK_SECRET_KEY #Optional - Add this to any container that has ENV variables you dont want in the output compose files. Just use a comma seperated list of ENV varibles to exclude
    ports:
      - "8501:5000"
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock #Required
      - path/on/host:/generated_compose_files #Optional - You only need this if you plan on saving locally
```
