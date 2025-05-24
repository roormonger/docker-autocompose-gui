# Use an official Python runtime as a parent image
FROM python:3.10-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1
ENV FLASK_APP app.py
# Set FLASK_ENV to 'production' for gunicorn, or 'development' for flask run
ENV FLASK_ENV production
# Application-specific environment variables
# These can be overridden at runtime (e.g., docker run -e VAR_NAME=new_value)
# You should set FLASK_SECRET_KEY as an environment variable at runtime for security
# For GITHUB_TOKEN, it's STRONGLY recommended to provide this at runtime for security.
# Do NOT hardcode your actual token here in a committed Dockerfile.
# ENV FLASK_SECRET_KEY=""
# ENV GITHUB_TOKEN="" 
# ENV GITHUB_TARGET_REPO="" 
# ENV GITHUB_UPLOAD_PATH="" 
# ENV GITHUB_UPLOAD_BRANCH=""
# If GITHUB_UPLOAD_COMMIT_MSG is empty, the app.py script will use a dynamic default.
# ENV GITHUB_UPLOAD_COMMIT_MSG=""
# This ENV VAR is used by autocompose.py to identify itself for sensitive var filtering
ENV AUTOCONPOSE_GUI_SERVICE_NAME="autocompose-gui" 


# Set the working directory in the container
WORKDIR /app

# Install system dependencies (if any, e.g., for certain Python packages)
# RUN apt-get update && apt-get install -y --no-install-recommends some-package && rm -rf /var/lib/apt/lists/*

# Copy the requirements file into the container
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the application code into the container
# Ensure autocompose.py is in the same directory as this Dockerfile or adjust path
COPY . . 
# If autocompose.py is not meant to be part of the repo, 
# you'd download it here or mount it as a volume at runtime.
# For now, assuming it's copied with "COPY . ."

# Make port 5000 available to the world outside this container (Flask's default, Gunicorn will also use this)
EXPOSE 5000

# Define the command to run the application
# For development: CMD ["flask", "run", "--host=0.0.0.0"]
# For production (using Gunicorn):
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "app:app"]
