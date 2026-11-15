import pytest

from lab.cli import main
from lab.common import fit_budget, is_under_home, leaking_ancestors, norm, world_id


def test_world_id_can_be_pinned(monkeypatch):
    # 公開 repo 少了 7 頁 wiki，算出來的 world_id 會不同；用 LAB_WORLD_ID 指定，才能重算 repo 裡的既有結果
    monkeypatch.setenv("LAB_WORLD_ID", "pinned-world")
    assert world_id() == "pinned-world"


@pytest.mark.parametrize("cmd", [["run", "--rounds", "1"], ["closed"]])
def test_pinned_world_id_refuses_to_run(monkeypatch, cmd):
    # 新作答會被記成指定的 world_id，和既有結果混在一起，所以不准跑
    monkeypatch.setattr("lab.run.run", lambda **kw: None)
    monkeypatch.setattr("lab.run.run_closed", lambda **kw: None)
    monkeypatch.setenv("LAB_WORLD_ID", "1b2014a0e3f6")
    with pytest.raises(SystemExit, match="LAB_WORLD_ID"):
        main(cmd)


def test_fit_budget_takes_largest_n_that_fits():
    assert fit_budget(lambda n: "x" * n * 10, most=5, budget=30) == "x" * 30
    with pytest.raises(ValueError):
        fit_budget(lambda n: "x" * 99, most=5, budget=30)


def test_norm_fullwidth_spaces_commas():
    assert norm("４，２００ mAh") == "4200mah"
    assert norm("NT$ 1,200 元") == "nt$1200元"


def test_is_under_home(tmp_path):
    home = tmp_path / "home"
    (home / "proj").mkdir(parents=True)
    assert is_under_home(home / "proj", home)
    assert is_under_home(home, home)
    assert not is_under_home(tmp_path / "elsewhere", home)


def test_leaking_ancestors(tmp_path):
    (tmp_path / "a" / "b" / ".claude").mkdir(parents=True)
    (tmp_path / "a" / "AGENTS.md").write_text("x")
    (tmp_path / "a" / "b" / ".claude" / "CLAUDE.md").write_text("x")
    found = leaking_ancestors(tmp_path / "a" / "b")
    assert tmp_path.resolve() / "a" / "AGENTS.md" in found
    assert tmp_path.resolve() / "a" / "b" / ".claude" / "CLAUDE.md" in found
