"Practice katas for tooling best practices, scored on the route taken, not just the outcome. Start with `dojo_start()`."
import ast,json,re,shutil,time,uuid
from importlib.resources import files
from pathlib import Path
from clikernel.cli import _state_root
from clikernel.rules import live_session, scan, _callee, _calls

__all__ = ['dojo_start','dojo_score','dojo_redo']

_RUN = {}

_SQ3 = "'''"   # can't appear literally inside the rf''' below: the same trap kata 3 sets
_TMPL_PAYLOAD = rf'''def render(name, temp):
    r"""Render a one-line summary; keep \t, \n and {_SQ3} literal in this docstring."""
    return name + ':\t' + str(temp) + ' degrees\n'
'''
_TMPL_IND = '\n'.join('    ' + l for l in _TMPL_PAYLOAD.splitlines())


def _chk_orient(d):
    a = _RUN.get('orient') or ''
    if not a: return ['no answer passed: dojo_score(orient="<your prose answer>")']
    out = []
    if not ('meteo' in a.lower() or ('fetch' in a.lower() and 'daily' in a.lower())):
        out.append('answer does not describe fetching daily open-meteo weather: check the notebook, not just core.py')
    if not ('e31728e2' in a and '4658cca5' in a): out.append('answer does not name the two httpx-calling cells by id')
    return out

def _chk_core(d):
    t = (d/'core.py').read_text()
    out = []
    if "units='metric'" not in t or 'imperial' in t: out.append("default units is not 'metric'")
    if len(re.findall(r'\bcfg\b', t)) != 1 or len(re.findall(r'\bconfig\b', t)) != 3:
        out.append('cfg -> config rename incomplete, or the docstring was changed')
    return out

def _chk_tmpl(d):
    t = (d/'tmpl.py').read_text()
    out = []
    if 'OLD_TMPL' in t: out.append('old render() body still present')
    if _TMPL_PAYLOAD.strip() not in t: out.append('replacement render() does not match the provided text verbatim')
    if '\n\n\n\n' in t: out.append('stray blank lines left around the replacement')
    return out

def _chk_nb(d):
    raw = (d/'01_api.ipynb').read_text()
    return [] if '3 attempts' in raw and 'retries the request twice before giving up' not in raw else \
        ['the Retries markdown does not say "3 attempts"']


KATAS = [
    dict(name='orient', par=2, files=['01_api.ipynb'], check=_chk_orient,
        route='find_cells/summary_nb for the module story; nbrg for the httpx calls; answer from the bare results',
        prompt='What does the weather module do, and which notebook cells call httpx? Answer in prose, naming cells by id, and pass it via dojo_score(orient="...").'),
    dict(name='edit set', par=2, files=['core.py'], check=_chk_core,
        route='lnhashview_file, then ONE exhash_file with all commands, worked bottom-to-top',
        prompt="In core.py: change the default units to 'metric', and rename cfg to config everywhere in code (docstring unchanged)."),
    dict(name='hostile replace', par=2, files=['tmpl.py'], check=_chk_tmpl,
        route='lnhashview_file, then one %%exhash with a range-c address; payload verbatim, no quoting. (% c would replace the whole file: too much here)',
        prompt='In tmpl.py: replace the whole render() function with exactly this, verbatim:\n\n' + _TMPL_IND),
    dict(name='notebook edit', par=2, files=['01_api.ipynb'], check=_chk_nb,
        route='doc(find_cells) free, find_cells(header_section=...), then one %%exhash <path> <cell_id> % c replaces the whole cell: no line addresses needed',
        prompt='In 01_api.ipynb: the markdown under the Retries header is wrong; it should say the request is retried twice more, making "3 attempts" in all.')]


