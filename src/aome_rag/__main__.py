"""Command-line entry point: `uv run aomerag`.

Runs the AomeRAG backend under uvicorn. Workers is LOCKED to 1: Zvec writes are
single-process exclusive, so multiple worker processes would corrupt the vector store.
(If you ever need >1 process, switch to a server-mode vector DB or split read/write first.)
"""

from __future__ import annotations

import argparse

import uvicorn


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="aomerag",
        description="Run the AomeRAG backend (FastAPI + uvicorn). Workers locked to 1 "
        "(Zvec writes are single-process exclusive).",
    )
    parser.add_argument("--host", default="localhost")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--reload", action="store_true", help="auto-reload on code changes (dev)")
    args = parser.parse_args()

    uvicorn.run(
        "aome_rag.main:app",
        host=args.host,
        port=args.port,
        workers=1,  # locked: Zvec writes are single-process exclusive
        reload=args.reload,
    )


if __name__ == "__main__":
    main()
