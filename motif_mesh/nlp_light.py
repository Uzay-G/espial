import math
from os.path import exists
import copy
import warnings
import string
import time
import json
import re
from sys import argv
from hashlib import sha256
from pathlib import Path

import flask
import click
from flask import request, jsonify
import spacy
from spacy.tokens import DocBin, Doc
import numpy as np
import networkx

import archivy
nlp = spacy.load("en_core_web_md")

Doc.set_extension("title", default=None)
Doc.set_extension("id", default=None)

# idea: compute concept average vector to avoid highly abstract concepts slip their way through
def cos_sim(v1, v2):
    res = np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2))
    return res


def sigmoid(z):
    return 1/(1 + np.exp(-z))

class ConceptMesh:

    def __init__(self, mode, spacy_cache):
        self.freq_cache = {}
        self.concepts = set()
        self.graph = networkx.DiGraph()
        self.seen_concepts = set()
        self.temp_cache = set()
        self.nb_docs = 0
        self.query_results = {}
        self.max_score = -1
        self.dbg = ""
        self.spacy_cache = spacy_cache
        if mode:
            self.avg_exp_o = 0.1 * mode
            self.tf_exp_o = 0.05 * mode
        else:
            self.avg_exp_o = 0
            self.tf_exp_o = 0


    def create_link(self, item, concept, single_word=False, is_ent=False):
        if single_word:
            text = concept.lemma_.lower()
            if concept.is_stop or not concept.is_alpha:
                return
        else:
            text = concept.text.lower()
            if concept.root.is_stop or not concept.root.is_alpha :
                return
        if len(text) < 4: return
        if not text in self.spacy_cache:
            self.spacy_cache[text] = concept
            self.seen_concepts.add(text)
            self.graph.add_node(text, sim=0, score=0, count=1, is_ent=is_ent)
        if self.graph.has_edge(item, text):
            self.graph[item][text]["count"] += 1
        else:
            self.graph.add_edge(item, text, count=1)
            self.graph.nodes[text]["count"] += 1 
        self.graph.nodes[item]["tf"] += 1

    def get_sanitized_concepts(self, chunk, item_id):
        relevant_tokens = [token.text for token in chunk if not token.is_stop and token.is_alpha]
        #if len(relevant_tokens) > 1:
        #    self.create_link(item_id, chunk)
        self.create_link(item_id, chunk.root, True)

    def remove_irrelevant_edges(self):
        for item, concept, data in list(self.graph.edges(data=True)):
            tf = data["count"] / self.graph.nodes[item]["tf"]
            idf = math.log(self.nb_docs / self.graph.nodes[concept]["count"])
            if (tf * idf < 0.03 + self.tf_exp_o and not self.graph.nodes[concept]["is_ent"]) or (tf * idf < 0.025 and self.graph.nodes[concept]["is_ent"]):
                self.graph.remove_edge(item, concept)

    def trim_concept(self, concept):
        if concept in self.temp_cache:
            return
        avg = 0
        n = 0
        linked_docs = list(self.graph.in_edges(concept))
        word_sim = 0
        for link in linked_docs:
            doc1 = link[0]
            word_sim += self.spacy_cache[doc1].similarity(self.spacy_cache[concept])
            for link2 in linked_docs:
                doc2 = link2[0]
                if doc1 != doc2:
                    n += 1
                    avg += self.compute_similarity(doc1, doc2)
        avg = (n == 0) or avg / n
        word_sim /= (len(linked_docs) == 0) or len(linked_docs)
        #networkx.set_node_attributes(self.graph, {concept: avg}, name="sim")
        n = len(linked_docs)
        total_in_edges = len(linked_docs)
        #print(concept, child_mutual_sim, avg_child_sim, avg, len(linked_docs), len(child_concepts), word_sim)
        self.temp_cache.add(concept)
        #if child_mutual_sim < 0.85 or avg < 0.8 avg_child_sim < 0.85 or total_in_edges <= 2 or not ".n." in concept:
        #if self.graph.nodes[concept]["is_ent"]:
         #   print(concept, word_sim, avg, total_in_edges)
        ent_criteria = avg < 0.85 + self.avg_exp_o or word_sim < 0.4
        word_crit = avg < 0.8 + self.avg_exp_o or word_sim < 0.5 + self.avg_exp_o * 0.5
        is_ent = self.graph.nodes[concept]["is_ent"]
        if total_in_edges > 1:
            self.dbg += f"{avg} {word_sim} {concept} {total_in_edges}"
        if total_in_edges < 2 or (word_crit and not is_ent) or (ent_criteria and is_ent): # or child_mutual_sim < 0.8 or avg_child_sim < 0.8
            if total_in_edges > 1:
                self.dbg += "n\n"
            self.graph.remove_node(concept)
            self.seen_concepts.remove(concept)
        else:
            if is_ent:
                self.dbg += "ENT"
            self.dbg += "y\n"
            score = avg + sigmoid(min(total_in_edges - 3, 5)) + word_sim * 0.5
            self.max_score = max(self.max_score, score)
            self.graph.nodes[concept]["score"] = avg + sigmoid(total_in_edges - 3) + word_sim


    def trim_all(self):
        for concept in list(self.seen_concepts):
            if concept in self.graph:
                self.trim_concept(concept)


    def process_document(self, doc):
        self.nb_docs += 1
        self.graph.add_node(doc._.id, title=doc._.title, tf=0)
        self.spacy_cache[doc._.id] = doc
        for chunk in doc.noun_chunks:
            self.get_sanitized_concepts(chunk, doc._.id)
        for ent in doc.ents:
            if not ent.label_ in ["ORDINAL", "DATE", "MONEY", "CARDINAL", "TIME", "PERCENT"] and len(ent.text) < 50:
                self.dbg += f"ENT {ent.label_} {ent.text}\n" 
                self.create_link(doc._.id, ent, is_ent=True)

    def compute_similarity(self, doc1, doc2):
        return self.spacy_cache[doc1].similarity(self.spacy_cache[doc2])

    def remove_doc(self, id):
        for doc, concept in self.graph.out_edges(id):
            self.graph.nodes[concept]["count"] -= 1
        self.graph.remove_node(id)

