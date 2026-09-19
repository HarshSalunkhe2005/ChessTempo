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

# Plain `pip install torch` on Linux pulls the CUDA-enabled build, which
# drags in several hundred MB of nvidia-* runtime packages we never use
# (this box has no GPU) — real weight on a 512MB free-tier instance.
# Installing the CPU-only wheel first means the later `-r
# backend/requirements.txt` (which also lists torch, unpinned to a
# specific build) finds the constraint already satisfied and leaves it
# alone rather than re-resolving against the default index.
RUN pip install --no-cache-dir --index-url https://download.pytorch.org/whl/cpu torch \
    && pip install --no-cache-dir -e . \
    && pip install --no-cache-dir -r backend/requirements.txt

ENV STOCKFISH_PATH=/usr/games/stockfish
ENV PORT=8000
EXPOSE 8000

WORKDIR /repo/backend
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT}"]
