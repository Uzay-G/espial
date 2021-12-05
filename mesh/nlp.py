import math
from os.path import exists
import copy
import warnings
import string
import time
import json

import flask
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
nlp = spacy.load("en_core_web_md")

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
        self.concept_graph = networkx.DiGraph()
        self.doc_graph = networkx.DiGraph()
        self.cache = set()
        self.nb_docs = 0
        self.query_results = {}

    def build_concept_tree(self):
        for node in list(self.concept_graph):
            if len(self.doc_graph.in_edges(node)):
                self.get_higher_concepts(wordnet.synset(node))

    def get_higher_concepts(self, synset, prev=None):
        already_cached = synset.name() in self.concept_graph # check if this concept was already encountered
        if prev and prev != synset.name() and not self.concept_graph.has_edge(prev, synset.name()):
            self.concept_graph.add_edge(prev, synset.name()) # add child concept that spawned discovery of this one
        if not already_cached:
            self.concept_graph.add_node(synset.name(), sim=0, avg_vec=0)
        if already_cached and prev:
            return

        hyps = synset.hypernyms()
        for hyp in hyps:
            self.get_higher_concepts(hyp, prev=synset.name())

    def create_link(self, item, concept):
        if not ".n." in concept:
            return
        if not concept in self.concept_graph:
            spacy_cache[concept] = nlp(concept.split(".")[0].replace("_", " "))
            self.concept_graph.add_node(concept, sim=0, avg_vec=0, count=1)
        if self.doc_graph.has_edge(item, concept):
            self.doc_graph[item][concept]["count"] += 1
        else:
            self.doc_graph.add_edge(item, concept, count=1)
            self.concept_graph.nodes[concept]["count"] += 1 
        self.doc_graph.nodes[item]["tf"] += 1
