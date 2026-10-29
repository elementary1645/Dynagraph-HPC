"""Full analysis environment gate. No installation or package substitution."""
import io
import json
from pathlib import Path
import sys


def verify(version, version_of, initialize, requirements):
    if version < (3, 11):
        raise ValueError('full validation requires Python >=3.11; found ' + '.'.join(map(str, version)))
    expected = {}
    for line in requirements.read_text().splitlines():
        if line and not line.startswith('#'):
            name, wanted = line.split('==')
            expected[name] = wanted
    actual = {}
    for name, wanted in expected.items():
        try:
            actual[name] = version_of(name)
        except Exception as error:
            raise ValueError(f'missing pinned dependency {name}=={wanted}: {error}') from error
        if actual[name] != wanted:
            raise ValueError(f'pinned dependency mismatch: {name}: required {wanted}, found {actual[name]}')
    try:
        initialize()
    except Exception as error:
        raise ValueError(f'Matplotlib Agg initialization/render failed: {error}') from error
    return actual


def initialize_agg():
    import matplotlib
    matplotlib.use('Agg', force=True)
    from matplotlib import pyplot as plt
    fig, ax = plt.subplots()
    try:
        ax.plot([0, 1], [0, 1])
        fig.savefig(io.BytesIO(), format='png')
    finally:
        plt.close(fig)


def main():
    try:
        # Version check precedes imports that may not exist in older interpreters.
        if sys.version_info < (3, 11):
            raise ValueError('full validation requires Python >=3.11; found ' + sys.version)
        from importlib.metadata import version
        requirements = Path(__file__).resolve().parents[2] / 'benchmarks/requirements-analysis.txt'
        actual = verify(tuple(sys.version_info[:3]), version, initialize_agg, requirements)
        print(json.dumps(dict(python=sys.version, executable=sys.executable,
                              dependencies=actual, renderer='Agg: initialized and rendered')))
    except Exception as error:
        print(f'Full-validation environment check failed: {error}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
