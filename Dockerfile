# Use an official Python runtime as a parent image
FROM python:3.10-slim

# Set the working directory in the container
WORKDIR /app

# Install essential packages, download gui_app.py from GitHub, and cleanup
RUN apt-get update && \
    apt-get install -y --no-install-recommends wget ca-certificates && \
    echo "Downloading gui_app.py from GitHub repository (main branch)..." && \
    # IMPORTANT: Adjust the URL below if your default branch is not 'main'
    # or if gui_app.py is in a subdirectory in your repository.
    wget -O /app/gui_app.py https://raw.githubusercontent.com/roormonger/docker-autocompose-gui/main/gui_app.py && \
    # Basic check to ensure download was successful and file is not empty
    if [ ! -s /app/gui_app.py ]; then \
        echo "ERROR: gui_app.py downloaded from GitHub is empty or download failed!" >&2; \
        exit 1; \
    fi && \
    echo "gui_app.py downloaded successfully." && \
    # Clean up wget after use to keep the image smaller
    apt-get purge -y --auto-remove wget && \
    apt-get autoremove -y && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# The COPY gui_app.py /app/ line is now REMOVED, as we are downloading it above.

# Install necessary Python packages
RUN pip install --no-cache-dir streamlit docker pyaml

# Expose Streamlit default port
EXPOSE 8501

# Define environment variables for Streamlit
ENV STREAMLIT_SERVER_PORT=8501
ENV STREAMLIT_SERVER_ADDRESS=0.0.0.0
ENV STREAMLIT_SERVER_HEADLESS=true
ENV STREAMLIT_SERVER_ENABLE_XSRF_PROTECTION=false
ENV STREAMLIT_SERVER_RUN_ON_SAVE=false

# For documentation: Volume where autocompose.py is expected at runtime
# (autocompose.py is still expected to be mounted by the user at runtime)
VOLUME /app
# For documentation: Volume where generated files will be saved at runtime
VOLUME /generated_compose_files

# Command to run the Streamlit application
CMD ["streamlit", "run", "gui_app.py"]