#
    def get_hypernyms(self, chunk, item_id):
        sent = chunk.sent.text.strip().replace(" ", "_") # get current sentence of chunk
        #print(sent, chunk)
        ss = lesk(sent, str(chunk)) # test to see if we can get a meaning for the entire chunk
        if ss:
            self.create_link(item_id, ss.name())
        elif len(chunk) == 1:
            return
        else:
            ss = lesk(sent, chunk.root.text)
            if ss:
                #self.add_concept(ss, item_id)
                self.create_link(item_id, ss.name())
                
             #       ss = lesk(sent, w.text.translate(str.maketrans('', '', string.punctuation))) 

    def remove_irrelevant_edges(self):
        for item, concept, data in list(self.doc_graph.edges(data=True)):
            tf = data["count"] / self.doc_graph.nodes[item]["tf"]
            idf = math.log(self.nb_docs / self.concept_graph.nodes[concept]["count"])
            #print(tf * idf, item, concept)
            if tf * idf < 0.03:
                self.doc_graph.remove_edge(item, concept)
            
    def trim_node(self, concept):
        if concept in self.cache:
            return
        avg = 0
        n = 0
        linked_docs = list(self.doc_graph.in_edges(concept))
        defined = 0
        avg_vec = 0
        word_sim = 0
        for link in linked_docs:
            doc1 = link[0]
            doc_vector = spacy_cache[doc1].vector
            word_sim += spacy_cache[doc1].similarity(spacy_cache[concept])
            if defined:
                avg_vec += doc_vector
            else: 
                avg_vec = doc_vector.copy()
                defined = 1
            for link2 in linked_docs:
                doc2 = link2[0]
                if doc1 != doc2:
                    n += 1
                    avg += self.compute_similarity(doc1, doc2)
        avg = (n == 0) or avg / n
        word_sim /= (len(linked_docs) == 0) or len(linked_docs)
        networkx.set_node_attributes(self.concept_graph, {concept: avg}, name="sim")
        n = len(linked_docs)
        child_concepts = self.concept_graph.in_edges(concept)
        avg_child_sim = 0
        saved_avg = (n == 0) or avg_vec / len(linked_docs)
        for link in list(child_concepts):
            if link[0] in self.concept_graph:
                self.trim_node(link[0])
                if link[0] in self.concept_graph:
                    n += 1
                    other_avg_vec = self.concept_graph.nodes[link[0]]["avg_vec"]
                    if len(linked_docs):
                        avg_child_sim += cos_sim(saved_avg, other_avg_vec) 
                    if defined:
                        avg_vec += other_avg_vec
                    else:
                        avg_vec = other_avg_vec
                        defined = 1
        if len(linked_docs) and len(child_concepts):
            avg_child_sim /= len(child_concepts)
        else: avg_child_sim = 1
        if n:
            networkx.set_node_attributes(self.concept_graph, {concept: avg_vec / n}, name="avg_vec")
        
        n = 0
        #child_mutual_sim = 0
        #for link in child_concepts:
         #   for link2 in child_concepts:
          #      if link != link2:
           #         n += 1
                    #if self.concept_graph.nodes[link[0]]["avg_vec"] != 0 and self.concept_graph.nodes[link2[0]]["avg_vec"] != 0:
            #        child_mutual_sim += cos_sim(self.concept_graph.nodes[link[0]]["avg_vec"], self.concept_graph.nodes[link2[0]]["avg_vec"])
        #child_mutual_sim = (n == 0) or child_mutual_sim / n
        total_in_edges = len(self.concept_graph.in_edges(concept))
        if len(linked_docs):
            total_in_edges += len(linked_docs)
        #print(concept, child_mutual_sim, avg_child_sim, avg, len(linked_docs), len(child_concepts), word_sim)
        self.cache.add(concept)
        #if child_mutual_sim < 0.85 or avg < 0.8 avg_child_sim < 0.85 or total_in_edges <= 2 or not ".n." in concept:
        if total_in_edges <= 2 or avg < 0.8 or word_sim < 0.45  or avg_child_sim < 0.8: # or child_mutual_sim < 0.8
            if concept in self.doc_graph: self.doc_graph.remove_node(concept)
            self.concept_graph.remove_node(concept)


    def trim_all(self):
        for node in list(self.concept_graph):
            if node in self.concept_graph and not len(self.concept_graph.out_edges(node)):
                self.trim_node(node)


    def process_document(self, doc):
        self.nb_docs += 1
        self.doc_graph.add_node(doc._.id, title=doc._.title, tf=0)
        spacy_cache[doc._.id] = doc
        for chunk in doc.noun_chunks:
            self.get_hypernyms(chunk, doc._.id)

    def compose(self):
        return networkx.compose(self.doc_graph, self.concept_graph)

    def compute_similarity(self, doc1, doc2):
        return spacy_cache[doc1].similarity(spacy_cache[doc2])


    def propagate_specific_root(self, root, current, depth):
        if "roots" in self.concept_graph.nodes[current]:
            self.concept_graph.nodes[current]["roots"].append((root, depth))
        else:
            self.concept_graph.nodes[current]["roots"] = [(root, depth)]
        for i in self.concept_graph.in_edges(current):
            self.propagate_specific_root(root, i[0], depth + 1)


    def get_roots(self):
        for c in self.concept_graph:
            if not self.concept_graph.out_edges(c):
                self.propagate_specific_root(c, c, 1)

    def interlink_docs_graph(self):
        self.get_roots()
        interlinked = networkx.Graph()
        max_score = 0
        scores = []
        i = 0
        docs = [doc for name, doc in spacy_cache.items() if isinstance(name, int)]
        doc_roots = {}
        for d in self.doc_graph:
            doc_roots[d] = {}
            for link in self.doc_graph.out_edges(d):
                for c in self.concept_graph.nodes[link[1]]["roots"]:
                    doc_roots[d][c[0]] = c[1]

        for doc in docs:

            i += 1
            interlinked.add_node(doc._.id, title=doc._.title)
            for doc2 in docs[i:]:
                interlinked.add_node(doc2._.id, title=doc2._.title)
                sim = doc.similarity(doc2)
                score = 0
                if sim > 0.8:
                    for c, depth in doc_roots[doc._.id].items():
                        if c in doc_roots[doc2._.id]:
                            score += min(depth, doc_roots[doc2._.id][c])
                    score *= sim
                    interlinked.add_edge(doc2._.id, doc._.id, stroke=score)
                    scores.append([doc._.title, doc2._.title, score])
        scores.sort(reverse=True, key=lambda x: x[2])
        print(scores[:100])
        return interlinked

    def search_for_synset(self, ss, depth=1):
        if ss.name() in self.doc_graph:
            print(ss.name())
            for doc, _ in self.doc_graph.in_edges(ss.name()):
                print(spacy_cache[doc]._.title)
                self.query_results[doc] = self.query_results.get(doc, 0) + 1/depth
            return
        hyps = ss.hypernyms()
        for hyp in hyps:
            self.search_for_synset(hyp, depth + 1)


    def search(self, query):
        self.query_results = {}
        doc = nlp(query)

        nouns = set()
        for chunk in doc.noun_chunks:
            nouns.add(chunk.root.text)
            sent = chunk.sent.text.strip().replace(" ", "_") # get current sentence of chunk
            if len(sent.split(" ")) > 1:
                ss = lesk(sent, str(chunk)) # test to see if we can get a meaning for the entire chunk
                if ss:
                    self.search_for_synset(ss)
                else:
                    ss = lesk(sent, chunk.root.text)
                    if ss:
                        self.search_for_synset(ss)
            else:
                for ss in wordnet.synsets(chunk.text):
                    self.search_for_synset(ss)
        for word in doc:
            if not word.text in nouns and not word.is_stop:
                for ss in wordnet.synsets(word.text):
                    if ".n." in ss.name():
                        self.search_for_synset(ss)
        return [spacy_cache[key]._.title for key, _ in sorted(self.query_results.items(), key=lambda item: item[1], reverse=True)]

