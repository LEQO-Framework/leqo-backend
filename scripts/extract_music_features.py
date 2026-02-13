#!/usr/bin/env python3
"""
Extract music features from local files or via the backend API.
"""

from __future__ import annotations

import argparse
import base64
import json
import sys
import time
from pathlib import Path
from typing import Iterable
from urllib import request

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.model.CompileRequest import MusicDataNode
from app.music.feature_extractor import extract_music_features

_FORMAT_EXTENSIONS = {
    "musicxml": (".musicxml", ".xml"),
    "musicxml-xml": (".musicxml", ".xml"),
    "xml": (".xml",),
    "musicxml-mxl": (".mxl",),
    "mxl": (".mxl",),
    "midi": (".mid", ".midi"),
}


def _read_content(path: Path, fmt: str) -> str:
    data = path.read_bytes()
    if fmt in {"musicxml", "musicxml-xml", "xml"}:
        return data.decode("utf-8", errors="replace")
    return base64.b64encode(data).decode("ascii")


def _collect_paths(path: Path, fmt: str) -> list[Path]:
    if path.is_file():
        return [path]

    extensions = _FORMAT_EXTENSIONS.get(fmt, ())
    if not extensions:
        raise SystemExit(f"Unknown format for directory scan: {fmt}")

    matches: list[Path] = []
    for ext in extensions:
        matches.extend(sorted(path.glob(f"*{ext}")))
    if not matches:
        raise SystemExit(f"No *{extensions} files found in {path}")
    return matches


def _write_payload(payload: dict, output_path: Path) -> None:
    output = json.dumps(payload, indent=2, sort_keys=True)
    output_path.write_text(output, encoding="utf-8")


def _extract_local(paths: Iterable[Path], fmt: str, output: Path | None) -> None:
    for path in paths:
        content = _read_content(path, fmt)
        node = MusicDataNode(
            id="music-data",
            format=fmt,
            content=content,
            sourceName=path.name,
        )
        extracted = extract_music_features(node)
        payload = extracted.payload
        if output is not None:
            _write_payload(payload, output)
            return
        print(json.dumps(payload, indent=2, sort_keys=True))


def _send_api_batch(
    nodes: list[dict[str, object]],
    *,
    host: str,
    endpoint: str,
    timeout: float,
) -> list[dict[str, object]]:
    payload = {
        "metadata": {
            "version": "music-feature-batch",
            "name": "music-feature-batch",
            "description": "Extract music features via API",
            "author": "script",
        },
        "compilation_target": "qasm",
        "nodes": nodes,
        "edges": [],
    }
    data = json.dumps(payload).encode("utf-8")
    url = host.rstrip("/") + endpoint
    req = request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with request.urlopen(req, timeout=timeout) as response:
        body = response.read().decode("utf-8")
    result = json.loads(body)
    if not isinstance(result, list):
        raise ValueError(f"Unexpected API response: {result}")
    return [item for item in result if isinstance(item, dict)]


def _extract_via_api(
    paths: list[Path],
    fmt: str,
    output_dir: Path,
    *,
    host: str,
    endpoint: str,
    batch_size: int,
    sleep_s: float,
    overwrite: bool,
    timeout: float,
    output_overrides: dict[str, Path] | None = None,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    errors: list[str] = []

    for start in range(0, len(paths), batch_size):
        batch = paths[start : start + batch_size]
        nodes: list[dict[str, object]] = []
        pending: list[Path] = []
        for path in batch:
            out_path = output_dir / f"{path.stem}.json"
            if out_path.exists() and not overwrite:
                continue
            content = _read_content(path, fmt)
            nodes.append(
                {
                    "id": path.stem,
                    "type": "music-data",
                    "format": fmt,
                    "content": content,
                    "sourceName": path.name,
                }
            )
            pending.append(path)

        if not nodes:
            continue

        try:
            results = _send_api_batch(
                nodes, host=host, endpoint=endpoint, timeout=timeout
            )
            results_by_id = {
                item.get("id"): item for item in results if "id" in item
            }
            for path in pending:
                result = results_by_id.get(path.stem)
                if result is None:
                    raise ValueError(f"Missing API result for {path.name}")
                implementation = result.get("implementation")
                if not isinstance(implementation, str):
                    raise ValueError(f"Missing implementation for {path.name}")
                impl_payload = json.loads(implementation)
                features = impl_payload.get("features")
                if features is None:
                    raise ValueError(f"No features in result for {path.name}")
                override = (
                    output_overrides.get(path.stem)
                    if output_overrides is not None
                    else None
                )
                target = override if override is not None else output_dir / f"{path.stem}.json"
                _write_payload(features, target)
        except Exception as exc:
            for path in pending:
                errors.append(f"{path.name}: {exc}")

        if sleep_s:
            time.sleep(sleep_s)

    if errors:
        (output_dir / "_errors_api.txt").write_text(
            "\n".join(errors), encoding="utf-8"
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="Extract music features")
    parser.add_argument("path", help="Path to MusicXML/MXL/MIDI file or directory")
    parser.add_argument("--format", default="musicxml", help="Declared input format")
    parser.add_argument("--output", help="Write JSON output to file")
    parser.add_argument("--output-dir", help="Write outputs for batches to this dir")
    parser.add_argument(
        "--api",
        action="store_true",
        help="Use backend API instead of local extractor",
    )
    parser.add_argument(
        "--host",
        default="http://localhost:8000",
        help="Backend API host (default: http://localhost:8000)",
    )
    parser.add_argument(
        "--endpoint",
        default="/debug/enrich",
        help="Backend API endpoint (default: /debug/enrich)",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=10,
        help="Number of files per API request (default: 10)",
    )
    parser.add_argument(
        "--sleep",
        type=float,
        default=0.02,
        help="Seconds to sleep between API batches (default: 0.02)",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=60.0,
        help="API request timeout in seconds (default: 60)",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite existing output files",
    )
    args = parser.parse_args()

    path = Path(args.path)
    if not path.exists():
        raise SystemExit(f"File not found: {path}")

    fmt = args.format.lower()
    paths = _collect_paths(path, fmt)

    if args.api:
        if args.output and len(paths) > 1:
            raise SystemExit("--output is only supported for single-file input")
        output_dir = Path(args.output_dir) if args.output_dir else None
        if output_dir is None and len(paths) > 1:
            raise SystemExit("--output-dir is required when using --api on a directory")
        output_overrides = None
        if len(paths) == 1 and args.output:
            output_overrides = {paths[0].stem: Path(args.output)}
            output_dir = Path(args.output).parent
        _extract_via_api(
            paths,
            fmt,
            output_dir or Path.cwd(),
            host=args.host,
            endpoint=args.endpoint,
            batch_size=max(1, args.batch_size),
            sleep_s=max(0.0, args.sleep),
            overwrite=args.overwrite,
            timeout=max(1.0, args.timeout),
            output_overrides=output_overrides,
        )
        return

    if args.output and len(paths) > 1:
        raise SystemExit("--output is only supported for single-file input")
    output_path = Path(args.output) if args.output else None
    _extract_local(paths, fmt, output_path)


if __name__ == "__main__":
    main()
