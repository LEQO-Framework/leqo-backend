"""
Feature extraction utilities for music data (prefer MusicXML).
"""

from __future__ import annotations

import base64
import hashlib
import io
import zipfile
from dataclasses import dataclass
from typing import Any
from xml.etree import ElementTree as ET

from app.model.CompileRequest import MusicDataNode

SCHEMA_VERSION = "music-features/v1"

_STEP_TO_SEMITONE = {
    "C": 0,
    "D": 2,
    "E": 4,
    "F": 5,
    "G": 7,
    "A": 9,
    "B": 11,
}


@dataclass(frozen=True)
class MusicFeatureExtraction:
    """
    Container for extracted music features and storage metadata.
    """

    source_hash: str
    format: str
    schema_version: str
    payload: dict[str, Any]
    feature_vector: list[float] | None
    feature_vector_schema: list[str] | None
    part_count: int | None
    duration_seconds: float | None


def extract_music_features(node: MusicDataNode) -> MusicFeatureExtraction:
    """
    Extract structured features from a MusicDataNode.
    """

    warnings: list[str] = []
    fmt = node.format.lower() if node.format else "unknown"
    xml_text, source_bytes = _load_musicxml_text(node.content, fmt, warnings)
    source_hash = _sha256_hex(source_bytes)

    if xml_text is None:
        if fmt == "midi":
            payload, note_count = _extract_music21_payload_from_bytes(
                source_bytes, source_hash, fmt, node.sourceName, warnings
            )
            feature_vector, feature_vector_schema = _build_feature_vector(
                payload, note_count
            )
            payload["feature_vector"] = feature_vector
            payload["feature_vector_schema"] = feature_vector_schema
            part_count = payload.get("source", {}).get("partCount")
            return MusicFeatureExtraction(
                source_hash=source_hash,
                format=fmt,
                schema_version=SCHEMA_VERSION,
                payload=payload,
                feature_vector=feature_vector,
                feature_vector_schema=feature_vector_schema,
                part_count=part_count,
                duration_seconds=None,
            )

        warnings.append(f"Unsupported or unreadable format: {fmt}")
        payload = _empty_payload(
            source_hash, fmt, node.sourceName, warnings, part_count=None
        )
        return MusicFeatureExtraction(
            source_hash=source_hash,
            format=fmt,
            schema_version=SCHEMA_VERSION,
            payload=payload,
            feature_vector=None,
            feature_vector_schema=None,
            part_count=None,
            duration_seconds=None,
        )

    payload, note_count = _extract_musicxml_payload(
        xml_text, source_hash, fmt, node.sourceName, warnings
    )

    feature_vector, feature_vector_schema = _build_feature_vector(
        payload, note_count
    )
    payload["feature_vector"] = feature_vector
    payload["feature_vector_schema"] = feature_vector_schema

    part_count = payload.get("source", {}).get("partCount")
    return MusicFeatureExtraction(
        source_hash=source_hash,
        format=fmt,
        schema_version=SCHEMA_VERSION,
        payload=payload,
        feature_vector=feature_vector,
        feature_vector_schema=feature_vector_schema,
        part_count=part_count,
        duration_seconds=None,
    )


def _empty_payload(
    source_hash: str,
    fmt: str,
    source_name: str | None,
    warnings: list[str],
    *,
    part_count: int | None,
) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "source": {
            "format": fmt,
            "sourceName": source_name,
            "hash": source_hash,
            "partCount": part_count,
        },
        "per_part": [],
        "global": {"meter_changes": [], "tempo_changes": []},
        "computed": {
            "ambitus": {"lowest": None, "highest": None, "semitone_span": None},
            "pitch_class_distribution": {
                "counts": {str(i): 0 for i in range(12)},
                "normalized": {str(i): 0.0 for i in range(12)},
            },
        },
        "feature_vector": None,
        "feature_vector_schema": None,
        "warnings": warnings,
    }


