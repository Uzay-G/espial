import click
from espial.config import Config
from espial import create_app
from pathlib import Path


@click.group()
def espial():
    """Build a second brain, with a sane amount of effort :)"""
    pass


@espial.command("run")
@click.argument("data-dir", type=click.Path(exists=True))
@click.option("--rerun", help="Regenerate existing concept graph", is_flag=True)
@click.option("--port", type=int, help="Port to run server on.", default=None)
@click.option("--host", type=str, help="Host to run server on.", default=None)
def run(data_dir, rerun, port, host):
    data_dir = Path(data_dir)
    if not data_dir.exists():
        click.echo("Data directory does not exist.")
        return
    config_path = data_dir / "espial.py"
    try:
        contents = open(config_path)
        config_locals = {}
        exec(contents.read(), globals(), config_locals)
        contents.close()
        config = config_locals.get("Config", Config)()
    except FileNotFoundError:
        config = Config()
    config.data_dir = data_dir
    config.port = port or config.port
    config.host = host or config.host
    config.ANALYSIS["rerun"] = rerun
    app = create_app(config)
    app.run(port=config.port, host=config.host)

@espial.command("config")
@click.argument("data-dir", type=click.Path(exists=True))
def config(data_dir):
    data_dir = Path(data_dir)
    if not data_dir.exists():
        click.echo("Data directory does not exist.")
        return
    config_path = data_dir / "espial.py"
    if config_path.exists():
        click.echo("Config file already exists")
        return
    contents = open(config_path, "w")
    contents.write(
        "from espial.config import Config\n"
        "class Config(Config):\n"
        "   def __init__(self):\n"
        "       super().__init__()\n"
        "       # set attributes here: see https://github.com/Uzay-G/espial/blob/main/espial/config.py\n"
        "   # redefine the functions you want here\n"
    )
    click.echo(f"Config file created at {config_path}")
