from clikernel.rules import scan, Session

def fires(src, name, sess=None): return any(f.rule == name for f in scan(src, sess or Session()))


def test_rules():
    "Each rule fires on its anti-pattern and stays quiet on the blessed route."
    # read_text/open().read -> lnhashview
    assert fires("p.read_text()", "read_file")
    assert fires("open(p).read()", "read_file")
    assert not fires("lnhashview_file(p)", "read_file")

    # big replace_lines payload -> delete + %%exhash a
    big = "x = 1\n" * 9
    assert fires(f"file_replace_lines(p, new_content={big!r})", "big_replace")
    assert fires(f"cell_replace_lines(p, cid, new_content={big!r})", "big_replace")
    assert not fires("file_replace_lines(p, new_content='x = 1')", "big_replace")

    # single-cell cell_str_replace -> %%exhash path cellid; batch replaces (id list / 'all') are sanctioned
    assert fires("cell_str_replace(p, 'ab12', 'a', 'b')", "cell_str_replace")
    assert not fires("cell_str_replace(p, ['ab12','cd34'], 'a', 'b')", "cell_str_replace")
    assert not fires("cell_str_replace(p, 'all', 'a', 'b')", "cell_str_replace")
    assert not fires("cell_str_replace(p, cids, 'a', 'b')", "cell_str_replace")   # variables unknowable: stay quiet

    # non-raw triple-quote containing backslashes -> r-string
    assert fires('s = """a\\nb"""', "rawstr")
    assert not fires('s = r"""a\\nb"""', "rawstr")
    assert not fires('s = """plain text"""', "rawstr")

    # computing exhash addresses -> views only
    assert fires("addr = lnhash(3, line)", "hashcalc")
    assert fires("line_hash(s)", "hashcalc")

    # post-processing tooling results -> bare repr / tool params
    assert fires("'\\n'.join(lnhashview_file(p))", "postproc")
    assert fires("rg('x', p).splitlines()[:5]", "postproc")
    assert not fires("lnhashview_file(p)", "postproc")

    # programmatic magic invocation -> % syntax
    assert fires("get_ipython().run_line_magic('nbrun', 'abc')", "run_magic")
    assert not fires("%nbrun abc", "run_magic")                  # a real magic is the blessed route

    # blockers
    assert fires("import subprocess", "shell_escape")
    assert fires("os.system('ls')", "shell_escape")
    assert fires("!ls", "shell_escape")                          # `!` escapes are seen via the transformed cell
    assert fires("%nbopen f.ipynb\np.read_text()", "read_file")  # rules still run on cells containing magics
    assert fires("sys.path.insert(0, 'x')", "sys_path")
    assert fires("sys.path.append('x')", "sys_path")


def test_session_rules():
    "Cross-cell rules: piecemeal skill imports, doc-before-first-call, and re-nagging on every miss."
    s = Session()
    assert fires("from rgapi import rg", "piecemeal", s)          # rgapi has a .skill module
    assert not fires("from rgapi.skill import *", "piecemeal", s)
    assert not fires("from pathlib import Path", "piecemeal", s)  # no pathlib.skill: fine
    assert not fires("from pyskills import list_pyskills, doc", "piecemeal", s)  # the blessed bootstrap line
    assert not fires("from clikernel.rules import doced, forget_doced", "piecemeal", s)  # the prescribed session-reset line

    # doc(f) before first call: rg resolves to an editable-install function in this session
    import rgapi.skill  # ensure resolvable
    ns = {"rg": rgapi.skill.rg}
    assert fires("rg('x', '.')", "nodoc", Session(ns=ns))
    s3 = Session(ns=ns)
    assert not fires("doc(rg)", "nodoc", s3)
    assert not fires("rg('x', '.')", "nodoc", s3)                 # doc'd first: quiet
    assert not fires("len('abc')", "nodoc", Session(ns=ns))       # stdlib: quiet
    import clikernel.dojo as dj
    assert not fires("dojo_score()", "nodoc", Session(ns={"dojo_score": dj.dojo_score}))  # the dojo interface is the blessed route

    # doc(f) in a loop or comprehension over literal names docs each of them
    s5 = Session(ns={"rg": rgapi.skill.rg, "fd": rgapi.skill.fd})
    assert not fires("for f in (rg, fd): print(doc(f))", "nodoc", s5)
    assert not fires("rg('x', '.')", "nodoc", s5)
    assert not fires("fd('.')", "nodoc", s5)
    s6 = Session(ns={"rg": rgapi.skill.rg, "fd": rgapi.skill.fd})
    assert not fires("[doc(f) for f in (rg, fd)]", "nodoc", s6)
    assert not fires("rg('x', '.')", "nodoc", s6)

    # re-nag: findings repeat on every offending cell until the habit is fixed
    s4 = Session()
    assert fires("p.read_text()", "read_file", s4)
    assert fires("q.read_text()", "read_file", s4)
    s7 = Session(ns=ns)
    assert fires("rg('x', '.')", "nodoc", s7)
    assert fires("rg('y', '.')", "nodoc", s7)                     # keeps nagging until doc'd
    assert not fires("doc(rg)\nrg('x', '.')", "nodoc", s7)        # compliance ends the nag
    s8 = Session(ns=ns)
    assert not fires("doced('rg')\nrg('x', '.')", "nodoc", s8)    # declaring is recorded at scan time, like doc()
    s9 = Session(ns=ns)
    assert not fires("doced(rg)\nrg('y', '.')", "nodoc", s9)      # bare symbols declare too
    import clikernel.rules as cr
    assert not fires("doced('x')\nforget_doced()", "nodoc", Session(ns={"doced": cr.doced, "forget_doced": cr.forget_doced}))  # the prescribed interfaces are exempt


def test_notes_single_way():
    "Notes teach exactly one route and never name exceptions."
    from clikernel.rules import RULES
    for r in RULES:
        assert r.note and len(r.note) < 120
        for word in ("unless", "except when", "sometimes", "usually"): assert word not in r.note.lower()


def test_doced_state(tmp_path, monkeypatch):
    "doced survives worker restarts via a ppid-keyed state file; doced() declares; forget_doced() resets; stale files swept"
    monkeypatch.setenv("CLIKERNEL_STATE_DIR", str(tmp_path))
    import os, clikernel.rules as cr
    stale = tmp_path/'doced'/'99999.json'
    stale.parent.mkdir(parents=True)
    stale.write_text('[]')
    os.utime(stale, (0, 0))
    insp = cr.make_inspector()
    assert not stale.exists()                       # abandoned session state swept
    insp(None, "doc(rg)")
    cr.make_inspector()                             # a fresh worker in the same session
    assert 'rg' in cr._LIVE.doced                   # state survived the restart
    cr.doced('lnhashview_file')
    cr.doced(cr.forget_doced)                       # plain symbols work too, like doc()
    cr.make_inspector()
    assert {'rg','lnhashview_file','forget_doced'} <= set(cr.doced())
    cr.forget_doced()
    cr.make_inspector()
    assert not cr._LIVE.doced                       # post-compaction reset: everything needs doc() again
