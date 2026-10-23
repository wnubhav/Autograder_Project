"""Readability analyzer: ask a local LLM (Ollama) to rate how readable the code is.

We send the student's code with a fixed prompt to Ollama's local API
(http://localhost:11434) and ask for JSON like
    {"score": 7, "reasons": ["clear names", "no comments"]}
score = that number / 10.

Reproducible grades:
  - temperature 0 and a fixed seed (both from the rules) make the model
    give the same answer to the same question;
  - every answer is also saved in cache/llm/<hash>.json, where the hash is
    made from the code, the prompt, the model, the temperature and the seed.
    On a rerun we read the saved answer instead of asking again, so the
    score cannot change even if the model would answer slightly differently.

If Ollama is not running, or the model is not downloaded, we stop the whole
grading run with a message that says how to fix it. Carrying on would give
readability 0 and a grade that is wrong without anyone noticing.
"""

import hashlib
import json
import os
import sys
import urllib.error
import urllib.request

OLLAMA_URL = "http://localhost:11434/api/generate"
CACHE_DIR = os.path.join("cache", "llm")
TIMEOUT_S = 300  # the first call also loads the model into memory

PROMPT = """You are grading the readability of a student's C program.
Judge only readability: clear names, helpful comments, consistent indentation
and spacing, short focused functions. Do not judge correctness or speed.
Give a score from 0 (unreadable) to 10 (very clear).
Answer with JSON only, in exactly this form, with at most 3 short reasons:
{"score": <integer 0-10>, "reasons": ["<reason>", "<reason>"]}

Program:
```c
CODE
```
"""


def ask_ollama(model, prompt, temperature, seed):
    """Send one prompt to Ollama and return the text of its answer."""
    request_body = {
        "model": model,
        "prompt": prompt,
        "stream": False,      # one complete answer instead of pieces
        "format": "json",     # Ollama makes the model answer in valid JSON
        "options": {"temperature": temperature, "seed": seed},
    }
    request = urllib.request.Request(
        OLLAMA_URL, data=json.dumps(request_body).encode(),
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_S) as response:
            return json.loads(response.read())["response"]
    except urllib.error.HTTPError as error:
        # Ollama answers 404 when the model has not been downloaded.
        details = error.read().decode(errors="replace")
        sys.exit(f"Ollama error for model {model!r}: {details}\n"
                 f"Download the model with: ollama pull {model}")
    except urllib.error.URLError:
        sys.exit(f"Ollama is not running at {OLLAMA_URL}. The readability metric needs it.\n"
                 f"Start it with: ollama serve   (and once: ollama pull {model})")


def analyze(source_path, first_pass, params, rules):
    model = params["model"]
    temperature = params.get("temperature", 0)
    seed = params.get("seed", 42)

    with open(source_path, errors="replace") as f:
        code = f.read()
    # replace() rather than format(): the JSON example in PROMPT has { } in it.
    prompt = PROMPT.replace("CODE", code)

    key = json.dumps([code, PROMPT, model, temperature, seed])
    cache_path = os.path.join(CACHE_DIR, hashlib.sha256(key.encode()).hexdigest() + ".json")

    if os.path.exists(cache_path):
        with open(cache_path) as f:
            raw = f.read()
    else:
        raw = ask_ollama(model, prompt, temperature, seed)

    # Check the answer before saving it, so a bad answer is never cached.
    answer = json.loads(raw)
    value = answer["score"]
    if not isinstance(value, (int, float)) or not 0 <= value <= 10:
        raise ValueError(f"model gave score {value!r}, expected a number from 0 to 10")
    reasons = [str(reason) for reason in answer.get("reasons", [])][:3]

    if not os.path.exists(cache_path):
        os.makedirs(CACHE_DIR, exist_ok=True)
        with open(cache_path, "w") as f:
            f.write(raw)

    return {
        "score": value / 10,
        "evidence": {"model": model, "temperature": temperature, "seed": seed,
                     "raw_response": raw, "cache_file": cache_path},
        "feedback": f"{value}/10 from {model}: " + ("; ".join(reasons) or "no reasons given"),
    }
