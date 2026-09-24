"""Run inside the Agent Zero framework runtime, e.g.

    cd /a0 && /opt/venv-a0/bin/python -m pytest usr/plugins/realtime_voice/tests -q
"""

import os
import sys
from pathlib import Path

A0_ROOT = Path(os.environ.get("A0_ROOT") or Path(__file__).resolve().parents[4])
if str(A0_ROOT) not in sys.path:
    sys.path.insert(0, str(A0_ROOT))
