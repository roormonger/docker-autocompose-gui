# Use an official Python runtime as a parent image
FROM python:3.10-slim

# Set the working directory in the container
WORKDIR /app

# (Optional: ca-certificates might still be useful if your GUI app needs to make other HTTPS requests)
RUN apt-get update && \
    apt-get install -y --no-install-recommends ca-certificates && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Copy the Streamlit GUI wrapper script into the container
COPY gui_app.py . # This copies your local gui_app.py

# Install necessary Python packages:
# - streamlit: For the GUI
# - docker: Required by autocompose.py to interact with the Docker API
RUN pip install --no-cache-dir streamlit docker

# Expose Streamlit default port
EXPOSE 8501

# Define environment variables for Streamlit (as before)
ENV STREAMLIT_SERVER_PORT=8501
ENV STREAMLIT_SERVER_ADDRESS=0.0.0.0
ENV STREAMLIT_SERVER_HEADLESS=true
ENV STREAMLIT_SERVER_ENABLE_XSRF_PROTECTION=false
ENV STREAMLIT_SERVER_RUN_ON_SAVE=false

# Define mount points for user-provided scripts and generated files.
# This is more for documentation; actual mounting is done in `docker run`.
VOLUME /app
VOLUME /generated_compose_files

# --- Important Note ---
# The autocompose.py script is NOT bundled in this image.
# It MUST be provided via a volume mount to /app/autocompose.py when running the container.
# Example: -v /path/to/your/autocompose.py:/app/autocompose.py
#
# Generated compose files will be saved to /generated_compose_files (if configured in gui_app.py)
# Mount a volume to this path to persist them on your host.
# Example: -v /path/on/host/for/outputs:/generated_compose_files

# Command to run the Streamlit application
CMD ["streamlit", "run", "gui_app.py"]