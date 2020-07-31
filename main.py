import argparse
import os

import pandas as pd

import utils
from audits import Plurality, SuperMajority, DHondt

if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description='Verify a Ballot-Polling or Batch-Comparison Risk Limiting Audit'
    )
    parser.add_argument(
        '-r',
        '--risk-limit',
        metavar='<alpha>',
        dest='risk_limit',
        type=float,
        required=True,
        help='risk limit for the RLA'
    )
    parser.add_argument(
        '-p',
        '--p-value',
        metavar='p-value',
        dest='pvalue',
        type=float,
        required=True,
        help='reported p-value for the audit'
    )
    parser.add_argument(
        '-n',
        '--winners',
        metavar='<n_winners>',
        dest='n_winners',
        type=int,
        default=1,
        help='number of winners for the election (default 1)'
    )
    parser.add_argument(
        '-s',
        '--social-choice-function',
        metavar='<type>',
        dest='social_choice',
        required=True,
        choices=[utils.PLURALITY, utils.SUPERMAJORITY, utils.DHONDT],
        help=f'social choice function ({utils.PLURALITY}, {utils.SUPERMAJORITY}, {utils.DHONDT})'
    )
    parser.add_argument(
        '-a',
        '--audit-type',
        metavar='<type>',
        dest='audit_type',
        required=True,
        choices=[utils.BALLOTPOLLING, utils.COMPARISON],
        help=f'auditing scheme ({utils.BALLOTPOLLING}, {utils.COMPARISON})'
    )
    parser.add_argument(
        '-f',
        '--preliminary-count-file',
        metavar='</path/to/file>',
        dest='preliminary',
        required=True,
        help='path to csv file with preliminary results'
    )
    parser.add_argument(
        '-c',
        '--recount-files',
        metavar='</path/to/recount-files>',
        dest='recount',
        required=True,
        help='path to directory containing recount files'
    )
    args = parser.parse_args()
    risk_limit = args.risk_limit
    pvalue = args.pvalue
    n_winners = args.n_winners
    social_choice_function = args.social_choice
    audit_type = args.audit_type
    preliminary_file = args.preliminary
    recount_dir = args.recount

    preliminary = pd.read_csv(preliminary_file)

    recount_df_list = []
    for file in os.listdir(recount_dir):
        if file.endswith('.csv'):
            recount_df_list.append(pd.read_csv(os.path.join(recount_dir, file)))

    recount = pd.concat(recount_df_list, axis=0, ignore_index=True)

    if social_choice_function == utils.PLURALITY:
        audit = Plurality(risk_limit, audit_type, n_winners, preliminary, recount)

    elif social_choice_function == utils.SUPERMAJORITY:
        audit = SuperMajority(risk_limit, audit_type, preliminary, recount)

    elif social_choice_function == utils.DHONDT:
        audit = DHondt(risk_limit, audit_type, n_winners, preliminary, recount)

    else:
        raise NotImplementedError(f'Social choice function {social_choice_function} not implemented')

    audit.sanity_check()
    audit.verify()
    if round(float(audit.max_p_value), 3) == round(pvalue, 3):
        print('Audit validated correctly')

    else:
        print(f'Audit result is incorrect, reached p-value of {audit.max_p_value} != {pvalue}')
