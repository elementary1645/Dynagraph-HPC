"""Deterministic diagnostic accounting reports; no scientific timing adapter."""
from pathlib import Path
import platform
from analysis_evidence import load_phase_d, anchored_inventory, VERSION
from analysis_figures import pinned_versions, COLORS
from workloads import canonical_json, sha256


def render_accounting(output,summary):
    import matplotlib
    matplotlib.use('Agg')
    from matplotlib import pyplot as plt
    with plt.rc_context():
        plt.rcdefaults()
        plt.rcParams.update({'font.family':'DejaVu Sans','font.size':9,'svg.hashsalt':VERSION,
                             'pdf.fonttype':42,'svg.fonttype':'path','path.simplify':False})
        fig,axes=plt.subplots(1,2,figsize=(9,4))
        panels=[('Original campaign', ['Unexecuted','Verified'],[summary['original_campaign']['unexecuted'],summary['original_campaign']['verified_complete']]),
                ('Derived pilot: overlapping evidence categories',['Selected','Verified','Interference','Eligible'],
                 [summary['derived_pilot']['selected'],summary['derived_pilot']['verified_complete'],summary['resource_classifications'].get('observed_interference',0),summary['derived_pilot']['scientifically_eligible']])]
        for ax,(title,labels,values) in zip(axes,panels):
            bars=ax.bar(labels,values,color=COLORS[:len(values)]);ax.bar_label(bars,padding=3)
            ax.set_title(title);ax.set_ylabel('Trial count');ax.set_ylim(0,max(values)*1.25+1)
            ax.tick_params(axis='x',rotation=20)
        fig.suptitle('Diagnostic evidence only — no performance measurements')
        fig.tight_layout()
        fig.savefig(output/'accounting.svg',metadata={'Date':None,'Creator':VERSION})
        fig.savefig(output/'accounting.pdf',metadata={'CreationDate':None,'ModDate':None,'Creator':VERSION})
        plt.close(fig)


def analyze_phase_d(source,output,inventory_sha256):
    source=Path(source).absolute();output=Path(output).absolute()
    if output.resolve()==source.resolve() or source.resolve() in output.resolve().parents:
        raise ValueError('output must be outside immutable input evidence')
    summary=load_phase_d(source,inventory_sha256)
    versions=pinned_versions()
    code=Path(__file__).parent
    metadata={'analysis_version':VERSION,'python':platform.python_version(),'packages':versions,
              'code_sha256':{p.name:sha256(p.read_bytes()) for p in sorted(code.glob('analysis_*.py'))},
              'entrypoint_sha256':sha256((code/'analyze.py').read_bytes()),
              'requirements_sha256':sha256((code.parent/'requirements-analysis.txt').read_bytes()),
              'numerical_method':{'bootstrap':'iid-unit percentile mean; nearest-rank 2.5/97.5%; n>=5 nonconstant units',
                                  'seed':7,'resamples':2000,'performed_on_actual_evidence':False}}
    summary['analysis_metadata']=metadata
    output.mkdir(parents=True,exist_ok=False)
    (output/'summary.json').write_bytes(canonical_json(summary))
    (output/'diagnostic-trials.jsonl').write_bytes(b''.join(canonical_json(row) for row in summary['diagnostics']))
    render_accounting(output,summary)
    (output/'report.md').write_text(
        '# Phase E diagnostic evidence assessment\n\n'
        'Analysis version: '+VERSION+'. Input inventory SHA-256: `'+inventory_sha256+'`.\n\n'
        'Original campaign: 104 planned, 0 selected/attempted/completed/verified, 104 unexecuted. '
        'Derived pilot: 104 expanded, 2 selected/attempted/completed/verified, 102 unselected; 2 diagnostic-only. '
        'Interrupted/rejected executions: 0. Scientifically eligible observations: 0.\n\n'
        'Retained resource classifications: '+str(summary['resource_classifications'])+'. Complete coverage is verified. '
        'They are correctness/evidence observations, not performance measurements. Timing values are null. '
        'Mean, median, standard deviation, percentiles, confidence intervals, paired comparisons and speedup '
        'are unavailable: no scientifically eligible verified timing measurements. '
        'No defensible multicore speedup or performance confidence interval follows.\n\n'
        'The accounting figure shows original and derived identities separately. Pilot categories overlap '
        'and must not be summed. No runtime or scaling figure is generated.\n\n'
        'The numerical library is separately tested with synthetic exact-rational samples. Its bootstrap '
        'requires independent experimental units, at least five nonconstant observations, and resamples '
        'whole matched pairs. Ordered updates are not replication. No bootstrap is applied here.\n\n'
        'All input file identities, code hashes, Python/package versions and method configuration are in '
        'summary.json. Input records were reverified through the existing pilot/journal gates and reconciled '
        'field-by-field with Phase D exports. Anchored digests establish transfer integrity and local '
        'consistency, not producer authentication. Future scientific campaigns require an evidence adapter '
        'with genuine scientific admission; no flag upgrades this diagnostic contract. '
        'TSan acceptance and physical-core/isolation claims remain unmet.\n',encoding='utf-8')
    anchored_inventory(source,inventory_sha256)
    manifest={'analysis_version':VERSION,'status':'complete','source_inventory_sha256':inventory_sha256,
              'analysis_metadata':metadata,'output_sha256':{p.name:sha256(p.read_bytes()) for p in sorted(output.iterdir()) if p.is_file()}}
    (output/'analysis-manifest.json').write_bytes(canonical_json(manifest))
    return {'status':'complete','analysis_version':VERSION,'scientific_eligible_trials':0,'diagnostic_trials':2,'figures':2}
