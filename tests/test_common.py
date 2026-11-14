from lab.common import is_under_home, leaking_ancestors, norm


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
