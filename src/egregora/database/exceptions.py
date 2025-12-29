"""Custom exceptions for database operations."""


class DatabaseError(Exception):
    """Base exception for database-related errors."""


class DatabaseObjectError(DatabaseError):
    """Base for errors related to a specific database object (e.g., table, sequence)."""

    def __init__(self, object_type: str, object_name: str, message: str | None = None) -> None:
        self.object_type = object_type
        self.object_name = object_name
        if message is None:
            message = f"{object_type.capitalize()} '{object_name}' not found"
        super().__init__(message)


class TableNotFoundError(DatabaseObjectError):
    """Raised when a table is not found in the database."""

    def __init__(self, table_name: str) -> None:
        super().__init__(
            object_type="table",
            object_name=table_name,
            message=f"Table '{table_name}' not found in database",
        )


class SequenceNotFoundError(DatabaseObjectError):
    """Raised when a sequence is not found in the database."""

    def __init__(self, sequence_name: str) -> None:
        super().__init__(object_type="sequence", object_name=sequence_name)


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


class SequenceCreationError(SequenceError):
    """Raised when creating a sequence fails verification."""

    def __init__(self, sequence_name: str) -> None:
        self.sequence_name = sequence_name
        super().__init__(f"Failed to create or verify sequence '{sequence_name}'")


class TableInfoError(DatabaseError):
    """Raised when fetching table metadata (e.g., columns) fails."""

    def __init__(self, table_name: str) -> None:
        self.table_name = table_name
        super().__init__(f"Failed to retrieve metadata for table '{table_name}'")