def _load_musicxml_text(
    content: str, fmt: str, warnings: list[str]
) -> tuple[str | None, bytes]:
    """
    Return MusicXML text and raw source bytes for hashing.
    """

    if content is None:
        warnings.append("Missing content")
        return None, b""

    stripped = content.lstrip()
    if fmt in {"musicxml", "musicxml-xml", "xml"} or stripped.startswith("<"):
        source_bytes = content.encode("utf-8", errors="replace")
        return content, source_bytes

    if fmt in {"musicxml-mxl", "mxl"}:
        try:
            decoded = base64.b64decode(content)
            xml_text = _extract_xml_from_mxl(decoded, warnings)
            return xml_text, decoded
        except Exception as exc:  # pragma: no cover - defensive
            warnings.append(f"Failed to decode MXL content: {exc}")
            source_bytes = content.encode("utf-8", errors="replace")
            return None, source_bytes

    if fmt == "midi":
        try:
            decoded = base64.b64decode(content)
            return None, decoded
        except Exception as exc:
            warnings.append(f"Failed to decode MIDI content: {exc}")
            return None, content.encode("utf-8", errors="replace")

    return None, content.encode("utf-8", errors="replace")


def _extract_xml_from_mxl(data: bytes, warnings: list[str]) -> str | None:
    """
    Extract the MusicXML payload from an MXL zip archive.
    """

    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            if "META-INF/container.xml" in archive.namelist():
                container_xml = archive.read("META-INF/container.xml")
                root_path = _parse_container_rootfile(container_xml)
                if root_path and root_path in archive.namelist():
                    return archive.read(root_path).decode("utf-8", errors="replace")

            for name in archive.namelist():
                if name.lower().endswith((".musicxml", ".xml")) and (
                    "meta-inf" not in name.lower()
                ):
                    return archive.read(name).decode("utf-8", errors="replace")
    except zipfile.BadZipFile:
        warnings.append("Invalid MXL archive")
    return None


def _parse_container_rootfile(container_xml: bytes) -> str | None:
    try:
        root = ET.fromstring(container_xml)
    except ET.ParseError:
        return None

    for rootfile in root.findall(".//{*}rootfile"):
        full_path = rootfile.get("full-path")
        if full_path:
            return full_path
    return None


def _sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _extract_musicxml_payload(
    xml_text: str,
    source_hash: str,
    fmt: str,
    source_name: str | None,
    warnings: list[str],
) -> tuple[dict[str, Any], int]:
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as exc:
        warnings.append(f"Failed to parse MusicXML: {exc}")
        payload = _empty_payload(source_hash, fmt, source_name, warnings, part_count=0)
        return payload, 0

    part_list = _parse_part_list(root)
    per_part: list[dict[str, Any]] = []
    pitch_class_counts = {i: 0 for i in range(12)}
    min_midi: int | None = None
    max_midi: int | None = None
    note_count = 0
    global_time_changes: list[dict[str, Any]] = []
    global_tempo_changes: list[dict[str, Any]] = []

    for part in root.findall(".//{*}part"):
        part_id = part.get("id") or f"part-{len(per_part) + 1}"
        instrument = part_list.get(part_id)
        part_data = {
            "part_id": part_id,
            "instrument": instrument,
            "key_signatures": [],
            "time_signatures": [],
            "clefs": [],
            "tempi": [],
            "dynamics": [],
            "directions": [],
        }

        for measure in part.findall("./{*}measure"):
            measure_number = _parse_measure_number(measure.get("number"))

            for attributes in measure.findall("./{*}attributes"):
                _collect_key_signatures(
                    attributes, part_data["key_signatures"], measure_number
                )
                _collect_time_signatures(
                    attributes, part_data["time_signatures"], measure_number
                )
                _collect_clefs(attributes, part_data["clefs"], measure_number)

            _collect_directions(measure, part_data, measure_number)

            for note in measure.findall(".//{*}note"):
                midi, pc = _pitch_to_midi_and_class(note)
                if midi is None or pc is None:
                    continue
                note_count += 1
                pitch_class_counts[pc] += 1
                min_midi = midi if min_midi is None else min(min_midi, midi)
                max_midi = midi if max_midi is None else max(max_midi, midi)

        per_part.append(part_data)
        global_time_changes.extend(part_data["time_signatures"])
        global_tempo_changes.extend(part_data["tempi"])

    if min_midi is None or max_midi is None:
        alt_ambitus = _try_music21_ambitus(xml_text, warnings)
        if alt_ambitus is not None:
            min_midi, max_midi = alt_ambitus

    global_payload = {
        "meter_changes": _unique_changes(
            global_time_changes, ("measure", "beats", "beat_type")
        ),
        "tempo_changes": _unique_changes(global_tempo_changes, ("measure", "bpm")),
    }

    ambitus = {
        "lowest": min_midi,
        "highest": max_midi,
        "semitone_span": None
        if min_midi is None or max_midi is None
        else max_midi - min_midi,
    }

    total = sum(pitch_class_counts.values())
    if total == 0:
        warnings.append("No pitched notes found for pitch class distribution")
    normalized = {
        str(pc): (pitch_class_counts[pc] / total if total > 0 else 0.0)
        for pc in range(12)
    }
    counts = {str(pc): pitch_class_counts[pc] for pc in range(12)}

    payload = {
        "schema_version": SCHEMA_VERSION,
        "source": {
            "format": fmt,
            "sourceName": source_name,
            "hash": source_hash,
            "partCount": len(per_part),
        },
        "per_part": per_part,
        "global": global_payload,
        "computed": {
            "ambitus": ambitus,
            "pitch_class_distribution": {"counts": counts, "normalized": normalized},
        },
        "feature_vector": None,
        "feature_vector_schema": None,
        "warnings": warnings,
    }
    return payload, note_count


