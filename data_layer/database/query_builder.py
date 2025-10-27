"""
Module: Query Builder
Purpose: SQL query builder focused on INSERT operations
Version: 2.0

This module provides:
- Simple INSERT query builder
- Batch INSERT support
- Type-safe parameter handling
- Integration with data models
"""

import logging
from typing import Dict, List, Any, Tuple


class QueryBuilder:
    """
    SQL query builder for INSERT operations.

    Features:
    - Build INSERT queries from dictionaries
    - Batch INSERT query generation
    - Parameter extraction for safe execution
    - Works with data models (Round, Threshold, etc.)
    """

    def __init__(self):
        """Initialize QueryBuilder."""
        self.logger = logging.getLogger(self.__class__.__name__)

    def build_insert(
        self,
        table: str,
        data: Dict[str, Any],
        ignore_none: bool = True
    ) -> Tuple[str, Tuple[Any, ...]]:
        """
        Build INSERT query from dictionary.

        Args:
            table: Table name
            data: Dictionary with column names and values
            ignore_none: Skip columns with None values

        Returns:
            Tuple of (query_string, parameters)

        Example:
            >>> builder = QueryBuilder()
            >>> query, params = builder.build_insert(
            ...     "rounds",
            ...     {"bookmaker": "Mozzart", "final_score": 3.45}
            ... )
            >>> print(query)
            INSERT INTO rounds (bookmaker, final_score) VALUES (?, ?)
            >>> print(params)
            ('Mozzart', 3.45)
        """
        # Filter out None values if requested
        if ignore_none:
            data = {k: v for k, v in data.items() if v is not None}

        # Filter out 'id' field (auto-increment)
        data = {k: v for k, v in data.items() if k != 'id'}

        if not data:
            raise ValueError("No data to insert")

        # Build column and value lists
        columns = list(data.keys())
        values = [data[col] for col in columns]

        # Build query
        columns_str = ", ".join(columns)
        placeholders = ", ".join(["?" for _ in columns])

        query = f"INSERT INTO {table} ({columns_str}) VALUES ({placeholders})"

        return query, tuple(values)

    def build_batch_insert(
        self,
        table: str,
        data_list: List[Dict[str, Any]],
        ignore_none: bool = True
    ) -> Tuple[str, List[Tuple[Any, ...]]]:
        """
        Build batch INSERT query from list of dictionaries.

        All dictionaries must have the same keys.

        Args:
            table: Table name
            data_list: List of dictionaries with column names and values
            ignore_none: Skip columns with None values

        Returns:
            Tuple of (query_string, list_of_parameters)

        Example:
            >>> builder = QueryBuilder()
            >>> data = [
            ...     {"bookmaker": "Mozzart", "final_score": 3.45},
            ...     {"bookmaker": "BalkanBet", "final_score": 2.11}
            ... ]
            >>> query, params_list = builder.build_batch_insert("rounds", data)
            >>> print(query)
            INSERT INTO rounds (bookmaker, final_score) VALUES (?, ?)
            >>> print(params_list)
            [('Mozzart', 3.45), ('BalkanBet', 2.11)]
        """
        if not data_list:
            raise ValueError("Empty data list")

        # Get first item to determine columns
        first_item = data_list[0]

        # Filter out None and id
        if ignore_none:
            first_item = {k: v for k, v in first_item.items() if v is not None}
        first_item = {k: v for k, v in first_item.items() if k != 'id'}

        columns = list(first_item.keys())

        # Build query (same for all rows)
        columns_str = ", ".join(columns)
        placeholders = ", ".join(["?" for _ in columns])
        query = f"INSERT INTO {table} ({columns_str}) VALUES ({placeholders})"

        # Extract parameters for each row
        params_list = []
        for data in data_list:
            # Filter same way as first item
            if ignore_none:
                data = {k: v for k, v in data.items() if v is not None}
            data = {k: v for k, v in data.items() if k != 'id'}

            # Extract values in same order as columns
            values = tuple(data.get(col) for col in columns)
            params_list.append(values)

        return query, params_list

    def build_insert_from_model(
        self,
        table: str,
        model: Any
    ) -> Tuple[str, Tuple[Any, ...]]:
        """
        Build INSERT query from data model (Round, Threshold, etc.).

        Args:
            table: Table name
            model: Model instance with to_dict() method

        Returns:
            Tuple of (query_string, parameters)

        Example:
            >>> from data_layer.models.round import Round
            >>> builder = QueryBuilder()
            >>> round_data = Round(bookmaker="Mozzart", final_score=3.45)
            >>> query, params = builder.build_insert_from_model("rounds", round_data)
        """
        if not hasattr(model, 'to_dict'):
            raise ValueError("Model must have to_dict() method")

        data = model.to_dict()
        return self.build_insert(table, data)

    def build_batch_insert_from_models(
        self,
        table: str,
        models: List[Any]
    ) -> Tuple[str, List[Tuple[Any, ...]]]:
        """
        Build batch INSERT query from list of data models.

        Args:
            table: Table name
            models: List of model instances with to_dict() method

        Returns:
            Tuple of (query_string, list_of_parameters)

        Example:
            >>> from data_layer.models.round import Round
            >>> builder = QueryBuilder()
            >>> rounds = [
            ...     Round(bookmaker="Mozzart", final_score=3.45),
            ...     Round(bookmaker="BalkanBet", final_score=2.11)
            ... ]
            >>> query, params_list = builder.build_batch_insert_from_models("rounds", rounds)
        """
        if not models:
            raise ValueError("Empty models list")

        # Convert models to dictionaries
        data_list = [model.to_dict() for model in models]

        return self.build_batch_insert(table, data_list)

    def build_select(
        self,
        table: str,
        columns: List[str] = None,
        where: Dict[str, Any] = None,
        order_by: str = None,
        limit: int = None
    ) -> Tuple[str, Tuple[Any, ...]]:
        """
        Build SELECT query (basic support for future use).

        Args:
            table: Table name
            columns: List of column names (default: all columns)
            where: WHERE clause as dictionary
            order_by: ORDER BY column name
            limit: LIMIT value

        Returns:
            Tuple of (query_string, parameters)

        Example:
            >>> builder = QueryBuilder()
            >>> query, params = builder.build_select(
            ...     "rounds",
            ...     columns=["bookmaker", "final_score"],
            ...     where={"bookmaker": "Mozzart"},
            ...     order_by="timestamp DESC",
            ...     limit=10
            ... )
        """
        # Build SELECT clause
        if columns:
            columns_str = ", ".join(columns)
        else:
            columns_str = "*"

        query = f"SELECT {columns_str} FROM {table}"
        params = []

        # Build WHERE clause
        if where:
            where_parts = []
            for col, val in where.items():
                where_parts.append(f"{col} = ?")
                params.append(val)

            query += " WHERE " + " AND ".join(where_parts)

        # Add ORDER BY
        if order_by:
            query += f" ORDER BY {order_by}"

        # Add LIMIT
        if limit:
            query += f" LIMIT {limit}"

        return query, tuple(params)


