from html2text import html2text
import requests
import re

def most_relevant_tags(mesh, n_tags=30, entities=False):
    concept_avgs = [{"name": concept, "relevance": mesh.graph.nodes[concept]["score"]} for concept in mesh.concept_cache.keys()]
    if entities:
        concept_avgs = list(filter(lambda x: mesh.graph.nodes[x["name"]]["is_ent"], concept_avgs))
    concept_avgs.sort(key=lambda x: x["relevance"], reverse=True)
    for i in range(min(len(concept_avgs), n_tags)):
        in_docs = list(map(lambda x: mesh.doc_cache[x[0]]._.title, mesh.graph.in_edges(concept_avgs[i]["name"])))
        concept_avgs[i]["in_docs"] = in_docs
    return concept_avgs[:n_tags]

def find_most_sim(mesh, doc_id, top_n=10):
    doc = mesh.doc_cache[doc_id]
    results = []
    in_edges = list(map(lambda x: x[1], mesh.graph.out_edges(doc_id)))
    for doc2 in mesh.doc_cache.values():
        if doc2._.id != doc_id:
            in_edges2 = list(map(lambda x: x[1], mesh.graph.out_edges(doc2._.id)))
            inter = [conc for conc in in_edges if conc in in_edges2]
            results.append({"id": doc2._.id, "sim": doc.similarity(doc2), "related": inter, "title": doc2._.title})
    results.sort(key=lambda x: x["sim"], reverse=True)
    return results[:min(len(results) - 1, top_n)]

def search_q(mesh, q, top_n=10):
    results = []
    potent_concepts = mesh.get_existing_doc_concepts(q)
    for doc2 in mesh.doc_cache.values():
        doc_concepts = list(map(lambda x: x[1], mesh.graph.out_edges(doc2._.id)))
        inter = [conc for conc in doc_concepts if conc in potent_concepts]
        results.append({"id": doc2._.id, "sim": q.similarity(doc2), "related": inter, "title": doc2._.title})
    max_inter = 1
    sim_norm = [0, 0]
    for result in results:
        max_inter = max(max_inter, len(result["related"]))
        sim_norm[0] = max(sim_norm[0], result["sim"])
        sim_norm[1] = min(sim_norm[1], result["sim"])
    for result in results:
        result["sim"] = (result["sim"] - sim_norm[1])/(sim_norm[0] - sim_norm[1])*20 + (len(result["related"]) / max_inter)
    results.sort(key=lambda x: x["sim"], reverse=True)
    return results[:min(len(results) - 1, top_n)]

def process_markdown(content):

    STOPWORDS = [
            'a', 'about', 'an', 'are', 'and', 'as', 'at', 'be', 'but', 'by', 'com',
            'do', 'don\'t', 'for', 'from', 'has', 'have', 'he', 'his', 'i', 'i\'m',
            'in', 'is', 'it', 'it\'s', 'just', 'like', 'me', 'my', 'not', 'of',
            'on', 'or', 'so', 't', 'that', 'the', 'they', 'this', 'to', 'was',
            'we', 'were', 'with', 'you', 'your',
    ]
    content = " ".join(filter(lambda x: not x in STOPWORDS, content.split()))
    content = re.sub(r"\[([^\]]*)\]\(http[^)]+\)", r"\1", content)
    return content

def load_url(url):
    """
    Process url to get content for analysis.

    Returns (status, result) tuple; false if failed, true if succeeded.
    """
    try:
        url_request = requests.get(
            self.url,
            headers={"User-agent": f"Archivy/v{require('archivy')[0].version}"},
        )
    except Exception:
        return (False, "Could not load webpage.")
    content = html2text(url_request.text, bodywidth=0)
    return (True, process_markdown(content))
