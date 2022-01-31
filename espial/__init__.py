import time
import json
from pathlib import Path
from espial.config import Config
from os import urandom

import flask
from flask_cors import CORS
import networkx
from flask import request, jsonify
from espial.load import load_mesh
from espial.analysis import *


def create_app(config=Config()):
    app = flask.Flask(__name__)
    app.secret_key = urandom(24)
    CORS(app)
    data_dir = Path(config.data_dir)
    mesh, nlp, rerun = load_mesh(config)
    trim1 = time.time()
    if rerun:
        print(
            f"{mesh.graph.number_of_edges()} number of doc-concept links before sanitization. {len(mesh.concept_cache)} concepts."
        )
        mesh.remove_irrelevant_edges()
        print(
            mesh.graph.number_of_edges(),
            "number of doc-concept links after tf-idf pre-processing",
        )
        trim2 = time.time()
        print(
            f"time spent to remove irrelevant edges: edges [{mesh.graph.number_of_edges()}]",
            trim2 - trim1,
        )
        mesh.trim_all()
        print(time.time() - trim2, "time spent to remove all uninteresting concepts")
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
            flask.flash("Document not found", "error")
            return flask.redirect_to("/")
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
            flask.flash("Concept not found", "error")
            return flask.redirect("/")  # todo, setup flashes
        concept_node = mesh.graph.nodes[concept]

        related_docs = list(
            map(
                lambda x: (x[0], mesh.doc_cache[x[0]]._.title),
                mesh.graph.in_edges(concept),
            )
        )
        return flask.render_template(
            "show_concept.html", title=concept, concept=concept_node, docs=related_docs
        )

    @app.route("/doc/<id>")
    def view_doc(id):
        if not id in mesh.graph or "score" in mesh.graph.nodes[id]:
            flask.flash("Document not found", "error")
            return flask.redirect("/")
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
    def search_endpoint():
        q = request.args.get("q")
        top_n = int(request.args.get("top_n", 10))
        if not q:
            return flask.redirect("/")
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
        article = load_url(url, nlp)
        hits = search_q(mesh, article, top_n)
        for doc in hits:
            doc["link"] = config.get_link(mesh.doc_cache[doc["id"]])
        resp = {
            "hits": hits,
            "article": {"title": article._.title, "text": article.text},
        }
        return jsonify(resp)

    @app.route("/create_tag/<concept>")
    def make_tag(concept):
        if not concept in mesh.concept_cache:
            flask.flash("Concept not found", "error")
            return flask.redirect("/")
        config.create_tag(concept, mesh)
        flask.flash("Tag created", "success")
        return flask.redirect(f"/concept/{concept}")

    @app.route("/create_concept_note/<concept>")
    def concept_note(concept):
        if not concept in mesh.concept_cache:
            flask.flash("Concept not found", "error")
            return flask.redirect("/")
        config.create_concept_note(concept, mesh)
        flask.flash("Concept note created", "success")
        return flask.redirect(f"/concept/{concept}")

    @app.route("/misc")
    def misc_page():
        return flask.render_template("misc.html", title="Misc")

    # with open("dbg_pain", "w") as f:
    #    f.write(mesh.dbg)

    @app.route("/create_all_concept_notes")
    def create_all_concept_notes():
        for concept in mesh.concept_cache:
            config.create_concept_note(concept, mesh)
        flask.flash("All concept notes created", "success")
        return flask.redirect("/misc")
    return app
