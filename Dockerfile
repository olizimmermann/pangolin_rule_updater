FROM python:3.12-slim

# Install runtime libs
COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

# Copy application code
WORKDIR /app
COPY update_ip.py /app/update_ip.py

# Entrypoint
CMD ["python", "-u", "/app/update_ip.py"]

