#!/usr/bin/env python3
"""
Simple helper script to insert enrichments into the database.
"""

import argparse
import sys
from pathlib import Path
from urllib import error, request

SUCCESS_CODE = 200


def send_json(json_path: Path, endpoint: str) -> bool:
    try:
        with json_path.open() as f:
            data = f.read().encode("utf-8")

        req = request.Request(
            endpoint,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with request.urlopen(req) as response:
            status: int = response.status
            print(f"Request successful, status code: {status}")
            return status == SUCCESS_CODE
    except error.HTTPError as e:
        print(f"HTTP error: {e.code} - {e.reason}")
    except error.URLError as e:
        print(f"URL error: {e.reason}")
    except Exception as e:
        print(f"Unexpected error: {e}")
    return False


def main() -> None:
    parser = argparse.ArgumentParser(description="Send JSON via POST to an endpoint.")
    parser.add_argument("json_file", help="Path to the JSON file to send")
    parser.add_argument(
        "--endpoint",
        default="http://localhost:8000/insert",
        help="Endpoint URL (default: http://localhost:8000/insert)",
    )
    args = parser.parse_args()

    success = send_json(Path(args.json_file), args.endpoint)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
