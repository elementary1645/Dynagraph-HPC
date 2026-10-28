"""Deterministic SVG/PDF rendering from serialized descriptive tables only."""
import csv
from fractions import Fraction
import importlib.metadata
from pathlib import Path

from experiment_records import POLICIES
from workloads import canonical_json, sha256

COLORS=('#0072B2','#E69F00','#009E73','#CC79A7')
MARKERS=('o','s','^','D')


def pinned_versions():
    requirements=Path(__file__).resolve().parents[1]/'requirements-analysis.txt'
    expected={}
    for line in requirements.read_text().splitlines():
        if line and not line.startswith('#'):
            name,version=line.split('==');expected[name]=version
    actual={name:importlib.metadata.version(name) for name in expected}
    if actual!=expected:
        raise ValueError('rendering dependency versions differ from requirements-analysis.txt')
    return actual


def read_table(path):
    with Path(path).open(newline='',encoding='utf-8') as stream:
        return list(csv.DictReader(stream))


def render(directory,selections):
    versions=pinned_versions()
    import matplotlib
    matplotlib.use('Agg')
    from matplotlib import pyplot as plt
    import matplotlib.ft2font
    # Ignore caller styles and local matplotlibrc settings.
    plt.rcdefaults()
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':9,'svg.hashsalt':'dynagraph-analysis-v1',
                         'pdf.fonttype':42,'svg.fonttype':'path','axes.spines.top':False,'axes.spines.right':False,
                         'figure.dpi':100,'savefig.dpi':150,'path.simplify':False})
    directory=Path(directory)
    trials=read_table(directory/'trials.csv')
    pairs=read_table(directory/'paired-ratios.csv')
    run_ratios=read_table(directory/'run-ratios.csv')
    runtime=read_table(directory/'runtime-summary.csv')
    ecdf=read_table(directory/'latency-ecdf.csv')
    output=directory/'figures';output.mkdir()
    products=[]
    skipped=[]
    groups={}
    for row in trials:
        groups.setdefault((row['stratum'],row['workload_id']),[]).append(row)
    def number(value,scale=1):
        return float(Fraction(value)*scale)
    def comparison_names(values,include_workload=False):
        keys={(r['workload_id'] if include_workload else '',r['numerator'],r['baseline']) for r in values}
        keys=sorted(keys,key=lambda key:(key[0],POLICIES.index(key[1]),POLICIES.index(key[2])))
        return [(w+' | ' if include_workload else '')+a+' / '+b for w,a,b in keys]
    for kind in selections:
        produced=0
        current_groups=groups
        if kind=='family-ratios':
            current_groups={}
            for row in trials:
                if row['timing_mode']=='full-trace':
                    current_groups.setdefault((row['stratum'],'family-'+row['family']),[]).append(row)
        for (stratum,workload),rows in sorted(current_groups.items()):
            full=[r for r in rows if r['timing_mode']=='full-trace']
            latency=[r for r in rows if r['timing_mode']=='per-update']
            if kind in ('latency-ecdf','update-profile') and not latency:
                continue
            if kind not in ('latency-ecdf','update-profile') and not full:
                continue
            selected_pairs=[r for r in pairs if r['stratum']==stratum and (r['family']==rows[0]['family'] if kind=='family-ratios' else r['workload_id']==workload)]
            selected_runs=[r for r in run_ratios if r['stratum']==stratum and (r['family']==rows[0]['family'] if kind=='family-ratios' else r['workload_id']==workload)]
            fig,ax=plt.subplots(figsize=(7.5,4.5))
            suffix=''
            if kind=='paired-ratios':
                comparisons=comparison_names(selected_pairs)
                for index,name in enumerate(comparisons):
                    values=[number(r['runtime_ratio']) for r in selected_pairs if r['runtime_ratio'] and r['numerator']+' / '+r['baseline']==name]
                    ax.scatter([index]*len(values),values,color=COLORS[index%4],marker=MARKERS[index%4])
                ax.set_xticks(range(len(comparisons)),comparisons,rotation=18,ha='right')
                ax.axhline(1,color='0.35',linestyle='--');ax.set_ylabel('Paired runtime ratio\n(numerator / baseline)')
                suffix='; block points; undefined log pairs='+str(sum(bool(r['undefined_reason']) for r in selected_pairs))
            elif kind=='policy-runtimes':
                values=[r for r in runtime if r['stratum']==stratum and r['workload_id']==workload]
                for index,policy in enumerate(POLICIES):
                    for row in values:
                        if row['policy']==policy:
                            mid=number(row['median_seconds'],1000000)
                            ax.errorbar(index,mid,yerr=[[mid-number(row['minimum_seconds'],1000000)],
                                                       [number(row['maximum_seconds'],1000000)-mid]],fmt=MARKERS[index],color=COLORS[index],capsize=3)
                ax.set_xticks(range(4),POLICIES,rotation=15);ax.set_ylabel('Full-trace wall time (µs)')
                suffix='; run medians and observed block ranges, not confidence intervals'
            elif kind=='latency-ecdf':
                values=[r for r in ecdf if r['stratum']==stratum and r['workload_id']==workload]
                for index,policy in enumerate(POLICIES):
                    for trial in sorted({(r['input_id'],r['trial_id']) for r in values if r['policy']==policy}):
                        current=[r for r in values if r['policy']==policy and (r['input_id'],r['trial_id'])==trial]
                        current.sort(key=lambda r:Fraction(r['duration_seconds']))
                        xs=[number(r['duration_seconds'],1000000) for r in current]
                        ys=[number(r['cumulative_fraction']) for r in current]
                        if xs:
                            ax.step([xs[0],*xs],[0,*ys],where='post',color=COLORS[index],linestyle=('-','--','-.',':')[index],label=policy if trial==min((r['input_id'],r['trial_id']) for r in values if r['policy']==policy) else None,alpha=.75)
                ax.set_xlabel('Per-update latency (µs)');ax.set_ylabel('Empirical cumulative fraction');ax.set_ylim(0,1.02);ax.legend()
                suffix='; one step ECDF per trial; dependent update positions; no uncertainty bands'
            elif kind=='update-profile':
                for index,policy in enumerate(POLICIES):
                    current=[r for r in latency if r['policy']==policy]
                    ax.scatter([int(r['update_index']) for r in current],[number(r['duration_seconds'],1000000) for r in current],
                               s=13,alpha=.6,color=COLORS[index],marker=MARKERS[index],label=policy)
                ax.set_xlabel('Canonical update index');ax.set_ylabel('Per-update latency (µs)');ax.legend()
                suffix='; raw trial points; no fitted trend or interpolation'
            elif kind in ('family-ratios','adaptive-comparisons'):
                values=[r for r in selected_runs if r['geometric_mean_ratio'] and (kind!='adaptive-comparisons' or r['numerator']=='heuristic')]
                comparisons=comparison_names(values,kind=='family-ratios')
                for index,name in enumerate(comparisons):
                    current=[r for r in values if (r['workload_id']+' | ' if kind=='family-ratios' else '')+r['numerator']+' / '+r['baseline']==name]
                    ax.scatter([index]*len(current),[float(r['geometric_mean_ratio']) for r in current],color=COLORS[index%4],marker=MARKERS[index%4])
                ax.set_xticks(range(len(comparisons)),comparisons,rotation=18,ha='right');ax.axhline(1,color='0.35',linestyle='--')
                ax.set_ylabel('Geometric mean paired runtime ratio\n(numerator / baseline)')
                suffix='; family='+rows[0]['family']+'; one point per run; withheld summaries='+str(sum(bool(r['withheld_reason']) for r in selected_runs))
            elif kind=='block-order':
                for index,policy in enumerate(POLICIES):
                    for input_id in sorted({r['input_id'] for r in full}):
                        current=[r for r in full if r['policy']==policy and r['input_id']==input_id]
                        ax.scatter([int(r['trial_id']) for r in current],[number(r['duration_seconds'],1000000) for r in current],
                                   color=COLORS[index],marker=MARKERS[index],label=policy if input_id==min(r['input_id'] for r in full) else None)
                ax.set_xlabel('Scheduled trial index within each run (runs overlaid)');ax.set_ylabel('Full-trace wall time (µs)');ax.legend()
                suffix='; raw block/order variation, not inferential uncertainty'
            runs=len({r['input_id'] for r in rows});sessions=len({r['session_id'] for r in rows})
            trials_count=len({(r['input_id'],r['trial_id']) for r in rows})
            block_count=len({(r['input_id'],r['block_id']) for r in rows})
            prefix='SYNTHETIC FIXTURE — ' if rows[0]['synthetic']=='true' else ''
            ax.set_title(prefix+kind+' | '+workload+'\n'+rows[0]['hardware_id']+' | '+rows[0]['evidence_class']+' | '+rows[0]['no_effect'])
            fig.text(.02,.015,f'Runs={runs}; declared sessions={sessions}; blocks={block_count}; trials={trials_count}; samples={len(rows)}\nDescriptive only; ratios <1 favor numerator'+suffix,fontsize=7)
            fig.tight_layout(rect=(0,.12,1,1))
            name=kind+'-'+stratum[:16]+'-'+workload
            for extension in ('svg','pdf'):
                path=output/(name+'.'+extension)
                metadata={'Creator':'DynaGraph-HPC analysis v1'}
                metadata.update({'Date':None} if extension=='svg' else {'CreationDate':None,'ModDate':None})
                fig.savefig(path,metadata=metadata)
                products.append(dict(path=path.relative_to(directory).as_posix(),sha256=sha256(path.read_bytes()),figure_type=kind,
                                     stratum=stratum,workload_id=None if kind=='family-ratios' else workload,family=rows[0]['family']))
            plt.close(fig);produced+=1
        if not produced:
            skipped.append(dict(figure_type=kind,reason='no_accepted_data_in_required_timing_mode'))
    return dict(products=products,skipped=skipped,dependencies=versions,settings=dict(backend='Agg',font='DejaVu Sans',svg_hashsalt='dynagraph-analysis-v1',
                formats=['svg','pdf'],freetype=matplotlib.ft2font.__freetype_version__,confidence_intervals=False))
