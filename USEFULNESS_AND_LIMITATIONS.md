# Usefulness and Limitations

Four cases where the agent helps, and four where its verdict is wrong or
unreliable. Every example comes from the sample submissions in this
repository; the full reports are in `sample_outputs/`. All results were made
with gcc 15.2 and cppcheck 2.19.

## Usefulness

### 1. A wrong answer is explained with the input, the expected output and a fix

`submissions/add/add.c` stores the sum in an `int`. The report shows the
exact input that breaks it, what should come out, what came out, and how to
fix it:

    INPUT:    2147483647 1
    EXPECTED: 2147483648
    GOT:      -2147483648
    WHY:      sum goes beyond int range; use long long (and %lld) for the
              numbers and the sum

The student does not have to guess which test failed or why. add.c passes
8 of 10 tests and gets 81.0 / 100.

### 2. A copy is caught even when every name is changed

`submissions/add/add_copy.c` is `add_good.c` with every variable and function
renamed. The originality check replaces all names with `ID` and all numbers
with `NUM` before comparing, so the renaming hides nothing: the similarity is
1.00 and both files are flagged for the teacher. The teacher only has to look
at the flagged pairs instead of comparing every submission by hand.

### 3. A correct but slow solution is told apart from a good one

`submissions/search/search_sort.c` bubble sorts the numbers before searching.
It passes all 8 tests and all 8 edge cases, so a test-only grader would give
it full marks. The complexity metric times it on bigger inputs: it times out
at n = 100,000 and gets 0 for complexity (O(n) is required), with the advice
to look at each number once instead of sorting first. It gets 87.0 / 100,
against 99.0 for the plain linear search.

### 4. A memory leak is found in a program that passes every test

`submissions/add/add_leak.c` gives the right answer on all 10 tests but never
frees the memory it allocates. Its output is correct, so the tests cannot see
the problem. AddressSanitizer reports "Direct leak of 16 byte(s)" at
`add_leak.c:8` in `main()`, and the memory safety score drops to 0.75. The
student learns about a bug that would matter in a longer-running program.

## Limitations

### 1. Short programs look copied even when they are not

`submissions/add/add.c` has a similarity of 1.00 with an answer we got from
the Qwen LLM (`submissions/add/corpus/ai/qwen3_8_27b.c`), so it is flagged as
suspected copying. For a five-line program there is really only one obvious
way to write it, and after names and spacing are ignored, everyone's
solution looks the same. The agent cannot tell "copied from an LLM" from
"wrote the obvious thing". This is why a flag never lowers the grade and a
teacher has to decide.

### 2. O(n log n) passes as O(n)

Linear search requires O(n). We tried a version that sorts with `qsort`
(O(n log n)) and then does a binary search. It measured a growth of 0.69,
the same as the real linear search in `search_good.c`, and was judged
"O(n) confirmed". Reading n numbers with `scanf` already takes most of the
run time, and log n changes too little between n = 10,000 and
n = 1,000,000 to show up. A student who sorts first with a good sort gets
full complexity marks for a slower algorithm. (`search_sort.c` is only
caught because bubble sort is O(n^2).)

### 3. A different cppcheck version gives a different grade

`submissions/search/search_crash.c` gets 77.8 with cppcheck 2.19 and 81.8
with cppcheck 2.13. Version 2.19 reports two warnings on line 7
(`nullPointerOutOfMemory` and `ctunullpointerOutOfMemory`: `malloc` might
return NULL and the result is used without a check). Each costs 0.2 in
structure, which is exactly the 4 point difference. The same submission and
the same rules give a different grade on a machine with a different tool
version. The report records the tool versions, so the cause can be found,
but the grade is only reproducible with the same versions.

### 4. The LLM punishes a syntax error in readability

The readability prompt tells the model to judge only how easy the code is to
read. `submissions/add/add_syntax_error.c` is neatly indented and spaced and
differs from a correct program only by one missing `;`, yet it got 3/10,
with "Missing semicolon after scanf reduces readability" as one of the
reasons. The more cramped `submissions/add/add.c` got 6/10. The missing `;`
is already counted by the syntax metric (0), so one character costs points
twice.
