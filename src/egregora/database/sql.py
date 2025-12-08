"""SQL template management for Egregora.

This module provides a lightweight wrapper around Jinja2 for loading and
rendering SQL templates from the ``src/egregora/resources/sql`` directory.
It enforces security best practices by automatically registering a Jinja2
filter for quoting SQL identifiers, preventing SQL injection vulnerabilities.

The ``SQLManager`` is the single entry point for all database query
generation that is not handled by the Ibis compiler.

See Also:
    - :mod:`egregora.database.duckdb_manager`: The primary consumer of this module.
    - :func:`egregora.database.ir_schema.quote_identifier`: The quoting function
      used by the 'quote' filter.

"""

from jinja2 import Environment, PackageLoader

from egregora.database.utils import quote_identifier


class SQLManager:
    """Manages SQL template rendering with security defaults."""

    def __init__(self) -> None:
        """Initialize the SQLManager and configure the Jinja2 environment."""
        # autoescape=False is intentional here as we are generating SQL, not HTML.
        # We use a custom 'quote' filter to prevent SQL injection for identifiers.
        # Values are parameterized by the DB driver, so they don't need escaping here.
        self.env = Environment(
            loader=PackageLoader("egregora.resources", "sql"),
            autoescape=False,  # noqa: S701 (SQL generation, not HTML)
        )
        # Register the existing secure quoting function as a filter
        self.env.filters["quote"] = quote_identifier

    def render(self, template_name: str, **kwargs: object) -> str:
        """Render a SQL template with the given context.

        Args:
            template_name: The path to the template relative to the
                           ``resources/sql`` directory (e.g., 'ddl/create_index.sql.jinja').
            **kwargs: The context variables to pass to the template.

        Returns:
            The rendered SQL query as a string.

        """
        template = self.env.get_template(template_name)
        return template.render(**kwargs)
