"""Bounded single-gzip transport and preflighted regular-file POSIX tar subset."""
import hashlib
from pathlib import Path, PurePosixPath
import re
import tarfile
import zlib

MAX_COMPRESSED = 256 * 1024 * 1024
MAX_EXPANDED = 1024 * 1024 * 1024
MAX_FILE = 128 * 1024 * 1024
MAX_MEMBERS = 50000
MAX_METADATA = 64 * 1024
MAX_METADATA_TOTAL = 4 * 1024 * 1024
CHUNK = 64 * 1024


def safe_name(name):
    if (not isinstance(name, str) or not name or '\\' in name or ':' in name or
            any(ord(c) < 32 or ord(c) == 127 for c in name) or
            PurePosixPath(name).as_posix() != name or name.startswith('/') or
            any(p in ('', '.', '..') for p in name.split('/'))):
        raise ValueError('unsafe archive path: ' + repr(name))
    try:
        name.encode('utf-8', errors='strict')
    except UnicodeError as error:
        raise ValueError('archive path must be UTF-8') from error
    if len(name.encode('utf-8')) > 4096:
        raise ValueError('archive path length limit exceeded')
    return name


def sha(path):
    value = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(CHUNK), b''):
            value.update(block)
    return value.hexdigest()


def expand(archive, raw):
    """Drain exactly one gzip member; zlib checks CRC and ISIZE at termination."""
    decoder = zlib.decompressobj(31)
    compressed = expanded = 0
    try:
        with archive.open('rb') as source, raw.open('xb') as out:
            for block in iter(lambda: source.read(CHUNK), b''):
                compressed += len(block)
                if compressed > MAX_COMPRESSED:
                    raise ValueError('compressed archive size limit exceeded')
                if decoder.eof:
                    raise ValueError('trailing compressed data or concatenated gzip member')
                pending = block
                while True:
                    piece = decoder.decompress(pending, CHUNK)
                    expanded += len(piece)
                    if expanded > MAX_EXPANDED:
                        raise ValueError('expanded archive size limit exceeded')
                    out.write(piece)
                    pending = decoder.unconsumed_tail
                    if decoder.eof:
                        if decoder.unused_data:
                            raise ValueError('trailing compressed data or concatenated gzip member')
                        break
                    if not pending and len(piece) < CHUNK:
                        break
        if not decoder.eof:
            raise ValueError('incomplete gzip stream/footer')
    except zlib.error as error:
        message = str(error)
        if 'incorrect data check' in message:
            diagnostic = 'invalid gzip CRC'
        elif 'incorrect length check' in message:
            diagnostic = 'invalid gzip size trailer'
        else:
            diagnostic = 'malformed gzip stream'
        raise ValueError(diagnostic) from error


def pax_fields(raw):
    """Parse bounded local PAX records; reject keys that alter size/type/sparseness."""
    fields = {}
    offset = 0
    while offset < len(raw):
        space = raw.find(b' ', offset, min(offset + 12, len(raw)))
        if space < 0 or not raw[offset:space].isdigit():
            raise ValueError('malformed PAX record length')
        length = int(raw[offset:space])
        end = offset + length
        if length <= space-offset+2 or end > len(raw) or raw[end-1:end] != b'\n':
            raise ValueError('malformed PAX record boundary')
        try:
            key, value = raw[space+1:end-1].decode('utf-8').split('=', 1)
        except (UnicodeError, ValueError) as error:
            raise ValueError('malformed PAX field') from error
        if key not in ('path', 'mtime') or key in fields:
            raise ValueError('unsupported or duplicate PAX field: ' + key)
        if key == 'path':
            safe_name(value)
        elif re.fullmatch(r'-?[0-9]{1,20}(\.[0-9]{1,20})?', value) is None:
            raise ValueError('invalid PAX mtime')
        fields[key] = value
        offset = end
    return fields


