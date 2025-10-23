#!/usr/bin/env python3
"""
Utility script to interact with the LEQO backend from the command line.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from time import sleep
from urllib import error, request

POLL_INTERVAL = 0.1
MAX_ATTEMPTS = 5
SIMPLE_ENDPOINTS = ("/insert", "/debug/compile", "/debug/enrich")
POLLING_ENDPOINTS = ("/compile", "/enrich")


def simple_send_json(json_path: Path, endpoint: str) -> None:
    """Send a payload to a synchronous endpoint."""

    with json_path.open("rb") as f:
        data = f.read()

    req = request.Request(
        endpoint, data=data, headers={"Content-Type": "application/json"}, method="POST"
    )
    with request.urlopen(req) as response:
        print(response.read().decode("utf-8"))


def polling_send_json(json_path: Path, host: str, endpoint: str) -> None:
    """Send a payload to a polling endpoint and display its results."""

    with json_path.open("rb") as f:
        data = f.read()

    submit_request = request.Request(
        host + endpoint,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with request.urlopen(submit_request) as response:
        status_url = response.url

    result_url: str | None = None
    for _ in range(MAX_ATTEMPTS):
        with request.urlopen(request.Request(status_url, method="GET")) as response:
            payload = json.loads(response.read().decode("utf-8"))
        status = payload["status"]
        if status == "completed":
            result_url = payload["result"]
            break
        if status == "failed":
            print(payload["result"])
            sys.exit(1)
        sleep(POLL_INTERVAL)

    if result_url is None:
        raise TimeoutError(f"No success after {MAX_ATTEMPTS * POLL_INTERVAL}s")

    print(f"Result URL: {result_url}")
    with request.urlopen(request.Request(result_url, method="GET")) as response:
        print("--- Result ---")
        print(response.read().decode("utf-8"))
        link_header = response.headers.get("Link")
        if link_header and 'rel="request"' in link_header:
            print(f"Link Header: {link_header}")
            request_url = link_header.split("<", 1)[1].split(">", 1)[0]
            fetch_request_payload(request_url)


def fetch_result(host: str, uuid: str | None = None) -> None:
    """Fetch results either as an overview or by UUID."""

    endpoint = f"{host}/results"
    if uuid:
        endpoint += f"?uuid={uuid}"

    with request.urlopen(request.Request(endpoint, method="GET")) as response:
        body = response.read().decode("utf-8")
        print(body)
        link_header = response.headers.get("Link")
        if link_header and 'rel="request"' in link_header:
            print(f"Link Header: {link_header}")


def fetch_request_payload(url: str) -> None:
    """Retrieve the stored compile request payload."""

    try:
        with request.urlopen(request.Request(url, method="GET")) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except error.HTTPError as exc:  # pragma: no cover - manual usage
        print(f"Failed to fetch request payload: {exc}")
        return

    print("--- Request Payload ---")
    print(json.dumps(payload, indent=2))


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Interact with the LEQO backend.")
    subparsers = parser.add_subparsers(dest="command")

    send_parser = subparsers.add_parser(
        "send", help="Send a request payload to an endpoint"
    )
    send_parser.add_argument("json_file", help="Path to the JSON payload file")
    send_parser.add_argument("endpoint", help="Endpoint to use")
    send_parser.add_argument(
        "--host",
        default="http://localhost:8000",
        help="Host URL (default: http://localhost:8000)",
    )

    result_parser = subparsers.add_parser(
        "result", help="Fetch results overview or a specific result"
    )
    result_parser.add_argument(
        "--host",
        default="http://localhost:8000",
        help="Host URL (default: http://localhost:8000)",
    )
    result_parser.add_argument(
        "--uuid",
        default=None,
        help="Optional UUID to fetch a single result",
    )

    request_parser = subparsers.add_parser(
        "request", help="Fetch the stored compile request payload by UUID"
    )
    request_parser.add_argument("uuid", help="UUID of the compile request")
    request_parser.add_argument(
        "--host",
        default="http://localhost:8000",
        help="Host URL (default: http://localhost:8000)",
    )

    return parser


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        return

    if args.command == "send":
        assert args.endpoint in (*SIMPLE_ENDPOINTS, *POLLING_ENDPOINTS), (
            f"Invalid endpoint: {args.endpoint}"
        )
        json_file = Path(args.json_file)
        if args.endpoint in SIMPLE_ENDPOINTS:
            simple_send_json(json_file, args.host + args.endpoint)
        else:
            polling_send_json(json_file, args.host, args.endpoint)
        return

    if args.command == "result":
        fetch_result(args.host, args.uuid)
        return

    if args.command == "request":
        fetch_request_payload(f"{args.host}/request/{args.uuid}")
        return

    parser.error(f"Unknown command {args.command}")  # pragma: no cover - defensive


if __name__ == "__main__":
    main()
