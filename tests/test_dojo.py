import pytest
from clikernel.cli import _stream_text
import clikernel.dojo as dj


def test_dojo(tmp_path, monkeypatch):
    "Smoke: start copies seeds and traces cells; score counts strokes (Bash = 2), reports kata outcomes and par routes; redo resets files."
    monkeypatch.setenv("CLIKERNEL_STATE_DIR", str(tmp_path))
    from execnb.shell import CaptureShell
    sh = CaptureShell()
    def run(code):
        out = _stream_text(sh.run(code))
        assert not sh.exc, out
        return out

    run("import clikernel.dojo")
    run("from clikernel.rules import doced")
    run("doced('pretool')")                                 # pre-round declaration: persists before any inspector exists
    run("from clikernel.dojo import *")
    card = run("dojo_start()")
    assert "== clikernel dojo ==" in card and "(par 2)" in card and "par 3" not in card and "best route" in card and "print()" in card
    assert "early version" in card.lower()                  # card asks for imperfection reports
    hostile = dj._TMPL_PAYLOAD                               # kata 3 payload defeats every Python literal form
    assert "'"*3 in hostile and '"'*3 in hostile and '\\' in hostile and '\n' in hostile
    d = dj._RUN['dir']
    assert (d/'core.py').exists() and (d/'01_api.ipynb').exists()

    run("x = 1 + 1")                                      # 1 stroke
    run("help(len)")                                      # free
    run("import collections, json")                       # free: imports cost nothing
    run("# a narration comment")                          # free: comments cost nothing
    run("for f in (len, max): help(f)")                   # free: reading docs in a loop
    run("print(x)")                                       # free cell shape, but each print() costs 1
    out = run("dojo_score(bash_calls=1)")                 # free itself; +2 for the Bash call
    assert "strokes 4" in out and "par 8" in out                        # cell + print + 2*bash
    assert "1| x = 1 + 1" in out and "0| # a narration comment" in out  # per-cell stroke ledger
    assert "kata 'edit set'" in out and "par route" in out  # unedited files: fails, with the route shown
    assert "kata 'orient': no answer passed" in out and dj.KATAS[0]['route'] in out  # ungraded orient fails, route shown
    assert 'expected answer' in out                          # expected answer still printed for calibration
    assert "early version" in out.lower()                   # scorer asks for imperfection reports
    assert "per-kata scoring" in out                        # no tags yet: gentle how-to nudge, old kata format kept
    assert dj._RUN                                          # not a clean round: run dir kept

    assert "| dojo_score" not in out                        # scoring machinery stays out of the stroke ledger

    run("pretool = clikernel.dojo._card; pretool()")        # 1 stroke; doced pre-round: no penalty
    run("fake = clikernel.dojo._card")                      # 1 stroke
    run("fake()")                                           # 1 stroke, and a nodoc penalty
    out = run("dojo_score(bash_calls=1)")
    assert "doc penalties 1" in out and "undoc'd first uses: fake" in out   # pre-round doced honored: only fake flagged
    run("doced('fake')")                                    # free declaration remedies the miss
    decoy = "configuration handling for the weather project; httpx in e31728e2 and 4658cca5"
    out = run(f"dojo_score(bash_calls=1, orient={decoy!r})")
    assert "strokes 7 + doc penalties 0" in out and "habit miss" not in out # doc-fix forgiven on rescore
    assert "check the notebook" in out                                      # core.py decoy prose rejected despite ids

    run("# kata 2: rename sweep")                           # free tag cell sets attribution
    run("y = 2")                                            # 1 stroke -> kata 2
    run("# kata 2 done. Katas 1+4 - shared search")         # transitional narration: the LAST kata mention wins
    run("z = 3")                                            # 1 stroke -> split between katas 1 and 4
    run("# kata 99: bogus number is ignored")               # graceful: invalid tag leaves 1+4 current
    run("w = 1")                                            # 1 stroke -> still katas 1 and 4
    run("# kata 3: one more pass")                          # tag switch to a par-2 kata
    run("v = 9")                                            # 1 stroke -> kata 3
    run("v2 = 8")                                           # 1 stroke -> kata 3
    run("v3 = 7")                                           # 1 stroke -> kata 3: now over par
    ans = "fetches daily open-meteo weather; httpx called in e31728e2 and 4658cca5"
    out = run(f"dojo_score(bash_calls=1, orient={ans!r})")
    assert "strokes 13" in out                                          # 11 cell strokes + 2*bash
    assert "kata 'orient' (strokes 1, par 2): ok" in out                # graded answer + 0.5 + 0.5 shared strokes
    assert "kata 'edit set' (strokes 1, par 2)" in out
    assert "kata 'hostile replace' (strokes 3, par 2, +1 over)" in out  # per-kata over-par surfaced
    assert "dojo_redo(3)" in out                                        # ...with the retry hint
    assert "kata 'notebook edit' (strokes 1, par 2)" in out
    assert "5 untagged" in out                                          # pre-tag strokes surfaced, gently

    (d/'core.py').write_text("broken")
    run("dojo_redo(2)")
    assert "units='imperial'" in (d/'core.py').read_text()  # pristine again

    ok_dir = d.parent/'zz'                                  # a genuine run dir: deletable
    ok_dir.mkdir()
    dj._rm_run(ok_dir)
    assert not ok_dir.exists()
    with pytest.raises(ValueError): dj._rm_run(tmp_path/'elsewhere')   # tampered path: refused
