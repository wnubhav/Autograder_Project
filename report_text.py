"""The student-facing text report, laid out like the example on page 7 of the brief.

Sections:
  1. score table (weight, score, contribution and feedback for each metric)
  2. flags for the teacher (suspected copying)
  3. "Where you failed": failing tests and edge cases with input, expected, got, why
  4. "Suggestions to raise the grade": the rules' advice line of every metric below full marks
  5. a short usefulness and limitations section (the same for every submission)
"""
import os
import textwrap

# Show at most this many failures per metric; the rest are in the JSON report.
MAX_FAILURES = 3

# Real cases from our sample submissions. Also saved in the JSON report.
USEFULNESS_LIMITATIONS = {
    "usefulness": [
        {"use_case": "Explaining a wrong answer to the student",
         "example": "add.c prints -2147483648 for the input 2147483647 1. The report "
                    "shows the input, the expected 2147483648, what the program printed, "
                    "and says to use long long.",
         "benefit": "The student sees exactly which input breaks the program and how to fix it."},
        {"use_case": "Finding copies for the teacher",
         "example": "add_copy.c is add_good.c with every name changed. The agent still "
                    "finds a similarity of 1.00 and raises a flag.",
         "benefit": "The teacher checks only the flagged pairs instead of every submission."},
    ],
    "limitations": [
        {"limitation": "Short programs look copied even when they are not",
         "example": "add.c has a similarity of 1.00 with an answer from the qwen LLM, "
                    "because the obvious 5-line solution is the same for everyone.",
         "mitigation": "A flag never lowers the grade; the teacher decides."},
        {"limitation": "The readability score is the opinion of an LLM",
         "example": "add_syntax_error.c is neatly written but got 3/10 for one missing ';', "
                    "while the more cramped add.c got 6/10.",
         "mitigation": "Readability is only 10% of the grade, and answers are cached so "
                       "the score does not change between runs."},
    ],
}


def first_pass_status(fp):
    if not fp["compiled"]:
        return "does not compile"
    status = f"compiled, smoke run {fp['smoke']['status']}"
    if fp["suspected_infinite_loop"]:
        status += " (suspected infinite loop: only source-based analyzers run)"
    return status


def wrap(text, indent):
    return textwrap.fill(text, width=72, initial_indent=indent, subsequent_indent=indent)


def why_from_status(status):
    """A reason for a failing test when no analyzer gave a better one."""
    if status == "timeout":
        return "the program did not finish within the time limit"
    if status == "crash":
        return "the program crashed before printing an answer"
    if status == "output_limit":
        return "the program printed far too much output"
    if status == "error_exit":
        return "the program ended with an error code"
    return "the program printed a wrong answer"


def show(text):
    """Line up a multi-line input under the first line, and cut very long lines."""
    lines = [line if len(line) <= 60 else line[:60] + " ..." for line in text.split("\n")]
    return ("\n" + " " * 13).join(lines)


def failure_block(title, failure, why):
    got = failure["got"] if failure["got"] else "(nothing)"
    return [f"{title}",
            f"   INPUT:    {show(failure['input'])}",
            f"   EXPECTED: {show(failure['expected'])}",
            f"   GOT:      {show(got)}",
            textwrap.fill(why, width=72, initial_indent="   WHY:      ",
                          subsequent_indent=" " * 13)]


def where_you_failed(metrics):
    skipped = metrics.get("correctness", {}).get("evidence", {}).get("skipped")
    if skipped:
        return [f"The tests could not be run: {skipped}."]

    tests = metrics.get("correctness", {}).get("evidence", {}).get("failures", [])
    edges = metrics.get("logical", {}).get("evidence", {}).get("failures", [])
    # Edge-case reasons are more helpful than the run status, so reuse them for tests.
    reasons = {e["input"]: e["reason"] for e in edges}

    lines = []
    for t in tests[:MAX_FAILURES]:
        why = reasons.get(t["input"]) if t["status"] == "ok" else None
        lines += failure_block(f"Test {t['test']}", t, why or why_from_status(t["status"]))
    if len(tests) > MAX_FAILURES:
        lines.append(f"... and {len(tests) - MAX_FAILURES} more failing tests")

    # Skip edge cases whose input was already shown as a failing test.
    shown = {t["input"] for t in tests}
    edges = [e for e in edges if e["input"] not in shown]
    for e in edges[:MAX_FAILURES]:
        lines += failure_block(f"Edge case ({e['case']})", e, e["reason"])
    if len(edges) > MAX_FAILURES:
        lines.append(f"... and {len(edges) - MAX_FAILURES} more failing edge cases")

    if not lines:
        lines.append("Nothing: every test and edge case gave the expected answer.")
    return lines


def usefulness_lines():
    lines = ["Useful for:"]
    for i, u in enumerate(USEFULNESS_LIMITATIONS["usefulness"], 1):
        lines += [f"  {i}. {u['use_case']}",
                  wrap("Example: " + u["example"], "     "),
                  wrap("Benefit: " + u["benefit"], "     ")]
    lines.append("Limits of this report:")
    for i, l in enumerate(USEFULNESS_LIMITATIONS["limitations"], 1):
        lines += [f"  {i}. {l['limitation']}",
                  wrap("Example: " + l["example"], "     "),
                  wrap("Fix: " + l["mitigation"], "     ")]
    return lines


def full_report(report):
    """The text saved as reports/<name>.txt."""
    metrics = report["metrics"]
    lines = [f"===== Grading report for {os.path.basename(report['submission'])} =====",
             f"Overall grade: {report['grade']:.1f} / 100",
             f"First pass: {first_pass_status(report['first_pass'])}",
             "",
             f"{'Metric':15} {'Weight':>6}  {'Score':>7}  {'Contribution':>12}  Feedback"]
    for name, r in metrics.items():
        out_of = 100 * r["weight"]
        points = r["score"] * out_of
        score = f"{points:g}/{out_of:g}"
        lines.append(f"{name:15} {out_of:6g}  {score:>7}  {points:12.1f}  {r['feedback']}")

    if report["flags"]:
        lines += ["", "--- Flags for the teacher (they do not change the grade) ---"]
        lines += [f"- {flag}" for flag in report["flags"]]

    lines += ["", "--- Where you failed ---"]
    lines += where_you_failed(metrics)

    lines += ["", "--- Suggestions to raise the grade ---"]
    # The advice line comes from the rules file; without one, repeat the feedback.
    suggestions = [f"- {name}: {r.get('advice', r['feedback'])}"
                   for name, r in metrics.items() if r["score"] < 1]
    lines += suggestions or ["- None: full marks on every metric."]

    lines += ["", "--- Usefulness & limitations of this evaluation ---"]
    lines += usefulness_lines()
    return "\n".join(lines) + "\n"
