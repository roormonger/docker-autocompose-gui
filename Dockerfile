# Use an official Python runtime as a parent image
FROM python:3.10-slim

# Set the working directory in the container
WORKDIR /app

# Install wget and ca-certificates (for HTTPS download)
# Clean up apt cache to reduce image size
RUN apt-get update && \
    apt-get install -y --no-install-recommends wget ca-certificates && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Download the docker-autocompose.py script from GitHub
# Using a specific commit hash for stability is good practice, but master is fine for this example.
RUN wget https://raw.githubusercontent.com/Red5d/docker-autocompose/master/autocompose.py -O autocompose.py

# Copy the Streamlit GUI wrapper script into the container
COPY gui_app.py .

# Install necessary Python packages:
# - streamlit: For the GUI
# - docker: Required by autocompose.py to interact with the Docker API
# Using --no-cache-dir to reduce layer size
RUN pip install --no-cache-dir streamlit docker

# Make port 8501 available to the world outside this container (Streamlit's default port)
EXPOSE 8501

# Define environment variable for Streamlit
ENV STREAMLIT_SERVER_PORT=8501
ENV STREAMLIT_SERVER_ADDRESS=0.0.0.0
ENV STREAMLIT_SERVER_HEADLESS=true
ENV STREAMLIT_SERVER_ENABLE_XSRF_PROTECTION=false
# Disable runOnSave for production images; only rerun when explicitly triggered in GUI
ENV STREAMLIT_SERVER_RUN_ON_SAVE=false

# Command to run the Streamlit application when the container launches
# Using the list form of CMD is preferred
CMD ["streamlit", "run", "gui_app.py"]