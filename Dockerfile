# Keystone — minimal container for a one-command live demo (no paid services).
# Serves the FastAPI backend over the committed REAL Orbit self-index, with the
# static hero mounted at /. Real LLM brief/agent activate if a free key is provided
# via the environment (.env); otherwise everything runs deterministically offline.
FROM python:3.13-slim

WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Use the committed real Orbit index as the LIVE graph (same data as the public deploy).
ENV KEYSTONE_GRAPH_PATH=data/keystone_self_graph.duckdb \
    KEYSTONE_PREFER_LIVE=1 \
    PORT=8787

EXPOSE 8787
CMD ["python", "-m", "uvicorn", "backend.app:app", "--host", "0.0.0.0", "--port", "8787"]
