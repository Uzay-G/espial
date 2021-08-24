import math
import string
import time
import json

import spacy
import networkx
from nltk.wsd import lesk

import archivy

nlp = spacy.load("en_core_web_md")

# idea: compute concept average vector to avoid highly abstract concepts slip their way through
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
        print(synset.name(), depth)
        already_cached = synset.name() in self.concept_graph # check if this concept was already encountered
        hyps = synset.hypernyms()
        if not already_cached:
            self.concept_graph.add_node(synset.name(), color="blue", sim=0)
        if depth == 0:
            self.doc_graph.add_edge(item_id, synset.name())
        if prev and prev != synset.name():
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
        print(sent, chunk)
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
        avg = 0
        n = 0
        linked_docs = list(self.doc_graph.in_edges(concept))
        for link in linked_docs:
            for link2 in linked_docs:
                doc1 = link[0]
                doc2 = link2[0]
                if doc1 != doc2:
                    n += 1
                    avg += self.compute_similarity(doc1, doc2)
        avg = (n == 0) or avg / n
        self.concept_graph.nodes[concept]["sim"] = avg
        #print(avg)
        for link in list(self.concept_graph.in_edges(concept)):
            if link[0] in self.concept_graph:
                self.trim_node(link[0])
        total_in_edges = len(self.concept_graph.in_edges(concept))
        if len(linked_docs):
            total_in_edges += len(self.doc_graph.in_edges(concept))
        if avg < 0.9 or total_in_edges <= 2 or not ".n." in concept:
            if len(linked_docs): self.doc_graph.remove_node(concept)
            self.concept_graph.remove_node(concept)


    def trim_all(self):
        for node in list(self.concept_graph):
            if node in self.concept_graph and not len(self.concept_graph.out_edges(node)):
                self.trim_node(node)


    def process_document(self, item_id, text):
        doc = nlp(text)
        self.doc_graph.add_node(item_id, doc_nlp=doc)
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
        vector_sim = self.doc_graph.nodes[doc1]["doc_nlp"].similarity(self.doc_graph.nodes[doc2]["doc_nlp"])
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
        if item["id"] < 10000:
            mesh.process_document(item["id"], item.content)
    b = time.time()

print(b - a)
#mesh.trim_all()
c = time.time()
print(c - b)
#print(len(mesh.concept_graph))
#for c in mesh.concept_graph:
#    print(c, list(mesh.concept_graph.out_edges(c)), mesh.concept_graph.nodes[c]["sim"])
    
#composed_graph = mesh.compose()
#for node in composed_graph:
#    if "doc_nlp" in composed_graph.nodes[node]:
#        composed_graph.nodes[node]["doc_nlp"] = 0
#d = networkx.json_graph.node_link_data(composed_graph)
#json.dump(d, open("force/force.json", "w"))
#networkx.nx_agraph.write_dot(mesh.compose(), './compose.dot')
#networkx.nx_agraph.write_dot(mesh.concept_graph, './concepts2.dot')
#networkx.nx_agraph.write_dot(mesh.doc_graph, './docs2.dot')
