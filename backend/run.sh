#!/usr/bin/zsh

set -a
source .env.local
set +a

alembic upgrade head && python -m app.seed && uvicorn app.main:app --host 0.0.0.0 --port 8000

