import math
from os.path import exists
import copy
import warnings
import string
import time
import json

import spacy
from spacy.tokens import DocBin, Doc
import numpy as np
import networkx
from nltk.wsd import lesk
from nltk.corpus import wordnet

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
        if not concept in self.concept_graph:
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
            if tf * idf < 0.02:
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
        nlp_conc = nlp(concept.split(".")[0].replace("_", " "))
        for link in linked_docs:
            doc1 = link[0]
            doc_vector = spacy_cache[doc1].vector
            word_sim += spacy_cache[doc1].similarity(nlp_conc)
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
        child_mutual_sim = 0
        for link in child_concepts:
            for link2 in child_concepts:
                if link != link2:
                    n += 1
                    #if self.concept_graph.nodes[link[0]]["avg_vec"] != 0 and self.concept_graph.nodes[link2[0]]["avg_vec"] != 0:
                    child_mutual_sim += cos_sim(self.concept_graph.nodes[link[0]]["avg_vec"], self.concept_graph.nodes[link2[0]]["avg_vec"])
        child_mutual_sim = (n == 0) or child_mutual_sim / n
        total_in_edges = len(self.concept_graph.in_edges(concept))
        if len(linked_docs):
            total_in_edges += len(linked_docs)
        #print(concept, child_mutual_sim, avg_child_sim, avg, len(linked_docs), len(child_concepts), word_sim)
        self.cache.add(concept)
        #if child_mutual_sim < 0.85 or avg < 0.8 avg_child_sim < 0.85 or total_in_edges <= 2 or not ".n." in concept:
        if total_in_edges <= 3 or avg < 0.8 or child_mutual_sim < 0.8 or avg_child_sim < 0.8 or word_sim < 0.4: 
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
            #print(time.time() - b, "time for one concept")

    def compose(self):
        return networkx.compose(self.doc_graph, self.concept_graph)

    def compute_similarity(self, doc1, doc2):
        return spacy_cache[doc1].similarity(spacy_cache[doc2])


    def propagate_specific_root(self, root, current, depth):
        if "roots" in self.concept_graph.nodes[current]:
            self.concept_graph.nodes[current].append((root, depth))
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
        docs = list(spacy_cache.values())
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


mesh = ConceptMesh()
a = time.time()
if exists("serialized"):
    with open("serialized", "rb") as f:
        doc_bin = DocBin(store_user_data=True).from_bytes(f.read())
        docs = list(doc_bin.get_docs(nlp.vocab))
        for doc in docs:
            mesh.process_document(doc)
    print(time.time() - a)
else:
    doc_bin = DocBin(store_user_data=True)
docs = []
with archivy.app.app_context():
    for item in archivy.data.get_items(structured=False):
        if not item["id"] in mesh.doc_graph:
            print("b", item["id"])
            docs.append((item.content, {"id": item["id"], "title": item["title"]}))

for doc, ctx in nlp.pipe(docs, as_tuples=True, disable=["ner", "lemmatizer", "textcat"]):
    doc._.title = ctx["title"]
    doc._.id = ctx["id"]
    mesh.process_document(doc)
    doc_bin.add(doc)


b = time.time()
print("indexing", b - a)
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

"""

print("len", len(mesh.concept_graph))
for c in mesh.concept_graph:

    print(c, list(mesh.concept_graph.out_edges(c)), list(mesh.concept_graph.in_edges(c)), mesh.concept_graph.nodes[c]["sim"])
    
#networkx.nx_agraph.write_dot(mesh.compose(), './compose.dot')
#networkx.nx_agraph.write_dot(mesh.concept_graph, './concepts2.dot')
#networkx.nx_agraph.write_dot(mesh.doc_graph, './docs2.dot')
"""

composed_graph = mesh.compose()
print(mesh.nb_docs, "number of docs")
i = 0
for node in composed_graph:
    composed_graph.nodes[node]["avg_vec"] = 0
    composed_graph.nodes[node]["i"] = i
    i += 1
d = networkx.json_graph.node_link_data(composed_graph)
json.dump(d, open("force/force.json", "w"))

t = time.time()
d2 = networkx.json_graph.node_link_data(mesh.interlink_docs_graph())
json.dump(d2, open("force/force2.json", "w"))
print(time.time() - t, "similarity graph")

#with open("serialized", "wb") as f:
#    f.write(doc_bin.to_bytes())
