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
@click.option("--port", type=int, help="Port to run server on.", default=5002)
@click.option("--host", type=str, help="Host to run server on.", default="127.0.0.1")
#@click.option("--build", type=bool, help="If enabled will build the concept graph as a static website")
def run(data_dir, rerun, port, host):
    config_path = Path(data_dir) / "espial.py"
    if config_path:
        contents = open(config_path)
        config_locals = {}
        exec(contents.read(), globals(), config_locals)
        contents.close()
        config = config_locals.get("Config", Config)()
    else:
        config = Config()
    config.data_dir = data_dir
    config.port = port
    config.host = host
    config.ANALYSIS["rerun"] = rerun
    app = create_app(config)
    app.run(port=port, host=host)
