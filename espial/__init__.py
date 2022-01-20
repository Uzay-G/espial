import time
import json
import re
from pathlib import Path
from espial.config import Config

import flask
from flask_cors import CORS
import networkx
from flask import request, jsonify
from espial.load import load_mesh
from espial.analysis import *
import newspaper


def create_app(config=Config()):
    app = flask.Flask(__name__)
    CORS(app)
    data_dir = Path(config.data_dir)
    mesh, nlp, rerun = load_mesh(config)
    b = time.time()
    if rerun:
        print(
            f"{mesh.graph.number_of_edges()} number of doc-concept links before sanitization."
        )
        mesh.remove_irrelevant_edges()
        print(
            mesh.graph.number_of_edges(),
            "number of doc-concept links after tf-idf pre-processing",
        )
        print(len(mesh.concept_cache), "number of concepts before relevance cleaning.")
        z = time.time()
        print(time.time() - z, "merges")
        c = time.time()
        print(
            f"time spent to remove irrelevant edges: edges [{mesh.graph.number_of_edges()}]",
            c - b,
        )
        mesh.trim_all()
        print(time.time() - c, "time spent to remove all uninteresting concepts")
    print(len(mesh.concept_cache), "number of concepts found")
    print(mesh.graph.number_of_edges(), "number of edges left")
    json_graph = networkx.json_graph.node_link_data(
        mesh.display_graph(config.ANALYSIS["max_concepts"])
    )
    json.dump(json_graph, (data_dir / "graph.json").open("w"))
    json.dump(json_graph, (Path(app.root_path) / "static/force.json").open("w"))

    search_q(mesh, nlp("test"))  # prep search server up - makes results faster

    @app.route("/")
    def index():
        return flask.render_template(
            "index.html", title="Graph", n_nodes=len(mesh.graph.nodes)
        )

    @app.route("/graph")
    def concept_graph():
        return flask.render_template("force.html", n_nodes=len(mesh.graph.nodes))

    @app.route("/most_sim/<id>")
    def find_sim(id):
        if not id in mesh.graph or "score" in mesh.graph.nodes[id]:
            return
        top_n = request.args.get("top_n", 10)
        return jsonify(find_most_sim(mesh, id, top_n))

    @app.route("/best_tags")
    def get_most_relevant_tags():
        top_n = int(request.args.get("top_n", 30))
        only_ents = request.args.get("only_ents", False)
        return jsonify(most_relevant_tags(mesh, top_n, only_ents))

    @app.route("/concept/<concept>")
    def view_concept(concept):
        if not concept in mesh.graph or not "score" in mesh.graph.nodes[concept]:
            return
        concept_node = mesh.graph.nodes[concept]

        docs = list(
            map(
                lambda x: (x[0], mesh.doc_cache[x[0]]._.title),
                mesh.graph.in_edges(concept),
            )
        )
        return flask.render_template(
            "show_concept.html", title=concept, concept=concept_node, docs=docs
        )

    @app.route("/doc/<id>")
    def view_doc(id):
        if not id in mesh.graph or "score" in mesh.graph.nodes[id]:
            return
        tags = list(map(lambda x: x[1], mesh.graph.out_edges(id)))
        most_sim = find_most_sim(mesh, id)
        return flask.render_template(
            "show_doc.html",
            doc=mesh.doc_cache[id],
            tags=tags,
            title=mesh.doc_cache[id]._.title,
            most_sim=most_sim,
        )

    @app.route("/semantic_search")
    def search():
        q = request.args.get("q")
        top_n = int(request.args.get("top_n", 10))
        if not q:
            return
        res = search_q(mesh, nlp(q), top_n)
        for doc in res:
            doc["link"] = config.get_link(mesh.doc_cache[doc["id"]])
        return jsonify(res)

    @app.route("/search")
    def search_view():
        return flask.render_template("/search.html", title="Search")

    @app.route("/article_search")
    def compare_article():
        url = request.args.get("url")
        top_n = int(request.args.get("top_n", 10))
        ar = newspaper.Article(url)
        ar.download()
        ar.parse()
        hits = search_q(mesh, nlp(ar.text), top_n)
        for doc in hits:
            doc["link"] = config.get_link(mesh.doc_cache[doc["id"]])
        resp = {"hits": hits, "article": {"title": ar.title, "text": ar.text}}
        return jsonify(resp)

    @app.route("/create_tag/<concept>")
    def make_tag(concept):
        if not concept in mesh.concept_cache:
            return
        config.create_tag(concept, mesh)
        return "Success", 200

    @app.route("/create_concept_note/<concept>")
    def concept_note(concept):
        if not concept in mesh.concept_cache:
            return
        config.create_concept_note(concept, mesh)
        return "Success", 200

    @app.route("/misc")
    def misc_page():
        return flask.render_template("misc.html", title="Misc")

    with open("dbg_pain", "w") as f:
        f.write(mesh.dbg)

    @app.route("/create_all_concept_notes")
    def create_all_concept_notes():
        for concept in mesh.concept_cache:
            config.create_concept_note(concept, mesh)
        return "Success", 200

    return app
