#!/usr/bin/env python3
"""The smallest useful client of the clikernel stream protocol: a line REPL, stdlib only.

Run with a gateway up (`python examples/streamrepl.py [URL]`). Enter runs a line
in a kernel created for this session; outputs print as they stream. Blank line
or ctrl-D quits. What this file demonstrates: the whole protocol is `exec` in,
`out`/`done` events back -- everything else (state, interrupts, completion) is
the kernel's, reached through `StreamWorker`."""
import select, sys
from clikernel.stream import StreamWorker

def _text(t): return ''.join(t) if isinstance(t, list) else (t or '')

def show(o):
    ot = o.get('output_type')
    if ot == 'stream': print(_text(o.get('text')), end='')
    elif ot in ('execute_result', 'display_data'): print(_text(o.get('data', {}).get('text/plain', '')))
    elif ot == 'error': print('\n'.join(o.get('traceback', [])))

def main():
    argv = [sys.executable, '-m', 'clikernel.stream', *sys.argv[1:]]
    with StreamWorker(argv=argv) as w:
        while True:
            try: line = input('>>> ')
            except (EOFError, KeyboardInterrupt): break
            if not line: break
            w.exec(line)
            while w.busy:
                select.select([w.fd], [], [], 0.1)
                for ev in w.pump():
                    if ev.get('ev') == 'out': show(ev['output'])

if __name__ == '__main__': main()
