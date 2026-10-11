import pytest


@pytest.fixture(autouse=True)
def isolated_data_dir(tmp_path, monkeypatch):
    """Never read or write the real user data folder in tests."""
    d = tmp_path / "threadline-data"
    monkeypatch.setenv("THREADLINE_DATA_DIR", str(d))
    return d
