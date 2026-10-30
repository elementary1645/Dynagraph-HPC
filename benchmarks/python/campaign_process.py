"""Bounded POSIX pilot subprocesses; no shell, retries or executable discovery."""
from datetime import datetime, timezone
import os
import selectors
import signal
import subprocess
import time


def timestamp():
    return datetime.now(timezone.utc).isoformat(timespec='microseconds')


def capture(command, cwd, environment, timeout, output_limit):
    """Bound each stream in memory and kill the process group on every exit path.

    Timeout includes draining inherited pipes. Children retaining pipes cannot
    evade the deadline by letting the immediate child exit first.
    """
    started = timestamp()
    begin = time.monotonic()
    buffers = {'stdout': bytearray(), 'stderr': bytearray()}
    result = dict(command=command, start=started, end=None, returncode=None,
                  signal=None, reason='exited', truncated=False)
    process = None
    try:
        with selectors.DefaultSelector() as selector:
            process = subprocess.Popen(command, cwd=cwd, env=environment,
                                       stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                       stderr=subprocess.PIPE, start_new_session=True)
            for name in buffers:
                pipe = getattr(process, name)
                os.set_blocking(pipe.fileno(), False)
                selector.register(pipe, selectors.EVENT_READ, name)
            while selector.get_map() or process.poll() is None:
                remaining = timeout - (time.monotonic() - begin)
                if remaining <= 0:
                    result['reason'] = 'timeout'
                    break
                for key, _ in selector.select(min(remaining, 0.05)):
                    data = os.read(key.fd, 65536)
                    if not data:
                        selector.unregister(key.fileobj)
                        continue
                    target = buffers[key.data]
                    available = output_limit - len(target)
                    target.extend(data[:available])
                    if len(data) > available:
                        result.update(reason='output-limit', truncated=True)
                        break
                if result['reason'] == 'output-limit':
                    break
    except KeyboardInterrupt:
        result['reason'] = 'interrupted'
    except OSError as error:
        result['reason'] = 'launch-error' if process is None else 'capture-error'
        # Diagnostics are bounded just like child output.
        buffers['stderr'].extend(str(error).encode('utf-8', errors='replace')[:output_limit])
    finally:
        if process is not None:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            process.wait()
            result['returncode'] = process.returncode
            if process.returncode < 0:
                result['signal'] = -process.returncode
            for name in buffers:
                getattr(process, name).close()
        result['end'] = timestamp()
    if result['reason'] == 'exited' and result['returncode'] != 0:
        result['reason'] = 'signal' if result['signal'] else 'nonzero-exit'
    return result, {name: bytes(data) for name, data in buffers.items()}
