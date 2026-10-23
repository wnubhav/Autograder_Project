# AutoGrader project (context carried over from a claude.ai chat)

## What this is
A friend's assignment: build "AutoGrader", an agent that grades student C programs from an
instructor-written rules file. The full brief is in `Agentic-AI-assignment.pdf` (keep it in
this folder). The plan report already submitted is `agentic01.pdf`.

Hard requirements from the brief:
- Run the submission safely with time and memory limits, and survive crashes and infinite loops.
- Rules (metrics, weights, thresholds, params) live in a JSON file outside the code.
- One analyzer per metric. A coordinator combines them: grade = 100 x sum(weight x score).
- For wrong code: show a failing input with the expected output and an explanation (counter-tests, corner cases).
- Flag suspected copying (other students, online, LLM output).
- Reproducible: same submission + same rules gives the same grade.
- Final report needs a "Usefulness and Limitations" section with 3-4 concrete examples each.

## Design already agreed (keep it simple, no unnecessary complexity)
- Python 3 on Linux/WSL. Tools: gcc, lizard, cppcheck, ASan/UBSan, Valgrind, Groq API (LLM, Week 3).
- Every analyzer returns `{"score": 0..1, "evidence": {...}, "feedback": "one line"}`.
- Registry in `analyzers/__init__.py` maps analyzer name (from rules JSON) to a function.
- First pass: compile, smoke run on the sample input, regex checks for main/scanf/printf/return.
  If the smoke run times out, set `suspected_infinite_loop` and run only source-based analyzers
  (syntax, structure, modularity, readability, originality).
- Two separate compiles. The first pass compiles with plain `gcc` (no -Werror) to get the binary
  every run-based analyzer uses. `compiler_warnings` compiles again using exactly the `flags`
  string from the rules file, so -Werror only lowers the syntax score and never stops other analyzers.
- Edge cases: generate tricky + seeded random inputs, run student code and a reference solution,
  and report any mismatch with input, expected, got and a reason.
- Complexity: time growing input sizes, take the median of 5 runs, map the growth to a class (O(1), O(n), ...).
- Readability: LLM on Groq at temperature 0 with a fixed seed. Cache answers by hash(code + prompt + model).
- Originality: strip comments, replace names with ID and numbers with NUM, compare 5-token
  k-gram sets against a corpus folder (submissions/, ai/, web/). Flag at or above 0.85; never auto-zero.
  Implemented in `analyzers/similarity_flag.py` (was the `originality.py` prototype).
- Reports: `reports/<name>.json` (with the rules SHA-256 and tool versions) plus a text report.
  `reports/` is git-ignored because it is rebuilt on every run. In Week 4, save the final outputs
  for all samples to a committed `sample_outputs/` folder, since the brief requires them.
- Reproducibility check: run the grader twice and compare the grade and every metric score.
  Never compare timings (`time_s` in sandbox results changes from run to run).
- `compiler_warnings` scoring: 0 on a real error, otherwise 1 - 0.25 per warning (agreed).
  The penalty can be overridden with `"penalty_per_warning"` in the metric's params.

## Planned folder layout
```
autograder.py        coordinator (entry point)
sandbox.py           safe runner: subprocess + resource.setrlimit + timeout
first_pass.py
analyzers/__init__.py, compiler_warnings.py, io_tests.py, ...
rules/add.json       copied from the brief
tests/add/           01.in / 01.out ...
submissions/         sample C files (incl. infinite loop, crash, non-compiling)
reports/
```

## Timeline
- Week 1: rules loader, sandbox, first pass, correctness (io_tests) + syntax (compiler_warnings), end-to-end run on add.c
- Week 2: structure, modularity, memory safety, edge-case generator
- Week 3: complexity, readability (LLM), originality, report writer
- Week 4: run on sample submissions, usefulness/limitations, GitHub README, video, final report

## Current status
Week 1 is done (as of 2026-10-22). Built and committed:
- `sandbox.py`: `run(command, input_text, time_limit_s, memory_limit_mb)` returns status
  ok / timeout / crash / error_exit / output_limit. Limits: RLIMIT_CPU, RLIMIT_AS, RLIMIT_FSIZE (1 MB
  output), RLIMIT_CORE; stdin/stdout via temp files; kills the process group on timeout.
  `memory_limit_mb=None` disables the memory limit (needed for ASan in `sanitizer_run`).
  No process-count limit yet (fork bombs not blocked); mention in Limitations.
- `rules.py`: `load_rules(path)` checks required keys, unique names, weights in 0..1 summing to 1,
  and adds `rules["sha256"]`. `rules/add.json` has an added `"sample_input": "tests/add/01.in"`.
