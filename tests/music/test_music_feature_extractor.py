from pathlib import Path

from app.model.CompileRequest import MusicDataNode
from app.music.feature_extractor import SCHEMA_VERSION, extract_music_features


def test_extract_musicxml_features() -> None:
    xml_text = Path("tests/music/simple.musicxml").read_text(encoding="utf-8")
    node = MusicDataNode(
        id="music-node",
        format="musicxml",
        content=xml_text,
        sourceName="simple.musicxml",
    )

    extraction = extract_music_features(node)
    payload = extraction.payload

    assert payload["schema_version"] == SCHEMA_VERSION
    assert payload["source"]["partCount"] == 1

    part = payload["per_part"][0]
    assert part["instrument"] == "Piano"

    key = part["key_signatures"][0]
    assert key["fifths"] == 0
    assert key["mode"] == "major"

    time_signatures = part["time_signatures"]
    assert time_signatures[0]["beats"] == 4
    assert time_signatures[0]["beat_type"] == 4
    assert time_signatures[1]["beats"] == 3
    assert time_signatures[1]["beat_type"] == 4

    tempi = part["tempi"]
    assert tempi[0]["bpm"] == 80.0
    assert tempi[1]["bpm"] == 100.0

    assert part["dynamics"][0]["value"] == "p"
    assert part["directions"][0]["text"] == "Allegro"

    distribution = payload["computed"]["pitch_class_distribution"]
    assert distribution["counts"]["0"] == 2
    assert distribution["counts"]["2"] == 1
    assert distribution["counts"]["6"] == 1

    ambitus = payload["computed"]["ambitus"]
    assert ambitus["lowest"] == 60
    assert ambitus["highest"] == 72
    assert ambitus["semitone_span"] == 12

    feature_vector = payload["feature_vector"]
    feature_schema = payload["feature_vector_schema"]
    assert feature_vector is not None
    assert feature_schema is not None
    assert len(feature_vector) == 13
    assert feature_schema[-1] == "ambitus_span"
