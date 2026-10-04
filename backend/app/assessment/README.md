# assessment/ — owned by Developer 1

Applicability engine (`applies_if` rules), tax calculators, projected crossing, scoring and sequencing.

Only `stubs.py` lives here for now. It is **STUB: replaced by Developer 1**: hard-coded rules per
requirement ID, simple PST ($10,000 rolling 12 months + premises) and GST ($30,000 single quarter or
four quarters) tests, and the section 2.5 scoring formula. It implements `ApplicabilityService`,
`CalculatorService` and `ScoringService` from `app/contracts/services.py`.

Real implementations must keep the protocol signatures and be wired into `app/core/services.py`.
