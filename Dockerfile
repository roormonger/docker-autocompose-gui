# Use an official Python runtime as a parent image
FROM python:3.10-slim

# Set the working directory in the container
WORKDIR /app

# Install essential packages, download gui_app.py and autocompose.py from GitHub, and cleanup
RUN apt-get update && \
    apt-get install -y --no-install-recommends wget ca-certificates && \
    \
    echo "Downloading gui_app.py from roormonger/autocompose-gui repository (main branch)..." && \
    # Download gui_app.py from your repository
    wget -O /app/gui_app.py https://raw.githubusercontent.com/roormonger/autocompose-gui/main/gui_app.py && \
    if [ ! -s /app/gui_app.py ]; then \
        echo "ERROR: gui_app.py downloaded from GitHub is empty or download failed!" >&2; \
        exit 1; \
    fi && \
    echo "gui_app.py downloaded successfully." && \
    \
    echo "Downloading autocompose.py from roormonger/autocompose-gui repository (main branch)..." && \
    # Download autocompose.py from your roormonger/autocompose-gui repository
    # Ensure autocompose.py exists in the root of the 'main' branch of this repository.
    wget -O /app/autocompose.py https://raw.githubusercontent.com/roormonger/autocompose-gui/main/autocompose.py && \
    if [ ! -s /app/autocompose.py ]; then \
        echo "ERROR: autocompose.py downloaded from GitHub is empty or download failed!" >&2; \
        exit 1; \
    fi && \
    echo "autocompose.py downloaded successfully." && \
    \
    # Clean up wget after use to keep the image smaller
    apt-get purge -y --auto-remove wget && \
    apt-get autoremove -y && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# The COPY autocompose.py /app/autocompose.py line is now REMOVED, as it's downloaded above.

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

# For documentation: Volume where generated files will be saved at runtime
VOLUME /generated_compose_files

# Command to run the Streamlit application
CMD ["streamlit", "run", "gui_app.py"]