def _extract_music21_payload_from_bytes(
    data: bytes,
    source_hash: str,
    fmt: str,
    source_name: str | None,
    warnings: list[str],
) -> tuple[dict[str, Any], int]:
    try:
        from music21 import converter  # type: ignore[import-not-found]
    except Exception:
        warnings.append("music21 not available for MIDI parsing")
        return (
            _empty_payload(source_hash, fmt, source_name, warnings, part_count=None),
            0,
        )

    try:
        score = converter.parseData(data)
    except Exception as exc:
        warnings.append(f"music21 failed to parse MIDI content: {exc}")
        return (
            _empty_payload(source_hash, fmt, source_name, warnings, part_count=None),
            0,
        )

    pitches = [pitch.midi for pitch in score.pitches]
    pitch_class_counts = {i: 0 for i in range(12)}
    for midi in pitches:
        pitch_class_counts[midi % 12] += 1

    total = len(pitches)
    if total == 0:
        warnings.append("No pitched notes found in MIDI data")

    normalized = {
        str(pc): (pitch_class_counts[pc] / total if total > 0 else 0.0)
        for pc in range(12)
    }
    counts = {str(pc): pitch_class_counts[pc] for pc in range(12)}

    min_midi = min(pitches) if pitches else None
    max_midi = max(pitches) if pitches else None

    payload = _empty_payload(
        source_hash, fmt, source_name, warnings, part_count=len(score.parts)
    )
    payload["computed"]["ambitus"] = {
        "lowest": min_midi,
        "highest": max_midi,
        "semitone_span": None
        if min_midi is None or max_midi is None
        else max_midi - min_midi,
    }
    payload["computed"]["pitch_class_distribution"] = {
        "counts": counts,
        "normalized": normalized,
    }
    return payload, total


def _try_music21_ambitus(
    xml_text: str, warnings: list[str]
) -> tuple[int | None, int | None] | None:
    try:
        from music21 import converter  # type: ignore[import-not-found]
    except Exception:
        return None

    try:
        score = converter.parseData(xml_text)
        pitches = [pitch.midi for pitch in score.pitches]
        if not pitches:
            return None
        return min(pitches), max(pitches)
    except Exception as exc:
        warnings.append(f"music21 ambitus fallback failed: {exc}")
        return None


def _parse_part_list(root: ET.Element) -> dict[str, str | None]:
    part_map: dict[str, str | None] = {}
    for score_part in root.findall(".//{*}part-list/{*}score-part"):
        part_id = score_part.get("id")
        if part_id is None:
            continue
        part_name = _get_text(score_part.find("./{*}part-name"))
        part_map[part_id] = part_name
    return part_map


def _collect_key_signatures(
    attributes: ET.Element,
    bucket: list[dict[str, Any]],
    measure_number: int | str | None,
) -> None:
    for key in attributes.findall("./{*}key"):
        fifths = _parse_int(_get_text(key.find("./{*}fifths")))
        mode = _get_text(key.find("./{*}mode"))
        if fifths is None and mode is None:
            continue
        bucket.append(
            {
                "measure": measure_number,
                "fifths": fifths,
                "mode": mode,
            }
        )


