import json
import sys
from pathlib import Path

import pytest

GATES = Path(__file__).resolve().parents[2] / "scripts" / "gates"
sys.path.insert(0, str(GATES))


@pytest.fixture
def config():
    return json.loads((GATES / "gates.json").read_text(encoding="utf-8"))
