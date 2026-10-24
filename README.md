# AutoGrader

AutoGrader grades student C programs using a rules file written by the instructor.
It compiles and runs each submission safely (with time and memory limits), checks it
with one analyzer per metric, and combines the results into a grade:

    grade = 100 x sum(weight x score)

Each analyzer gives a score from 0 to 1, the evidence behind it and a one-line feedback.
For wrong programs the report shows a failing input with the expected output, what the
program printed and why. Suspected copies (from other students, websites or LLMs) are
flagged for the teacher but never lower the grade. The same submission and the same
rules always give the same grade.

The metrics, weights, limits and parameters all live in `rules/add.json`, not in the code.

| Metric | Analyzer | What it checks |
|---|---|---|
| correctness | `io_tests` | output on the tests in `tests/add/` |
| syntax | `compiler_warnings` | errors and warnings with the rules' gcc flags |
| structure | `static_analysis` | function size and branching (lizard) and cppcheck findings |
| modularity | `function_split` | whether the work is split into helper functions |
| logical | `edge_case_runner` | tricky and random inputs compared with a reference solution |
| complexity | `complexity_estimator` | how the run time grows with the input |
| memory_safety | `sanitizer_run` | AddressSanitizer and UndefinedBehaviorSanitizer reports |
| readability | `llm_review` | an LLM on Groq (temperature 0, fixed seed, cached answers) |
| originality | `similarity_flag` | similarity with other submissions, LLM answers and websites |

## Install (Ubuntu on WSL)

1. Install WSL with Ubuntu from a Windows terminal (skip this on a Linux machine):

       wsl --install -d Ubuntu

2. In Ubuntu, install the C tools and Python:

       sudo apt update
       sudo apt install gcc cppcheck python3 python3-venv python3-pip git

   gcc on Ubuntu already includes the address and undefined behaviour sanitizers.

3. Get the code and install the Python package (lizard) in a virtual environment:

       git clone https://github.com/wnubhav/Autograder_Project.git
       cd Autograder_Project
       python3 -m venv .venv
       source .venv/bin/activate
       pip install -r requirements.txt

4. Set your Groq API key (free at https://console.groq.com). The readability metric needs it:

       export GROQ_API_KEY="your-key-here"

   Add that line to `~/.bashrc` to keep it for new terminals. Never put the key in a file
   in the repository. The answers for the sample submissions are already cached in
   `cache/llm/`, so the samples can be graded without a key. A new or changed submission
   needs the key and an internet connection.

## Run

    python3 autograder.py rules/add.json submissions/*.c

You can also grade one file: `python3 autograder.py rules/add.json submissions/add.c`.
A short summary is printed for each submission, and two files are written:

- `reports/<name>.json`: every score and its evidence, the rules file's SHA-256 hash and the tool versions
- `reports/<name>.txt`: the report for the student (score table, where you failed,
  suggestions to raise the grade, usefulness and limitations)

## Folders

| Path | Contents |
|---|---|
| `autograder.py` | coordinator and entry point: runs the first pass and every metric, computes the grade |
| `sandbox.py` | runs a program with CPU time, memory and output limits, and survives crashes and infinite loops |
| `first_pass.py` | quick checks: main/scanf/printf/return, plain compile, smoke run on the sample input |
| `rules.py` | loads and checks the rules file |
| `report_text.py` | writes the student report in `reports/<name>.txt` |
| `analyzers/` | one file per analyzer; `__init__.py` maps analyzer names from the rules to functions |
| `rules/` | the rules files (`add.json`) |
| `tests/add/` | test inputs (`NN.in`) and expected outputs (`NN.out`) |
| `reference/` | the correct solution that the edge-case analyzer compares against |
| `submissions/` | sample student programs: correct, wrong, crashing, infinite loop, not compiling, leaking, slow, messy, copied |
| `submissions/corpus/` | LLM answers (`ai/`) and website solutions (`web/`), used only for the originality check, never graded |
| `cache/llm/` | saved LLM readability answers, so reruns give the same score |
| `sample_outputs/` | the final `.json` and `.txt` reports for all sample submissions |
| `reports/` | reports from your latest run (not committed) |
| `build/` | compiled programs (not committed) |
| `LIMITATIONS.md` | concrete cases where the agent gives a wrong or unreliable verdict |

## Sample outputs

`sample_outputs/` holds the reports for every program in `submissions/`:

| Submission | Grade | Note |
|---|---|---|
| add.c | 81.0 | fails on overflow (tests 07, 08); flagged: same as an LLM answer |
| add_copy.c | 97.0 | add_good.c with names changed; flagged |
| add_crash.c | 43.5 | null pointer write, crashes on every input |
| add_good.c | 99.0 | correct and clean; flagged with add_copy.c |
| add_infinite.c | 40.0 | infinite loop; only source-based metrics run |
| add_leak.c | 86.5 | correct, but never frees its memory |
| add_loop.c | 73.5 | adds by counting, so it is O(n); flagged against an LLM answer |
| add_messy.c | 77.5 | correct, but one long branchy main and a warning |
| add_syntax_error.c | 26.0 | does not compile |

The run times in the `complexity` feedback of `add_loop` change a little between runs;
the grades, scores and flags do not.
