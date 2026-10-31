"""Isolated Linux launcher. No workload runs until the parent sends one GO byte."""
import hashlib
import json
import os
import sys
import time
from datetime import datetime, timezone


def main():
    ack, gate, target = map(int, sys.argv[1:4])
    cpus = json.loads(sys.argv[4])
    expected = sys.argv[5]
    deadline = float(sys.argv[6])
    arguments = sys.argv[7:]
    message = dict(pid=os.getpid(), process_stat=None, requested_cpus=cpus,
                   applied_cpus=None, executable_sha256=None, timestamp=None,
                   errno=0, error=None)
    try:
        # Pin and hash the same descriptor later passed to execve (also scripts).
        with os.fdopen(os.dup(target), 'rb') as stream:
            raw = stream.read(64*1048576+1)
        if len(raw)>64*1048576 or hashlib.sha256(raw).hexdigest()!=expected:
            raise ValueError('launcher executable identity mismatch')
        os.lseek(target, 0, os.SEEK_SET)
        message['executable_sha256'] = expected
        if time.monotonic()>=deadline:raise ValueError('deadline before affinity application')
        os.sched_setaffinity(0, cpus)
        message['timestamp'] = datetime.now(timezone.utc).isoformat(timespec='microseconds')
        message['applied_cpus'] = sorted(os.sched_getaffinity(0))
        with open('/proc/self/stat', encoding='utf-8') as stream:
            message['process_stat'] = stream.read(16385).strip()
        if message['applied_cpus']!=cpus:
            raise ValueError('OS applied a different affinity; no fallback')
    except (OSError, ValueError) as error:
        message['errno'] = getattr(error, 'errno', None) or 0
        message['error'] = str(error)[:1024]
    raw = (json.dumps(message, sort_keys=True, separators=(',', ':'))+'\n').encode()
    # Acknowledgements fit in the parent's bounded reader, but may exceed PIPE_BUF.
    while raw:
        raw = raw[os.write(ack, raw):]
    os.close(ack)
    if message['error'] is not None:
        return 125
    try:
        if os.read(gate, 1)!=b'G':
            return 125  # Parent crash/EOF is never permission.
    finally:
        os.close(gate)
    if time.monotonic()>=deadline:
        return 125
    os.set_inheritable(target, True)  # Needed for shebang execution via an fd.
    os.execve(target, arguments, os.environ)
    return 125


if __name__=='__main__':
    sys.exit(main())
