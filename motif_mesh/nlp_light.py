import math
from os.path import exists
import copy
import warnings
import string
import time
import json
from sys import argv

import flask
from flask import request, jsonify
from bs4 import BeautifulSoup
from flask_cors import CORS, cross_origin
import html2text
import spacy
from spacy.tokens import DocBin, Doc
import numpy as np
import networkx
from nltk.wsd import lesk
from nltk.corpus import wordnet
from sklearn.feature_extraction.text import TfidfVectorizer

import archivy
nlp = spacy.load("en_core_web_lg")

Doc.set_extension("title", default=None)
Doc.set_extension("id", default=None)

# idea: compute concept average vector to avoid highly abstract concepts slip their way through

def cos_sim(v1, v2):
    res = np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2))
    return res

spacy_cache = {}
class ConceptMesh:

    def __init__(self):
        self.freq_cache = {}
        self.concepts = set()
        self.graph = networkx.DiGraph()
        self.seen_concepts = set()
        self.temp_cache = set()
        self.nb_docs = 0
        self.query_results = {}

    def create_link(self, item, concept, single_word=False, is_ent=False):
        if single_word:
            text = concept.lemma_
            if concept.is_stop or not concept.is_alpha:
                return
        else:
            text = concept.text
            if concept.root.is_stop or not concept.root.is_alpha :
                return
        if len(text) < 4: return
        if not text in spacy_cache:
            spacy_cache[text] = concept
            self.seen_concepts.add(text)
            self.graph.add_node(text, sim=0, avg_vec=0, count=1, is_ent=is_ent)
        if self.graph.has_edge(item, text):
            self.graph[item][text]["count"] += 1
        else:
            self.graph.add_edge(item, text, count=1)
            self.graph.nodes[text]["count"] += 1 
        self.graph.nodes[item]["tf"] += 1

    def get_sanitized_concepts(self, chunk, item_id):
        relevant_tokens = [token.text for token in chunk if not token.is_stop and token.is_alpha]
        if len(relevant_tokens) > 1:
            self.create_link(item_id, chunk)
        self.create_link(item_id, chunk.root, True)

    def remove_irrelevant_edges(self):
        for item, concept, data in list(self.graph.edges(data=True)):
            tf = data["count"] / self.graph.nodes[item]["tf"]
            idf = math.log(self.nb_docs / self.graph.nodes[concept]["count"])
            if (tf * idf < 0.03 and not self.graph.nodes[concept]["is_ent"]) or (tf * idf < 0.01 and self.graph.nodes[concept]["is_ent"]):
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
            word_sim += spacy_cache[doc1].similarity(spacy_cache[concept])
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
        if total_in_edges <= 2 or avg < 0.65 or (word_sim < 0.45 and not self.graph.nodes[concept]["is_ent"]): # or child_mutual_sim < 0.8 or avg_child_sim < 0.8
            self.graph.remove_node(concept)
            self.seen_concepts.remove(concept)


    def trim_all(self):
        for concept in list(self.seen_concepts):
            if concept in self.graph:
                self.trim_concept(concept)


    def process_document(self, doc):
        self.nb_docs += 1
        self.graph.add_node(doc._.id, title=doc._.title, tf=0)
        spacy_cache[doc._.id] = doc
        for chunk in doc.noun_chunks:
            self.get_sanitized_concepts(chunk, doc._.id)
        for ent in doc.ents:
            if not ent.label_ in ["ORDINAL", "DATE", "MONEY", "CARDINAL", "TIME"]:
                self.create_link(doc._.id, ent, is_ent=True)

    def compute_similarity(self, doc1, doc2):
        return spacy_cache[doc1].similarity(spacy_cache[doc2])

    def remove_doc(self, id):
        for _, concept in self.graph.out_edges(id):
            self.graph.nodes[concept]["count"] -= 1
        self.graph.remove_node(id)


mesh = ConceptMesh()
rerun_heuristics = len(argv) > 1
if exists("graph.json") and not rerun_heuristics:
    mesh.graph = networkx.json_graph.node_link_graph(json.load(open("graph.json", "r")))
    print("loading graphs")

a = time.time()
docs = []
if exists("serialized_annot"):
    with open("serialized_annot", "rb") as f:
        doc_bin = DocBin(store_user_data=True).from_bytes(f.read())
        docs = list(doc_bin.get_docs(nlp.vocab))
        spacy_cache = {doc._.id: doc for doc in docs}
else:
    doc_bin = DocBin(store_user_data=True)
unseen_docs = []
with archivy.app.app_context():
    for item in archivy.data.get_items(structured=False):
        if not item["id"] in spacy_cache or (item.content != spacy_cache[item["id"]].text):
            unseen_docs.append((item.content, {"id": item["id"], "title": item["title"]}))
print(len(unseen_docs))
i = 0
for doc, ctx in nlp.pipe(unseen_docs, as_tuples=True, disable=["textcat"], batch_size=40):
    i += 1
    if i % 40 == 0: print(i)
    doc._.title = ctx["title"]
    doc._.id = ctx["id"]
    doc_bin.add(doc)
    docs.append(doc)
    if ctx["id"] in spacy_cache:
        mesh.remove_doc(ctx["id"])

print(time.time() - a, f"time to scrape docs, of {len(unseen_docs)} new ones.")
if len(unseen_docs):
    with open("serialized_annot", "wb") as f:
        f.write(doc_bin.to_bytes())


b = time.time()
if len(unseen_docs) or rerun_heuristics:
    list(map(lambda x: mesh.process_document(x), docs + unseen_docs))
    print(mesh.graph.number_of_edges())
    mesh.remove_irrelevant_edges()
    print(mesh.graph.number_of_edges(), "number of edges after tf-idf")
    print(len(mesh.seen_concepts), "number of concepts")
    c = time.time()
    print("removing edges", c - b)
    mesh.trim_all()
    print(time.time() - c, "time to trim")
print(len(mesh.seen_concepts), "number of concepts post-processing")
print(mesh.graph.number_of_edges(), "number of edges post-processing")
json_graph = networkx.json_graph.node_link_data(mesh.graph)
json.dump(json_graph, open("graph.json", "w"))
json.dump(json_graph, open("force/force.json", "w"))
print(mesh.seen_concepts)

app = flask.Flask(__name__)
cors = CORS(app)
app.config['CORS_HEADERS'] = 'Content-Type'

@app.route("/<file>")
def serve_file(file):
    return flask.send_file(f"../force/{file}")

@app.route("/most_sim")
def find_sim():
    id = int(request.args.get("id"))
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
app.run(port=5002)
