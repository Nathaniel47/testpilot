# Limitations

## Where the results are weak

- **Unseen bugs are not unrelated bugs.** The held-out mutants come from the same
  engine and often the same line as mutants M3 was shown, so a test written for a shown bug can
  catch a neighbouring held-out one. That is a milder advantage than grading on the shown bugs,
  but the score does not prove M3 finds unrelated kinds of bug; an independent tool such as mutmut
  would test that and has not been run. Each half is small, so per-function unseen scores are
  coarse. The all-bug score is biased towards M3, and M2 has the same bias on line and branch
  coverage, the signal it is guided by.
- **Small sample, wide intervals.** The full set is 228 functions from 12 libraries
  (68 dev, 160 test), fewer than the 300 first planned. Bootstrap intervals over about 70 units
  are wide, so small differences between modes are not evidence. Results use the dev split unless
  stated; prompts were tuned on dev only, and the test split should be run once at the end.
- **Scores can move with machine load.** A mutant run that times out is retried once with three
  times the limit; if it times out again it counts as caught, and so does hitting the memory
  limit (see the counts section for how often). Before the retry was added, rescoring the same
  template-baseline tests changed the score of a few units, so a busy machine can still matter.
  Where two modes end with identical tests, compare their per-unit scores to check a given run.
- **Memorisation.** The libraries are popular and public, so the model may have seen their code
  and tests in training. Moving the repo's own tests out of the working copy stops copying from
  the prompt, not from memory. Scores may be inflated for the best-known libraries.
- **Mutation score is an estimate.** The engine is our own and has a small operator set (no
  statement deletion, no exception-type changes, no loop edits). At most 40 mutants are sampled
  per function. Equivalent mutants cannot be removed automatically, so every score is a lower
  bound on the true detection rate. The optional "likely equivalent" flag (a mutant that also
  survives the repo's own tests) is a heuristic that can wrongly drop real survivors when the
  reference suite is weak, and it is slow, so it is off unless `--flag-equivalent` is given. Check
  the counts section: if no mutants are flagged, scores are not corrected at all. The planned
  mutmut cross-check has not been run.
- **Ceiling effect.** Functions are small and get only a handful of mutants each (see the counts
  section), so per-function scores are coarse. If an LLM mode scores close to 1.0, the mutant set
  is too easy to tell stronger modes apart, and differences between M1, M2 and M3 will be hidden.
  A larger operator set (statement deletion, boundary and exception mutations) or more mutants
  per function would be needed to separate them.
- **Template baseline is generous to itself.** B0 drafts that fail are dropped before scoring, so
  its score reflects only tests that already pass. The baseline is weak by design, not a strong
  competitor.
- **One model family, one temperature.** Only Groq's `openai/gpt-oss-120b` at temperature 0 was
  planned for the main runs. The Gemini confirmation run has not been done, and its model ID is
  unverified. Free-tier token limits (about 200K a day) cap how many units and seeds can run.
- **Seeds.** Variance over seeds is only measured where several seeds were actually run (a small
  subset). A seed changes only the model's sampling seed; mutant samples and the shown/unseen
  split stay fixed. At temperature 0 this probably understates how much results could vary.
- **Missing comparisons.** B1 (the library's own human tests, scored per function) and B2
  (Pynguin) are not yet scored, so there is no human-test yardstick in the table.
- **Sandbox.** Process limits and soft guards stop accidents, not a determined attacker; Docker in
  CI is the hard boundary and was not run locally.
- **Python only**, deterministic pure functions only. Results say nothing about code that uses
  files, time, randomness, the network, or large objects, which is much of real code.

## What would improve them

More libraries and units (or a pooled run across all 228 on the test split), several real LLM
seeds, a second model family, the mutmut cross-check in Docker, B1 and B2 on a subset, and a hand
review of a sample of survivors to measure how many are truly equivalent.
