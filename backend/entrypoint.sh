#!/bin/sh
set -e

# Migrate, then seed, exactly once, before any uvicorn worker starts serving.
# Both steps run here rather than as FastAPI startup hooks because --workers 2
# would otherwise run them concurrently in each worker process.
alembic upgrade head
python -c "from server import seed; seed()"

exec uvicorn server:app --host 0.0.0.0 --port 8001 --workers 2
