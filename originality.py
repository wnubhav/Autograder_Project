"""Originality checker: compares a C file against a folder of other C files.

Steps: remove comments/strings -> turn code into tokens -> replace names with ID
and numbers with NUM -> cut into overlapping 5-token pieces -> compare the sets.
"""
import glob
import os
import re
import sys

KEYWORDS = {
    "int", "long", "short", "char", "float", "double", "void", "unsigned", "signed",
    "const", "static", "struct", "if", "else", "for", "while", "do", "switch", "case",
    "default", "break", "continue", "return", "sizeof",
}
TOKEN = re.compile(r"[A-Za-z_]\w*|\d+(?:\.\d+)?|==|!=|<=|>=|&&|\|\||\+\+|--|->|<<|>>|[^\s\w]")


def normalize(code):
    code = re.sub(r"/\*.*?\*/", " ", code, flags=re.S)    # /* block comments */
    code = re.sub(r"//[^\n]*", " ", code)                 # // line comments
    code = re.sub(r"#[^\n]*", " ", code)                  # #include, #define
    code = re.sub(r'"(?:\\.|[^"\\])*"', " STR ", code)    # "string literals"
    tokens = []
    for t in TOKEN.findall(code):
        if t in KEYWORDS:
            tokens.append(t)                # keep keywords as they are
        elif t[0].isalpha() or t[0] == "_":
            tokens.append("ID")             # every name becomes ID
        elif t[0].isdigit():
            tokens.append("NUM")            # every number becomes NUM
        else:
            tokens.append(t)                # operators and brackets stay
    return tokens


def kgrams(tokens, k=5):
    return {tuple(tokens[i:i + k]) for i in range(len(tokens) - k + 1)}


def similarity(a, b, k=5):
    A, B = kgrams(a, k), kgrams(b, k)
    if not A or not B:
        return 0.0
    return len(A & B) / min(len(A), len(B))   # share of the smaller file found in the other


def check(student_file, corpus_dir, threshold=0.85):
    me = normalize(open(student_file).read())
    best, match = 0.0, None
    for f in sorted(glob.glob(os.path.join(corpus_dir, "**", "*.c"), recursive=True)):
        if os.path.abspath(f) == os.path.abspath(student_file):
            continue
        s = similarity(me, normalize(open(f).read()))
        if s > best:
            best, match = s, f
    flagged = best >= threshold
    return {
        "metric": "originality",
        "score": 0.0 if flagged else 1.0,
        "evidence": {"max_similarity": round(best, 2), "closest_file": match},
        "flagged_for_teacher": flagged,
        "feedback": (f"Very similar to {os.path.basename(match)}; sent for manual review."
                     if flagged else "No close match found."),
    }


if __name__ == "__main__":
    import json
    print(json.dumps(check(sys.argv[1], sys.argv[2]), indent=2))
