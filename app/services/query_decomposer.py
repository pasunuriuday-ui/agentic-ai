import re
from typing import List


class QueryDecomposer:
    """
    Decomposes compound user queries into independent sub-queries.

    This first version intentionally uses deterministic rules so the
    decomposition step is predictable and easy to test.
    """

    def decompose(self, query: str) -> List[str]:
        """
        Split a query into independent sub-queries.
        """

        if not query or not query.strip():
            raise ValueError("Query cannot be empty")

        query = query.strip()

        # ----------------------------------------------------
        # Normalize whitespace
        # ----------------------------------------------------

        query = re.sub(
            r"\s+",
            " ",
            query
        )

        # ----------------------------------------------------
        # Split explicit question marks
        # ----------------------------------------------------

        question_parts = re.split(
            r"(?<=[?])\s+",
            query
        )

        parts: List[str] = []

        for part in question_parts:

            part = part.strip()

            if not part:
                continue

            # ------------------------------------------------
            # Split common compound connectors
            # ------------------------------------------------

            connector_parts = re.split(
                r"\s+(?:and|also)\s+"
                r"(?=(?:what|how|why|when|where|who|which|"
                r"does|is|are|can|tell|explain)\b)",
                part,
                flags=re.IGNORECASE
            )

            for item in connector_parts:

                item = item.strip(" ,.")

                if item:
                    parts.append(item)

        # ----------------------------------------------------
        # Remove duplicates
        # ----------------------------------------------------

        unique_parts: List[str] = []

        for part in parts:

            normalized = part.lower().strip()

            if not any(
                normalized == existing.lower().strip()
                for existing in unique_parts
            ):
                unique_parts.append(part)

        # ----------------------------------------------------
        # Preserve question marks
        # ----------------------------------------------------

        final_parts: List[str] = []

        for part in unique_parts:

            if (
                "?" in query
                and not part.endswith("?")
            ):
                part = f"{part}?"

            final_parts.append(part)

        return final_parts