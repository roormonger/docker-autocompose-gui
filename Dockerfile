# Use an official Python runtime as a parent image
FROM python:3.10-slim

# Set the working directory in the container
WORKDIR /app

# Install necessary Python packages:
# - streamlit: For the GUI
# - docker: Required by autocompose.py to interact with the Docker API
RUN pip install --no-cache-dir streamlit docker pyaml

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

# Command to run the Streamlit application
CMD ["streamlit", "run", "gui_app.py"]