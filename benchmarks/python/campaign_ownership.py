"""Cooperative POSIX directory ownership; no PID inference or process signalling."""
from contextlib import contextmanager
import fcntl
import os
from pathlib import Path

from campaign_contract import path_text

OWNER = 'execution-owner.json'


@contextmanager
def directory_lock(path):
    """Lock the directory inode, refusing symlinks in every path component.

    Locks are advisory and only coordinate cooperating writers on a local
    filesystem implementing flock. They do not establish descendant ownership.
    """
    path = Path(path).absolute()
    path_text(str(path))
    fd = os.open('/', os.O_RDONLY | os.O_DIRECTORY)
    try:
        for part in path.parts[1:]:
            next_fd = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            os.close(fd)
            fd = next_fd
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise ValueError('execution writer is active') from error
        yield path
    finally:
        os.close(fd)


def owner(root, output):
    output = Path(output).absolute()
    identity = output.lstat()
    return dict(schema='dynagraph-pilot-owner', schema_version=1,
                protocol='directory-flock-v1', input_root=str(Path(root).absolute()),
                output_directory=str(output), device=identity.st_dev, inode=identity.st_ino)
