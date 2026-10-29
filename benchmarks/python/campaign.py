"""Planning and hardware qualification only. No benchmark execution subcommand."""
import argparse
from pathlib import Path
import sys

from campaign_contract import expand, plan_hash, read_json, validate_plan
from campaign_hardware import admit, inspect
from workloads import canonical_json


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    sub = parser.add_subparsers(dest='command', required=True)
    for name in ('validate', 'expand', 'admit'):
        command = sub.add_parser(name, allow_abbrev=False)
        command.add_argument('--plan', required=True, type=Path)
        if name == 'admit': command.add_argument('--hardware', required=True, type=Path)
    probe = sub.add_parser('inspect', allow_abbrev=False)
    probe.add_argument('--executable', type=Path)
    probe.add_argument('--pid', type=int, help='inspect existing process mappings; never launch a process')
    args = parser.parse_args(argv)
    try:
        if args.command == 'inspect':
            if args.executable is not None and not args.executable.is_file():
                raise ValueError('inspected executable must be an existing file')
            if args.pid is not None and args.executable is None:
                raise ValueError('--pid requires --executable')
            result = inspect(args.executable, pid=args.pid)
        else:
            plan = validate_plan(read_json(args.plan))
            if args.command == 'validate':
                result = dict(status='valid', planning_only=True, plan_sha256=plan_hash(plan))
            elif args.command == 'expand': result = expand(plan)
            else: result = admit(plan, read_json(args.hardware))
        sys.stdout.buffer.write(canonical_json(result))
        return 1 if args.command == 'admit' and not result['admitted'] else 0
    except (ValueError, OSError, RecursionError) as error:
        print('Campaign rejected: '+str(error), file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
