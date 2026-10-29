"""Source inventory and faithful overlay copy; no Git or subprocess side effects."""
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import stat


def validate_paths(source, output):
    source, output = source.resolve(), output.resolve()
    if source == output or source in output.parents or output in source.parents:
        raise ValueError('source and output must be disjoint: neither may contain the other')
    if not source.is_dir():
        raise ValueError('source must be an existing directory')
    if output.exists():
        raise ValueError('output must be new; preexisting evidence is never deleted')
    return source, output


def safe_path(root, name):
    rel = PurePosixPath(name)
    if rel.is_absolute() or '..' in rel.parts or not rel.parts or rel.parts[0] == '.git':
        raise ValueError(f'unsafe source path: {name!r}')
    path = root / rel
    for parent in path.parents:
        if parent == root:
            break
        if parent.is_symlink():
            raise ValueError(f'symlink directory in source path: {name!r}')
    return path


def internal_target(root, path):
    """Resolve leaf-link chains without ever traversing outside or through link directories."""
    seen = set()
    while path.is_symlink():
        if path in seen:
            raise ValueError(f'cyclic symlink: {path.relative_to(root)}')
        seen.add(path)
        target = PurePosixPath(os.readlink(path))
        if target.is_absolute():
            raise ValueError(f'nonrelocatable absolute symlink target: {path.relative_to(root)}')
        parts = list(path.parent.relative_to(root).parts)
        for index, part in enumerate(target.parts):
            if part == '..':
                if not parts:
                    raise ValueError(f'symlink escapes checkout boundary: {path.relative_to(root)}')
                parts.pop()
            else:
                parts.append(part)
            component = root.joinpath(*parts)
            if index < len(target.parts) - 1:
                if component.is_symlink():
                    raise ValueError(f'symlink directory in target: {path.relative_to(root)}')
                if not component.is_dir():
                    raise ValueError(f'broken symlink directory: {path.relative_to(root)}')
        if not parts:
            raise ValueError('symlink target may not be the checkout root')
        path = safe_path(root, PurePosixPath(*parts).as_posix())
    if not path.exists():
        raise ValueError(f'broken symlink target: {path.relative_to(root)}')
    return path


def inventory(root, names):
    result = {}
    for name in sorted(set(names)):
        path = safe_path(root, name)
        try:
            info = path.lstat()
        except FileNotFoundError:
            # Git lists tracked deletions; absence is represented by omission,
            # with the deletion itself also retained in the binary Git patch.
            continue
        mode = stat.S_IMODE(info.st_mode)
        if stat.S_ISREG(info.st_mode):
            result[name] = dict(type='file', mode=mode, sha256=hashlib.sha256(path.read_bytes()).hexdigest())
        elif stat.S_ISLNK(info.st_mode):
            target = os.readlink(path)
            internal_target(root, path)
            result[name] = dict(type='symlink', mode=mode, target=target)
        else:
            raise ValueError(f'unsupported source file type (including submodule/directory): {name}')
    for name, entry in result.items():
        if entry['type'] == 'symlink':
            resolved = internal_target(root, root / name).relative_to(root).as_posix()
            if resolved not in result and not any(n.startswith(resolved + '/') for n in result):
                raise ValueError(f'symlink target is not captured in inventory: {name}')
    return result


def copy_inventory(source, destination, entries):
    for name, entry in entries.items():
        src, dst = safe_path(source, name), safe_path(destination, name)
        dst.parent.mkdir(parents=True, exist_ok=True)
        # Only replace a named file in the new checkout, never follow a link.
        if dst.is_symlink():
            dst.unlink()
        if entry['type'] == 'symlink':
            if dst.exists():
                dst.unlink()
            dst.symlink_to(entry['target'])
        else:
            shutil.copy2(src, dst, follow_symlinks=False)


def compare_inventory(expected, actual):
    if expected != actual:
        missing = sorted(expected.keys() - actual.keys())
        extra = sorted(actual.keys() - expected.keys())
        changed = sorted(k for k in expected.keys() & actual.keys() if expected[k] != actual[k])
        raise ValueError(f'source inventory mismatch: missing={missing}, extra={extra}, changed={changed}')


def inventory_hash(entries):
    return hashlib.sha256(json.dumps(entries, sort_keys=True, ensure_ascii=True).encode()).hexdigest()
