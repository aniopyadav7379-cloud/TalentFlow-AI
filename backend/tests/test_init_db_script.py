import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.init_db import _redact  # noqa: E402


def test_redact_hides_password_in_postgres_url():
    url = "postgresql+psycopg2://avnadmin:supersecret@my-db.aivencloud.com:12345/defaultdb?sslmode=require"
    redacted = _redact(url)
    assert "supersecret" not in redacted
    assert "avnadmin" not in redacted
    assert "my-db.aivencloud.com:12345/defaultdb" in redacted


def test_redact_leaves_sqlite_url_unchanged():
    url = "sqlite:///./local.db"
    assert _redact(url) == url


def test_main_creates_all_tables(tmp_path, monkeypatch, capsys):
    from app.core.config import get_settings
    from scripts.init_db import main

    db_path = tmp_path / "init_test.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")
    get_settings.cache_clear()
    try:
        main()
    finally:
        get_settings.cache_clear()

    captured = capsys.readouterr()
    assert "8 tables ensured" in captured.out
    assert db_path.exists()


def test_main_is_idempotent(tmp_path, monkeypatch, capsys):
    from app.core.config import get_settings
    from scripts.init_db import main

    db_path = tmp_path / "init_test.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")
    get_settings.cache_clear()
    try:
        main()
        main()  # must not raise on second run
    finally:
        get_settings.cache_clear()

    captured = capsys.readouterr()
    assert captured.out.count("Done.") == 2
