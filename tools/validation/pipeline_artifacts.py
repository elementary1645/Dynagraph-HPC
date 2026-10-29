"""Validate smoke products and digests; SHA-256 is integrity, not authentication."""
import hashlib
import math
from pathlib import PurePosixPath
import re
import xml.etree.ElementTree as ET

from check_registration import strict_loads


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def artifact(root, name):
    rel = PurePosixPath(name)
    if rel.is_absolute() or '..' in rel.parts or not rel.parts:
        raise ValueError('unsafe artifact path: ' + name)
    path = root/rel
    if any(p.is_symlink() for p in (path, *path.parents)) or not path.is_file():
        raise ValueError('missing/symlink artifact: ' + name)
    return path


def verify_hashes(root, entries):
    if not isinstance(entries, dict) or not entries:
        raise ValueError('nonempty artifact digest inventory required')
    for name, wanted in entries.items():
        if not isinstance(wanted, str) or re.fullmatch('[0-9a-f]{64}', wanted) is None:
            raise ValueError('invalid artifact digest: ' + name)
        if digest(artifact(root, name)) != wanted:
            raise ValueError('artifact digest mismatch: ' + name)


def verify_figure(path):
    raw = path.read_bytes()
    if path.suffix == '.svg':
        try:
            root = ET.fromstring(raw)
            box = [float(v) for v in root.attrib['viewBox'].split()]
        except (ET.ParseError, KeyError, ValueError) as error:
            raise ValueError('malformed SVG: ' + path.name) from error
        if (root.tag != '{http://www.w3.org/2000/svg}svg' or len(box) != 4 or
                not all(math.isfinite(v) for v in box) or min(box[2:]) <= 0 or
                not any(p.tag == '{http://www.w3.org/2000/svg}path' and p.get('d') for p in root.iter())):
            raise ValueError('empty/invalid SVG: ' + path.name)
    elif path.suffix == '.pdf':
        # Structural sanity of Matplotlib's PDF output, not a general PDF validator.
        end = re.search(rb'startxref\s+(\d+)\s+%%EOF\s*$', raw)
        if (not raw.startswith(b'%PDF-1.') or end is None or
                raw[int(end[1]):int(end[1])+4] != b'xref' or
                b'/Type /Catalog' not in raw or b'/Type /Pages' not in raw or b'/Type /Page ' not in raw):
            raise ValueError('malformed PDF: ' + path.name)
    else:
        raise ValueError('unsupported figure format')


def verify_analysis(directory):
    manifest = strict_loads((directory/'analysis-manifest.json').read_bytes())
    if manifest.get('status') != 'complete':
        raise ValueError('analysis incomplete')
    verify_hashes(directory, manifest['output_sha256'])
    required = {'acceptance.jsonl', 'trials.csv', 'paired-ratios.csv', 'summaries.json', 'report.md'}
    if not required <= manifest['output_sha256'].keys():
        raise ValueError('analysis products missing')
    summary = strict_loads((directory/'summaries.json').read_bytes())
    if summary.get('status') != 'complete' or summary.get('accepted_input_count') != '2':
        raise ValueError('analysis did not accept both timing modes')
    products = manifest['figure_generation']['products']
    kinds = {'paired-ratios', 'policy-runtimes', 'latency-ecdf', 'update-profile',
             'family-ratios', 'adaptive-comparisons', 'block-order'}
    seen = set()
    paths = set()
    for product in products:
        name = product['path']
        if name in paths or manifest['output_sha256'].get(name) != product['sha256']:
            raise ValueError('figure digest missing/contradictory/duplicate')
        paths.add(name)
        path = artifact(directory, name)
        verify_figure(path)
        seen.add((product['figure_type'], path.suffix))
    if seen != {(kind, ext) for kind in kinds for ext in ('.svg', '.pdf')}:
        raise ValueError('missing expected figure types/formats')
    return dict(status='complete', figures=len(products), output_sha256=manifest['output_sha256'])
