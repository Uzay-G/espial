import time
import json
import re
from pathlib import Path

import flask
import networkx
import click
from flask import request, jsonify
from mesh.load import load_mesh
from mesh.analysis import *


@click.group()
def motif_mesh():
    """Build a second brain, with a sane amount of effort :)"""
    pass

@motif_mesh.command("run")
@click.argument("data-dir", type=click.Path(exists=True))
@click.option("--rerun", help="Regenerate existing concept graph", is_flag=True)
@click.option("--openness", type=float, help="Negative values (eg -1) will lower the thresholds motif mesh uses when deciding whether to add links / ideas to the graph or not. This is more prone for exploration. Positive values (don't go too high) will make it more strict (less concepts, higher quality).", default=0)
def run(data_dir, rerun, openness):
    data_dir = Path(data_dir)
    mesh, nlp, rerun = load_mesh(data_dir, rerun, -openness)
    b = time.time()
    if rerun:
        print(f"{mesh.graph.number_of_edges()} number of doc-concept links before sanitization.")
        mesh.remove_irrelevant_edges()
        print(mesh.graph.number_of_edges(), "number of doc-concept links after tf-idf pre-processing")
        print(len(mesh.concept_cache), "number of concepts before relevance cleaning.")
        z = time.time()
        print(time.time() - z, "merges")
        c = time.time()
        print("time spent to remove irrelevant edges", c - b)
        mesh.trim_all()
        print(time.time() - c, "time spent to remove all uninteresting concepts")
    print(len(mesh.concept_cache), "number of concepts found")
    print(mesh.graph.number_of_edges(), "number of edges left")
    json_graph = networkx.json_graph.node_link_data(mesh.graph)
    json.dump(json_graph, (data_dir / "graph.json").open("w"))

    app = flask.Flask(__name__)
    json.dump(json_graph, (Path(app.root_path) / "../force/force.json").open("w"))

    @app.route("/<file>")
    def serve_file(file):
        return flask.send_file(f"../force/{file}")

    @app.route("/most_sim/<id>")
    def find_sim(id):
        if not id in mesh.graph or "score" in mesh.graph.nodes[id]:
            return
        top_n = request.args.get("top_n", 10)
        return jsonify(find_most_sim(mesh, id, top_n))

    @app.route("/best_tags")
    def get_most_relevant_tags():
        top_n = request.args.get("top_n", 30)
        return jsonify(most_relevant_tags(mesh, top_n))

    @app.route("/view_tag/<tag>")
    def view_tag(tag):
        if not tag in mesh.graph or not "score" in mesh.graph.nodes[tag]:
            return
        tag_node = mesh.graph.nodes[tag]
        tag_inf = {
            "score": f"{tag_node['score']}/{mesh.max_score}",
            "docs": list(map(lambda x: mesh.doc_cache[x[0]]._.title, mesh.graph.in_edges(tag)))
        }
        return jsonify(tag_inf)

    @app.route("/view_doc/<id>")
    def view_doc(id):
        if not id in mesh.graph or "score" in mesh.graph.nodes[id]:
            return
        doc_info = {
            "doc": mesh.doc_cache[id]._.title,
            "tags": list(map(lambda x: x[1], mesh.graph.out_edges(id))),
            "info": f"See most similar: http://localhost:5002/most_sim/{id}"
        }
        return jsonify(doc_info)

    @app.route("/create/<tag>")
    def create_tag(tag):
        if not tag in mesh.graph or not "score" in mesh.graph.nodes[tag]:
            return
        doc_paths = list(map(lambda x: Path(mesh.graph.nodes[x[0]]["path"]), mesh.graph.in_edges(tag)))
        print(doc_paths)
        for path in doc_paths:
            tag_re = re.compile(f"(^|\n| )({tag})", re.IGNORECASE)
            contents = tag_re.sub(r"\1#\2" ,path.open("r").read())
            with path.open("w") as f:
                f.write(contents)
        readable_paths = list(map(lambda x: x.parts[-1], doc_paths))
        return jsonify({"paths": readable_paths})

    @app.route("/search")
    def search():
        q = request.args.get("q")
        if not q:
            return
        return jsonify(search_q(mesh, nlp(q)))

    app.run(port=5002)

if __name__ == "__main__":
    motif_mesh()
