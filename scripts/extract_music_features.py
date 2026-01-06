#!/usr/bin/env python3
"""
Extract music features from a local file for quick testing.
"""

from __future__ import annotations

import argparse
import base64
import json
from pathlib import Path

from app.model.CompileRequest import MusicDataNode
from app.music.feature_extractor import extract_music_features


def _read_content(path: Path, fmt: str) -> str:
    data = path.read_bytes()
    if fmt in {"musicxml", "musicxml-xml", "xml"}:
        return data.decode("utf-8", errors="replace")
    return base64.b64encode(data).decode("ascii")


def main() -> None:
    parser = argparse.ArgumentParser(description="Extract music features")
    parser.add_argument("path", help="Path to MusicXML/MXL/MIDI file")
    parser.add_argument("--format", default="musicxml", help="Declared input format")
    parser.add_argument("--output", help="Write JSON output to file")
    args = parser.parse_args()

    path = Path(args.path)
    if not path.exists():
        raise SystemExit(f"File not found: {path}")

    fmt = args.format.lower()
    content = _read_content(path, fmt)
    node = MusicDataNode(
        id="music-data",
        format=fmt,
        content=content,
        sourceName=path.name,
    )
    extracted = extract_music_features(node)
    payload = extracted.payload

    output = json.dumps(payload, indent=2, sort_keys=True)
    if args.output:
        Path(args.output).write_text(output, encoding="utf-8")
        return
    print(output)


if __name__ == "__main__":
    main()
