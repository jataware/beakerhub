#!/usr/bin/env python3
"""
Seed the database with context data from context_details.json.

Usage:
    # Using default paths (looks for context_details.json in beakerhub package)
    python -m beakerhub.scripts.seed_contexts

    # Specify custom paths
    python -m beakerhub.scripts.seed_contexts --db-url sqlite:///jupyterhub.sqlite --json-file /path/to/contexts.json

    # Specify source package name
    python -m beakerhub.scripts.seed_contexts --source-package beaker-weather

    # Dry run (don't commit changes)
    python -m beakerhub.scripts.seed_contexts --dry-run
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Ensure beakerhub is importable
import beakerhub
import beakerhub.orm  # noqa: F401 - registers models with Base
from beakerhub.utils import ingest_original_format


def get_default_json_path() -> pathlib.Path:
    """Get the default path to context_details.json."""
    package_dir = pathlib.Path(beakerhub.__file__).parent
    return package_dir / "context_details.json"


def get_default_db_url() -> str:
    """Get a reasonable default database URL."""
    # Check common locations
    candidates = [
        pathlib.Path("jupyterhub.sqlite"),
        pathlib.Path("/srv/jupyterhub/jupyterhub.sqlite"),
        pathlib.Path.home() / "jupyterhub.sqlite",
    ]

    for candidate in candidates:
        if candidate.exists():
            return f"sqlite:///{candidate.absolute()}"

    # Default to current directory
    return "sqlite:///jupyterhub.sqlite"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Seed the database with context data from context_details.json",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--db-url",
        type=str,
        default=None,
        help="SQLAlchemy database URL (default: auto-detect jupyterhub.sqlite)",
    )
    parser.add_argument(
        "--json-file",
        type=pathlib.Path,
        default=None,
        help="Path to context_details.json (default: bundled file)",
    )
    parser.add_argument(
        "--source-package",
        type=str,
        default="legacy",
        help="Source package name for tracking (default: 'legacy')",
    )
    parser.add_argument(
        "--enable-contexts",
        action="store_true",
        default=True,
        help="Enable contexts after import (default: True)",
    )
    parser.add_argument(
        "--no-enable-contexts",
        action="store_false",
        dest="enable_contexts",
        help="Don't enable contexts after import",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Don't commit changes to database",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Print verbose output",
    )

    args = parser.parse_args(argv)

    # Resolve paths
    json_path = args.json_file or get_default_json_path()
    db_url = args.db_url or get_default_db_url()

    if args.verbose:
        print(f"Database URL: {db_url}")
        print(f"JSON file: {json_path}")
        print(f"Source package: {args.source_package}")
        print(f"Enable contexts: {args.enable_contexts}")
        print(f"Dry run: {args.dry_run}")
        print()

    # Validate JSON file exists
    if not json_path.exists():
        print(f"Error: JSON file not found: {json_path}", file=sys.stderr)
        return 1

    # Load JSON data
    print(f"Loading context data from {json_path}...")
    with open(json_path) as f:
        data = json.load(f)

    print(f"Found {len(data)} contexts to import:")
    for slug in data.keys():
        ctx = data[slug]
        print(f"  - {slug}: {len(ctx.get('integrations', []))} integrations, {len(ctx.get('workflows', []))} workflows")
    print()

    # Set up database connection
    print(f"Connecting to database: {db_url}")
    engine = create_engine(db_url)
    Session = sessionmaker(bind=engine)
    session = Session()

    try:
        # Run ingestion
        print("Ingesting context data...")
        stats = ingest_original_format(
            db=session,
            data=data,
            source_package=args.source_package,
            enable_contexts=args.enable_contexts,
        )

        # Print results
        print()
        print("Ingestion complete!")
        print("Statistics:")
        for key, value in stats.items():
            if value > 0:
                print(f"  {key}: {value}")

        if args.dry_run:
            print()
            print("Dry run - rolling back changes...")
            session.rollback()
        else:
            print()
            print("Changes committed to database.")

        return 0

    except Exception as e:
        print(f"Error during ingestion: {e}", file=sys.stderr)
        session.rollback()
        raise

    finally:
        session.close()


if __name__ == "__main__":
    sys.exit(main())
