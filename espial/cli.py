import click
from espial.config import Config
from espial import create_app
@click.group()

def espial():
    """Build a second brain, with a sane amount of effort :)"""
    pass

@espial.command("run")
@click.argument("data-dir", type=click.Path(exists=True))
@click.option("--rerun", help="Regenerate existing concept graph", is_flag=True)
@click.option("--openness", type=float, help="Positive values (eg -1) will lower the thresholds motif mesh uses when deciding whether to add links / ideas to the graph or not. This is better for exploration. Negative values will make it more strict (less concepts, higher quality).", default=0)
@click.option("--batch-size", type=int, help="Processes documents by batches. If running on large documents, you may want to reduce batch size so as not to overload memory.", default=40)
@click.option("--max-concepts", type=int, help="Upper bound on number of concepts saved in graph.", default=500)
@click.option("--config-path", type=click.Path(exists=True), help="Path to python config.")
@click.option("--port", type=int, help="Port to run server on.", default=5002)
@click.option("--host", type=str, help="Host to run server on.", default="127.0.0.1")
def run(data_dir, rerun, openness, batch_size, max_concepts, config_path, port, host):
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
    config.ANALYSIS = {
        "openness": openness,
        "batch_size": batch_size,
        "max_concepts": max_concepts,
        "rerun": rerun
    }
    app = create_app(config)
    app.run(port=port, host=host)
