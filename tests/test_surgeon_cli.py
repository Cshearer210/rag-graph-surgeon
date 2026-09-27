# CALLED BY: pytest -- the surgeon's command line, called IN PROCESS.
# FIRES WHEN: asked.
"""The surgeon CLI's own branches, exercised in process rather than through a subprocess.

⛔ WHY THIS FILE EXISTS: `tests/test_builders_ship.py` runs the surgeon through `subprocess`, which
proves the command works end to end and shows coverage of **0%** for `surgeon/__main__.py`, because
an in-process coverage run cannot see another interpreter. So a real gap and a measurement artefact
looked identical, and the branches that matter most here -- the ones that decide an EXIT CODE -- had
no in-process test at all. Added 2026-09-27.

The exit contract, which is the same three-outcome rule the rest of the tool holds to:
    0  shipped and graded clean
    1  shipped below the grading bar, or blocked
    2  bad input -- and a target that is not a directory is bad input, never a clean run
"""
import json
import os

from ragghost.surgeon.__main__ import main


def test_a_target_that_is_not_a_directory_is_exit_2_never_0(tmp_path, capsys):
    """A path it cannot read is UNKNOWN. The one answer it must never give is 'fine'."""
    missing = str(tmp_path / "no-such-system")
    assert main([missing, "--out", str(tmp_path / "out")]) == 2
    assert "not a directory" in capsys.readouterr().err


def test_a_file_given_where_a_system_was_expected_is_also_exit_2(tmp_path):
    f = tmp_path / "a-file.txt"
    f.write_text("not a system", encoding="utf-8")
    assert main([str(f), "--out", str(tmp_path / "out")]) == 2


def test_it_ships_and_returns_0_with_the_name_from_the_command_line(tmp_path, capsys):
    target = tmp_path / "shop"
    target.mkdir()
    (target / "products.json").write_text('[{"name":"Candle","price":12},]', encoding="utf-8")
    (target / "config.json").write_text('{"currency":"USD"}', encoding="utf-8")
    out = tmp_path / "shipped"
    rc = main([str(target), "--output", "landing", "--name", "Aurora Goods",
               "--out", str(out), "--workspace", str(tmp_path / "ws")])
    assert rc == 0, capsys.readouterr().out[-800:]
    page = (out / "index.html").read_text(encoding="utf-8")
    assert "Aurora Goods" in page, "--name must reach the built page, not just the scope"


def test_json_mode_prints_a_parseable_proof_and_nothing_else(tmp_path, capsys):
    target = tmp_path / "shop"
    target.mkdir()
    (target / "products.json").write_text('[{"name":"Candle","price":12}]', encoding="utf-8")
    (target / "config.json").write_text('{"currency":"USD"}', encoding="utf-8")
    rc = main([str(target), "--output", "api", "--name", "Aurora", "--json",
               "--out", str(tmp_path / "shipped"), "--workspace", str(tmp_path / "ws")])
    assert rc == 0
    proof = json.loads(capsys.readouterr().out)      # the whole of stdout, or this raises
    assert proof["shipped"] is True
    assert proof["output"] == "api"


def test_a_scope_file_is_read_instead_of_the_defaults(tmp_path):
    target = tmp_path / "shop"
    target.mkdir()
    (target / "products.json").write_text('[{"name":"Candle","price":12}]', encoding="utf-8")
    (target / "config.json").write_text('{"currency":"USD"}', encoding="utf-8")
    scope = tmp_path / "scope.json"
    scope.write_text(json.dumps({"output": "cli", "goal": "a tool",
                                 "store_name": "From The Scope File"}), encoding="utf-8")
    out = tmp_path / "shipped"
    assert main([str(target), "--scope", str(scope), "--out", str(out),
                 "--workspace", str(tmp_path / "ws")]) == 0
    assert os.path.exists(out / "tool.py"), "the scope file's output type should be what shipped"


def test_the_proof_lands_beside_the_output_every_run(tmp_path):
    """The proof is the deliverable the owner reads afterwards; a run without one is unauditable."""
    target = tmp_path / "shop"
    target.mkdir()
    (target / "products.json").write_text('[{"name":"Candle","price":12}]', encoding="utf-8")
    (target / "config.json").write_text('{"currency":"USD"}', encoding="utf-8")
    out = tmp_path / "shipped"
    main([str(target), "--output", "landing", "--name", "A", "--out", str(out),
          "--workspace", str(tmp_path / "ws")])
    proof = json.loads((out / "_surgeon_proof.json").read_text(encoding="utf-8"))
    assert proof["output"] == "landing"
    assert "surfaced_for_owner" in proof, "the owner's decisions must survive the run"
