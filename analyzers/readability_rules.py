"""Readability analyzer without AI: three simple, countable checks.

1. Comments: share of non-empty lines that have a comment, compared with
   params["min_comment_ratio"] (for example 0.1 = one line in ten).
   part score = min(1, share / min_comment_ratio)
2. Names: variable and parameter names should have at least
   params["min_name_length"] characters. Loop counters i, j, k are allowed.
   part score = good names / all names
3. Lines: lines should be at most params["max_line_length"] characters.
   part score = short enough lines / all non-empty lines

score = average of the three part scores. Each part gives a short reason.

Finding names uses regular expressions, not a real C parser: we look for a
basic type (int, long, char, ...) followed by a name. Names declared with
other types, such as a struct or a typedef, are not checked.

(analyzers/llm_review.py does the same job with a local LLM; see CLAUDE.md.)
"""

import re

from first_pass import strip_comments

TYPES = r"\b(?:int|long|short|char|float|double|unsigned|signed|size_t|bool)\b"
KEYWORDS = {"int", "long", "short", "char", "float", "double", "unsigned", "signed",
            "size_t", "bool", "const", "static", "return", "sizeof"}
LOOP_COUNTERS = {"i", "j", "k"}


def comment_lines(code):
    """Count lines that hold a comment.

    strip_comments keeps every line in place, so a line that changed when
    comments were removed is a line that had a comment on it.
    """
    before = code.splitlines()
    after = strip_comments(code).splitlines()
    return sum(1 for old, new in zip(before, after) if old != new)


def variable_names(code):
    """Return the set of names declared with a basic type."""
    code = strip_comments(code)
    code = re.sub(r'"(?:\\.|[^"\\])*"', '""', code)   # "strings" can hold any words
    names = set()
    # The first name after a type: "int a", "long long sum;", "int add(int x, ..."
    # The lookahead makes sure it is a variable, not a function name before "(".
    for match in re.finditer(TYPES + r"[\s*]+([A-Za-z_]\w*)\s*(?=[,;=\[)])", code):
        names.add(match.group(1))
    # Further names in a list such as "int a, b, c;" (lines without calls only).
    for match in re.finditer(TYPES + r"[^;(){}]*;", code):
        for part in match.group().split(",")[1:]:
            name = re.match(r"[\s*]*([A-Za-z_]\w*)", part)
            if name:
                names.add(name.group(1))
    return names - KEYWORDS


def analyze(source_path, first_pass, params, rules):
    min_ratio = params.get("min_comment_ratio", 0.1)
    min_name = params.get("min_name_length", 2)
    max_line = params.get("max_line_length", 80)

    with open(source_path, errors="replace") as f:
        code = f.read()
    lines = [line for line in code.splitlines() if line.strip()]
    total = max(len(lines), 1)

    # 1. Comments
    commented = comment_lines(code)
    comments_score = min(1.0, commented / total / min_ratio)
    comments_reason = f"{commented} of {total} lines have a comment (want at least {min_ratio:.0%})"

    # 2. Names
    names = sorted(variable_names(code))
    short = [n for n in names if len(n) < min_name and n not in LOOP_COUNTERS]
    names_score = 1 - len(short) / len(names) if names else 1.0
    if short:
        names_reason = f"{len(short)} of {len(names)} names shorter than {min_name}: {', '.join(short)}"
    else:
        names_reason = f"all {len(names)} names have at least {min_name} characters"

    # 3. Line length
    long_lines = [n for n, line in enumerate(code.splitlines(), 1) if len(line) > max_line]
    lines_score = 1 - len(long_lines) / total
    lines_reason = f"{len(long_lines)} lines longer than {max_line} characters"
    if long_lines:
        lines_reason += f" (line {long_lines[0]} first)"

    score = (comments_score + names_score + lines_score) / 3
    return {
        "score": score,
        "evidence": {
            "comments": {"score": round(comments_score, 2), "commented_lines": commented,
                         "lines": total},
            "names": {"score": round(names_score, 2), "names": names, "too_short": short},
            "lines": {"score": round(lines_score, 2), "too_long": long_lines},
        },
        "feedback": f"comments: {comments_reason}; names: {names_reason}; lines: {lines_reason}",
    }