def _collect_time_signatures(
    attributes: ET.Element,
    bucket: list[dict[str, Any]],
    measure_number: int | str | None,
) -> None:
    for time in attributes.findall("./{*}time"):
        beats = _parse_int(_get_text(time.find("./{*}beats")))
        beat_type = _parse_int(_get_text(time.find("./{*}beat-type")))
        if beats is None or beat_type is None:
            continue
        bucket.append(
            {
                "measure": measure_number,
                "beats": beats,
                "beat_type": beat_type,
            }
        )


def _collect_clefs(
    attributes: ET.Element,
    bucket: list[dict[str, Any]],
    measure_number: int | str | None,
) -> None:
    for clef in attributes.findall("./{*}clef"):
        sign = _get_text(clef.find("./{*}sign"))
        line = _parse_int(_get_text(clef.find("./{*}line")))
        if sign is None and line is None:
            continue
        bucket.append({"measure": measure_number, "sign": sign, "line": line})


def _collect_directions(
    measure: ET.Element,
    part_data: dict[str, Any],
    measure_number: int | str | None,
) -> None:
    for direction in measure.findall("./{*}direction"):
        for direction_type in direction.findall("./{*}direction-type"):
            for dynamics in direction_type.findall("./{*}dynamics"):
                for child in list(dynamics):
                    value = _strip_tag(child.tag)
                    if value:
                        part_data["dynamics"].append(
                            {"measure": measure_number, "value": value}
                        )
            for words in direction_type.findall("./{*}words"):
                text = _get_text(words)
                if text:
                    part_data["directions"].append(
                        {"measure": measure_number, "text": text}
                    )

        sound = direction.find("./{*}sound")
        if sound is not None and "tempo" in sound.attrib:
            bpm = _parse_float(sound.attrib.get("tempo"))
            if bpm is not None:
                part_data["tempi"].append({"measure": measure_number, "bpm": bpm})


def _pitch_to_midi_and_class(note: ET.Element) -> tuple[int | None, int | None]:
    if note.find("./{*}rest") is not None:
        return None, None

    pitch = note.find("./{*}pitch")
    if pitch is None:
        return None, None

    step = _get_text(pitch.find("./{*}step"))
    octave = _parse_int(_get_text(pitch.find("./{*}octave")))
    if step is None or octave is None:
        return None, None

    semitone = _STEP_TO_SEMITONE.get(step.upper())
    if semitone is None:
        return None, None

    alter = _parse_int(_get_text(pitch.find("./{*}alter"))) or 0
    midi = (octave + 1) * 12 + semitone + alter
    pitch_class = (semitone + alter) % 12
    return midi, pitch_class


def _build_feature_vector(
    payload: dict[str, Any], note_count: int
) -> tuple[list[float] | None, list[str] | None]:
    if note_count == 0:
        return None, None

    distribution = payload.get("computed", {}).get("pitch_class_distribution", {})
    normalized = distribution.get("normalized", {})
    vector = [float(normalized.get(str(i), 0.0)) for i in range(12)]

    ambitus = payload.get("computed", {}).get("ambitus", {})
    span = ambitus.get("semitone_span")
    vector.append(float(span) if span is not None else 0.0)

    schema = [f"pitch_class_norm_{i}" for i in range(12)] + ["ambitus_span"]
    return vector, schema


def _unique_changes(
    items: list[dict[str, Any]], keys: tuple[str, ...]
) -> list[dict[str, Any]]:
    seen: set[tuple[Any, ...]] = set()
    unique: list[dict[str, Any]] = []
    for item in items:
        key = tuple(item.get(k) for k in keys)
        if key in seen:
            continue
        seen.add(key)
        unique.append(item)
    unique.sort(key=_measure_sort_key)
    return unique


def _measure_sort_key(item: dict[str, Any]) -> tuple[int, str]:
    measure = item.get("measure")
    if isinstance(measure, int):
        return (measure, "")
    if isinstance(measure, str) and measure.isdigit():
        return (int(measure), "")
    return (10**9, str(measure))


def _parse_measure_number(value: str | None) -> int | str | None:
    if value is None:
        return None
    if value.isdigit():
        return int(value)
    return value


def _get_text(element: ET.Element | None) -> str | None:
    if element is None or element.text is None:
        return None
    text = element.text.strip()
    return text if text else None


def _parse_int(value: str | None) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except ValueError:
        return None


def _parse_float(value: str | None) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except ValueError:
        return None


def _strip_tag(tag: str) -> str:
    return tag.split("}")[-1] if "}" in tag else tag
