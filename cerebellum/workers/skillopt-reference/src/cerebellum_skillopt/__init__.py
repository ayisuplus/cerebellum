"""Cerebellum's isolated adapter for the pinned SkillOpt reference worker."""

UPSTREAM_COMMIT = "3c8873f016397817dcd40c3e5436d92fe19372b8"
ALLOWED_ACTIONS = frozenset(
    {"list_files", "read_file", "apply_patch", "run_tests", "git_diff", "finish"}
)
