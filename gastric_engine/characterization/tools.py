"""Retrieval tool interfaces for agentic substance characterization.

Real PubChem/FooDB adapters can implement this small protocol later. The engine
depends only on the returned evidence records, never on network clients.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Protocol


@dataclass
class CharacterizationEvidence:
    source: str
    url: str
    facts: dict

    def to_dict(self) -> dict:
        return asdict(self)


class SubstanceRetriever(Protocol):
    def retrieve(self, substance: str) -> list[CharacterizationEvidence]:
        ...


def retrieve_substance(
    substance: str,
    retrievers: list[SubstanceRetriever] | None = None,
) -> list[dict]:
    evidence: list[dict] = []
    for retriever in retrievers or []:
        for item in retriever.retrieve(substance):
            evidence.append(item.to_dict())
    return evidence
