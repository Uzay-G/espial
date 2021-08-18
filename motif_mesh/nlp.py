import math
import string
import time

import spacy
import networkx
from matplotlib import pyplot as plt
import treelib
from nltk.wsd import lesk

import archivy

nlp = spacy.load("en_core_web_md")

class Freq:
    def __init__(self):
        self.concept_freq = 0
        self.doc_freq = set()
        self.cached = False

class ConceptMesh:

    def __init__(self):
        self.freq_cache = {}
        self.concept_graph = networkx.DiGraph()
        self.doc_graph = networkx.DiGraph()


    def add_concept(self, synset, item_id=None, depth=0, prev=None):
        already_cached = synset.name() in self.concept_graph # check if this concept was already encountered
        hyps = synset.hypernyms()
        if not already_cached:
            self.concept_graph.add_node(synset.name(), color="blue")
        if depth == 0:
            self.doc_graph.add_edge(item_id, synset.name())
        if prev:
            self.concept_graph.add_edge(prev, synset.name()) # add child concept that spawned discovery of this one
        if already_cached:
            root_concepts = list(self.doc_graph.out_edges(synset.name(), data="depth"))
            return [(concept[1], concept[2]) for concept in root_concepts] # return all root_parents of current concpet

        if not hyps:
            return [(synset.name(), depth)] # if no parent concepts, return current root concept

        all_roots = []
        for hyp in hyps:
            curr_roots = self.add_concept(hyp, item_id, depth + 1, prev=synset.name()) # iterate over overarching concepts
            for root in curr_roots:
                curr_depth = root[1] - depth
                existing_depth = self.doc_graph.get_edge_data(synset.name(), root[0])
                if existing_depth and existing_depth["depth"] > curr_depth:
                    self.doc_graph.add_edge(synset.name(), root[0], depth=curr_depth)
            all_roots += curr_roots
        return all_roots

    def get_hypernyms(self, chunk, item_id):
        sent = chunk.sent.text.strip() # get current sentennce of chunk
        ss = lesk(sent, str(chunk)) # test to see if we can get a meaning for the entire chunk
        if ss:
            self.add_concept(ss, item_id)
        elif len(chunk) == 1:
            return
        else:
            for w in chunk:
                if w.pos_ in ["NOUN", "ADJ"]: # otherwise process only relevant words
                    ss = lesk(sent, w.text.translate(str.maketrans('', '', string.punctuation))) 
                    if ss:
                        self.add_concept(ss, item_id)

    def process_document(self, item_id, text):
        doc = nlp(text)
        self.doc_graph.add_node(item_id, doc_nlp=doc)
        for chunk in doc.noun_chunks:
            self.get_hypernyms(chunk, item_id)

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
        vector_sim = doc1["doc_nlp"].similarity(doc2["doc_nlp"])
        return vector_sim

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
        if item["id"] < 30:
            mesh.process_document(item["id"], item.content)
    b = time.time()

print(b - a)
networkx.nx_agraph.write_dot(mesh.concept_graph, './concepts2.dot')
networkx.nx_agraph.write_dot(mesh.doc_graph, './docs2.dot')
