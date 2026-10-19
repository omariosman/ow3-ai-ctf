# Author notes — Context Hijack

- Distinct from Release Roulette (tool permissions), RenderTrap (output
  rendering), Model Crate (artifact integrity) and Model Mirror (extraction):
  the only impact is that retrieved text changes the answer.
- Trust (`trusted`) is application metadata in `corpus.py`; the vulnerable
  step is `simulator.build_context`, which flattens everything into one string.
- Solve check (`state.verify_outcome`), all recomputed server-side: the question
  does not contain the marker, the untrusted FAQ was retrieved, and the
  response has the marker and "lifetime refund".
- Retrieval is keyword overlap; return/refund terms hit the official policy and
  the FAQ, shipping terms hit only `shipping_times.md`.
- Do not add a "secure mode"; the labels in the UI are not a fix.
