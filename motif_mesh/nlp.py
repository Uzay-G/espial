import math
import copy
import warnings
import string
import time
import json

import spacy
import numpy as np
import networkx
from nltk.wsd import lesk

import archivy
nlp = spacy.load("en_core_web_md")

# idea: compute concept average vector to avoid highly abstract concepts slip their way through

def cos_sim(v1, v2):
    res = np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2))
    return res

class Freq:
    def __init__(self):
        self.concept_freq = 0
        self.doc_freq = set()
        self.cached = False

spacy_cache = {}
class ConceptMesh:

    def __init__(self):
        self.freq_cache = {}
        self.concept_graph = networkx.DiGraph()
        self.doc_graph = networkx.DiGraph()
        self.cache = set()


    def add_concept(self, synset, item_id=None, depth=0, prev=None):
        #print(synset.name(), depth)
        if synset.name().strip() == "":
            return
        if not synset.name() in spacy_cache:
            spacy_cache[synset.name()] = nlp(synset.name().split(".")[0].replace("_", " "))
        sim = spacy_cache[item_id].similarity(spacy_cache[synset.name()])
        if depth == 0 and sim < 0.3 and spacy_cache[synset.name()].has_vector:
            print(synset.name(), self.doc_graph.nodes[item_id]["title"], sim)
            return
        already_cached = synset.name() in self.concept_graph # check if this concept was already encountered
        hyps = synset.hypernyms()
        if not already_cached:
            self.concept_graph.add_node(synset.name(), color="blue", sim=0, avg_vec=0)
        if depth == 0:
            self.doc_graph.add_edge(item_id, synset.name())
        if prev and prev != synset.name() and not self.concept_graph.has_edge(prev, synset.name()):
            self.concept_graph.add_edge(prev, synset.name()) # add child concept that spawned discovery of this one
        if already_cached:
            #root_concepts = list(self.doc_graph.out_edges(synset.name(), data="depth"))
            #return [(concept[1], concept[2]) for concept in root_concepts] # return all root_parents of current concpet
            return

        if not hyps:
            #return [(synset.name(), depth)] # if no parent concepts, return current root concept
            return

        all_roots = []
        for hyp in hyps:
            #curr_roots = self.add_concept(hyp, item_id, depth + 1, prev=synset.name()) # iterate over overarching concepts
            self.add_concept(hyp, item_id, depth + 1, prev=synset.name())
           # for root in curr_roots:
            #    curr_depth = root[1] - depth
             #   existing_depth = self.doc_graph.get_edge_data(synset.name(), root[0])
              #  if existing_depth and existing_depth["depth"] > curr_depth:
               #     self.doc_graph.add_edge(synset.name(), root[0], depth=curr_depth)
           # all_roots += curr_roots
       # return all_roots
        return

    def get_hypernyms(self, chunk, item_id):
        sent = chunk.sent.text.strip().replace(" ", "_") # get current sentence of chunk
        #print(sent, chunk)
        ss = lesk(sent, str(chunk)) # test to see if we can get a meaning for the entire chunk
        if ss:
            #print(chunk.text, ss.name())
            self.add_concept(ss, item_id)
        elif len(chunk) == 1:
            return
        else:
            ss = lesk(sent, chunk.root.text)
            if ss:
                #print(chunk.text, chunk.root.text, ss.name())
                self.add_concept(ss, item_id)
                
           # for w in chunk:
              #  if w.pos_ in ["NOUN", "ADJ"]: # otherwise process only relevant words

            #    if w.pos_ in ["NOUN"]: # otherwise process only relevant words
             #       ss = lesk(sent, w.text.translate(str.maketrans('', '', string.punctuation))) 
              #      if ss:
               #         print(chunk.text, ss.name())
                #        self.add_concept(ss, item_id)
            
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
            #word_sim += spacy_cache[doc1].similarity(nlp_conc)
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
        #word_sim /= (len(linked_docs) == 0) or len(linked_docs)
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
        print(concept, child_mutual_sim, avg_child_sim, avg, len(linked_docs), len(child_concepts), word_sim)
        self.cache.add(concept)
        if child_mutual_sim < 0.85 or avg_child_sim < 0.85 or total_in_edges <= 3 or not ".n." in concept:
            if len(linked_docs): self.doc_graph.remove_node(concept)
            self.concept_graph.remove_node(concept)


    def trim_all(self):
        for node in list(self.concept_graph):
            if node in self.concept_graph and not len(self.concept_graph.out_edges(node)):
                self.trim_node(node)


    def process_document(self, item_id, text, title):
        doc = nlp(text)
        self.doc_graph.add_node(item_id, title=title)
        spacy_cache[item_id] = doc
        for chunk in doc.noun_chunks:
            self.get_hypernyms(chunk, item_id)

    def compose(self):
        return networkx.compose(self.doc_graph, self.concept_graph)

    """
    def count_freq(self, concept, name):
        curr_freq = self.freq_cache[name]
        if not curr_freq.cached:
            for child in concept.children:
                child_freq = self.count_freq(self.concept_map[child], child)
                curr_freq.concept_freq += child_freq.concept_freq
                curr_freq.doc_freq = set.union(curr_freq.doc_freq, child_freq.doc_freq)
            curr_freq.cached = 1
        return self.freq_cache[name]
            
    def get_concept_frequencies(self):
        self.freq_cache = {name: Freq() for name in self.concept_map.keys()}
        self.total_concept_count = 0
        for id, d in self.documents.items():
            for concept, freq in d.direct_concepts.items():
                self.freq_cache[concept].concept_freq += freq
                self.total_concept_count += freq
                self.freq_cache[concept].doc_freq.add(id)
        for name, concept in self.concept_map.items():
            if not concept.parents:
                self.count_freq(concept, name)

    def idf(self, concept_name):
        Implementation of tf-idf algorithm to discount highly abstract concepts.
        #tf = self.freq_cache[concept_name].concept_freq / self.total_concept_count
        idf = math.log(len(self.documents) / len(self.freq_cache[concept_name].doc_freq))
        if idf < 0.1:
            print(idf, concept_name)
        return idf
    """

    def compute_similarity(self, doc1, doc2):
        return spacy_cache[doc1].similarity(spacy_cache[doc2])

    """
    def add_node_to_graph(self, concept, name):
        if not name in self.graph:
            graph.add_node(name, {"color": "blue"})
            


    def build_graph(self):
        self.graph = networkx.Graph()
        for name, concept in self.concept_map.items():
            if not concept.parents:
                self.add_concept_to_graph(concept, name)
    """
        


mesh = ConceptMesh()
a = time.time()
with archivy.app.app_context():
    for item in archivy.data.get_items(structured=False):
        if item["id"] < 10000:
            mesh.process_document(item["id"], item.content, item["title"])
    b = time.time()

print(b - a)
mesh.trim_all()
c = time.time()
print(c - b)
print("len", len(mesh.concept_graph))
for c in mesh.concept_graph:

    print(c, list(mesh.concept_graph.out_edges(c)), list(mesh.concept_graph.in_edges(c)), mesh.concept_graph.nodes[c]["sim"])
    
composed_graph = mesh.compose()
print(len(composed_graph) - len(mesh.concept_graph))
i = 0
for node in composed_graph:
    composed_graph.nodes[node]["avg_vec"] = 0
    composed_graph.nodes[node]["i"] = i
    i += 1
d = networkx.json_graph.node_link_data(composed_graph)
json.dump(d, open("force/force.json", "w"))
#networkx.nx_agraph.write_dot(mesh.compose(), './compose.dot')
#networkx.nx_agraph.write_dot(mesh.concept_graph, './concepts2.dot')
#networkx.nx_agraph.write_dot(mesh.doc_graph, './docs2.dot')
