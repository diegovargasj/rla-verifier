# Risk Limiting Audit Verifier

Based on `Python3`

This project aims to help verifying the results of a _Risk Limiting Audit_,
made with the project https://github.com/diegovargasj/RLA.git. 

## Dependencies

Install the dependencies with `pip3 install -r requirements.txt`. 

## Usage

To use this, you need the reported results file, and a directory with all the
recounted csv files.

    usage: main.py [-h] -r <alpha> -p p-value [-n <n_winners>] -s <type> -a <type> -f </path/to/file> -c </path/to/recount-files>
    
    Verify a Ballot-Polling or Batch-Comparison Risk Limiting Audit
    
    optional arguments:
      -h, --help            show this help message and exit
      -r <alpha>, --risk-limit <alpha>
                            risk limit for the RLA
      -p p-value, --p-value p-value
                            reported p-value for the audit
      -n <n_winners>, --winners <n_winners>
                            number of winners for the election (default 1)
      -s <type>, --social-choice-function <type>
                            social choice function (plurality, super, dhondt)
      -a <type>, --audit-type <type>
                            auditing scheme (ballot-polling, batch-comparison)
      -f </path/to/file>, --preliminary-count-file </path/to/file>
                            path to csv file with preliminary results
      -c </path/to/recount-files>, --recount-files </path/to/recount-files
                            path to directory containing recount files  

This will compare the given `p-value` with the one reached by running the 
audit correctly. Then print out if it is really correct or not.
