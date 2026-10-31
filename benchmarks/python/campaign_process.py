"""Bounded POSIX pilot subprocesses; no shell, retries or executable discovery."""
from datetime import datetime, timezone
from contextlib import contextmanager
import os
import selectors
import signal
import subprocess
import sys
import time


@contextmanager
def termination_as_interrupt():
    """CLI/main-thread scope only: reuse interruption cleanup on SIGTERM."""
    requested = False
    def interrupted(signum, frame):
        nonlocal requested
        if not requested:
            requested = True
            raise KeyboardInterrupt('SIGTERM')
    previous = signal.signal(signal.SIGTERM, interrupted)
    try:
        yield
    finally:
        signal.signal(signal.SIGTERM, previous)


@contextmanager
def defer_cleanup_signals():
    """Defer SIGINT/SIGTERM over ownership transitions and kill/reap, not execution.

    A pending signal is delivered on mask restoration; callers still handle the
    original interruption after resources are settled. Linux enforcement requires
    pthread_sigmask; default non-Linux capture retains a portable cleanup path.
    """
    previous = None
    if hasattr(signal, 'pthread_sigmask'):
        previous = signal.pthread_sigmask(signal.SIG_BLOCK, {signal.SIGINT, signal.SIGTERM})
    try:
        yield
    finally:
        if previous is not None:
            signal.pthread_sigmask(signal.SIG_SETMASK, previous)


def timestamp():
    return datetime.now(timezone.utc).isoformat(timespec='microseconds')


class LaunchDeadlineExpired(Exception):
    """No process was created: the launch-layer deadline check expired."""


def capture(command, cwd, environment, timeout, output_limit, *, deadline=None, runtime_observer=None, enforcement=None):
    """Bound each stream in memory and kill the process group on every exit path.

    Timeout includes draining inherited pipes. Children retaining pipes cannot
    evade the deadline by letting the immediate child exit first.
    """
    started = timestamp()
    begin = time.monotonic()
    stop = begin+timeout if deadline is None else min(begin+timeout, deadline)
    buffers = {'stdout': bytearray(), 'stderr': bytearray()}
    result = dict(command=command, start=started, end=None, returncode=None,
                  signal=None, reason='exited', truncated=False)
    process = None
    interruption = None
    barrier = None
    if enforcement is not None:
        from campaign_enforcement import Barrier
        barrier = Barrier(enforcement, command, cwd, environment, stop)
    try:
        with selectors.DefaultSelector() as selector:
            # Setup may consume the caller's remaining budget. Do no further
            # journal/file I/O after this check and before process creation.
            if time.monotonic() >= stop:
                raise LaunchDeadlineExpired('process launch deadline expired')
            if barrier is None:
                process = subprocess.Popen(command, cwd=cwd, env=environment,
                                           stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                           stderr=subprocess.PIPE, start_new_session=True)
            else:
                process = barrier.spawn()
                barrier.verify_and_release(process)
            for name in buffers:
                pipe = getattr(process, name)
                os.set_blocking(pipe.fileno(), False)
                selector.register(pipe, selectors.EVENT_READ, name)
            if runtime_observer is not None:
                try:
                    result['_runtime_snapshot'] = runtime_observer(process.pid)
                except (ValueError, OSError, UnicodeError) as error:
                    result['reason'] = 'capture-error'
                    diagnostic = ('runtime observation rejected: '+str(error)).encode('utf-8')
                    buffers['stderr'].extend(diagnostic[:output_limit])
                    result['truncated'] = len(diagnostic) > output_limit
            while result['reason'] == 'exited' and (selector.get_map() or process.poll() is None):
                remaining = stop - time.monotonic()
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
    except KeyboardInterrupt as error:
        interruption = error
        result['reason'] = 'interrupted'
        if barrier is not None and not barrier.value['released']:
            barrier.fail('interrupted', 'termination during affinity enforcement')
    except TimeoutError as error:
        if barrier is not None and barrier.process is None:
            raise LaunchDeadlineExpired('enforcement setup exhausted launch deadline') from error
        result['reason'] = 'timeout' if barrier is not None else ('launch-error' if process is None else 'capture-error')
        if barrier is not None and not barrier.value['released']:barrier.fail('indeterminate', error)
    except ValueError as error:
        if barrier is None:raise
        process = process or barrier.process
        result['reason'] = 'capture-error' if process is not None else 'launch-error'
        if not barrier.value['released']:barrier.fail('rejected', error)
        diagnostic = str(error).encode('utf-8')
        buffers['stderr'].extend(diagnostic[:output_limit])
        result['truncated'] = len(diagnostic)>output_limit
    except OSError as error:
        if barrier is not None:
            process = process or barrier.process
        result['reason'] = 'launch-error' if process is None else 'capture-error'
        if barrier is not None and not barrier.value['released']:
            barrier.fail('indeterminate', error)
        # Diagnostics are bounded just like child output.
        diagnostic = str(error).encode('utf-8', errors='replace')
        remaining = max(0, output_limit-len(buffers['stderr']))
        buffers['stderr'].extend(diagnostic[:remaining])
        if len(diagnostic) > remaining:
            result['truncated'] = True
    finally:
        primary = sys.exc_info()[1]
        cleanup_errors = []
        def attempt(action):
            try:
                action()
            except BaseException as error:
                cleanup_errors.append(error)
        def terminate_group():
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        try:
            with defer_cleanup_signals():
                if barrier is not None:
                    process = process or barrier.process
                # Close/seal failures cannot bypass termination or reaping.
                if process is not None:
                    attempt(terminate_group)
                    attempt(lambda: process.wait(timeout=2))
                    result['returncode'] = process.returncode
                    if process.returncode is not None and process.returncode < 0:
                        result['signal'] = -process.returncode
                    for name in buffers:
                        attempt(getattr(process, name).close)
                if barrier is not None:
                    attempt(barrier.close)
        except KeyboardInterrupt as error:
            # Pending SIGTERM/SIGINT was delivered only after kill/reap/close.
            interruption = error
            result['reason'] = 'interrupted'
            if barrier is not None and not barrier.value['released'] and barrier.value['state']=='requested':
                barrier.fail('interrupted', error)
        if barrier is not None:
            from campaign_enforcement import seal
            def record_enforcement():
                result['_enforcement'] = seal(barrier.value)
            attempt(record_enforcement)
        result['end'] = timestamp()
        if cleanup_errors:
            first = cleanup_errors[0]
            for extra in cleanup_errors[1:]:
                first.add_note('Additional cleanup failure: '+repr(extra))
            if primary is not None:
                raise primary from first
            if interruption is not None:
                raise interruption from first
            raise first
    if result['reason'] == 'exited' and result['returncode'] != 0:
        result['reason'] = 'signal' if result['signal'] else 'nonzero-exit'
    return result, {name: bytes(data) for name, data in buffers.items()}
