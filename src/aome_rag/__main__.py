"""命令行入口：`uv run aomerag`。用 uvicorn 启动后端，worker 锁死为 1（Zvec 写独占）。"""

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
