from alembic.config import Config
from alembic.script import ScriptDirectory
from pathlib import Path


def test_single_alembic_head():
    cfg = Config(str(Path("backend/alembic.ini")))
    cfg.set_main_option("script_location", str(Path("backend/alembic")))
    script = ScriptDirectory.from_config(cfg)
    heads = script.get_heads()
    assert len(heads) == 1, f"Expected one alembic head, found {heads}"
    assert heads == ["20260914_0019"]
