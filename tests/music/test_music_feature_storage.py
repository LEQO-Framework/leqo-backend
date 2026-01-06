from pathlib import Path

import pytest

from app.model.CompileRequest import MusicDataNode
from app.music.feature_extractor import extract_music_features
from app.utils import (
    add_music_feature_to_db,
    get_music_feature_from_db,
    get_music_features_by_source_hash,
)


@pytest.mark.asyncio
async def test_music_feature_storage(engine) -> None:
    xml_text = Path("tests/music/simple.musicxml").read_text(encoding="utf-8")
    node = MusicDataNode(
        id="music-node",
        format="musicxml",
        content=xml_text,
        sourceName="simple.musicxml",
    )

    extraction = extract_music_features(node)
    feature_id = await add_music_feature_to_db(
        engine,
        source_hash=extraction.source_hash,
        fmt=extraction.format,
        schema_version=extraction.schema_version,
        features=extraction.payload,
        feature_vector=extraction.feature_vector,
        feature_vector_schema=extraction.feature_vector_schema,
        part_count=extraction.part_count,
        duration_seconds=extraction.duration_seconds,
    )

    stored = await get_music_feature_from_db(engine, feature_id)
    assert stored is not None
    assert stored["id"] == str(feature_id)
    assert stored["sourceHash"] == extraction.source_hash
    assert stored["schemaVersion"] == extraction.schema_version
    assert stored["featureVector"] is not None
    assert stored["featureVectorSchema"] is not None

    matches = await get_music_features_by_source_hash(engine, extraction.source_hash)
    assert any(entry["id"] == str(feature_id) for entry in matches)
