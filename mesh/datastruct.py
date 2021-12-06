import math
import networkx

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
        self.temp_cache = set()
        self.nb_docs = 0
        self.max_score = -1

        if mode:
            self.avg_exp_o = 0.025 * mode
            self.tf_exp_o = 0
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
        if not text in self.concept_cache:
            self.concept_cache[text] = concept
            self.graph.add_node(text, sim=0, score=0, count=1, is_ent=is_ent, type="concept")
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
            tf = data["count"] / self.graph.nodes[item]["tf"]
            idf = math.log(self.nb_docs / self.graph.nodes[concept]["count"])
            tf_idf = tf * idf
            if (tf_idf < 0.03 + self.tf_exp_o and not self.graph.nodes[concept]["is_ent"]) or (tf_idf < 0.025 and self.graph.nodes[concept]["is_ent"]):
                self.graph.remove_edge(item, concept)
            else:
                self.graph[item][concept]["tf_idf"] = tf_idf

    def trim_concept(self, concept):
        if concept in self.temp_cache:
            return
        avg = 0
        n = 0
        linked_docs = list(self.graph.in_edges(concept))
        word_sim = 0
        for link in linked_docs:
            doc1 = link[0]
            word_sim += self.doc_cache[doc1].similarity(self.concept_cache[concept])
            for link2 in linked_docs:
                doc2 = link2[0]
                if doc1 != doc2:
                    n += 1
                    avg += self.compute_similarity(doc1, doc2)
        avg = (n == 0) or avg / n
        word_sim /= (len(linked_docs) == 0) or len(linked_docs)
        n = len(linked_docs)
        total_in_edges = len(linked_docs)
        self.temp_cache.add(concept)
        ent_criteria = avg < 0.85 + self.avg_exp_o or word_sim < 0.4
        word_crit = avg < 0.8 + self.avg_exp_o or word_sim < 0.5 + self.avg_exp_o * 0.5
        is_ent = self.graph.nodes[concept]["is_ent"]
        if total_in_edges < 2 or (word_crit and not is_ent) or (ent_criteria and is_ent): # or child_mutual_sim < 0.8 or avg_child_sim < 0.8
            self.graph.remove_node(concept)
            self.concept_cache.pop(concept)
        else:
            score = avg + sigmoid(min(total_in_edges - 3, 5)) + word_sim * 0.5
            self.max_score = max(self.max_score, score)
            self.graph.nodes[concept]["score"] = avg*(sigmoid(total_in_edges - 3) + word_sim)

    def trim_all(self):
        for concept in list(self.concept_cache.keys()):
            if concept in self.graph:
                self.trim_concept(concept)


    def process_document(self, doc, index_concepts=True):
        self.nb_docs += 1
        self.graph.add_node(doc._.id, title=doc._.title, tf=0, path=doc._.path, type="doc")
        self.doc_cache[doc._.id] = doc
        if index_concepts:
            for chunk in doc.noun_chunks:
                self.get_sanitized_concepts(chunk, doc._.id)
            for ent in doc.ents:
                if not ent.label_ in ["ORDINAL", "DATE", "MONEY", "CARDINAL", "TIME", "PERCENT"] and len(ent.text) < 50:
                    self.create_link(doc._.id, ent, is_ent=True)

    def compute_similarity(self, doc1, doc2):
        return self.doc_cache[doc1].similarity(self.doc_cache[doc2])

    def remove_doc(self, id):
        self.nb_docs -= 1
        for doc, concept in self.graph.out_edges(id):
            self.graph.nodes[concept]["count"] -= 1
        self.graph.remove_node(id)
