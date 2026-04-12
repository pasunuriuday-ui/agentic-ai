class Planner:
    """
    Decides which tool to use.
    """

    def plan(self, query: str) -> dict:
        # deterministic rule (safe + reliable)
        return {
            "tool": "search_docs",
            "input": query.strip()
        }