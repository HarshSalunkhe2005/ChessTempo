# Docker (not Render's native Python runtime) so we can install the
# Stockfish binary alongside the app — needed for hints and high-difficulty play.
FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    stockfish \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /repo

# Copy the whole repo (not just backend/) since the backend imports the
# `tempo` package from the repo root.
COPY pyproject.toml requirements.txt ./
COPY src ./src
COPY backend ./backend

RUN pip install --no-cache-dir -e . \
    && pip install --no-cache-dir -r backend/requirements.txt

ENV STOCKFISH_PATH=/usr/games/stockfish
ENV PORT=8000
EXPOSE 8000

WORKDIR /repo/backend
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT}"]