# Convenience instance
_query_builder = None


def get_query_builder() -> QueryBuilder:
    """Get singleton QueryBuilder instance."""
    global _query_builder

    if _query_builder is None:
        _query_builder = QueryBuilder()

    return _query_builder


if __name__ == "__main__":
    # Quick test
    logging.basicConfig(level=logging.INFO)

    builder = QueryBuilder()

    # Test simple insert
    query, params = builder.build_insert(
        "rounds",
        {
            "bookmaker": "Mozzart",
            "timestamp": "2024-01-01 12:00:00",
            "final_score": 3.45
        }
    )
    print(f"Simple INSERT:\n{query}\nParams: {params}\n")

    # Test batch insert
    data = [
        {"bookmaker": "Mozzart", "final_score": 3.45},
        {"bookmaker": "BalkanBet", "final_score": 2.11},
        {"bookmaker": "Soccer", "final_score": 5.67}
    ]
    query, params_list = builder.build_batch_insert("rounds", data)
    print(f"Batch INSERT:\n{query}\nParams: {params_list}\n")

    # Test SELECT
    query, params = builder.build_select(
        "rounds",
        columns=["bookmaker", "final_score"],
        where={"bookmaker": "Mozzart"},
        order_by="timestamp DESC",
        limit=10
    )
    print(f"SELECT:\n{query}\nParams: {params}\n")
