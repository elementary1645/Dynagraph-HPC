"""Portable v2 evidence archives, explicit profiles and standalone offline verification."""
import argparse
import json
import re
from pathlib import Path
import shutil
import stat
import sys
import tarfile
import tempfile

# Locally use the established validators; the offline kit carries reviewed copies
# beside this module, and never imports code from the untrusted archived source.
if not (Path(__file__).parent/'experiment_records.py').is_file():
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]/'benchmarks/python'))
from archive_contract import FAILED, PROFILES, load, require_files, validate_evidence
from archive_transport import (expand, extract, file_inventory as files, safe_name, sha,
                               verify_sidecar, write_sidecar)
from snapshot import inventory

KIT = ('evidence_archive.py', 'archive_contract.py', 'archive_transport.py',
       'check_execution.py', 'check_registration.py', 'default-tests.json',
       'pipeline_artifacts.py', 'snapshot.py', 'test_smoke.py', 'command_receipts.py',
       'experiment_records.py', 'artifacts.py', 'workloads.py', 'deterministic.py')
BENCH_KIT = {'experiment_records.py', 'artifacts.py', 'workloads.py', 'deterministic.py'}


def kit_path(name):
    local = Path(__file__).parent/name
    if local.is_file():
        return local
    if name in BENCH_KIT:
        return Path(__file__).resolve().parents[2]/'benchmarks/python'/name
    return local


def profile_for(evidence):
    value = load(evidence, 'result.json')
    for profile, (mode, smoke) in PROFILES.items():
        if value.get('mode') == mode and value.get('smoke') is smoke:
            return profile
    raise ValueError('unsupported successful validation profile')


def verify(archive, sidecar=None):
    archive = Path(archive)
    if sidecar is not None:
        verify_sidecar(archive, Path(sidecar))
    with tempfile.TemporaryDirectory(prefix='dynagraph-offline-') as tmp:
        raw, root = Path(tmp)/'payload.tar', Path(tmp)/'content'
        expand(archive, raw)
        extract(raw, root)
        manifest = load(root, 'archive-manifest.json')
        if (type(manifest.get('schema_version')) is not int or manifest['schema_version'] != 2 or
                not isinstance(manifest.get('files'), dict) or manifest.get('integrity_only') is not True or
                manifest.get('profile') not in (*PROFILES, FAILED)):
            raise ValueError('invalid archive manifest schema/profile')
        for name, entry in manifest['files'].items():
            safe_name(name)
            if (not isinstance(entry, dict) or set(entry) != {'mode', 'size', 'sha256'} or
                    type(entry.get('mode')) is not int or not 0 <= entry['mode'] <= 0o777 or
                    type(entry.get('size')) is not int or entry['size'] < 0 or
                    not isinstance(entry.get('sha256'), str) or re.fullmatch('[0-9a-f]{64}', entry['sha256']) is None):
                raise ValueError('invalid archive manifest file entry')
        actual = files(root)
        actual.pop('archive-manifest.json')
        if (manifest['files'] != actual or any(not n.startswith(('evidence/','source/','verifier/')) for n in actual)):
            raise ValueError('complete archive inventory/hash/mode mismatch')
        require_files(root, ['verifier/'+name for name in KIT])
        return validate_evidence(root/'evidence', root/'source', manifest['profile'])


def create(evidence, source, output, profile=None):
    evidence, source, output = Path(evidence).resolve(), Path(source).resolve(), Path(output).absolute()
    if (output.exists() or output.is_symlink() or Path(str(output)+'.sha256').exists() or
            Path(str(output)+'.sha256').is_symlink()):
        raise ValueError('archive and sidecar outputs must be new')
    output = output.resolve()
    safe_name(output.name)
    for root in (evidence, source):
        if root == output or root in output.parents:
            raise ValueError('archive output must be outside inputs')
    profile = profile or profile_for(evidence)
    if profile not in (*PROFILES, FAILED):
        raise ValueError('unsupported archive profile')
    entries = load(evidence, 'source-identity.json').get('inventory')
    if not isinstance(entries, dict) or inventory(source, list(entries)) != entries:
        raise ValueError('source no longer matches completed evidence')
    with tempfile.TemporaryDirectory(prefix='dynagraph-archive-') as tmp:
        stage = Path(tmp)
        for path in evidence.rglob('*'):
            rel = path.relative_to(evidence)
            if rel.parts[0] in ('build', 'tmp', 'mpl-cache'):
                continue
            info = path.lstat()
            if stat.S_ISDIR(info.st_mode):
                continue
            if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
                raise ValueError('unsupported evidence file/link')
            dst = stage/'evidence'/rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, dst)
        for name in entries:
            info = (source/name).lstat()
            if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
                raise ValueError('unsupported source file/link')
            dst = stage/'source'/safe_name(name)
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source/name, dst)
        for name in KIT:
            dst = stage/'verifier'/name
            dst.parent.mkdir(exist_ok=True)
            shutil.copy2(kit_path(name), dst)
        manifest = dict(schema_version=2, profile=profile, files=files(stage), integrity_only=True)
        (stage/'archive-manifest.json').write_text(json.dumps(manifest, sort_keys=True, indent=2)+'\n')
        validate_evidence(stage/'evidence', stage/'source', profile)
        with output.open('xb') as stream, tarfile.open(fileobj=stream, mode='w:gz', format=tarfile.PAX_FORMAT) as tar:
            for name in sorted(files(stage)):
                info = tar.gettarinfo(str(stage/name), arcname=name)
                info.uid = info.gid = 0
                info.uname = info.gname = ''
                info.mtime = 0
                with (stage/name).open('rb') as member:
                    tar.addfile(info, member)
    result = verify(output)
    write_sidecar(output)
    verify_sidecar(output, Path(str(output)+'.sha256'))
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    choice = parser.add_mutually_exclusive_group(required=True)
    choice.add_argument('--verify', type=Path)
    choice.add_argument('--create', type=Path)
    parser.add_argument('--source', type=Path)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--profile', choices=(*PROFILES, FAILED))
    parser.add_argument('--sidecar', type=Path, help='verify transferred archive against this SHA-256 sidecar')
    args = parser.parse_args()
    if args.create and (args.source is None or args.output is None):
        parser.error('--create requires --source and --output')
    if args.verify and args.profile:
        parser.error('--profile applies only to creation; verification reads and enforces the manifest profile')
    try:
        result = verify(args.verify, args.sidecar) if args.verify else create(args.create, args.source, args.output, args.profile)
        print(json.dumps(result, sort_keys=True))
    except (ValueError, OSError, EOFError, tarfile.TarError) as error:
        print('Archive rejected: ' + str(error), file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
