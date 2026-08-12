"The stream protocol round trip: a real worker subprocess against a spawned rustygate."
import select, sys, time
import pytest


@pytest.fixture(scope="module")
def gateway():
    from rustygate.tools import start_gateway
    g = start_gateway()
    yield g.url
    g.stop()


def _drain_until(w, pred, timeout=30):
    "Pump until `pred(ev)` matches some event, returning all events seen."
    evs, end = [], time.monotonic() + timeout
    while time.monotonic() < end:
        select.select([w.fd], [], [], 0.05)
        evs += w.pump()
        if any(pred(e) for e in evs): return evs
    raise TimeoutError(f'no matching event within {timeout}s: {evs}')


def test_stream_round_trip(gateway):
    from clikernel.stream import StreamWorker
    with StreamWorker(argv=[sys.executable, '-m', 'clikernel.stream', gateway]) as w:
        rid = w.exec('print("hi"); 6*7')
        evs = _drain_until(w, lambda e: e.get('ev') == 'done' and e.get('id') == rid)
        outs = [e['output'] for e in evs if e.get('ev') == 'out']
        assert any(o['output_type'] == 'stream' and 'hi' in o['text'] for o in outs)
        assert any(o['output_type'] == 'execute_result' and '42' in o['data']['text/plain'] for o in outs)
        assert w.busy is None

        w.exec('x = 41 + 1')                                 # state persists across execs
        _drain_until(w, lambda e: e.get('ev') == 'done')
        rid = w.exec('x')
        evs = _drain_until(w, lambda e: e.get('ev') == 'done' and e.get('id') == rid)
        assert any(e.get('ev') == 'out' and '42' in e['output'].get('data', {}).get('text/plain', '') for e in evs)

        matches, start = w.complete('import o', 8)
        assert 'os' in matches and start == 7

        rid = w.exec('import time; time.sleep(60)')          # interrupt unwedges a long cell
        time.sleep(0.5)
        w.interrupt()
        evs = _drain_until(w, lambda e: e.get('ev') == 'done' and e.get('id') == rid)
        assert any(e.get('ev') == 'out' and e['output'].get('output_type') == 'error' for e in evs)
