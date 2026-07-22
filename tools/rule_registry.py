"""
tools/rule_registry.py

Tiny in-memory store, keyed by (table_name, rule_name), that carries two
things across the pipeline's steps without the LLM having to repeat them
on every tool call:

- rule descriptions, written once by plan_rules() and read later by
  append_result() when it needs to generate a rule's insight.
- a rule's validated query results, written once by execute_sql() on
  success and read (and cleared) by append_result() when it writes the
  report row.

No LLM calls and no DuckDB calls happen here - it's just a dict.
"""

_descriptions: dict[tuple[str, str], str] = {}
_results: dict[tuple[str, str], list[dict]] = {}


def register_rule(table_name: str, rule_name: str, description: str) -> None:
    """Called once per rule by plan_rules(), right after the rule plan
    comes back from the LLM."""
    _descriptions[(table_name, rule_name)] = description


def get_rule_description(table_name: str, rule_name: str) -> str | None:
    """Called by append_result() to fetch the description it needs for
    the insight-generation call. Returns None if the rule is unknown."""
    return _descriptions.get((table_name, rule_name))


def store_results(table_name: str, rule_name: str, results: list[dict]) -> None:
    """Called by execute_sql() once a rule's full query list has run
    cleanly, so append_result() can retrieve the exact rows later."""
    _results[(table_name, rule_name)] = results


def pop_results(table_name: str, rule_name: str) -> list[dict] | None:
    """Called by append_result(). Removes and returns the cached results
    so a rule can't accidentally be appended to the report twice with the
    same cached data. Returns None if execute_sql hasn't succeeded for
    this rule yet."""
    return _results.pop((table_name, rule_name), None)
