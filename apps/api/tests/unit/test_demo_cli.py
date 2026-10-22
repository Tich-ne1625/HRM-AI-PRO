from types import SimpleNamespace

from app.cli import seed_demo


def test_production_demo_is_rejected_before_creating_engine(monkeypatch, capsys):
    monkeypatch.setattr(seed_demo, "get_settings", lambda: SimpleNamespace(app_env="production"))

    def forbidden(*args):
        raise AssertionError("Production must not open a database or hash a demo password")

    monkeypatch.setattr(seed_demo, "get_engine", forbidden)
    assert seed_demo.main([]) == 1
    assert "never production" in capsys.readouterr().err
