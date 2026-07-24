"""Streaming JSON-lines worker protocol: nbformat-shaped output events, and a supervisor for select-based UIs.

The base protocol returns one rendered text body per request -- right for LLM
clients. UI clients (e.g. teleprint) want typed outputs as events instead:
each `shell.run` output (stream/display_data/execute_result/error) arrives as
its own `out` event with the nbformat dict intact (mime bundles included), then
a `done` event. Requests are one JSON object per line: `{"op":"exec","id":n,
"code":...}`, `{"op":"complete","id":n,"code":...,"pos":n}`, `{"op":"exit"}`.
Interrupt is not on the wire: the supervisor sends SIGINT to the worker process.
"""
import json,os,select,signal,subprocess,sys,time

def _emit(obj):
    sys.stdout.write(json.dumps(obj) + '\n')
    sys.stdout.flush()

def _do_exec(shell, req):
    rid = req.get('id')
    for o in shell.run(req['code']): _emit(dict(ev='out', id=rid, output=o))
    _emit({'ev':'done','id':rid})

def _do_complete(shell, req):
    line, pos = req['code'], req.get('pos', len(req['code']))
    try: text, matches = shell.Completer.complete(line_buffer=line, cursor_pos=pos)
    except Exception: text, matches = '', []
    _emit(dict(ev='completions', id=req.get('id'), matches=matches, start=pos - len(text or '')))

def main():
    signal.signal(signal.SIGINT, signal.default_int_handler)
    from clikernel.cli import _make_shell,_set_default_dirs
    _set_default_dirs()
    shell = _make_shell()
    _emit({'ev':'ready'})
    while True:
        try: line = sys.stdin.readline()
        except KeyboardInterrupt: continue  # an idle SIGINT aimed at an execution that just finished
        if not line: break
        req = json.loads(line)
        op = req.get('op')
        if op == 'exit': break
        try:
            if op == 'exec': _do_exec(shell, req)
            elif op == 'complete': _do_complete(shell, req)
            else: _emit(dict(ev='protocol-error', id=req.get('id'), error=f'unknown op {op!r}'))
        except KeyboardInterrupt: _emit(dict(ev='done', id=req.get('id'), interrupted=True))

class StreamWorker:
    "Drive a `clikernel.stream` worker subprocess: non-blocking `pump` for select loops, SIGINT interrupt."
    def __init__(self, argv=None):
        self.proc = subprocess.Popen(argv or [sys.executable,'-m','clikernel.stream'],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, bufsize=0)
        self._buf = b''
        self._next = 1
        self.busy = None  # id of the in-flight exec, or None
        self._wait_for('ready')

    @property
    def fd(self): return self.proc.stdout.fileno()

    def _send(self, **req):
        self.proc.stdin.write((json.dumps(req) + '\n').encode())
        self.proc.stdin.flush()

    def pump(self):
        "All events the worker has written so far (never blocks; call when `fd` selects readable)."
        while select.select([self.fd], [], [], 0)[0]:
            data = os.read(self.fd, 1 << 20)
            if not data: break  # EOF: the worker died
            self._buf += data
        evs = []
        while b'\n' in self._buf:
            line, self._buf = self._buf.split(b'\n', 1)
            ev = json.loads(line)
            if ev.get('ev') == 'done' and ev.get('id') == self.busy: self.busy = None
            evs.append(ev)
        return evs

    def _wait_for(self, kind, timeout=30):
        "Block until an event of `kind` arrives, returning it (any earlier events are dropped: idle-time use only)."
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            for ev in self.pump():
                if ev.get('ev') == kind: return ev
            select.select([self.fd], [], [], min(0.05, max(end - time.monotonic(), 0)))
        raise TimeoutError(f'no {kind} event within {timeout}s')

    def exec(self, code):
        "Send `code` for execution: events arrive via `pump`; returns the request id."
        rid = self._next
        self._next += 1
        self.busy = rid
        self._send(op='exec', id=rid, code=code)
        return rid

    def complete(self, code, pos, timeout=5):
        "Completion round-trip (idle only): returns (matches, start offset in `code`)."
        rid = self._next
        self._next += 1
        self._send(op='complete', id=rid, code=code, pos=pos)
        ev = self._wait_for('completions', timeout)
        return ev.get('matches', []), ev.get('start', pos)

    def interrupt(self):
        "SIGINT the worker: the in-flight execution returns with a KeyboardInterrupt error output."
        if self.busy: self.proc.send_signal(signal.SIGINT)

    def close(self):
        try: self._send(op='exit')
        except Exception: pass
        self.proc.terminate()
        self.proc.wait()

    def __enter__(self): return self
    def __exit__(self, *args): self.close()

if __name__ == '__main__': main()
