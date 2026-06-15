FROM python:3.9-slim

# Keeps Python output unbuffered (logs appear immediately in OpenShift console)
ENV PYTHONUNBUFFERED=1 \
    PORT=8080

WORKDIR /app

# Install dependencies first (separate layer – cached unless requirements.txt changes)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY app.py .
COPY templates/ templates/

# OpenShift runs containers as a random non-root UID in the root group (GID 0).
# Granting group write access to /app satisfies that without creating a named user.
RUN chown -R 0:0 /app && chmod -R g=u /app

EXPOSE 8080

USER 1001

CMD ["python", "app.py"]
