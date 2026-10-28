"""Exact descriptive calculations. No inference, resampling or timing execution."""
from decimal import Decimal, ROUND_HALF_EVEN, localcontext
from fractions import Fraction

PRECISION = 80
OUTPUT_PRECISION = 40
CI = {'confidence_interval': None, 'confidence_interval_reason': 'inference_not_implemented'}


def decimal_text(value):
    with localcontext() as context:
        context.prec = PRECISION
        context.rounding = ROUND_HALF_EVEN
        if isinstance(value, Fraction):
            value = Decimal(value.numerator) / Decimal(value.denominator)
        context.prec = OUTPUT_PRECISION
        value = +Decimal(value)
        return '0' if value == 0 else str(value.normalize())


def fraction_text(value):
    return str(value.numerator) + '/' + str(value.denominator)


def parse_fraction(value):
    return Fraction(value)


def duration(ticks, period_num, period_den, stored_ns):
    from experiment_records import uint
    ticks, numerator, denominator = map(uint, (ticks, period_num, period_den))
    if numerator == 0 or denominator == 0:
        raise ValueError('invalid clock period')
    value = Fraction(ticks * numerator, denominator)
    ns = value * 1000000000
    if uint(stored_ns) != ns.numerator // ns.denominator:
        raise ValueError('nanosecond conversion mismatch')
    return value


def logarithm(value):
    if value <= 0:
        raise ValueError('logarithm requires a positive exact ratio')
    with localcontext() as context:
        context.prec = PRECISION
        context.rounding = ROUND_HALF_EVEN
        return (Decimal(value.numerator) / Decimal(value.denominator)).ln()


