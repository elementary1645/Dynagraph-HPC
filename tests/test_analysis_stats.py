"""Exact synthetic calculations, not algorithm performance assertions."""
from fractions import Fraction
from decimal import Decimal
import unittest
from analysis_test_support import ROOT
from analysis_stats import duration,logarithm,decimal_text,median,quantile,pair_rows,aggregate_pairs,panel_summaries,latency_summary

class StatisticsTests(unittest.TestCase):
    def test_exact_time_large_integers_and_subnanosecond(self):
        self.assertEqual(duration('18446744073709551615','1','1000000000','18446744073709551615'),Fraction(18446744073709551615,1000000000))
        self.assertEqual(duration('1','1','1000000000000','0'),Fraction(1,1000000000000))
        self.assertEqual(duration('0','1','1','0'),0)
        for args in (('1','1','3','0'),('01','1','1','1'),('18446744073709551616','1','1','0')):
            with self.assertRaises(ValueError): duration(*args)

    def test_median_quantiles_and_log_symmetry(self):
        self.assertEqual(median(list(map(Fraction,(1,2,8,9)))),5)
        self.assertEqual(quantile(list(map(Fraction,range(1,101))),95,100),95)
        self.assertEqual(logarithm(Fraction(1)),0)
        self.assertLess(abs(logarithm(Fraction(2))+logarithm(Fraction(1,2))),Decimal('1e-78'))
        with self.assertRaises(ValueError): logarithm(Fraction(0))

    def rows(self,zero=False):
        result=[]
        for block in range(4):
            for position,policy in enumerate(('dijkstra','delta-stepping','incremental','heuristic')):
                value={'dijkstra':8,'delta-stepping':6,'incremental':4,'heuristic':5}[policy]*(block+1)
                if zero and block==0 and policy=='dijkstra':value=0
                result.append(dict(input_id='r',stratum='s',workload_id='w',dependence_group='dep',hardware_id='h',session_id='session',run_id='1',block_id=str(block),
                       policy=policy,trial_id=str(block*4+position),policy_position=str(position),duration_seconds=str(value)+'/1',timing_mode='full-trace',configuration_sha256='c',
                       graph_sha256='g',trace_sha256='t',executable_sha256='e',evidence_class='valid_harness_only',synthetic=True,family='chain',weight_distribution='positive_uniform'))
        return result

    def test_pairing_geometric_mean_zero_and_duplicates(self):
        comparisons=[dict(numerator='incremental',baseline='dijkstra',family='primary'),dict(numerator='dijkstra',baseline='incremental',family='exploratory')]
        paired=pair_rows(self.rows(),comparisons);summary=aggregate_pairs(paired)
        self.assertEqual({s['geometric_mean_ratio'] for s in summary},{'0.5','2'})
        for row in summary:self.assertIsNone(row['confidence_interval'])
        self.assertEqual(aggregate_pairs(pair_rows(self.rows(True),comparisons))[0]['withheld_reason'],'zero_tick_duration')
        with self.assertRaises(ValueError):pair_rows(self.rows()[:-1],comparisons)
        with self.assertRaises(ValueError):pair_rows(self.rows()+[self.rows()[0]],comparisons)

    def test_latency_thresholds_never_pool_trials(self):
        for n in (49,50,99,100,499,500):
            rows=[dict(input_id='i',stratum='s',workload_id='w',hardware_id='h',session_id='s',run_id='1',block_id='0',trial_id='0',policy='dijkstra',
                       evidence_class='valid_harness_only',synthetic=True,timing_mode='per-update',update_index=str(i),duration_seconds=str(i)+'/1') for i in range(n)]
            summary=latency_summary(rows)[0]
            self.assertEqual(summary['median'],str(Fraction(n-1,2).numerator)+'/'+str(Fraction(n-1,2).denominator))
            self.assertEqual(summary['p90'] is not None,n>=50)
            self.assertEqual(summary['p95'] is not None,n>=100)
            self.assertEqual(summary['p99'] is not None,n>=500)
            self.assertEqual(summary['zero_duration_count'],'1')
            self.assertIsNone(summary['confidence_interval'])

    def test_pairing_uses_block_identity_and_retains_all_zero_cases(self):
        comparisons=[dict(numerator='incremental',baseline='dijkstra',family='primary')]
        rows=self.rows()
        # Different block factors make ratio-of-unpaired-means an incorrect estimator.
        expected=[Fraction(1,4),Fraction(1,2),Fraction(3,4),Fraction(1)]
        for row in rows:
            if row['policy']=='incremental':
                row['duration_seconds']=str(8*(int(row['block_id'])+1)*expected[int(row['block_id'])])
        paired=pair_rows(list(reversed(rows)),comparisons)
        self.assertEqual([Fraction(r['runtime_ratio']) for r in paired],expected)
        self.assertTrue(all(int(r['numerator_trial_id'])//4==int(r['baseline_trial_id'])//4 for r in paired))
        for policy in ('incremental','dijkstra','both'):
            current=self.rows()
            for row in current:
                if row['block_id']=='0' and (policy=='both' or row['policy']==policy):row['duration_seconds']='0/1'
            pairs=pair_rows(current,comparisons)
            self.assertEqual(len(pairs),4)
            self.assertEqual(pairs[0]['undefined_reason'],'zero_tick_duration')
            self.assertIsNone(pairs[0]['log_runtime_ratio'])
            self.assertIsNone(aggregate_pairs(pairs)[0]['geometric_mean_ratio'])
        for name in ('graph_sha256','trace_sha256','executable_sha256','session_id'):
            current=self.rows();current[2][name]='different'
            with self.assertRaisesRegex(ValueError,'incompatible'):pair_rows(current,comparisons)

    def test_panel_weights_and_session_replication(self):
        rows=[]
        for workload,ratio in (('a',Fraction(1,2)),('b',Fraction(2))):
            for repetition in range(3 if workload=='a' else 1):
                rows.append(dict(stratum='s',input_id=workload+str(repetition),workload_id=workload,session_id='same',numerator='incremental',baseline='dijkstra',
                                 mean_log_ratio=decimal_text(logarithm(ratio)),withheld_reason=None))
        workloads=[dict(id=x,weight={'numerator':'1','denominator':'1'}) for x in ('a','b')]
        value=panel_summaries(rows,workloads)[0]
        self.assertLess(abs(Decimal(value['geometric_mean_ratio'])-1),Decimal('1e-38'))
        self.assertEqual(value['declared_session_count'],'1')
        workloads[0]['weight']['numerator']='3'
        value=panel_summaries(rows,workloads)[0]
        self.assertLess(abs(Decimal(value['geometric_mean_ratio'])-Decimal('0.5').sqrt()),Decimal('1e-27'))
        self.assertEqual(panel_summaries(rows[:-1],workloads)[0]['withheld_reason'],'incomplete_fixed_workload_panel')

if __name__=='__main__':unittest.main()
