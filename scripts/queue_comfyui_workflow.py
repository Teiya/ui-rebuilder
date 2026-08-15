from __future__ import annotations

import argparse
import json
import urllib.request
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description="Queue a ComfyUI API-format workflow.")
    parser.add_argument("workflow", type=Path)
    parser.add_argument("--server", default="http://127.0.0.1:8190")
    parser.add_argument("--client-id", default="ui-rebuilder")
    args = parser.parse_args()

    workflow = json.loads(args.workflow.read_text(encoding="utf-8"))
    payload = json.dumps({"prompt": workflow, "client_id": args.client_id}).encode("utf-8")
    request = urllib.request.Request(
        f"{args.server.rstrip('/')}/prompt",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        print(response.read().decode("utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