def preflight(raw):
    """Inspect fixed headers before PAX parsing; no untrusted tarfile.open/extract."""
    size = raw.stat().st_size
    if size < 1024 or size % 512:
        raise ValueError('truncated tar structure/alignment')
    members, names, metadata_total = [], set(), 0
    pending = None
    with raw.open('rb') as stream:
        while True:
            block = stream.read(512)
            if len(block) != 512:
                raise ValueError('missing complete tar terminator')
            if block == b'\0'*512:
                if pending is not None or stream.read(512) != b'\0'*512:
                    raise ValueError('incomplete tar terminator')
                # Standard tar record padding is allowed; further headers/data are not.
                for tail in iter(lambda: stream.read(CHUNK), b''):
                    if any(tail):
                        raise ValueError('unexpected trailing tar data')
                break
            try:
                info = tarfile.TarInfo.frombuf(block, 'utf-8', 'strict')
            except (tarfile.TarError, UnicodeError, ValueError) as error:
                raise ValueError('malformed tar header/checksum') from error
            offset = stream.tell()
            if info.size < 0 or offset + ((info.size+511)//512)*512 > size:
                raise ValueError('truncated tar member payload')
            if info.type == tarfile.XHDTYPE:
                if pending is not None:
                    raise ValueError('consecutive PAX headers unsupported')
                metadata_total += info.size
                if info.size > MAX_METADATA or metadata_total > MAX_METADATA_TOTAL:
                    raise ValueError('PAX metadata size limit exceeded')
                pending = pax_fields(stream.read(info.size))
            elif info.type in (tarfile.REGTYPE, tarfile.AREGTYPE):
                if len(members) >= MAX_MEMBERS:
                    raise ValueError('archive member count limit exceeded')
                if info.size > MAX_FILE:
                    raise ValueError('archive member size limit exceeded')
                name = safe_name((pending or {}).get('path', info.name))
                pending = None
                if name in names:
                    raise ValueError('duplicate archive member: ' + name)
                if info.mode < 0 or info.mode & ~0o777 or info.linkname:
                    raise ValueError('unsupported archive member mode/link')
                names.add(name)
                members.append(dict(name=name, size=info.size, mode=info.mode, offset=offset))
                stream.seek(info.size, 1)
            else:
                raise ValueError('unsupported archive member type')
            padding = (-info.size) % 512
            if stream.read(padding) != b'\0'*padding:
                raise ValueError('invalid tar member padding')
    for name in names:
        if any(str(parent) in names for parent in PurePosixPath(name).parents if str(parent) != '.'):
            raise ValueError('file used as archive parent')
    return members


def extract(raw, root):
    members = preflight(raw)
    root.mkdir()
    with raw.open('rb') as stream:
        for member in members:
            path = root/member['name']
            path.parent.mkdir(parents=True, exist_ok=True)
            stream.seek(member['offset'])
            with path.open('xb') as out:
                remaining = member['size']
                while remaining:
                    block = stream.read(min(CHUNK, remaining))
                    if not block:
                        raise ValueError('truncated tar member during extraction')
                    out.write(block)
                    remaining -= len(block)
            path.chmod(member['mode'])


def write_sidecar(archive):
    safe_name(archive.name)
    sidecar = Path(str(archive) + '.sha256')
    with sidecar.open('x', encoding='utf-8', newline='\n') as stream:
        stream.write(sha(archive) + '  ' + archive.name + '\n')
    return sidecar


def verify_sidecar(archive, sidecar):
    if sidecar.stat().st_size > 8192:
        raise ValueError('SHA-256 sidecar size limit exceeded')
    try:
        text = sidecar.read_text(encoding='utf-8')
    except UnicodeError as error:
        raise ValueError('malformed SHA-256 sidecar') from error
    match = re.fullmatch(r'([0-9a-f]{64})  ([^\r\n]+)\n', text)
    if match is None:
        raise ValueError('malformed SHA-256 sidecar')
    if match[2] != archive.name:
        raise ValueError('SHA-256 sidecar archive basename mismatch')
    if match[1] != sha(archive):
        raise ValueError('SHA-256 sidecar digest mismatch')


def file_inventory(root):
    import stat
    entries = {}
    for path in sorted(root.rglob('*')):
        info = path.lstat()
        if stat.S_ISDIR(info.st_mode):
            continue
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
            raise ValueError('unsupported file/link in archive input: ' + str(path))
        mode = stat.S_IMODE(info.st_mode)
        if mode & ~0o777:
            raise ValueError('unsupported permission bits: ' + str(path))
        entries[safe_name(path.relative_to(root).as_posix())] = dict(mode=mode, size=info.st_size, sha256=sha(path))
    return entries
