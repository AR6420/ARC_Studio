"""Single-variant sanity check: call TRIBE on a short text and verify is_pseudo_score=False.

Exit 0 if real TRIBE inference worked, exit 1 otherwise. Prints a one-line verdict.
"""
from __future__ import annotations

import sys
import time
import urllib.request
import urllib.error
import json

TEXT = (
    "Announcing NexaVault: enterprise cloud storage with zero-knowledge encryption "
    "and real-time collaborative editing. Your data never leaves your control."
)
URL = "http://localhost:8001/api/score"


def main() -> int:
    payload = json.dumps({"text": TEXT}).encode("utf-8")
    req = urllib.request.Request(
        URL, data=payload, headers={"Content-Type": "application/json"}, method="POST",
    )
    start = time.time()
    try:
        with urllib.request.urlopen(req, timeout=900) as resp:
            body = resp.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        print(f"FAIL: HTTP {exc.code} — {exc.read()[:300].decode('utf-8', 'replace')}")
        return 1
    except urllib.error.URLError as exc:
        print(f"FAIL: cannot reach TRIBE — {exc.reason}")
        return 1
    duration = time.time() - start
    data = json.loads(body)
    is_pseudo = bool(data.get("is_pseudo_score"))
    infer_ms = data.get("inference_time_ms", 0)
    att = data.get("attention_capture")
    print(
        f"is_pseudo={is_pseudo} inference_ms={infer_ms} wall_s={duration:.1f} "
        f"attention={att}"
    )
    return 1 if is_pseudo else 0


if __name__ == "__main__":
    sys.exit(main())