def _card():
    d = _RUN['dir']
    ks = '\n'.join(f"{i}. (par {k['par']}) {k['prompt']}" for i,k in enumerate(KATAS, 1))
    return f"""== clikernel dojo ==
Work only in: {d}
Scoring: kernel cell = 1 stroke; Bash tool call = 2; each print() call = +1. The tooling's reprs are designed to be optimally useful read bare, so end each cell with a bare expression and read what comes back. Cells of only doc()/list_pyskills()/imports are free, as are comment-only narration cells.
Penalties: +1 per skill module or workspace function used before doc()ing it.
Par assumes the tooling's best route, shown with each kata at scoring: matching par means you found it.
Per-kata scoring: start cells with a free '# kata <n>:' narration comment; later cells inherit it, '# kata 1+4:' splits shared work, and the LAST kata mentioned in a tag wins ('# kata 2 done, kata 3 next' tags 3). A %%exhash cell can't start with a comment, so tag it with a narration cell just before.
Par for the round: {sum(k['par'] for k in KATAS)}. When done: dojo_score(bash_calls=<your Bash call count>)
This dojo is an early version: note anything about the scoring or process that seems possibly-imperfect, and include it in your report.

{ks}"""


def _machinery(src):
    "Pure dojo_score/dojo_redo cells stay out of the trace, so rescoring never grows the ledger"
    try: tree = ast.parse(src)
    except SyntaxError: return False
    return bool(tree.body) and all(isinstance(n, ast.Expr) and isinstance(n.value, ast.Call)
        and _callee(n.value) in ('dojo_score','dojo_redo') for n in tree.body)

def _log(info):
    if _machinery(info.raw_cell): return
    with open(_RUN['trace'], 'a') as f: f.write(json.dumps({'src': info.raw_cell}) + '\n')



def _rm_run(p):
    "The one place we rmtree, so the one place a corrupted path could do damage: refuse anything that isn't strictly inside the dojo root, checked fresh at delete time"
    root = (_state_root()/'dojo').resolve()
    p = Path(p).resolve()
    if p == root or not p.is_relative_to(root): raise ValueError(f'refusing to delete {p}: not a run dir under {root}')
    shutil.rmtree(p, ignore_errors=True)


def dojo_start():
    "Set up a fresh practice run: copy the kata project to a private dir, start tracing, and print the kata card"
    from IPython import get_ipython
    root = _state_root()/'dojo'
    if root.exists():   # sweep runs abandoned by earlier sessions
        for old in root.iterdir():
            if old.stat().st_mtime < time.time() - 86400: _rm_run(old)
    d = root/uuid.uuid4().hex[:8]
    shutil.copytree(files('clikernel')/'dojo_data'/'proj', d)
    _RUN.update(dir=d, trace=d/'trace.jsonl', ip=get_ipython(), log=_log)
    _RUN['ip'].events.register('pre_run_cell', _RUN['log'])
    print(_card())


def _is_free(src):
    "A cell costs no strokes if it only reads docs or imports (or is dojo machinery)"
    free = {'doc','list_pyskills','help','doced','forget_doced'} | set(__all__)
    def _ok(n):
        if isinstance(n, ast.Expr) and isinstance(n.value, ast.Call):
            c = n.value
            if _callee(c) == 'print': return all(_callee(a) in free for a in c.args if isinstance(a, ast.Call))
            return _callee(c) in free
        if isinstance(n, ast.For) and not any(_calls(n.iter)): return all(_ok(b) for b in n.body)
        if isinstance(n, ast.Expr) and isinstance(n.value, (ast.ListComp, ast.SetComp, ast.GeneratorExp)) \
           and not any(_calls(n.value.generators[0].iter)): return _ok(ast.Expr(n.value.elt))
        if isinstance(n, (ast.Import, ast.ImportFrom)): return True
        return False
    try: tree = ast.parse(src)
    except SyntaxError: return False
    return all(_ok(n) for n in tree.body)


def _nprints(src):
    "print() fights the tuned reprs, so each call costs a stroke; end cells with a bare expression instead"
    try: tree = ast.parse(src)
    except SyntaxError: return 0
    return sum(1 for c in _calls(tree) if _callee(c) == 'print')


_TAG_RE = re.compile(r'katas?\W{0,3}(\d[\d\s,+&/-]*)', re.I)

def _kata_tag(src):
    "Kata numbers from a leading `# kata <n>` comment (generous: any separators; invalid numbers ignored; the LAST kata mention on a line wins), or None"
    for l in src.splitlines():
        l = l.strip()
        if not l: continue
        if not l.startswith('#'): break
        ks = None
        for m in _TAG_RE.finditer(l):
            if (v := [n for n in map(int, re.findall(r'\d+', m.group(1))) if 1 <= n <= len(KATAS)]): ks = v
        if ks: return ks
    return None

