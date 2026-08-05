"""Regression tests for native runtime ordering in the composition root."""

import subprocess
import sys
from unittest.mock import patch

from docsmind.config import Settings
from docsmind.factory import build_pipeline


def test_factory_does_not_import_faiss_before_embedding():
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import sys; import docsmind.factory; "
                "assert 'docsmind.index.faiss_store' not in sys.modules"
            ),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr


def test_pipeline_loads_embedder_runtime_before_vector_backend():
    events = []

    class FakeEmbedder:
        @property
        def dim(self):
            events.append("embedder")
            return 384

    with (
        patch("docsmind.factory.build_embedder", return_value=FakeEmbedder()),
        patch(
            "docsmind.factory.load_store",
            side_effect=lambda settings, **kwargs: events.append("store") or object(),
        ),
        patch("docsmind.factory.build_retriever", return_value=object()),
        patch("docsmind.factory.build_llm", return_value=object()),
    ):
        build_pipeline(Settings(_env_file=None))

    assert events == ["embedder", "store"]