- `first_pass.py`: comment-stripped regex checks, plain `gcc ... -lm` into `build/`, smoke run.
  Sets `suspected_infinite_loop` and `can_run` (False if no compile or smoke timeout; a crash
  still allows run-based analyzers).
- `analyzers/io_tests.py`, `analyzers/compiler_warnings.py`, registered in `analyzers/__init__.py`.
  All analyzers have the signature `analyze(source_path, first_pass, params, rules)`.
  `NEEDS_BINARY` there lists the run-based analyzers the coordinator skips when `can_run` is False.
- `autograder.py`: `python3 autograder.py rules/add.json submissions/*.c`. Unregistered
  analyzers score 0 and show "not implemented yet"; analyzer exceptions are caught and recorded.

Current grades (out of a possible 30 until the other analyzers exist): add.c 26.0 (fails tests
07 and 08), add_good.c 30.0, add_crash.c 10.0, add_infinite.c 10.0, add_syntax_error.c 0.0.
Two runs give identical grades and scores.

Week 2 in progress (2026-10-23). Committed in 6ada321 (plus `requirements.txt`, lizard pinned):
- `analyzers/static_analysis.py` (structure): lizard per function (cyclomatic, nloc as length)
  + cppcheck (`--enable=warning,style,performance,portability`). Each over-limit function and
  each cppcheck finding is one problem; score = 1 - 0.2 per problem (`penalty_per_problem`).
