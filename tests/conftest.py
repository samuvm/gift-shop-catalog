from pathlib import Path

import pytest
from hypothesis import settings

ROOT = Path(__file__).resolve().parents[1]

settings.register_profile("dev", max_examples=25)
settings.register_profile("gate", max_examples=100)
settings.load_profile("dev")


@pytest.fixture(scope="session")
def root() -> Path:
    return ROOT
