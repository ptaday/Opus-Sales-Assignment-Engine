# Improvements & Tricky Bits

**FUTURE IMPROVEMENTS**

- Configurable timeouts and retry counts (currently hardcoded). 
- Optional checkpoint/resume for long assign runs. 
- A chatbot with a deterministic flow to replicate a compound AI system for running-code UX.

**TRICKY BITS**

# Tricky Bits

- Attio select fields don't support `$not_empty` in filters — couldn't integrate server-side filtering.
- Attio field slugs get a suffix (e.g. `owner_6`) not obvious from UI. API Playground helped.
- Attio numbers can be floats — using `round()` instead of `int()` truncation.
- Visualising the round-robin assignment logic was difficult to reason about on paper. Built a Monte Carlo simulation model to graph distributions and validate the scoring decision. You will be able to find the script under simulations.

"""
