from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import ibis
import ibis.expr.datatypes as dt

from egregora.database.schemas import UNIFIED_SCHEMA, create_table_if_not_exists

if TYPE_CHECKING:
    from ibis.backends.base import BaseBackend

logger = logging.getLogger(__name__)


def migrate_to_unified_schema(con: BaseBackend) -> None:
    """
    Migrates a database from the legacy multi-table schema to the V3 unified schema.

    This migration is designed to be idempotent. It checks for the existence of the
    `documents` table and will not run if it already exists.

    The migration performs the following steps:
    1. Creates the `documents` table based on `UNIFIED_SCHEMA`.
    2. Transforms and copies data from the legacy `posts` table.
    3. Transforms and copies data from the legacy `profiles` table.
    4. (Does not drop old tables to be non-destructive).
    """
    if "documents" in con.list_tables():
        logger.warning(
            "Migration skipped: 'documents' table already exists. "
            "Assuming migration has already been run."
        )
        return

    logger.info("Starting database migration to unified schema...")

    # 1. Create the new documents table
    create_table_if_not_exists(con, "documents", UNIFIED_SCHEMA)

    # 2. Migrate data from 'posts' table if it exists
    if "posts" in con.list_tables():
        logger.info("Migrating data from 'posts' table...")
        posts = con.table("posts")

        # Transform posts data to fit the unified schema
        posts_transformed = posts.mutate(
            doc_type=ibis.literal("post"),
            published=posts.date.cast(dt.Timestamp(timezone="UTC")),
            updated=posts.created_at,
            content_type=ibis.literal(None).cast(dt.string),
            links=ibis.literal("[]").cast(dt.json),
            contributors=ibis.literal("[]").cast(dt.json),
            categories=ibis.literal("[]").cast(dt.json),
            source=ibis.literal(None).cast(dt.json),
            in_reply_to=ibis.literal(None).cast(dt.json),
            searchable=ibis.literal(True),
            url_path=ibis.literal(None).cast(dt.string),
            extensions=ibis.literal("{}").cast(dt.json),
            internal_metadata=ibis.literal("{}").cast(dt.json),
            authors=posts.authors.cast(dt.json) # Keep as JSON array of strings for now
        ).select(*UNIFIED_SCHEMA.names) # Ensure column order and selection matches

        con.insert("documents", posts_transformed)

    # 3. Migrate data from 'profiles' table if it exists
    if "profiles" in con.list_tables():
        logger.info("Migrating data from 'profiles' table...")
        profiles = con.table("profiles")

        # For profiles, we'll pack extra fields into internal_metadata
        # A more complex migration could build a proper JSON object.
        profiles_transformed = profiles.mutate(
            doc_type=ibis.literal("profile"),
            published=ibis.literal(None).cast(dt.Timestamp(timezone="UTC")),
            updated=profiles.created_at,
            summary=profiles.summary,
            content_type=ibis.literal(None).cast(dt.string),
            links=ibis.literal("[]").cast(dt.json),
            authors=ibis.literal("[]").cast(dt.json),
            contributors=ibis.literal("[]").cast(dt.json),
            categories=ibis.literal("[]").cast(dt.json),
            source=ibis.literal(None).cast(dt.json),
            in_reply_to=ibis.literal(None).cast(dt.json),
            status=ibis.literal(None).cast(dt.string),
            searchable=ibis.literal(True),
            url_path=ibis.literal(None).cast(dt.string),
            extensions=ibis.literal("{}").cast(dt.json),
            internal_metadata=ibis.struct({"alias": profiles["alias"]}),
        ).select(*UNIFIED_SCHEMA.names)

        con.insert("documents", profiles_transformed)

    # 4. Migrate data from 'journals' table if it exists
    if "journals" in con.list_tables():
        logger.info("Migrating data from 'journals' table...")
        journals = con.table("journals")
        journals_transformed = journals.mutate(
            doc_type=ibis.literal("journal"),
            published=ibis.literal(None).cast(dt.Timestamp(timezone="UTC")),
            updated=journals.created_at,
            summary=ibis.literal(None).cast(dt.string),
            content_type=ibis.literal(None).cast(dt.string),
            links=ibis.literal("[]").cast(dt.json),
            authors=ibis.literal("[]").cast(dt.json),
            contributors=ibis.literal("[]").cast(dt.json),
            categories=ibis.literal("[]").cast(dt.json),
            source=ibis.literal(None).cast(dt.json),
            in_reply_to=ibis.literal(None).cast(dt.json),
            status=ibis.literal(None).cast(dt.string),
            searchable=ibis.literal(True),
            url_path=ibis.literal(None).cast(dt.string),
            extensions=ibis.literal("{}").cast(dt.json),
            internal_metadata=ibis.literal("{}").cast(dt.json),
        ).select(*UNIFIED_SCHEMA.names)
        con.insert("documents", journals_transformed)

    # 5. Migrate data from 'media' table if it exists
    if "media" in con.list_tables():
        logger.info("Migrating data from 'media' table...")
        media = con.table("media")
        media_transformed = media.mutate(
            doc_type=ibis.literal("media"),
            title=media.filename,
            published=ibis.literal(None).cast(dt.Timestamp(timezone="UTC")),
            updated=media.created_at,
            summary=ibis.literal(None).cast(dt.string),
            content_type=media.mime_type,
            links=ibis.literal("[]").cast(dt.json),
            authors=ibis.literal("[]").cast(dt.json),
            contributors=ibis.literal("[]").cast(dt.json),
            categories=ibis.literal("[]").cast(dt.json),
            source=ibis.literal(None).cast(dt.json),
            in_reply_to=ibis.literal(None).cast(dt.json),
            status=ibis.literal(None).cast(dt.string),
            searchable=ibis.literal(True),
            url_path=ibis.literal(None).cast(dt.string),
            extensions=ibis.literal("{}").cast(dt.json),
            internal_metadata=ibis.literal("{}").cast(dt.json),
        ).select(*UNIFIED_SCHEMA.names)
        con.insert("documents", media_transformed)

    logger.info("✓ Database migration completed successfully.")
