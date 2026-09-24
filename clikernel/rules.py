"""Rules that check agent-written kernel cells for common mistakes with this toolkit. The router checks each `exec` cell before forwarding it: most rules add a note to the reply, and blocking rules stop the cell. Rules see only the cell's text, not which kernel will run it, so each matches Python forms that no other kernel language produces."""
import ast,re,tokenize
from IPython.core.inputtransformer2 import TransformerManager
from io import StringIO
from fastcore.basics import store_attr


class Rule:
    "A named check: `fn(tree, src)` is truthy when `note` applies; `block` stops the cell, and `raw` checks the source as typed rather than as IPython transforms it"
    def __init__(self, name, note, fn, block=False, raw=False): store_attr()

_TOOLING = {'lnhashview','lnhashview_file','lnhashview_cell','lnhashview_cells','rg','nbrg','fd',
    'find_msgs','summary_dlg','view_dlg','view_msg','view_msgs','view_file','view_cell','doc','info_md'}


def _calls(tree):
    for n in ast.walk(tree):
        if isinstance(n, ast.Call): yield n


def _callee(c): return c.func.id if isinstance(c.func, ast.Name) else None


_DATA_EXTS = ('.json','.jsonl','.ndjson','.csv','.tsv','.log')

def _textpath(node):
    "A string constant under `node` recognisably names a non-data file: only then is a view-note earned"
    return any(isinstance(n, ast.Constant) and isinstance(n.value, str) and '.' in n.value
        and not n.value.lower().endswith(_DATA_EXTS) for n in ast.walk(node))


def _is_read(c):
    "A read_text()/open().read() call on a recognisably-named non-data file"
    if not (isinstance(c, ast.Call) and isinstance(c.func, ast.Attribute)): return False
    if c.func.attr == 'read_text': return _textpath(c.func.value)
    return c.func.attr == 'read' and isinstance(c.func.value, ast.Call) and _callee(c.func.value) == 'open' and _textpath(c.func.value)


def _read_file(tree, src):
    "Only a displayed read (bare expression or print) earns the note: a parser-bound or assigned read never enters context"
    for n in ast.walk(tree):
        if isinstance(n, ast.Expr):
            v = n.value
            if _is_read(v): return True
            if isinstance(v, ast.Call) and _callee(v) == 'print' and any(_is_read(a) for a in v.args): return True


def _big_replace(tree, src):
    for c in _calls(tree):
        if _callee(c) in ('file_replace_lines','cell_replace_lines'):
            for k in c.keywords:
                if k.arg == 'new_content' and isinstance(k.value, ast.Constant) and str(k.value.value).count('\n') >= 6: return True


def _cell_str_replace(tree, src):
    "Only the obvious single-cell form (a literal id that isn't 'all'): batch replaces over many cells are sanctioned"
    for c in _calls(tree):
        if _callee(c) != 'cell_str_replace': continue
        cid = c.args[0] if c.args else next((k.value for k in c.keywords if k.arg == 'id'), None)
        if isinstance(cid, ast.Constant) and isinstance(cid.value, str) and cid.value != 'all': return True


def _rawstr(tree, src):
    try: toks = list(tokenize.generate_tokens(StringIO(src).readline))
    except tokenize.TokenizeError: return
    for t in toks:
        if t.type == tokenize.STRING:
            m = re.match(r"""([A-Za-z]*)('''|\"\"\")""", t.string)
            if m and 'r' not in m[1].lower() and '\\' in t.string: return True


def _hashcalc(tree, src): return any(_callee(c) in ('lnhash','line_hash') for c in _calls(tree))


def _cmds(c):
    "Top-level command-tuple nodes of an exhash/file_exhash/cell_exhash call"
    if _callee(c) == 'exhash':
        a = c.args[1] if len(c.args) > 1 else None
        return a.elts if isinstance(a, (ast.List, ast.Tuple)) and any(isinstance(e, ast.Tuple) for e in a.elts) else []
    return c.args[2 if _callee(c) == 'cell_exhash' else 1:]

def _tuple_payload(tree, src):
    "A lone constant a/i/c payload that is long or contains quotes/backslashes belongs in a %%exhash cell; multi-command calls are exempt, since the one-command magic can't express them atomically"
    for c in _calls(tree):
        if _callee(c) not in ('exhash','file_exhash','cell_exhash'): continue
        cmds = _cmds(c)
        if len(cmds) != 1 or not isinstance(cmds[0], ast.Tuple): continue
        n = cmds[0]
        if len(n.elts) < 3: continue
        cmd,payload = n.elts[1],n.elts[2]
        if not (isinstance(cmd, ast.Constant) and cmd.value in ('a','i','c')): continue
        if not (isinstance(payload, ast.Constant) and isinstance(payload.value, str)): continue
        if len(payload.value) > 20 or any(ch in payload.value for ch in '\'"\\'): return True


