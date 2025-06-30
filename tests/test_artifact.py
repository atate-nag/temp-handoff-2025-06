import json
import pytest
from datetime import datetime, timedelta

from schemas import Artifact, ArtifactKind, ArtifactCollection


def test_artifact_roundtrip_minimal():
    art = Artifact(
        id="5-forces",
        kind=ArtifactKind.ANALYSIS,
        payload={"analysis": [{"force": "rivalry", "rating": 4}]},
        sources=["(BIS, 2024)", "(FT, 2023)"],
    )

    # Serialize to JSON and back — should still validate
    loaded = Artifact.model_validate(json.loads(art.model_dump_json()))
    assert loaded == art


def test_artifact_defaults_and_meta_timestamp():
    art = Artifact(
        id="dummy",
        kind=ArtifactKind.OTHER,
        payload={},
    )

    # tags and sources default to []
    assert art.tags == []
    assert art.sources == []

    # meta.created should be an ISO timestamp not older than 5 sec
    ts = datetime.fromisoformat(art.meta["created"])
    assert datetime.utcnow() - ts < timedelta(seconds=5)


def test_collection_lookup_and_sources():
    a1 = Artifact(
        id="foo",
        kind=ArtifactKind.ANALYSIS,
        payload={},
        sources=["(X, 2024)"],
    )
    a2 = Artifact(
        id="bar",
        kind=ArtifactKind.DATASET,
        payload={},
        sources=["(Y, 2025)", "(X, 2024)"],
    )

    bundle = ArtifactCollection(artifacts=[a1, a2])

    # lookup by id
    assert bundle.lookup["foo"] is a1
    assert bundle.lookup["bar"] is a2

    # aggregated, deduplicated, sorted sources
    assert bundle.all_sources == ["(X, 2024)", "(Y, 2025)"]
