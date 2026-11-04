import unittest
from scripts.report_rag_validation import paired_values, bootstrap_delta


class PairedComparisonTests(unittest.TestCase):
    def test_missing_scores_do_not_change_comparison_population(self):
        def row(identity, value, status='scored'):
            return dict(case_id=identity, metrics={'m':dict(value=value,status=status)})
        scores={'old':[row('a',.2),row('b',1)],
                'new':[row('a',.4),row('b',None,'error')]}
        common,values=paired_values(scores,'m')
        self.assertEqual(common,['a'])
        self.assertEqual(values,{'old':[.2],'new':[.4]})

    def test_bootstrap_preserves_pairs(self):
        result=bootstrap_delta([0,.3,.8],[.1,.4,.9],iterations=100)
        self.assertAlmostEqual(result['mean'],.1)
        self.assertAlmostEqual(result['low'],.1)
        self.assertAlmostEqual(result['high'],.1)
        self.assertEqual(result['n'],3)

    def test_empty_and_mismatched_populations_are_explicit(self):
        self.assertIsNone(bootstrap_delta([],[])['mean'])
        with self.assertRaises(ValueError):bootstrap_delta([0],[])


if __name__=='__main__':unittest.main()
