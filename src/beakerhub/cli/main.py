import click
import importlib
import os


class BeakerhubCli(click.Group):
    """
    Primary class for beakerhub cli to allow customization as needed.
    """
    pass

@click.group(cls=BeakerhubCli)
def main():
    """
    CLI Tooling for beakerhub

    More features coming soon.
    """
    pass

@main.command(name="serve", context_settings=dict(ignore_unknown_options=True))
@click.argument("args", nargs=-1, type=click.UNPROCESSED)
def serve(args):
    # TODO: Retrieve arguments from launch_instance and return them as part of usage.
    from beakerhub.app import BeakerHub
    BeakerHub.launch_instance(argv=args)


@main.command(name="import-image")
@click.argument("image_slug")
@click.option(
    "--config-file", "-f",
    default="beakerhub_config.py",
    help="Path to beakerhub config file.",
)
@click.option(
    "--db-url",
    default=None,
    help="Database URL. Overrides config file if provided.",
)
def import_image(image_slug: str, config_file: str, db_url: str | None):
    """Launch a context import job for a registered node image.

    IMAGE_SLUG is the slug of the node image to import (e.g., 'weather-node').
    The image must already be registered in the database.
    """
    from beakerhub.app import BeakerHub
    from beakerhub.orm import NodeImages, NodeImageTask
    from beakerhub.nodes.import_handlers import launch_import_task

    # Initialize app to load config (reporter image, resources, etc.)
    app = BeakerHub()
    if os.path.exists(config_file):
        app.load_config_file(config_file)

    # Set up database
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from jupyterhub.orm import Base

    import beakerhub.orm  # noqa: F401 - registers models with Base

    actual_db_url = db_url or app.db_url or "sqlite:///jupyterhub.sqlite"
    engine = create_engine(actual_db_url)
    Session = sessionmaker(bind=engine)
    db = Session()

    # Look up the node image
    node = db.query(NodeImages).filter(NodeImages.slug == image_slug).first()
    if not node:
        available = [n.slug for n in db.query(NodeImages).all()]
        click.echo(f"Error: No node image found with slug '{image_slug}'", err=True)
        if available:
            click.echo(f"Available images: {', '.join(available)}", err=True)
        raise SystemExit(1)

    click.echo(f"Launching import for '{node.slug}' ({node.default_img_string})")

    try:
        task = launch_import_task(db, app, node)
    except ValueError as e:
        click.echo(f"Error: {e}", err=True)
        raise SystemExit(1)
    except RuntimeError as e:
        click.echo(f"Error: {e}", err=True)
        raise SystemExit(1)

    click.echo(f"Import job created: {task.job_name} (task_id={task.id})")
    click.echo(f"Status: {task.status}")
    click.echo(
        f"Poll status via API: "
        f"GET /api/beakerhub/admin/node-images/{node.id}/import-status"
    )

    db.close()