mesh = ConceptMesh()
a = time.time()
docs = []
if exists("serialized"):
    with open("serialized", "rb") as f:
        doc_bin = DocBin(store_user_data=True).from_bytes(f.read())
        docs = list(doc_bin.get_docs(nlp.vocab))
        list(map(mesh.process_document, docs))
else:
    doc_bin = DocBin(store_user_data=True)
unseen_docs = []
with archivy.app.app_context():
    for item in archivy.data.get_items(structured=False):
        if not item["id"] in mesh.doc_graph:
            unseen_docs.append((item.content, {"id": item["id"], "title": item["title"]}))
print(len(unseen_docs))
for doc, ctx in nlp.pipe(unseen_docs, as_tuples=True, disable=["ner", "lemmatizer", "textcat"], batch_size=50):
    doc._.title = ctx["title"]
    doc._.id = ctx["id"]
    doc_bin.add(doc)
    docs.append(doc)
    mesh.process_document(doc)

print(time.time() - a, f"time to scrape docs, of {len(unseen_docs)} new ones.")


#tf_time = time.time()
#tf_idf = TfidfVectorizer(strip_accents="unicode", stop_words="english", max_df=0.7) # better preprocessing here
#tfidf_mat = tf_idf.fit_tranform(list(map(lambda doc: doc.text, docs)))
#print(time.time() - tf_time, "tf_idf")
if len(unseen_docs):
    with open("serialized", "wb") as f:
        f.write(doc_bin.to_bytes())


b = time.time()
print(mesh.doc_graph.number_of_edges())
mesh.remove_irrelevant_edges()
print(mesh.doc_graph.number_of_edges(), "number of edges after tf-idf")
c = time.time()
print("removing edges", c - b)
mesh.build_concept_tree()
d = time.time()
print(d - c, "time to build tree")
print(len(mesh.concept_graph), "number of concepts after building")
mesh.trim_all()
print(time.time() - d, "time to trim")

print(len(mesh.concept_graph), "number of concepts after trimming")
print(mesh.doc_graph.number_of_edges(), "number of edges after trimming")

composed_graph = mesh.compose()
print(mesh.nb_docs, "number of docs")
i = 0
for node in composed_graph:
    composed_graph.nodes[node]["avg_vec"] = 0
    composed_graph.nodes[node]["i"] = i
    i += 1
d = networkx.json_graph.node_link_data(composed_graph)
json.dump(d, open("force/force.json", "w"))

#t = time.time()
#d2 = networkx.json_graph.node_link_data(mesh.interlink_docs_graph())
#json.dump(d2, open("force/force2.json", "w"))
#print(time.time() - t, "similarity graph")

app = flask.Flask(__name__)
cors = CORS(app)
app.config['CORS_HEADERS'] = 'Content-Type'
with open("serialized", "wb") as f:
    f.write(doc_bin.to_bytes())


@app.route("/search", methods=["POST"])
@cross_origin()
def search():
    q = flask.request.json.get("q", None)
    is_web = flask.request.json["html"]
    if is_web:
        soup = BeautifulSoup(is_web)
        stripped = ["footer", "nav", "img"]
        for tag in stripped:
            for s in soup.select(tag):
                s.extract()
        q = html2text.html2text(str(soup), bodywidth=0)
    print(q)
    resp = flask.jsonify(mesh.search(q))
    return resp

@app.route("/<file>")
def serve_file(file):
    return flask.send_file(f"../force/{file}")
app.run(port=5002)
