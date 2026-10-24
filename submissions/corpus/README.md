# Originality corpus

Reference programs for the `originality` metric (`analyzers/similarity_flag.py`).
The grader compares every submission with every `*.c` file under `submissions/`,
including this folder, but it never grades these files: it is run on
`submissions/*.c`, which does not go into sub-folders.

- `ai/`: answers from LLMs to a short prompt, as a student might get them.
- `web/`: solutions copied from tutorial websites.

The first comment in each file says where it came from (collected 2026-10-24).
Comments are removed before comparing, so these headers do not change the similarity.
