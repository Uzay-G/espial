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


    def create_link(self, item, concept, is_ent=False):
        if len(concept) == 1:
            concept = concept[0]
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

    def remove_irrelevant_edges(self):
        for item, concept, data in list(self.graph.edges(data=True)):
            if concept in self.graph:
                tf = data["count"] / self.graph.nodes[item]["tf"]
                idf = math.log(self.nb_docs / self.graph.nodes[concept]["count"])
                tf_idf = tf * idf
                is_ent = self.graph.nodes[concept]["is_ent"]
                count_crit = (tf_idf < 0.005 + self.tf_exp_o and not is_ent) or (tf_idf < 0.10 and is_ent)

                has_vector = self.concept_cache[concept].has_vector
                if not count_crit and has_vector: # prev: 0.25 (ent)
                    sim = self.doc_cache[item].similarity(self.concept_cache[concept])
                if count_crit or (has_vector and sim < 0.3):
                    self.graph.remove_edge(item, concept)
                else:
                    if has_vector:
                        self.sim_cache[concept][item] = sim
                    self.graph[item][concept]["tf_idf"] = tf_idf
                    self.graph.nodes[concept]["avg_tf_idf"] += tf_idf
        for concept in list(self.concept_cache.keys()):
            if len(list(self.graph.in_edges(concept))) < 2:
                self.graph.remove_node(concept)
                self.concept_cache.pop(concept)
            else:
                self.graph.nodes[concept]["avg_tf_idf"] /= len(list(self.graph.in_edges(concept)))

    def trim_concept(self, concept):
        avg = 0
        is_ent = self.graph.nodes[concept]["is_ent"]
        n = 0
        linked_docs = list(self.graph.in_edges(concept))
        word_sim = 0
        has_vector = self.concept_cache[concept].has_vector
        for link in linked_docs:
            doc1 = link[0]
            if has_vector:
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
        avg /= n
        total_in_edges = len(linked_docs)
        word_sim /= (total_in_edges == 0) or total_in_edges
        if not has_vector: word_sim = 1
        ent_criteria = avg < 0.6 + self.avg_exp_o or word_sim < 0.3 # prev avg: 0.85
        avg_tf_idf = self.graph.nodes[concept]["avg_tf_idf"]
        word_crit = avg < 0.6 + self.avg_exp_o or word_sim < 0.4 + self.avg_exp_o * 0.5 or avg_tf_idf < 0.1
        self.dbg += f"TRIMMING {total_in_edges} {avg} {word_sim} {concept}length{len(concept.split())}\n"
        if (word_crit and not is_ent) or (ent_criteria and is_ent):
            self.graph.remove_node(concept)
            self.concept_cache.pop(concept)
        else:
            self.graph.nodes[concept]["avg_tf_idf"] /= len(self.graph.in_edges(concept))
            score = avg + word_sim + avg_tf_idf
            self.graph.nodes[concept]["score"] = score

    def trim_all(self):
        #avg_links = 0
        #n = 0
        max_links = 0
        for concept in list(self.concept_cache.keys()):
            if concept in self.graph:
                self.trim_concept(concept)
                max_links = max(max_links, len(list(self.graph.in_edges(concept)))-2)
                #avg_links += len(self.graph.in_edges(concept))
                #n += 1
        for concept in list(self.concept_cache.keys()):
            if concept in self.graph:
                z = (len(self.graph.in_edges(concept))- 2)/max_links
                self.graph.nodes[concept]["score"] += z
    
    def process_entities(self, doc):
        saved_ents = []
        for ent in doc.ents:
            if not ent.label_ in ["ORDINAL", "DATE", "MONEY", "CARDINAL", "TIME", "PERCENT", "QUANTITY"] and len(ent.text) < 50:
                if len(ent) > 2:
                    for i in range(len(ent) - 1):
                        saved_ents.append(ent[i:i+2])
                if len(ent) > 1:
                    for i in range(len(ent)):
                        self.dbg += f"RND{ent[i:i+1]}RND\n"
                        saved_ents.append(ent[i:i+1])
                saved_ents.append(ent)
        return saved_ents

    def process_nouns(self, doc):
        return [noun_chunk.root for noun_chunk in doc.noun_chunks]
        #for chunk in noun_chunks:
        #relevant_tokens = [token.text for token in chunk if not token.is_stop and token.is_alpha]


    def process_document(self, doc, index_concepts=True):
        self.sim_cache[doc._.id] = {}
        self.nb_docs += 1
        self.graph.add_node(doc._.id, title=doc._.title, tf=0, path=doc._.path, type="doc")
        self.doc_cache[doc._.id] = doc
        if index_concepts:
            for ent in self.process_entities(doc):
                 #   self.dbg += f"ENT {ent.text} {ent.root} {ent.label_}\n"
                self.create_link(doc._.id, ent, is_ent=True)
            for concept in self.process_nouns(doc):
                self.create_link(doc._.id, [concept])

    def get_existing_doc_concepts(self, doc):
        concepts = [c.text for c in self.process_nouns(doc) + self.process_entities(doc) if c.text in self.concept_cache]
        return set(concepts)


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
