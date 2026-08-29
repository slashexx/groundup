from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "sidecar"))

from cadastre import (
    loader,
    validate,
)

FIXTURE = REPO / "contracts/fixtures/demo-parcel.json"


@pytest.fixture(scope="session")
def bundle():
    return loader.load_bundle(FIXTURE)


@pytest.fixture(scope="session")
def result(bundle):
    return validate.run(bundle["units"], bundle["relationships"],
                        bundle["sources"], bundle["settings"])
