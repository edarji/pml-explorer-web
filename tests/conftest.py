"""Las pruebas nunca leen la red: la demanda (v0.10.0) se lee de los archivos de ejemplo de tests/fixtures/demanda."""
import os
from pathlib import Path

os.environ.setdefault("DEMANDA_URL", (Path(__file__).resolve().parent / "fixtures" / "demanda").as_uri())
