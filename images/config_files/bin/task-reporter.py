#!/usr/bin/env python3
"""
Task reporter for BeakerHub node image tasks.

Reads the stdout file produced by an init container (e.g., context dump JSON)
and POSTs it to the BeakerHub API callback URL. Stderr output from the init
container is logged separately for diagnostics.

Environment variables:
    CALLBACK_URL   - URL to POST results to (required)
    CALLBACK_TOKEN - Auth token for the callback (required)
    STDOUT_PATH    - Path to the stdout output file (default: /output/stdout)
    STDERR_PATH    - Path to the stderr output file (default: /output/stderr)
"""
import json
import os
import sys
import time
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError


CALLBACK_URL = os.environ.get("CALLBACK_URL")
CALLBACK_TOKEN = os.environ.get("CALLBACK_TOKEN")
STDOUT_PATH = os.environ.get("STDOUT_PATH", "/output/stdout")
STDERR_PATH = os.environ.get("STDERR_PATH", "/output/stderr")
MAX_WAIT_SECONDS = 30
POLL_INTERVAL = 1


def _read_file(path: str, label: str) -> str | None:
    """Read a file if it exists, returning its content or None."""
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r") as f:
            return f.read()
    except OSError as e:
        print(f"WARNING: Failed to read {label} file {path}: {e}", file=sys.stderr)
        return None


def main() -> int:
    if not CALLBACK_URL:
        print("ERROR: CALLBACK_URL environment variable is required", file=sys.stderr)
        return 1
    if not CALLBACK_TOKEN:
        print("ERROR: CALLBACK_TOKEN environment variable is required", file=sys.stderr)
        return 1

    # Wait for the stdout file to appear (init container may still be writing)
    elapsed = 0
    while not os.path.exists(STDOUT_PATH):
        if elapsed >= MAX_WAIT_SECONDS:
            print(f"ERROR: Stdout file {STDOUT_PATH} not found after {MAX_WAIT_SECONDS}s", file=sys.stderr)
            return 1
        time.sleep(POLL_INTERVAL)
        elapsed += POLL_INTERVAL

    # Read stdout (the primary output)
    content = _read_file(STDOUT_PATH, "stdout")
    if content is None:
        print(f"ERROR: Failed to read stdout file {STDOUT_PATH}", file=sys.stderr)
        return 1

    # Read and log stderr for diagnostics
    stderr_content = _read_file(STDERR_PATH, "stderr")
    if stderr_content and stderr_content.strip():
        print(f"Init container stderr output:\n{stderr_content.strip()}", file=sys.stderr)

    if not content.strip():
        print(f"ERROR: Stdout file {STDOUT_PATH} is empty", file=sys.stderr)
        return 1

    # Validate it's valid JSON
    try:
        json.loads(content)
    except json.JSONDecodeError as e:
        print(f"ERROR: Stdout file is not valid JSON: {e}", file=sys.stderr)
        print(f"Content (first 500 chars): {content[:500]}", file=sys.stderr)
        return 1

    # POST to callback URL
    print(f"Sending {len(content)} bytes to {CALLBACK_URL}")
    req = Request(
        CALLBACK_URL,
        data=content.encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {CALLBACK_TOKEN}",
        },
        method="POST",
    )

    try:
        with urlopen(req, timeout=30) as resp:
            status = resp.status
            body = resp.read().decode("utf-8", errors="replace")
            print(f"Callback response: {status} {body[:500]}")
            if status >= 400:
                print(f"ERROR: Callback returned status {status}", file=sys.stderr)
                return 1
    except HTTPError as e:
        body = e.read().decode("utf-8", errors="replace") if e.fp else ""
        print(f"ERROR: Callback HTTP error {e.code}: {body[:500]}", file=sys.stderr)
        return 1
    except URLError as e:
        print(f"ERROR: Callback connection error: {e.reason}", file=sys.stderr)
        return 1

    print("Reporter completed successfully")
    return 0


if __name__ == "__main__":
    sys.exit(main())