def median(values):
    values = sorted(values)
    if not values:
        raise ValueError('empty descriptive sample')
    return (values[(len(values)-1)//2] + values[len(values)//2]) / 2


def quantile(values, numerator, denominator):
    values = sorted(values)
    if not values or not 0 < numerator <= denominator:
        raise ValueError('invalid empirical quantile')
    return values[(numerator * len(values) + denominator - 1)//denominator - 1]


def pair_rows(trials, comparisons):
    groups = {}
    for row in trials:
        if row['timing_mode'] != 'full-trace':
            continue
        key = (row['input_id'], row['block_id'])
        group = groups.setdefault(key, {})
        if row['policy'] in group:
            raise ValueError('duplicate paired policy')
        group[row['policy']] = row
    from experiment_records import POLICIES
    output = []
    for key in sorted(groups, key=lambda k:(k[0],int(k[1]))):
        policies = groups[key]
        if set(policies) != set(POLICIES):
            raise ValueError('incomplete four-policy block')
        for comparison in comparisons:
            a, b = policies[comparison['numerator']], policies[comparison['baseline']]
            if any(a[name] != b[name] for name in ('stratum','workload_id','configuration_sha256','run_id',
                                                  'graph_sha256','trace_sha256','executable_sha256',
                                                  'hardware_id','session_id','evidence_class','synthetic')):
                raise ValueError('incompatible paired configuration')
            numerator = parse_fraction(a['duration_seconds'])
            denominator = parse_fraction(b['duration_seconds'])
            ratio = numerator / denominator if denominator else None
            defined = numerator > 0 and denominator > 0
            output.append({key:a[key] for key in ('input_id','stratum','workload_id','dependence_group','hardware_id','session_id',
                                                  'run_id','block_id','graph_sha256','trace_sha256','executable_sha256','configuration_sha256',
                                                  'evidence_class','synthetic','family','weight_distribution')} |
                          dict(numerator=a['policy'],baseline=b['policy'],comparison_family=comparison['family'],
                               numerator_trial_id=a['trial_id'],baseline_trial_id=b['trial_id'],numerator_position=a['policy_position'],baseline_position=b['policy_position'],
                               numerator_seconds=a['duration_seconds'],baseline_seconds=b['duration_seconds'],
                               numerator_elapsed_ticks=a.get('elapsed_ticks'),baseline_elapsed_ticks=b.get('elapsed_ticks'),
                               numerator_period_num=a.get('period_num'),numerator_period_den=a.get('period_den'),
                               baseline_period_num=b.get('period_num'),baseline_period_den=b.get('period_den'),
                               runtime_ratio=fraction_text(ratio) if ratio is not None else None,
                               log_runtime_ratio=decimal_text(logarithm(ratio)) if defined else None,
                               undefined_reason=None if defined else 'zero_tick_duration', **CI))
    return output


def aggregate_pairs(pairs):
    groups = {}
    for row in pairs:
        key = (row['input_id'],row['numerator'],row['baseline'])
        groups.setdefault(key,[]).append(row)
    result = []
    for key in sorted(groups):
        rows = groups[key]
        first = rows[0]
        base = {k:first[k] for k in ('input_id','stratum','workload_id','hardware_id','session_id','dependence_group','numerator','baseline','comparison_family',
                                    'evidence_class','synthetic','family','weight_distribution')}
        base.update(block_count=str(len(rows)), **CI)
        if any(row['undefined_reason'] for row in rows):
            base.update(geometric_mean_ratio=None,mean_log_ratio=None,median_ratio=None,min_ratio=None,max_ratio=None,
                        observed_ratio_range=None,withheld_reason='zero_tick_duration')
        else:
            ratios = [parse_fraction(row['runtime_ratio']) for row in rows]
            with localcontext() as context:
                context.prec = PRECISION
                context.rounding = ROUND_HALF_EVEN
                mean_log = sum((logarithm(ratio) for ratio in ratios),Decimal(0)) / Decimal(len(ratios))
                base.update(geometric_mean_ratio=decimal_text(mean_log.exp()),mean_log_ratio=decimal_text(mean_log),
                            median_ratio=fraction_text(median(ratios)),min_ratio=fraction_text(min(ratios)),max_ratio=fraction_text(max(ratios)),
                            observed_ratio_range=fraction_text(max(ratios)-min(ratios)),withheld_reason=None)
        result.append(base)
    return result


def panel_summaries(run_summaries, workloads):
    """Equal runs within session/workload, then equal sessions, then plan weights.

    Complete fixed panels only. No extra weight for repetitions or updates.
    """
    expected = {workload['id']:Fraction(int(workload['weight']['numerator']),int(workload['weight']['denominator'])) for workload in workloads}
    groups = {}
    for row in run_summaries:
        groups.setdefault((row['stratum'],row['numerator'],row['baseline']),[]).append(row)
    output = []
    for key in sorted(groups):
        rows = groups[key]
        sessions = sorted({row['session_id'] for row in rows})
        reason = None
        if any(row['withheld_reason'] for row in rows):
            reason = 'undefined_run_summary'
        if any({row['workload_id'] for row in rows if row['session_id']==session} != set(expected) for session in sessions):
            reason = 'incomplete_fixed_workload_panel'
        value = None
        with localcontext() as context:
            context.prec = PRECISION
            context.rounding = ROUND_HALF_EVEN
            if reason is None:
                session_logs = []
                for session in sessions:
                    total = Decimal(0)
                    for workload, weight in expected.items():
                        selected = [row for row in rows if row['session_id']==session and row['workload_id']==workload]
                        log_value = sum((Decimal(row['mean_log_ratio']) for row in selected),Decimal(0)) / len(selected)
                        total += log_value * Decimal(weight.numerator) / Decimal(weight.denominator)
                    weight_sum = sum(expected.values(),Fraction(0))
                    session_logs.append(total / (Decimal(weight_sum.numerator)/Decimal(weight_sum.denominator)))
                value = decimal_text((sum(session_logs,Decimal(0))/len(session_logs)).exp())
        output.append(dict(stratum=key[0],numerator=key[1],baseline=key[2],geometric_mean_ratio=value,withheld_reason=reason,
                           declared_session_count=str(len(sessions)),workload_count=str(len(expected)),
                           declared_workload_dependence_group_count=str(len({w.get('dependence_group',w['id']) for w in workloads})),run_count=str(len({row['input_id'] for row in rows})),
                           weighting='equal_runs_within_session_workload_then_equal_sessions_then_explicit_workload_weights', **CI))
    return output


def latency_summary(rows):
    groups = {}
    for row in rows:
        if row['timing_mode']=='per-update':
            groups.setdefault((row['input_id'],row['trial_id']),[]).append(row)
    output=[]
    for key in sorted(groups,key=lambda k:(k[0],int(k[1]))):
        samples=groups[key]
        if len({row['update_index'] for row in samples}) != len(samples):
            raise ValueError('duplicate latency position')
        values=[parse_fraction(row['duration_seconds']) for row in samples]
        result={k:samples[0][k] for k in ('input_id','stratum','workload_id','hardware_id','session_id','run_id','block_id','trial_id','policy','evidence_class','synthetic')}
        result.update(count=str(len(values)),distinct_update_positions=str(len(values)),minimum=fraction_text(min(values)),maximum=fraction_text(max(values)),
                      median=fraction_text(median(values)),zero_duration_count=str(values.count(Fraction(0))),units='seconds', **CI)
        for label,p,threshold in (('p90',90,50),('p95',95,100),('p99',99,500)):
            result[label]=fraction_text(quantile(values,p,100)) if len(values)>=threshold else None
            result[label+'_reason']=None if len(values)>=threshold else 'insufficient_distinct_update_positions'
        output.append(result)
    return output
