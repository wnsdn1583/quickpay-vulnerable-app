# Use an official Python runtime as a parent image
FROM python:3.9-slim

# Set the working directory in the container
WORKDIR /app

# 1. Install dependencies for building ImageMagick
RUN apt-get update && \
    DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
    wget \
    build-essential \
    pkg-config \
    libxml2-dev \
    libbz2-dev \
    libjpeg-dev \
    libpng-dev \
    libfreetype6-dev \
    libtiff-dev \
    liblcms2-dev \
    libwebp-dev \
    curl \ 
    netcat-traditional \
    libmagickwand-dev && \
    rm -rf /var/lib/apt/lists/*

RUN apt-get remove --purge -y imagemagick* libmagick* && \
    apt autoremove -y 

# 2. Download, compile, and install vulnerable ImageMagick
WORKDIR /tmp
RUN wget https://launchpad.net/imagemagick/main/6.9.3-9/+download/ImageMagick-6.9.3-9.tar.gz && \
    tar xvf ImageMagick-6.9.3-9.tar.gz
WORKDIR /tmp/ImageMagick-6.9.3-9
RUN ./configure --prefix=/usr && \
    make && \
    make install

# 3. Update library links and install libmagickwand-dev
RUN ldconfig /usr/lib

# Return to the app directory
WORKDIR /app

# Copy the dependencies file to the working directory
COPY requirements.txt .

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application's code to the working directory
COPY . .

# Make port 8000 available to the world outside this container
EXPOSE 8000

# Define environment variable
ENV FLASK_APP app.py

# Run app.py when the container launches
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "app:app"]
