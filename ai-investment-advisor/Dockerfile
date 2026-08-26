# Single image for both services (backend + dashboard) - they share the
# same codebase and dependencies; docker-compose.yml runs this image twice
# with different commands. See docker-compose.yml for the actual run
# config (env vars, volumes, networking between the two services).
FROM python:3.11-slim

WORKDIR /app

# Install dependencies first (separate layer) so `docker compose build`
# doesn't reinstall everything on every code change - only when
# requirements.txt itself changes.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p /app/data /app/logs

EXPOSE 8000 8501

# Overridden per-service in docker-compose.yml; this default just makes
# `docker run` on the bare image do something sensible.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
