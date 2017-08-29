from comptests.registrar import comptest, run_module_tests

s = """
description: |
    A simple regression test.

constructor: easy_regression.RegressionTest
parameters:
    logs:
    - 20160223-amadoa-amadobot-RCDP2
    processors: []
    analyzers:
    - count_messages

    checks:
    - desc: The number of messages read should remain the same.
      cond: |
        count_messages/20160223-amadoa-amadobot-RCDP2/num_messages == 5330
        count_messages/all/num_messages == 5330
"""

@comptest
def parse_conditions():
    s = " count_messages/20160223-amadoa-amadobot-RCDP2/num_messages == 5330 "
    
    

if __name__ == '__main__':
    run_module_tests()