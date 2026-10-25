FROM python:3.12-slim
WORKDIR /app
COPY agent ./agent
COPY sample_data ./sample_data
COPY scripts ./scripts
COPY tests ./tests
ENV SAMPLE_MODE=true PYTHONUNBUFFERED=1
# Default: runs the investigation on the bundled sample incident with no credentials.
# For live mode pass your env file: docker run --env-file .env -e SAMPLE_MODE=false ...
CMD ["python3", "-m", "agent.main", "--out", "/tmp/outputs", "--memory", "/tmp/memory"]
