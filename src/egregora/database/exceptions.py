"""Custom exceptions for database operations."""


class DatabaseError(Exception):
    """Base exception for database-related errors."""


class TableNotFoundError(DatabaseError):
    """Raised when a table is not found in the database."""

    def __init__(self, table_name: str) -> None:
        self.table_name = table_name
        super().__init__(f"Table '{table_name}' not found in database")


class SequenceNotFoundError(DatabaseError):
    """Raised when a sequence is not found in the database."""

    def __init__(self, sequence_name: str) -> None:
        self.sequence_name = sequence_name
        super().__init__(f"Sequence '{sequence_name}' not found")


class TableCreationError(DatabaseError):
    """Raised when a table could not be created."""

    def __init__(self, table_name: str) -> None:
        self.table_name = table_name
        super().__init__(f"Failed to create table '{table_name}'")


class InvalidTableNameError(DatabaseError):
    """Raised when an invalid table name is used."""

    def __init__(self, table_name: str) -> None:
        self.table_name = table_name
        super().__init__(f"Invalid table name: '{table_name}'")


class InvalidOperationError(DatabaseError):
    """Raised for invalid database operations."""


class SequenceError(DatabaseError):
    """Raised for errors during sequence operations."""


class SequenceFetchError(SequenceError):
    """Raised when fetching the next sequence value fails."""

    def __init__(self, sequence_name: str) -> None:
        self.sequence_name = sequence_name
        super().__init__(f"Failed to fetch next value for sequence '{sequence_name}'")


class SequenceRetryFailedError(SequenceError):
    """Raised when a sequence operation fails even after a retry."""

    def __init__(self, sequence_name: str) -> None:
        self.sequence_name = sequence_name
        super().__init__(f"Database error for sequence '{sequence_name}' after retry")