- `analyzers/function_split.py` (modularity): counts main + helpers that are actually called
  from another function's body (comments stripped; unused helpers, prototypes and pure
  self-recursion do not count). score = counted / max(min_functions, 2 if expect_helpers).
  Only main() gives 0.5 (the brief's example says 0.3; we chose a plain ratio).
- `first_pass.strip_comments` now keeps line numbers (block comments become their newlines).
- New sample `submissions/add_messy.c`: correct, but one long branchy main, an unused variable
  (compiler warning) and two cppcheck style findings.
- Report `tool_versions` now includes cppcheck and lizard.

Known quirk: cppcheck reports `unknownMacro` on add_syntax_error.c (side effect of the
missing `;`), so a syntax error also costs 0.2 in structure.

Committed in 164575d:
- `analyzers/sanitizer_run.py` (memory safety): ASan + UBSan only. LeakSanitizer works on
  WSL, so no Valgrind. Builds `build/<name>.asan` with the rules' flags plus
  `-fno-sanitize-recover=all -g -fno-omit-frame-pointer`. Runs on every input in the new
  optional param `inputs_dir` (falls back to `sample_input`), no memory limit, 3x time limit.
  Problems are read from stderr (not the exit code) and keyed by (kind, file:line); PIDs and
  addresses are never kept. score = 1 - 0.25 per distinct problem (`penalty_per_problem`).
  When LSan reports a leak, buffered stdout is lost; fine since io_tests judges output.
- `rules/add.json`: sanitizer_run has `"inputs_dir": "tests/add/"`, so add.c loses 0.25 for
  the signed overflow on test 07 (the brief's example gives 10/10 there; our choice).
- New sample `submissions/add_leak.c`: correct, but never frees its malloc.

Limitation to mention: a student program could print fake sanitizer lines on stderr.

Committed with the Week 2 wrap-up:
- `reference/add.c` (copy of add_good.c) is the reference solution, outside submissions/.
- `analyzers/edge_case_runner.py` (logical): per case name, fixed inputs + `random_per_case`
  random ones from one `random.Random(seed)`. Generators: negatives, zero, int_overflow
  (random overflow pairs always land just outside the int range). Reference is compiled into
  `build/reference/` (so it never overwrites the student's `build/add`). Mismatches report
  case, input, expected, got, status, reason; the case reason is used only when the program
  finished normally, otherwise the reason says it crashed or timed out.
  Unknown case name raises an error. score = matching inputs / all inputs (20 for add).
- Rules params added: `reference`, `random_per_case` (3), `seed` (42).
- `LIMITATIONS.md` has 8 entries, each with a concrete wrong-verdict case: input format of
  the generators, timing near the limit, absolute file paths escape the sandbox, fork bombs,
  out-of-memory shown as crash, -O2 changes warnings (tested: 0 vs 2 warnings), cppcheck
  unknownMacro on syntax errors, fake sanitizer lines on stderr. Add new ones there.

Grades now (max possible 70): add 55.0, add_crash 28.5, add_good 70.0, add_infinite 25.0,
add_leak 58.5, add_messy 54.5, add_syntax_error 13.0. Two runs identical (incl. failures).

Week 2 analyzers are all done.

Week 3 in progress (2026-10-23). Repo moved to github.com/wnubhav/Autograder_Project
(history squashed into one "Initial commit"; old repo deleted).
- `analyzers/complexity_estimator.py`: for each size n, input = params["input"].format(n=n)
  (`"{n} {n}"` for add), median of 5 runs. growth = log(time ratio) / log(size ratio) between
  the smallest and largest size only. growth < 0.3 is O(1), < 1.5 is O(n), < 2.5 is O(n^2),
  otherwise worse. score = 1 if the class is the required one or better, else 0. A timeout or
  crash at any size also gives 0.
- Rules sizes changed from the brief's [1, 10, 100] to [1000000, 10000000, 100000000]: at the
  small sizes every program takes about 4 ms (process start-up), so nothing can be told apart.
- New sample `submissions/add_loop.c`: adds by counting (O(n)), growth about 0.73.
- LIMITATIONS.md: 2 new complexity entries (start-up time hides growth; few classes).

Grades now (max possible 80): add 65.0, add_crash 28.5, add_good 80.0, add_infinite 25.0,
add_leak 68.5, add_loop 55.5, add_messy 64.5, add_syntax_error 13.0. Two runs identical.

- Readability was first a rule-based analyzer (`readability_rules.py`, comments/names/line
  length) while Ollama was too slow to download. Both were replaced by the Groq version below.

- `analyzers/similarity_flag.py` (originality, moved from `originality.py`): normalized 5-token
  k-grams against every *.c in corpus_dir (submission itself skipped). Score is always 1.0;
  similarity >= flag_threshold adds a "flag" to the result, and the coordinator collects
  these into the report's "flags" list (printed as FLAG lines). It never lowers the grade.
- New sample `submissions/add_copy.c`: add_good.c with every name changed; similarity 1.00
  with add_good.c, so both get flagged.
- LIMITATIONS.md: 2 originality entries (honest short solution flagged at 0.90; a flag
  costs no points).

- Report writer: `autograder.py` builds the summary with `summary_text(report)`, prints it and
  saves the same text to `reports/<name>.txt` next to `reports/<name>.json`. The text can
  differ between runs when it quotes timings (add_loop's complexity feedback), so the
  reproducibility check compares grades, scores and flags, not the text files.

Grades now (all 9 metrics, out of 100): add 78.33, add_copy 100.0 (flagged), add_crash 46.28,
add_good 100.0 (flagged), add_infinite 41.67, add_leak 88.5, add_loop 70.28, add_messy 81.35,
add_syntax_error 26.33. Two runs identical (grades, scores, flags).

Readability switched to Groq (2026-10-23):
- `analyzers/llm_review.py` calls Groq's OpenAI-compatible API
  (https://api.groq.com/openai/v1/chat/completions) with temperature 0, seed 42 and
  `response_format: json_object`, and asks for {"score": 0-10, "reasons": [...]}; score = value / 10.
  The key comes only from the GROQ_API_KEY environment variable, never from a file in the repo.
  Sends a custom User-Agent (Groq's firewall blocks Python's default one).
- Model: `openai/gpt-oss-120b`. The brief's `llama-3.3-70b-versatile` is no longer served by
  Groq (404 model_not_found), so we picked the largest general model Groq still offers.
- Cache unchanged: cache/llm/<sha256 of code+prompt+model+temperature+seed>.json. cache/llm/ is
  committed, so reruns and anyone without a key get the same readability scores for the samples.
  A new or edited submission needs the key (no key and no cached answer stops the run with a message).
- The model sometimes packs all reasons into one string joined by '","'; the feedback line splits it.
- `readability_rules.py` removed.
- LIMITATIONS.md: 3 readability entries (model also punishes the syntax error: 3/10 vs add.c 6/10;
  new submissions need internet + key; student code is sent to Groq).

Grades now (out of 100): add 81.0, add_copy 97.0 (flagged), add_crash 43.5, add_good 99.0
(flagged), add_infinite 40.0, add_leak 86.5, add_loop 73.5, add_messy 77.5, add_syntax_error 26.0.
Two runs identical (grades, scores, flags); the second run had GROQ_API_KEY unset and used only the cache.

Week 3 is done. Next is Week 4: sample_outputs/, usefulness/limitations, README, video, report.

## Notes
- The brief has two slips: the sample input "75" should be "7 5", and the example report lists
  the expected output of `2147483647 1` as `-2147483648` (the overflowed value). The true sum is
  2147483648. Decide which one the tests treat as correct, and document the choice.
- The brief's rules use the Groq model `llama-3.3-70b-versatile`, which Groq has retired. We use
  `openai/gpt-oss-120b`; the model is a rules setting, so this needs no code change. Say so in the report.

## How to work with me
- Go one step at a time and explain each piece in simple language. My friend has to understand
  and defend the code in the weekly evaluations, and the brief penalises blindly used AI output.
- Keep the code simple and readable. Avoid frameworks and unnecessary abstractions.
- In anything written for the report: plain human language, no em dashes.
