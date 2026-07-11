import re, pytest
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
    assert "not wrapped in print" in card.lower()           # free-cell rule says bare doc() calls only
    assert "early version" in card.lower()                  # card asks for imperfection reports
    assert "clean score" in card and "ascending order" in card  # completion gate + redo order spelled out
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
    assert "import cell too is fine" in out                  # calibration line anticipates being read as a ruling
    assert "early version" in out.lower()                   # scorer asks for imperfection reports
    assert "per-kata scoring" in out                        # no tags yet: gentle how-to nudge, old kata format kept
    assert dj._RUN                                          # not a clean round: run dir kept

    assert "| dojo_score" not in out                        # scoring machinery stays out of the stroke ledger

    run("nope = 1")                                         # ledger paused after scoring: uncounted
    out = run("dojo_score(bash_calls=1)")
    assert "strokes 4" in out                               # the stray cell stayed out of the ledger
    run("dojo_resume()")                                    # counted work resumes

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
    half = "fetches daily open-meteo weather; httpx called in e31728e2"
    out = run(f"dojo_score(bash_calls=1, orient={half!r})")
    assert "does not name httpx-calling cell(s) 4658cca5" in out               # the failure names the missing id

    run("dojo_resume()")                                  # counted work resumes
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
    assert "dojo_redo(0)" in out                                        # ...with the discard hint

    out = run("dojo_redo(3)")                               # over-par kata: retry replaces its strokes, not adds
    assert "verbatim: ..." in out                           # reset banner shows the prompt's whole first line, elision marked
    out = run(f"dojo_score(bash_calls=1, orient={ans!r})")
    assert "strokes 10" in out                              # kata 3's three strokes cleared from the ledger
    assert "kata 'hostile replace' (strokes 0, par 2)" in out

    out = run("dojo_redo(0)")                               # untagged protocol mistakes: recoverable without a fresh round
    assert "untagged" in out.lower()
    out = run(f"dojo_score(bash_calls=1, orient={ans!r})")
    assert "strokes 5 + doc penalties 0" in out             # the five untagged strokes discarded; free untagged cells kept
    out = run("dojo_redo(1)")                               # read-only kata: nothing to reset
    assert "kata 4" not in out                              # no shared-file warning, no reapply tax on kata 4
    out = run(f"dojo_score(bash_calls=1, orient={ans!r})")
    assert "strokes 4" in out                               # kata 1's half-shares of the 1+4 cells dropped
    assert "kata 'orient' (strokes 0, par 2): ok" in out
    assert "kata 'notebook edit' (strokes 1, par 2)" in out # kata 4 keeps its own half-shares

    (d/'core.py').write_text("broken")
    run("dojo_redo(2)")
    assert "units='imperial'" in (d/'core.py').read_text()  # pristine again

    ok_dir = d.parent/'zz'                                  # a genuine run dir: deletable
    ok_dir.mkdir()
    dj._rm_run(ok_dir)
    assert not ok_dir.exists()
    with pytest.raises(ValueError): dj._rm_run(tmp_path/'elsewhere')   # tampered path: refused

    run("dojo_start()")                                     # fresh round; this test edits its files directly
    run("# kata 3: overspend, compensated by an under-par rest of round")
    run("s1 = 1")
    run("s2 = 2")
    run("s3 = 3")
    d2 = dj._RUN['dir']
    core = (d2/'core.py').read_text().replace("'imperial'", "'metric'").replace('load_cfg', 'load_config') \
        .replace('cfg = dict', 'config = dict').replace('cfg[k', 'config[k').replace('return cfg', 'return config')
    (d2/'core.py').write_text(core)
    (d2/'tmpl.py').write_text('"Plain-text rendering for weather summaries."\n\n\n' + dj._TMPL_PAYLOAD)
    raw = (d2/'01_api.ipynb').read_text().replace('retries the request twice before giving up.',
        'retries the request twice more before giving up, making 3 attempts in all.')
    (d2/'01_api.ipynb').write_text(raw)
    out = run(f"dojo_score(orient={ans!r})")                # under-par round total: clean, despite the kata-3 overspend
    assert "Clean round" in out and "Completion id:" in out and "compaction" in out
    assert "kata 'hostile replace' (strokes 3, par 2, +1 over)" in out  # over-par kata, under-par round
    assert "over-par katas" not in out and "dojo_redo(" not in out       # clean round: no contradictory redo demand
    cid = re.search(r"Completion id: ([0-9a-f]{4})", out)[1]
    out = run(f"dojo_start({cid!r})")
    assert "already complete" in out and not dj._RUN        # receipt honored: no tasks, no run started
    run("forget_dojo()")                                    # tooling changed: truncate the record
    out = run(f"dojo_start({cid!r})")
    assert "not on record" in out and "== clikernel dojo ==" in out and dj._RUN  # graceful: full round again


def test_kata_tag():
    "Only text before the first ':' is the tag, so prose mentions of other katas can't re-attribute; last mention wins within it."
    assert dj._kata_tag('# kata 4: reapply fix (shown in kata 1 summary)') == [4]
    assert dj._kata_tag('# kata 2 done, kata 3 next') == [3]
    assert dj._kata_tag('# katas 1+4: shared search') == [1, 4]
    assert dj._kata_tag('# plain narration, no tag') is None
