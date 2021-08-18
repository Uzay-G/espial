import math
import string
import time

import spacy
import networkx
import matplotlib
import treelib
from nltk.wsd import lesk

import archivy

nlp = spacy.load("en_core_web_md")

class Concept:

    def __init__(self, parents):
        self.parents = parents
        self.children = []
        self.root_parents = {}
        self.freq = 0

    def __repr__(self):
       return " ".join(self.parents) + ";" + " ".join(self.root_parents.keys()) + ";"

class Freq:
    def __init__(self):
        self.concept_freq = 0
        self.doc_freq = set()
        self.cached = False

class Document:
    def __init__(self, doc):
        self.direct_concepts = {}
        self.embedding = None
        self.spacy_doc = doc

    def __repr__(self):
        return " ".join([x for x in self.direct_concepts])

class ConceptMesh:

    def __init__(self):
        self.concept_map = {}
        self.documents = {}
        self.freq_cache = {}
        self.total_concept_count = 0
        self.graph = networkx.Graph()
        pass

    def __repr__(self):
        l = "Documents\n"
        for k, v in self.documents.items():
            l += f"{k} - {v}\n"
        l += "Concepts\n"
        for k, v in self.concept_map.items():
            l += f"{k} - {v}\n"
        return l

    def add_concept(self, synset, item_id=None, depth=0, prev=None):
        already_cached = synset.name() in self.concept_map # check if this concept was already encountered
        hyps = synset.hypernyms()
        if depth == 0:
            doc_concepts = self.documents[item_id].direct_concepts
            doc_concepts[synset.name()] = doc_concepts.get(synset.name(), 1) + 1 # add this concept as directly linked to said document
        if not already_cached:
            self.concept_map[synset.name()] = Concept(parents=[hyp.name() for hyp in hyps]) # set up our cached concept
        curr_concept = self.concept_map[synset.name()]
        if prev:
            curr_concept.children.append(prev) # add child concept that spawned discovery of this one
        if already_cached:
            return [(k, v) for k, v in curr_concept.root_parents.items()] # return all root_parents of current concpet
        if not hyps:
            curr_concept.root_parents[synset.name()] = 0 # obviously its distance to itself is 0 
            return [(synset.name(), depth)] # if no parent concepts, return current root concept

        all_roots = []
        for hyp in hyps:
            curr_roots = self.add_concept(hyp, item_id, depth + 1, prev=synset.name()) # iterate over overarching concepts
            for root in curr_roots:
                # set depth from current concept to tentative root ones
                curr_concept.root_parents[root[0]] = min(root[1] - depth, curr_concept.root_parents.get(root[0], 0))
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
        self.documents[item_id] = Document(doc)
        for chunk in doc.noun_chunks:
            self.get_hypernyms(chunk, item_id)

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
        """
        Implementation of tf-idf algorithm to discount highly abstract concepts.
        """
        #tf = self.freq_cache[concept_name].concept_freq / self.total_concept_count
        idf = math.log(len(self.documents) / len(self.freq_cache[concept_name].doc_freq))
        if idf < 0.1:
            print(idf, concept_name)
        return idf

    def compute_similarity(self, doc1, doc2):
        vector_sim = doc1.spacy_doc.similarity(doc2.spacy_doc)
        return vector_sim

    def add_node_to_graph(self, concept, name):
        if not name in self.graph:
            graph.add_node(name, {"color": "blue"})
            


    def build_graph(self):
        self.graph = networkx.Graph()
        for name, concept in self.concept_map.items():
            if not concept.parents:
                self.add_concept_to_graph(concept, name)
        


mesh = ConceptMesh()
a = time.time()
with archivy.app.app_context():
 #   id = 1586
  #  text = archivy.data.get_item(id).content
   # mesh.process_document(id, text).
 #   print(mesh)
    for item in archivy.data.get_items(structured=False):
        if item["id"] < 100:
            mesh.process_document(item["id"], item.content)
    mesh.get_concept_frequencies()
    b = time.time()

print(b - a)
"""
max_sim = 0
pair = [0, 0]
for id1, d1 in mesh.documents.items():
    for id2, d2 in mesh.documents.items():
        if id1 != id2:
            sim = mesh.compute_similarity(d1, d2)
            if max_sim < sim:
                max_sim = sim
                pair = [id1, id2]
                """
tree = treelib.Tree()
tree.create_node("root", "root")
def temp_cr_tree(name, concept, parent):
    try:
        tree.create_node(name + ";" +  str(mesh.idf(name)), name, parent)
    except:
        pass
    for c in concept.children:
        temp_cr_tree(c, mesh.concept_map[c], name)




for name, c in mesh.concept_map.items():
    if not c.parents:
        temp_cr_tree(name, c, "root")

tree.show()
#print(pair, max_sim)
