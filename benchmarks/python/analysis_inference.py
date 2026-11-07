"""Numerical primitives, not evidence admission or performance authorization.

One value per independent experimental unit. Never pool ordered update positions.
The current pilot adapter admits no scientific timings. Synthetic tests of these
functions do not establish experimental independence or eligible measurements.
"""
from fractions import Fraction
from decimal import Decimal, localcontext
from analysis_stats import median, quantile, fraction_text, decimal_text, PRECISION
from deterministic import SplitMix64


def _values(values):
    if type(values) is not list or len(values)>10000:
        raise ValueError('bounded numerical sample required')
    result=[]
    for value in values:
        # Exact rational inputs only: no float NaN/Inf, bool, strings or coercion.
        if type(value) not in (int, Fraction) or value < 0:
            raise ValueError('nonnegative exact rational observation required')
        result.append(Fraction(value))
    return result


def numerical_summary(values, *, seed=7, resamples=2000):
    """Exact descriptives and 95% percentile bootstrap CI of the arithmetic mean.

    IID-unit assumption must be justified externally. Withhold CI for n<5 or a
    constant/zero-resolution sample. Nearest-rank endpoints at 2.5% and 97.5%.
    Zero durations remain in descriptives; ratios require strictly positive data.
    """
    values=_values(values)
    rng=SplitMix64(seed)
    if type(resamples) is not int or not 100<=resamples<=10000:
        raise ValueError('resamples must be in [100,10000]')
    if len(values)*resamples>2000000:
        raise ValueError('bootstrap work bound exceeded')
    n=len(values)
    out={'count':n,'mean':None,'median':None,'sample_standard_deviation':None,
         'minimum':None,'maximum':None,'p90':None,'p95':None,'confidence_interval':None,
         'confidence_interval_reason':'empty_sample','method':'iid-unit-percentile-bootstrap-mean-v1',
         'confidence_level':'95/100','seed':seed,'resamples':resamples,
         'scope':'numerical primitive; not scientific admission'}
    if not n:return out
    mean=sum(values,Fraction())/n
    out.update(mean=fraction_text(mean),median=fraction_text(median(values)),
               minimum=fraction_text(min(values)),maximum=fraction_text(max(values)),
               p90=fraction_text(quantile(values,90,100)),p95=fraction_text(quantile(values,95,100)))
    if n>1:
        variance=sum(((v-mean)**2 for v in values),Fraction())/(n-1)
        with localcontext() as context:
            context.prec=PRECISION
            out['sample_standard_deviation']=decimal_text((Decimal(variance.numerator)/Decimal(variance.denominator)).sqrt())
    reason='fewer_than_five_independent_units' if n<5 else 'constant_sample_or_clock_resolution' if min(values)==max(values) else None
    out['confidence_interval_reason']=reason
    if reason is None:
        draws=sorted(sum((values[rng.below(n)] for _ in range(n)),Fraction())/n for _ in range(resamples))
        out['confidence_interval']=[fraction_text(quantile(draws,25,1000)),fraction_text(quantile(draws,975,1000))]
    return out


def paired_numerical_summary(numerator,baseline,*,seed=7,resamples=2000):
    """Paired runtime ratios (candidate/baseline), never an unlabeled speedup.

    Inputs are exact {independent-unit-key: duration} mappings, pre-matched by the
    evidence adapter's workload/configuration/environment. Resample whole pairs.
    """
    if type(numerator) is not dict or type(baseline) is not dict or set(numerator)!=set(baseline):
        raise ValueError('paired independent-unit keys must match exactly')
    if any(type(k) is not str or not k for k in numerator):raise ValueError('invalid pair key')
    a=_values([numerator[k] for k in sorted(numerator)])
    b=_values([baseline[k] for k in sorted(baseline)])
    if any(v==0 for v in a+b):
        return {'count':len(a),'runtime_ratio':None,'reason':'zero_duration_ratio_undefined'}
    return {'count':len(a),'ratio_direction':'candidate/baseline',
            'runtime_ratio':numerical_summary([x/y for x,y in zip(a,b)],seed=seed,resamples=resamples)}


def unavailable_performance():
    return {'sample_count':0,'mean':None,'median':None,'sample_standard_deviation':None,
            'minimum':None,'maximum':None,'percentiles':None,'confidence_interval':None,
            'paired_comparison':None,'speedup':None,
            'reason':'no scientifically eligible verified timing measurements; diagnostic verification excludes timing'}
