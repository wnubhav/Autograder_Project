# Limitations

Notes collected while building the agent, for the "Usefulness and Limitations"
section of the final report. Each one names a concrete case where the agent
gives a wrong or unreliable verdict.

## Edge-case inputs only fit this problem's input format

The edge-case generators in `analyzers/edge_case_runner.py` are written for
this problem's input: two integers on one line. Case names like `negatives`,
`zero` and `int_overflow` make pairs such as `-7 5` or `2147483647 1`.
For a different problem, for example one that reads an array or a string,
these inputs would be meaningless. The program would just get two numbers
it does not expect, and the agent would report mismatches that say nothing
about the student's logic. A new problem needs new generators written in
the code; only the case names and counts can be changed from the rules file.

## Timing close to the limit can turn a pass into a timeout

The time limit is measured on a real clock, and the same program does not
take exactly the same time on every run. If a slow but correct submission
needs about 0.95 seconds against a 1 second limit, it may pass on one run
and time out on the next, for example when the machine is busy with other
work. The grade then changes even though the submission and the rules did
not, which breaks the reproducibility promise for that submission.

## The sandbox only protects against relative file paths

Each program runs in a fresh, empty temporary folder, so a file opened with
a relative name such as `fopen("out.txt", "w")` lands there and is deleted
afterwards. But nothing stops an absolute path. A submission that calls
`fopen("/home/<user>/autograder/reports/add.json", "w")` could overwrite a
report, and one that reads `/home/<user>/.ssh/id_rsa` could print a private
key into its output. The program runs as the same user as the grader, so it
can reach every file that user can. Real isolation would need a separate
user account, a container, or a tool such as firejail.

## Fork bombs are not blocked

The sandbox limits time, memory, output size and core dumps, but not the
number of processes. A submission that calls `fork()` in a loop can fill the
process table and slow down or freeze the whole machine before the time limit
kills it. Setting `RLIMIT_NPROC` would block this, but it counts every
process of the user, not just the student's, so it has to be chosen with care.

## Running out of memory is reported as a crash

The memory limit works by making `malloc` fail once the program asks for more
than allowed. Most student programs do not check for `NULL`, so they then
write through a null pointer and die with a segmentation fault. The report
says "crash", the same word used for a real bug such as an array index out
of range. A program that is correct but uses too much memory, for example one
that allocates a 100 MB array under a 64 MB limit, looks like buggy code,
and the student is not told that memory was the real problem.

## The optimisation level changes the warning count

The syntax score counts warnings from gcc with the flags in the rules file.
Some warnings, such as `-Wmaybe-uninitialized`, only appear when gcc
optimises the code, because the analysis that finds them runs only then.
The brief's example first pass uses `-O2`; our rules use
`-Wall -Wextra -Werror -std=c11` without it. We tested a small program that
reads `a` with `scanf`, sets `s = a` only when `a > 0`, and then prints `s`.
With our flags gcc 15.2 gives 0 warnings, so the syntax score is 1.0. With
`-O2` added it gives 2 warnings: `s` may be used uninitialized, and the
return value of `scanf` is ignored (on Ubuntu, `-O2` also switches on
`_FORTIFY_SOURCE`, which adds that check). The score drops to 0.5. The same
code gets a different syntax score depending on a flag that has nothing to
do with code quality.

## A syntax error also lowers the structure score

When the code does not compile, cppcheck can get confused too. On
`submissions/add_syntax_error.c`, the missing `;` after `scanf(...)` makes
cppcheck report "There is an unknown macro here somewhere" (`unknownMacro`).
That counts as one structure problem, so the student loses 0.2 in structure
for the same mistake that already gives 0 in syntax. The structure verdict
for code that does not compile is therefore not a fair measure of its
structure.

## A program can fake sanitizer reports

The memory safety analyzer reads the sanitizers' reports from the program's
stderr. A student program can print lines to stderr itself, for example
`fprintf(stderr, "x.c:1:1: runtime error: fake\n")`, and the agent counts it
as a real problem. This can only lower the student's own score, so it is not
useful for cheating, but it shows that the analyzer trusts text that the
student's code controls. A clean-looking program could also print confusing
lines that make the evidence hard to read.

## Complexity: process start-up hides small growth