@click.group()
def motif_mesh():
    """Build a second brain, with a sane amount of effort :)"""
    pass
@motif_mesh.command("run")
@click.argument("data-dir", type=click.Path(exists=True))
@click.option("--rerun", help="Regenerate existing concept graph", is_flag=True)
@click.option("--openness", type=int, help="Negative values (eg -1) will lower the thresholds motif mesh uses when deciding whether to add links / ideas to the graph or not. This is more prone for exploration. Positive values (don't go too high) will make it more strict (less concepts, higher quality).", default=0)
def run(data_dir, rerun, openness):
    data_dir = Path(data_dir)
    items = {}
    if openness: rerun = 1
    for path in data_dir.rglob("*.md"):
        item = {"content": path.open("r").read(), "title": path.parts[-1]}
        items[sha256(item["content"].encode()).hexdigest()] = item
    saved_graph = (data_dir / "graph.json")
    spacy_cache = {}
    a = time.time()
    docs = []
    dumped_annot = (data_dir / "serialized_annot")
    if dumped_annot.exists():
        with dumped_annot.open("rb") as f:
            doc_bin = DocBin(store_user_data=True).from_bytes(f.read())
            deleted_docs = False
            docs = []
            for doc in doc_bin.get_docs(nlp.vocab):
                if doc._.id in items:
                    docs.append(doc)
                else:
                    deleted_docs = True
            if deleted_docs:
                doc_bin = DocBin(store_user_data=True)
                for doc in docs:
                    doc_bin.add(doc)
            spacy_cache = {doc._.id: doc for doc in docs}
    else:
        doc_bin = DocBin(store_user_data=True)


    mesh = ConceptMesh(openness, spacy_cache)

    if (data_dir / "graph.json").exists() and not rerun:
        mesh.graph = networkx.json_graph.node_link_graph(json.load(saved_graph.open("r")))
        print("loading graphs")
    unseen_docs = []
    for curr_hash, item in items.items():
        STOPWORDS = [
                'a', 'about', 'an', 'are', 'and', 'as', 'at', 'be', 'but', 'by', 'com',
                'do', 'don\'t', 'for', 'from', 'has', 'have', 'he', 'his', 'i', 'i\'m',
                'in', 'is', 'it', 'it\'s', 'just', 'like', 'me', 'my', 'not', 'of',
                'on', 'or', 'so', 't', 'that', 'the', 'they', 'this', 'to', 'was',
                'we', 'were', 'with', 'you', 'your',
        ]
        item["content"] = " ".join(filter(lambda x: not x in STOPWORDS, item["content"].split()))
        item["content"] = re.sub(r"\[([^\]]*)\]\(http[^)]+\)", r"\1", item["content"])
        if not curr_hash in spacy_cache:
            unseen_docs.append((item["content"], {"id": curr_hash, "title": item["title"]}))
    print(f"{len(unseen_docs)} new docs.")
    i = 0
    for doc, ctx in nlp.pipe(unseen_docs, as_tuples=True, disable=["textcat"], batch_size=40):
        i += 1
        if i % 40 == 0: print(f"{i} docs processed.")
        doc._.title = ctx["title"]
        doc._.id = ctx["id"]
        doc_bin.add(doc)
        if ctx["id"] in spacy_cache and ctx["id"] in mesh.graph:
            mesh.remove_doc(ctx["id"])
        mesh.process_document(doc)

    print(time.time() - a, f"time spent to process docs, of {len(unseen_docs)} new ones.")
    if len(unseen_docs):
        with open("serialized_annot", "wb") as f:
            f.write(doc_bin.to_bytes())


    b = time.time()
    if len(unseen_docs) or rerun:
        if rerun:
            list(map(lambda x: mesh.process_document(x), docs))
        print(f"{mesh.graph.number_of_edges()} number of doc-concept links before sanitization.")
        mesh.remove_irrelevant_edges()
        print(mesh.graph.number_of_edges(), "number of doc-concept links after tf-idf pre-processing")
        if rerun:
            print(len(mesh.seen_concepts), "number of concepts before relevance cleaning.")
        c = time.time()
        print("time spent to remove irrelevant edges", c - b)
        mesh.trim_all()
        print(time.time() - c, "time spent to remove all uninteresting concepts")
    if rerun:
        print(len(mesh.seen_concepts), "number of concepts post-processing")
        print(mesh.seen_concepts)
    print(mesh.graph.number_of_edges(), "number of edges left post-processing")
    json_graph = networkx.json_graph.node_link_data(mesh.graph)
    json.dump(json_graph, saved_graph.open("w"))

    app = flask.Flask(__name__)
    print(app.root_path)

    json.dump(json_graph, (Path(app.root_path) / "../force/force.json").open("w"))
    with open("out.txt", "w") as f:
        f.write(mesh.dbg)

    @app.route("/<file>")
    def serve_file(file):
        return flask.send_file(f"../force/{file}")

    @app.route("/most_sim/<id>")
    def find_sim(id):
        if not id in mesh.graph or "score" in mesh.graph.nodes[id]:
            return
        doc = spacy_cache[id]
        results = []
        t = time.time()
        for doc2 in docs:
            if doc2._.id != id:
                results.append((doc2._.id, doc.similarity(doc2)))
        print(time.time() - t)
        results.sort(key=lambda x: x[1], reverse=True)
        top = results[:10]
        final_res = []
        for id2, _ in top:
            doc2 = spacy_cache[id2]
            max_sent = ""
            max_sim = -1
            for sent in doc2.sents:
                sim = doc.similarity(sent)
                if max_sim < sim:
                    max_sim = sim
                    max_sent = sent.text
            final_res.append((doc2._.title, max_sim, max_sent))
        return jsonify(final_res)


    @app.route("/best_tags")
    def most_relevant_tags():
        concept_avgs = [(concept, mesh.graph.nodes[concept]["score"]) for concept in mesh.graph if "score" in mesh.graph.nodes[concept]]
        concept_avgs.sort(key=lambda x: x[1], reverse=True)
        top = concept_avgs[:30]
        for i in range(30):
            in_docs = list(map(lambda x: spacy_cache[x[0]]._.title, mesh.graph.in_edges(top[i][0])))
            top[i] = (top[i][0], top[i][1], in_docs)
        return jsonify(top)

    @app.route("/view_tag/<tag>")
    def view_tag(tag):
        if not tag in mesh.graph or not "score" in mesh.graph.nodes[tag]:
            return
        tag_node = mesh.graph.nodes[tag]
        tag_inf = {
            "score": f"{tag_node['score']}/{mesh.max_score}",
            "docs": list(map(lambda x: spacy_cache[x[0]]._.title, mesh.graph.in_edges(tag)))
        }
        return jsonify(tag_inf)

    @app.route("/view_doc/<id>")
    def view_doc(id):
        if not id in mesh.graph or "score" in mesh.graph.nodes[id]:
            return
        doc_info = {
            "doc": spacy_cache[id]._.title,
            "tags": list(map(lambda x: x[1], mesh.graph.out_edges(id))),
            "info": f"See most similar: https://localhost:5002/most_sim/{id}"
        }
        return jsonify(doc_info)
    app.run(port=5002)

if __name__ == "__main__":
    motif_mesh()
