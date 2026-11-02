"""Bounded POSIX pilot subprocesses; no shell, retries or executable discovery."""
from datetime import datetime, timezone
from contextlib import contextmanager
import os
import selectors
import signal
import subprocess
import sys
import time
import threading


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


class CaptureSignals:
    """Record catchable termination before launch through teardown; raise only at checkpoints.

    Installing handlers requires the main thread. Worker-thread callers retain
    their caller's signal policy. No mask is held across Popen/exec.
    """
    def __init__(self):
        self.previous = {}
        self.requested = None
        self.delivered = False

    def install(self):
        if threading.current_thread() is not threading.main_thread():
            return
        try:
            for sig in (signal.SIGINT, signal.SIGTERM):
                old = signal.getsignal(sig)
                if old == signal.SIG_IGN:
                    continue
                self.previous[sig] = old
                signal.signal(sig, self.record)
        except BaseException:
            self.restore()
            raise

    def record(self, signum, frame):
        if self.requested is None:
            self.requested = (signum, frame)

    def checkpoint(self):
        if self.requested is not None and not self.delivered:
            self.delivered = True
            sig, frame = self.requested
            old = self.previous.get(sig)
            if callable(old):
                old(sig, frame)
            raise KeyboardInterrupt(signal.Signals(sig).name)

    def restore(self):
        if not self.previous:
            return
        previous_mask = None
        if hasattr(signal, 'pthread_sigmask'):
            previous_mask = signal.pthread_sigmask(signal.SIG_BLOCK, {signal.SIGINT, signal.SIGTERM})
        try:
            try:
                # A request recorded after the last execution checkpoint must
                # not disappear while handlers are handed back to the caller.
                self.checkpoint()
            finally:
                for sig, old in self.previous.items():
                    signal.signal(sig, old)
                self.previous.clear()
        finally:
            if previous_mask is not None:
                signal.pthread_sigmask(signal.SIG_SETMASK, previous_mask)


def child_exited(process):
    """Inspect without reaping: keep the session leader PID reserved for teardown."""
    if process.returncode is not None:
        return True
    if hasattr(os, 'WNOWAIT'):
        return os.waitid(os.P_PID, process.pid, os.WEXITED | os.WNOHANG | os.WNOWAIT) is not None
    return process.poll() is not None


class OwnedProcessTeardown:
    """One group signal and one bounded reap, with explicit completed steps.

    Linux WNOWAIT retains ownership until killpg. A caller externally reaping
    this exclusively owned child invalidates group ownership; never signal then.
    """
    def __init__(self, process):
        self.process = process
        self.signaled = False
        self.reaped = False
        self.finished = False
        self.deadline = None
        self.failed = False

    def run(self):
        if self.finished or self.failed:
            return
        if self.deadline is None:
            self.deadline = time.monotonic()+2
        try:
            self._run()
        except KeyboardInterrupt:
            raise
        except BaseException:
            self.failed = True
            raise

    def _run(self):
        p = self.process
        if not self.signaled:
            if p.returncode is not None:
                self.reaped = True
                raise ChildProcessError('owned child already reaped; group ownership lost')
            if hasattr(os, 'WNOWAIT'):
                # ECHILD means ownership was lost. Do not signal a recycled PID.
                os.waitid(os.P_PID, p.pid, os.WEXITED | os.WNOHANG | os.WNOWAIT)
            if os.getpgid(p.pid) != p.pid or os.getsid(p.pid) != p.pid:
                raise ChildProcessError('owned child session/group identity changed')
            try:
                os.killpg(p.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            self.signaled = True
        if not self.reaped:
            p.wait(timeout=max(0,self.deadline-time.monotonic()))
            self.reaped = True
        self.finished = True


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
    guard = CaptureSignals()
    guard.install()  # No owned child exists until both handlers are installed.
    if barrier is not None:
        barrier.checkpoint = guard.checkpoint
    try:
        guard.checkpoint()
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
            guard.checkpoint()
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
            guard.checkpoint()
            while result['reason'] == 'exited' and (selector.get_map() or not child_exited(process)):
                guard.checkpoint()
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
        try:
            primary = sys.exc_info()[1]
            cleanup_errors = []
            def attempt(action):
                try:
                    action()
                except KeyboardInterrupt as error:
                    nonlocal interruption
                    interruption = error
                    result['reason'] = 'interrupted'
                except BaseException as error:
                    cleanup_errors.append(error)
            if barrier is not None:
                process = process or barrier.process
            teardown = OwnedProcessTeardown(process) if process is not None else None
            entered = False
            def settle():
                if teardown is not None:
                    attempt(teardown.run)
                    result['returncode'] = process.returncode
                    if process.returncode is not None and process.returncode < 0:
                        result['signal'] = -process.returncode
                    for name in buffers:
                        attempt(getattr(process, name).close)
                if barrier is not None:
                    attempt(barrier.close)
            try:
                with defer_cleanup_signals():
                    entered = True
                    settle()
            except KeyboardInterrupt as error:
                interruption = error
                result['reason'] = 'interrupted'
            except BaseException as error:
                cleanup_errors.append(error)
            finally:
                # Entry failure is not teardown. Persistent non-raising handlers
                # protect this fallback even before a mask can be installed.
                if not entered or (teardown is not None and not teardown.finished and not teardown.failed):
                    settle()
            if teardown is not None and not teardown.finished and not cleanup_errors:
                cleanup_errors.append(RuntimeError('owned-process teardown incomplete'))
            try:
                guard.checkpoint()
            except KeyboardInterrupt as error:
                interruption = error
                result['reason'] = 'interrupted'
                if barrier is not None and not barrier.value['released'] and barrier.value['state']=='requested':
                    barrier.fail('interrupted', error)
            if barrier is not None:
                from campaign_enforcement import seal
                def record_enforcement():
                    result['_enforcement'] = seal(barrier.value)
                attempt(record_enforcement)
            try:
                guard.checkpoint()
            except KeyboardInterrupt as error:
                interruption = error
                result['reason'] = 'interrupted'
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
        finally:
            active_error = sys.exc_info()[1]
            try:
                guard.restore()
            except KeyboardInterrupt as error:
                # Resources are settled. Preserve an unrelated cleanup failure
                # while still recording a final termination request.
                result['reason'] = 'interrupted'
                if active_error is not None:
                    active_error.add_note('Termination during signal-handler restoration: '+str(error))
    if result['reason'] == 'exited' and result['returncode'] != 0:
        result['reason'] = 'signal' if result['signal'] else 'nonzero-exit'
    return result, {name: bytes(data) for name, data in buffers.items()}
