"""memory-recall CLI.

  memory-recall [--project P]... [--k 3] [--min-score S] [--max-chars N] QUERY
  memory-recall --hook                  Claude Code UserPromptSubmit hook (event JSON on stdin)
  memory-recall serve [--host H] [--port N]

Projects come from MEMORY_RECALL_PROJECTS (name=/path,...). See README for all variables.
"""
from __future__ import annotations

import argparse
import sys
from dataclasses import replace

from .config import Settings
from .hook import default_backend_factory, hook_main
from .recall import recall
from .server import serve


def _parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="memory-recall", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("query", nargs="?", default="")
    ap.add_argument("--project", action="append", default=[])
    ap.add_argument("--k", type=int, default=None)
    ap.add_argument("--min-score", type=float, default=None)
    ap.add_argument("--max-chars", type=int, default=None)
    ap.add_argument("--hook", action="store_true", help="read a UserPromptSubmit event on stdin")
    return ap


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    settings = Settings.from_env()
    if argv[:1] == ["serve"]:
        sp = argparse.ArgumentParser(prog="memory-recall serve")
        sp.add_argument("--host", default=settings.serve_host)
        sp.add_argument("--port", type=int, default=settings.serve_port)
        a = sp.parse_args(argv[1:])
        serve(replace(settings, serve_host=a.host, serve_port=a.port), default_backend_factory(settings))
        return 0

    a = _parser().parse_args(argv)
    overrides = {k: v for k, v in (("k", a.k), ("min_score", a.min_score), ("max_chars", a.max_chars))
                 if v is not None}
    settings = replace(settings, **overrides)
    if a.hook:
        return hook_main(settings)
    projects = a.project or list(settings.projects)
    if not projects:
        _parser().error("no projects: pass --project or set MEMORY_RECALL_PROJECTS")
    block = recall(a.query, projects, settings, default_backend_factory(settings), surface="cli")
    if block:
        print(block)
    return 0


if __name__ == "__main__":
    sys.exit(main())
