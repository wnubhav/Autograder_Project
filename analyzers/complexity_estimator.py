"""Complexity analyzer: time the program on bigger and bigger inputs.

For each size n in params["sizes"] we build an input from the pattern
params["input"] (for add: "{n} {n}", so both numbers are n), run the program
5 times and keep the median time. The median ignores one or two slow runs
caused by the machine being busy.

Then we compare only the smallest and the largest size:
    growth = log(time ratio) / log(size ratio)
If the time stays flat, growth is near 0 (O(1)). If the time grows as fast
as n, growth is near 1 (O(n)); as fast as n*n, near 2 (O(n^2)). We map
growth to a class with the cut-offs in CLASSES.

Every run also includes about 4 ms for starting the process, which makes
growth come out a bit lower than the true value (a loop up to n gives about
0.8, not 1). The cut-offs are wide enough for that.

score = 1 if the class is the required one or better, else 0.
A timeout or crash at any size also gives 0, since we cannot measure it.
"""

import math
import statistics

import sandbox

RUNS = 5

# (class name, growth must be below this), from fastest to slowest.
CLASSES = [("O(1)", 0.3), ("O(n)", 1.5), ("O(n^2)", 2.5), ("worse than O(n^2)", math.inf)]
ORDER = [name for name, _ in CLASSES]


def classify(growth):
    for name, upper in CLASSES:
        if growth < upper:
            return name


def analyze(source_path, first_pass, params, rules):
    required = params["required"]
    if required not in ORDER:
        raise ValueError(f"unknown required class {required!r}, use one of {ORDER}")

    timings = []  # one {"n", "median_s"} per size
    for n in params["sizes"]:
        test_input = params["input"].format(n=n) + "\n"
        times = []
        for _ in range(RUNS):
            result = sandbox.run([first_pass["binary"]], test_input,
                                 rules["time_limit_s"], rules["memory_limit_mb"])
            if result["status"] != "ok":
                return {
                    "score": 0.0,
                    "evidence": {"required": required, "timings": timings,
                                 "failed_at": n, "status": result["status"]},
                    "feedback": (f"program did not finish normally at size {n} "
                                 f"({result['status']}), so it is slower than {required} or broken"),
                }
            times.append(result["time_s"])
        timings.append({"n": n, "median_s": statistics.median(times)})

    first, last = timings[0], timings[-1]
    # max(..., 0.001): a time of 0 would break the log.
    time_ratio = max(last["median_s"], 0.001) / max(first["median_s"], 0.001)
    growth = math.log(time_ratio) / math.log(last["n"] / first["n"])
    estimated = classify(growth)

    ok = ORDER.index(estimated) <= ORDER.index(required)
    if ok:
        feedback = f"{estimated} confirmed (required {required})"
    else:
        feedback = (f"estimated {estimated}, required {required}: time went from "
                    f"{first['median_s']}s at n={first['n']} to {last['median_s']}s at n={last['n']}")
    return {
        "score": 1.0 if ok else 0.0,
        "evidence": {"required": required, "estimated": estimated,
                     "growth": round(growth, 2), "timings": timings},
        "feedback": feedback,
    }
