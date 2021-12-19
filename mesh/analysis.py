def most_relevant_tags(mesh, n_tags=30):
    concept_avgs = [{"name": concept, "relevance": mesh.graph.nodes[concept]["score"]} for concept in mesh.concept_cache.keys()]
    concept_avgs.sort(key=lambda x: x["relevance"], reverse=True)
    for i in range(n_tags):
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
            results.append({"doc": doc2._.title, "sim": doc.similarity(doc2), "related": inter})
    results.sort(key=lambda x: x["sim"], reverse=True)
    return results[:min(len(results) - 1, top_n)]

def search_q(mesh, q, top_n=10):
    results = []
    potent_concepts = [chunk.root.text.lower() for chunk in q.noun_chunks]
    for doc2 in mesh.doc_cache.values():
        doc_concepts = list(map(lambda x: x[1], mesh.graph.out_edges(doc2._.id)))
        inter = [conc for conc in doc_concepts if conc in doc_concepts]
        results.append({"doc": doc2._.title, "sim": q.similarity(doc2), "related": inter})
    results.sort(key=lambda x: x["sim"], reverse=True)
    return results[:min(len(results) - 1, top_n)]
