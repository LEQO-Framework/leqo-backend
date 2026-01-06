"""
Enricher strategy for music feature extraction nodes.
"""

import json
from typing import override

from sqlalchemy.ext.asyncio import AsyncEngine

from app.enricher import (
    Constraints,
    EnricherStrategy,
    EnrichmentResult,
    ImplementationMetaData,
)
from app.model.CompileRequest import ImplementationNode, MusicDataNode
from app.model.CompileRequest import Node as FrontendNode
from app.music.feature_extractor import extract_music_features
from app.utils import add_music_feature_to_db


class MusicFeatureEnricherStrategy(EnricherStrategy):
    """
    Extract features from MusicDataNode and persist them in a dedicated table.
    """

    def __init__(self, engine: AsyncEngine):
        self.engine = engine

    @override
    async def _enrich_impl(
        self, node: FrontendNode, constraints: Constraints | None
    ) -> list[EnrichmentResult]:
        if not isinstance(node, MusicDataNode):
            return []

        extraction = extract_music_features(node)
        feature_id = await add_music_feature_to_db(
            self.engine,
            source_hash=extraction.source_hash,
            fmt=extraction.format,
            schema_version=extraction.schema_version,
            features=extraction.payload,
            feature_vector=extraction.feature_vector,
            feature_vector_schema=extraction.feature_vector_schema,
            part_count=extraction.part_count,
            duration_seconds=extraction.duration_seconds,
        )

        result_payload = {
            "featureId": str(feature_id),
            "schemaVersion": extraction.schema_version,
            "features": extraction.payload,
        }

        return [
            EnrichmentResult(
                ImplementationNode(
                    id=node.id,
                    label=node.label,
                    implementation=json.dumps(result_payload),
                ),
                ImplementationMetaData(width=None, depth=None),
            )
        ]
