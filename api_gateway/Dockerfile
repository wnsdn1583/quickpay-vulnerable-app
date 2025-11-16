FROM python:3.11-slim

WORKDIR /app

# Install packages
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy app code
COPY app.py .

# Expose port
EXPOSE 8080

# Run with Gunicorn
CMD ["gunicorn", "-b", "0.0.0.0:8080", "-w", "4", "--access-logfile", "-", "--error-logfile", "-", "app:app"]