Every timed run includes about 4 ms just to start the program. For
`submissions/add_loop.c`, which adds by counting one step at a time (O(n)),
the time goes from 0.008 s at n = 1,000,000 to 0.219 s at n = 100,000,000.
A true O(n) curve would give a growth of 1, but we measure about 0.73,
because the start-up time makes the small size look slower than it is.
A program whose loop is fast enough to finish in a few milliseconds even at
the largest size would show almost no growth and be wrongly called O(1).
The brief's own sizes `[1, 10, 100]` show this clearly: at those sizes every
program, slow or fast, takes about 4 ms, so we had to raise the sizes in the
rules to `[1000000, 10000000, 100000000]`.

## Complexity: only a few classes, and similar ones look the same

The estimator only knows O(1), O(n), O(n^2) and "worse". It compares just
the smallest and the largest size, so O(log n) looks like O(1) (the time
barely grows) and O(n log n) looks like O(n). If an instructor requires
O(n log n) for a sorting problem, the agent cannot tell a correct merge sort
from an O(n) counting trick, and it cannot require O(log n) at all.
The input pattern (`"input": "{n} {n}"` in the rules) also has to make the
work depend on n. That works for "add two integers" only because a slow
solution loops up to the value of the numbers.

## Originality: short programs look copied even when they are not

The originality check replaces every name with `ID` and every number with
`NUM`, so that renaming variables cannot hide a copy. For a tiny program
this works against honest students. We wrote a solution on its own, with
`int x, y;`, `scanf("%d %d", &x, &y);` and `printf("%d\n", x + y);`, and
compared it with the brief's `add.c`, which uses `a` and `b`. The
similarity is 0.90, above the 0.85 threshold, so the agent flags it as
suspected copying. Almost every student who writes the obvious solution
would be flagged against every other. This is why a flag never lowers the
score and a teacher has to look at it. For short problems the threshold
should be higher, or the check should be switched off.

The same happens against LLM answers. We asked Groq's `qwen/qwen3.8-27b`
for a program that adds two integers and put its answer in
`submissions/corpus/ai/`. The brief's `add.c` matches it with similarity
1.00, because after spacing is ignored the two programs are the same. So
the agent cannot tell "copied from an LLM" from "wrote the obvious thing".
`add_loop.c` is also flagged (0.85) against `gpt_oss_120b.c`, although it
adds by counting and the LLM answer does not. The similarity is the share
of the smaller file found in the bigger one, and the LLM's whole program is
almost the same as `add_loop.c`'s `main()`.

## Originality: a flag does not cost any points

Because a flag never changes the score, the originality metric always gives
1.0. `submissions/add_copy.c` is `add_good.c` with every name changed; the
agent finds it (similarity 1.00) but still gives it 100 / 100. The grade
alone does not show the problem; only the flag in the report does, so a
teacher who reads only the grade misses it.

## Readability: the model also punishes a syntax error

The prompt tells the model to judge only readability, not correctness, but
it does not always follow that. `submissions/add_syntax_error.c` is neatly
indented and spaced, more so than `submissions/add.c`, and differs from a
correct program only by one missing `;`. The model gave it 3/10 and listed
"Missing semicolon after scanf reduces readability" as a reason, while the
more cramped `add.c` got 6/10. The same mistake is already counted by the
syntax metric (0) and the structure metric (cppcheck's unknownMacro), so one
missing character costs points in three places. The model also mentioned
the infinite loop in `add_infinite.c`, which is a correctness problem.

## Readability: new submissions need an internet connection

Only answers that are already in `cache/llm/` can be graded offline. The
cache key is a hash of the exact code, so any change to a submission, even
one added space or a renamed variable, needs a fresh answer from Groq. A
new student's file, graded on a machine with no internet or without the
`GROQ_API_KEY` environment variable set, stops the whole run with an error
instead of giving a grade. The run also stops if Groq is down, if the free
rate limit is used up, or if Groq retires the model in the rules. That
already happened once: the brief's `llama-3.3-70b-versatile` was no longer
served, so we had to switch to `openai/gpt-oss-120b`.

## Readability: student code is sent to Groq's servers

To get a readability score, the full source file is sent to Groq, an outside
company, over the internet. Anything the student wrote in the file goes with
it, for example their name or student number in a header comment. The
students are not asked first, and what Groq does with the code is set by
Groq's terms, not by us. A school that is not allowed to share student work
with outside services cannot use this metric as it is. It would need a local
model (the earlier Ollama plan) or the readability metric removed from the
rules.
