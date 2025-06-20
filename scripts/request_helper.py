#!/usr/bin/env python3
"""
Simple helper script to communicate with the LEQO backend.
"""

import argparse
import json
import sys
from pathlib import Path
from time import sleep
from urllib import request

POLL_INTERVAL = 0.1
MAX_ATTEMPTS = 5
SIMPLE_ENDPOINTS = ("/insert", "/debug/compile", "/debug/enrich")
POLLING_ENDPOINTS = ("/compile", "/enrich")


def simple_send_json(json_path: Path, endpoint: str) -> None:
    with json_path.open() as f:
        data = f.read().encode("utf-8")
    with request.urlopen(
        request.Request(
            endpoint,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
    ) as response:
        print(response.read().decode("utf-8"))


def polling_send_json(json_path: Path, host: str, endpoint: str) -> None:
    with json_path.open() as f:
        data = f.read().encode("utf-8")

    with request.urlopen(
        request.Request(
            host + endpoint,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
    ) as response:
        uuid = json.loads(response.read().decode("utf-8"))["uuid"]

    done = False
    for _ in range(MAX_ATTEMPTS):
        with request.urlopen(
            request.Request(host + f"/status/{uuid}", method="GET")
        ) as response:
            content = json.loads(response.read().decode("utf-8"))
            if content["status"] == "completed":
                done = True
                break
            if content["status"] == "failed":
                print(content["result"])
                sys.exit(1)
        sleep(POLL_INTERVAL)
    assert done, f"No success after {MAX_ATTEMPTS * POLL_INTERVAL}s"

    with request.urlopen(
        request.Request(host + f"/result/{uuid}", method="GET")
    ) as response:
        print(response.read().decode("utf-8"))


def main() -> None:
    parser = argparse.ArgumentParser(description="Send JSON via POST to an endpoint.")
    parser.add_argument("json_file", help="Path to the JSON file to send")
    parser.add_argument("endpoint", help="Endpoint to use for sending")
    parser.add_argument(
        "--host",
        default="http://localhost:8000",
        help="Host URL (default: http://localhost:8000)",
    )
    args = parser.parse_args()

    assert args.endpoint in (*SIMPLE_ENDPOINTS, *POLLING_ENDPOINTS), (
        f"Invalid endpoint: {args.endpoint}"
    )

    json_file = Path(args.json_file)
    if args.endpoint in SIMPLE_ENDPOINTS:
        simple_send_json(json_file, args.host + args.endpoint)
    else:
        polling_send_json(json_file, args.host, args.endpoint)


if __name__ == "__main__":
    main()
