"""Generate/verify Phase 5B-1 artifacts. No engine execution or timings."""

import argparse
import sys

from artifacts import read_bounded, verify_bundle, write_bundle
from workloads import MAX_JSON_BYTES, canonical_json, parse_json


def main():
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    commands = parser.add_subparsers(dest="command", required=True)
    generate = commands.add_parser("generate", allow_abbrev=False)
    generate.add_argument("--spec", required=True)
    generate.add_argument("--output", required=True, help="new output directory (must not exist)")
    verify = commands.add_parser("verify", allow_abbrev=False)
    verify.add_argument("--manifest", required=True)
    args = parser.parse_args()
    try:
        if args.command == "generate":
            spec = parse_json(read_bounded(args.spec, MAX_JSON_BYTES))
            manifest_path = write_bundle(spec, args.output)
            result = {"schema_version": 1, "status": "generated", "manifest": str(manifest_path)}
        else:
            result = verify_bundle(args.manifest)
        sys.stdout.buffer.write(canonical_json(result))
        return 0
    except (ValueError, OSError, MemoryError) as error:
        print(f"workload error: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