def _s_repls(tree):
    "String-constant replacement fields of s-commands in exhash calls"
    for c in _calls(tree):
        if _callee(c) not in ('exhash','file_exhash','cell_exhash'): continue
        for n in ast.walk(c):
            if not (isinstance(n, ast.Tuple) and len(n.elts) >= 4): continue
            if not (isinstance(n.elts[1], ast.Constant) and n.elts[1].value == 's'): continue
            if isinstance(n.elts[3], ast.Constant) and isinstance(n.elts[3].value, str): yield n.elts[3].value


def _s_newline(tree, src): return any('\\n' in r for r in _s_repls(tree))


def _s_long(tree, src): return any(len(r) > 120 for r in _s_repls(tree))



def _postproc(tree, src):
    for n in ast.walk(tree):
        if isinstance(n, ast.Attribute) and isinstance(n.value, ast.Call) and _callee(n.value) in _TOOLING \
           and n.attr in ('splitlines','split','join'): return True
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr == 'join' \
           and isinstance(n.func.value, ast.Constant) \
           and any(_callee(c) in _TOOLING for a in n.args for c in _calls(a)): return True


def _run_magic(tree, src):
    # raw-source rule: in the transformed cell every magic becomes run_*_magic, so only literal raw uses count
    return 'run_line_magic' in src or 'run_cell_magic' in src


def _shell_escape(tree, src):
    for n in ast.walk(tree):
        if isinstance(n, ast.Import) and any(a.name.split('.')[0] == 'subprocess' for a in n.names): return True
        if isinstance(n, ast.ImportFrom) and (n.module or '').split('.')[0] == 'subprocess': return True
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr in ('system','popen') and isinstance(n.func.value, ast.Name) and n.func.value.id == 'os': return True


def _sys_path(tree, src):
    for c in _calls(tree):
        f = c.func
        if isinstance(f, ast.Attribute) and f.attr in ('insert','append') and isinstance(f.value, ast.Attribute) \
           and f.value.attr == 'path' and isinstance(f.value.value, ast.Name) and f.value.value.id == 'sys': return True


RULES = [
    Rule('read_file', 'Read files with lnhashview_file (for editing) or view_file(nums=False).', _read_file),
    Rule('big_replace', 'Replace a whole cell or file with %%exhash <path> [<cell_id>] % c; an inner region with a range-c address.', _big_replace),
    Rule('cell_str_replace', 'Edit notebook cells with %%exhash <path> <cell_id>.', _cell_str_replace),
    Rule('rawstr', 'Write non-trivial strings as r""" raw strings; %%exhash text needs no escaping at all.', _rawstr),
    Rule('hashcalc', 'exhash addresses come only from a fresh lnhashview; never compute them.', _hashcalc),
    Rule('tuple_payload', 'Apply a/i/c text with the %%exhash magic: it needs no quoting or escaping.', _tuple_payload),
    Rule('s_newline', r'A 2-char \n in an s-replacement stays literal text: use a real newline in the string.', _s_newline),
    Rule('s_long', 'Use a c command (%%exhash <addr> c) for an s-replacement over 120 chars, except when the line is much longer still.', _s_long),
    Rule('postproc', "Show tooling results bare; narrow with the tool's own parameters.", _postproc),
    Rule('run_magic', 'Invoke magics directly with % syntax.', _run_magic, raw=True),
    Rule('shell_escape', 'Run shell commands with the Bash tool.', _shell_escape, block=True),
    Rule('sys_path', 'Never modify sys.path; stop and ask the user.', _sys_path, block=True)]


_tm = TransformerManager()

def _transform(src):
    "IPython-transform `src` so magics and `!` escapes parse; the raw text comes back if transformation fails"
    try: return _tm.transform_cell(src)
    except Exception: return src


def scan(src):
    "The rules that fire on cell `src`, parsed as IPython would parse it"
    tsrc = _transform(src)
    try: tree = ast.parse(tsrc)
    except SyntaxError: return []
    return [r for r in RULES if r.fn(tree, src if r.raw else tsrc)]