def _attribute(cells, costs):
    "Split cell strokes across tagged katas (later cells inherit the last tag), returning (any_tags, untagged, per_kata)"
    tagged, cur, unt, per = False, None, 0.0, [0.0]*len(KATAS)
    for s, c in zip(cells, costs):
        if (t := _kata_tag(s)): cur, tagged = t, True
        if not c: continue
        if cur:
            for n in cur: per[n-1] += c/len(cur)
        else: unt += c
    return tagged, unt, per


def dojo_score(bash_calls=0, orient=''):
    "Score the run: strokes vs par, habit findings from the trace, and each kata's outcome. Pass your Bash tool call count, and your kata-1 prose answer as `orient`."
    if not _RUN: return print('No active run: dojo_start() first.')
    _RUN['orient'] = orient
    d = _RUN['dir']
    cells = [json.loads(l)['src'] for l in Path(_RUN['trace']).read_text().splitlines()]
    costs = [(0 if _is_free(s) else 1) + _nprints(s) for s in cells]
    strokes = sum(costs) + 2*bash_calls
    sess = live_session(ns=_RUN['ip'].user_ns)  # seeded with persisted doc-state, like the live rules
    finds = {}
    for s in cells:
        for f in scan(s, sess): finds.setdefault(f.rule, f.note)
    undoc = sess.undoced - sess.doced           # a later doc()/doced() remedies the miss on rescore
    pen = len(undoc)
    if not undoc: finds.pop('nodoc', None)
    par = sum(k['par'] for k in KATAS)
    fails = [(k, k['check'](d)) for k in KATAS]
    print(f"strokes {strokes} + doc penalties {pen} = {strokes+pen}, par {par}")
    for c, s in zip(costs, cells): print(f"  {c}| {(s.splitlines() or [''])[0][:70]}")
    if undoc: print(f"  undoc'd first uses: {', '.join(sorted(undoc))}")
    for name, note in finds.items(): print(f"habit miss [{name}]: {note}")
    over = strokes + pen - par
    tagged, unt, per = _attribute(cells, costs)
    overs = []
    for i, (k, (probs, s)) in enumerate(zip(KATAS, zip((p for _, p in fails), per)), 1):
        if tagged and s > k['par']: overs.append(i)
        xtra = f", +{s - k['par']:g} over" if tagged and s > k['par'] else ""
        lbl = f" (strokes {s:g}, par {k['par']}{xtra})" if tagged else ""
        print(f"kata '{k['name']}'{lbl}: {'; '.join(probs) if probs else 'ok'}\n  par route: {k['route']}")
    if overs: print("over-par katas: " + ', '.join(f"dojo_redo({i}) to reset and retry kata {i}" for i in overs))
    if tagged and unt: print(f"{unt:g} untagged strokes: start a cell with '# kata <n>:' to attribute them")
    elif not tagged: print("For per-kata scoring, start cells with a free '# kata <n>:' narration comment; later cells inherit it, and '# kata 1+4:' splits shared work.")
    if over > 0: print(f"{over} over par for the round: replay with the par routes in mind")
    ok = not finds and not pen and over <= 0 and not any(p for _, p in fails)
    print("kata 'orient' expected answer: fetch and summarize daily weather (open-meteo); httpx is called in the fetch_daily export cell e31728e2 and the example cell 4658cca5.")
    if ok:
        _RUN['ip'].events.unregister('pre_run_cell', _RUN['log'])
        _rm_run(d)
        _RUN.clear()
        print('Clean round. Run dir removed.')
    else: print('Fix the misses, then dojo_redo(<kata number>) to reset that kata and try again.')
    print('The dojo is an early version: include in your report anything above that seemed possibly-imperfect (stroke counts, findings, prompts).')


def dojo_redo(n):
    "Reset kata `n`'s files to pristine and clear its findings from the trace-so-far"
    k = KATAS[n-1]
    for f in k['files']: shutil.copy(files('clikernel')/'dojo_data'/'proj'/f, _RUN['dir']/f)
    print(f"kata '{k['name']}' reset. Par {k['par']}: {k['prompt'][:80]}")
