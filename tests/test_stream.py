import pytest
from clikernel.stream import StreamWorker

@pytest.fixture(scope='module')
def w():
    with StreamWorker() as worker: yield worker

def run(w, code, timeout=15):
    w.exec(code)
    outs = []
    import select, time
    end = time.monotonic() + timeout
    while w.busy and time.monotonic() < end:
        select.select([w.fd], [], [], 0.05)
        for ev in w.pump():
            if ev.get('ev') == 'out': outs.append(ev['output'])
    assert w.busy is None, 'execution did not finish'
    return outs

def test_exec_result(w):
    outs = run(w, '6*7')
    assert outs[-1]['output_type'] == 'execute_result'
    assert '42' in ''.join(outs[-1]['data']['text/plain'])

def test_stream_and_state(w):
    run(w, 'x = 3')
    outs = run(w, 'print("hey", x)')
    assert any(o['output_type'] == 'stream' and 'hey 3' in ''.join(o['text']) for o in outs)

def test_error(w):
    outs = run(w, '1/0')
    assert outs[-1]['output_type'] == 'error'
    assert outs[-1]['ename'] == 'ZeroDivisionError'

def test_complete(w):
    matches, start = w.complete('import o', 8)
    assert 'os' in matches
    assert start == 7

def test_interrupt(w):
    w.exec('import time; time.sleep(30)')
    import time
    time.sleep(0.3)  # let it get into the sleep
    w.interrupt()
    outs = []
    end = time.monotonic() + 10
    while w.busy and time.monotonic() < end:
        import select
        select.select([w.fd], [], [], 0.05)
        for ev in w.pump():
            if ev.get('ev') == 'out': outs.append(ev['output'])
    assert w.busy is None
    assert any(o.get('ename') == 'KeyboardInterrupt' for o in outs)
