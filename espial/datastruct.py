import math
import networkx
import time

import numpy as np
# idea: compute concept average vector to avoid highly abstract concepts slip their way through
def cos_sim(v1, v2):
    res = np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2))
    return res

def sigmoid(z):
    return 1/(1 + np.exp(-z))

class ConceptMesh:
    def __init__(self, mode, doc_cache):
        self.graph = networkx.DiGraph(openness=mode)
        self.doc_cache = doc_cache
        self.concept_cache = {}
        self.nb_docs = 0
        self.dbg = ""
        self.sim_cache = {}

        if mode:
            self.avg_exp_o = 0.025 * mode
            self.tf_exp_o = 0.0001 * mode
        else:
            self.avg_exp_o = 0
            self.tf_exp_o = 0


    def create_link(self, item, concept, single_word=False, is_ent=False):
        if single_word:
            text = ''.join(filter(lambda x: str.isalnum(x) or x == ' ', concept.lemma_.lower().strip()))
            if concept.is_stop or not concept.is_alpha:
                return
        else:
            text = ''.join(filter(lambda x: str.isalnum(x) or x == ' ', concept.text.lower().strip()))
            if concept.root.is_stop or not concept.root.is_alpha :
                return
        if len(text) < 4: return
        if not text in self.concept_cache:
            self.sim_cache[text] = {}
            self.concept_cache[text] = concept
            self.graph.add_node(text, sim=0, score=0, count=1, is_ent=is_ent, type="concept", avg_tf_idf=0)
        elif is_ent:
            self.graph.nodes[text]["is_ent"] = True
        if self.graph.has_edge(item, text):
            self.graph[item][text]["count"] += 1
        else:
            self.graph.add_edge(item, text, count=1)
            self.graph.nodes[text]["count"] += 1 
        self.graph.nodes[item]["tf"] += 1

    def get_sanitized_concepts(self, chunk, item_id):
        #relevant_tokens = [token.text for token in chunk if not token.is_stop and token.is_alpha]
        self.create_link(item_id, chunk.root, True)

    def remove_irrelevant_edges(self):
        for item, concept, data in list(self.graph.edges(data=True)):
            if concept in self.graph:
                tf = data["count"] / self.graph.nodes[item]["tf"]
                idf = math.log(self.nb_docs / self.graph.nodes[concept]["count"])
                tf_idf = tf * idf
                if (tf_idf < 0.02 + self.tf_exp_o and not self.graph.nodes[concept]["is_ent"]) or (tf_idf < 0.15 and self.graph.nodes[concept]["is_ent"]): # prev: 0.25 (ent)
                    self.graph.remove_edge(item, concept)
                else:
                    self.graph[item][concept]["tf_idf"] = tf_idf
                    self.graph.nodes[concept]["avg_tf_idf"] += tf_idf
        for concept in list(self.concept_cache.keys()):
            if len(list(self.graph.in_edges(concept))) < 2:
                self.graph.remove_node(concept)
                self.concept_cache.pop(concept)

    def trim_concept(self, concept):
        avg = 0
        is_ent = self.graph.nodes[concept]["is_ent"]
        n = 0
        linked_docs = list(self.graph.in_edges(concept))
        word_sim = 0
        for link in linked_docs:
            doc1 = link[0]
            if not is_ent:
                if not doc1 in self.sim_cache[concept]:
                    self.sim_cache[concept][doc1] = self.doc_cache[doc1].similarity(self.concept_cache[concept])
                word_sim += self.sim_cache[concept][doc1]
            for link2 in linked_docs:
                doc2 = link2[0]
                if doc1 != doc2:
                    n += 1
                    if not doc2 in self.sim_cache[doc1]:
                        curr_sim = self.compute_similarity(doc1, doc2)
                        self.sim_cache[doc1][doc2] = curr_sim
                        self.sim_cache[doc2][doc1] = curr_sim
                    avg += self.sim_cache[doc1][doc2]
        avg = (n == 0) or avg / n
        total_in_edges = len(linked_docs)
        word_sim /= (total_in_edges == 0) or total_in_edges
        ent_criteria = avg < 0.6 + self.avg_exp_o# or word_sim < 0.4 # prev avg: 0.85
        word_crit = avg < 0.6 + self.avg_exp_o or word_sim < 0.3 + self.avg_exp_o * 0.5 # prev: 0.8
        self.dbg += f"TRIMMING {total_in_edges} {avg} {word_sim} {concept}length{len(concept.split())}\n"
        if (word_crit and not is_ent) or (ent_criteria and is_ent):
            self.graph.remove_node(concept)
            self.concept_cache.pop(concept)
        else:
            self.graph.nodes[concept]["avg_tf_idf"] /= len(self.graph.in_edges(concept))
            score =  avg*(sigmoid(total_in_edges - 3) + word_sim)*sigmoid(self.graph.nodes[concept]["avg_tf_idf"])
            self.graph.nodes[concept]["score"] = score
    def trim_all(self):
        for concept in list(self.concept_cache.keys()):
            if concept in self.graph:
                self.trim_concept(concept)


    def process_document(self, doc, index_concepts=True):
        self.sim_cache[doc._.id] = {}
        self.nb_docs += 1
        self.graph.add_node(doc._.id, title=doc._.title, tf=0, path=doc._.path, type="doc")
        self.doc_cache[doc._.id] = doc
        if index_concepts:
            for chunk in doc.noun_chunks:
                self.get_sanitized_concepts(chunk, doc._.id)
            for ent in doc.ents:
                if not ent.label_ in ["ORDINAL", "DATE", "MONEY", "CARDINAL", "TIME", "PERCENT", "QUANTITY"] and len(ent.text) < 50:
                    if len(ent) > 2:
                        for i in range(len(ent) - 1):
                            self.create_link(doc._.id, ent[i:i+2], is_ent=True)
                    if len(ent) > 1:
                        for i in range(len(ent)):
                            self.dbg += f"RND{ent[i:i+1]}RND\n"
                            self.create_link(doc._.id, ent[i:i+1], is_ent=True)
                    self.dbg += f"ENT {ent.text} {ent.root} {ent.label_}\n"
                    self.create_link(doc._.id, ent, is_ent=True)

    def compute_similarity(self, doc1, doc2):
        return self.doc_cache[doc1].similarity(self.doc_cache[doc2])

    def remove_doc(self, id):
        self.nb_docs -= 1
        for doc, concept in self.graph.out_edges(id):
            self.graph.nodes[concept]["count"] -= 1
        self.graph.remove_node(id)

    
    def display_graph(self, max_conc=None):
        concepts = [(c, self.graph.nodes[c]["score"]) for c in self.concept_cache.keys()]
        concepts.sort(key=lambda x: x[1], reverse=True)
        dg = self.graph.copy()
        if max_conc and max_conc < len(concepts):
            for conc, score in concepts[max_conc-1:-1]:
                dg.remove_node(conc)
        return dg
