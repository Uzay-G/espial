from html2text import html2text
from readability import Document
import requests
import re


def most_relevant_tags(mesh, n_tags=30, entities=False):
    """This method needs work - current heuristics remain flawed."""
    concept_avgs = [
        {"name": concept, "relevance": mesh.graph.nodes[concept]["score"]}
        for concept in mesh.concept_cache.keys()
    ]
    if entities:  # only return entities
        concept_avgs = list(
            filter(lambda x: mesh.graph.nodes[x["name"]]["is_ent"], concept_avgs)
        )
    concept_avgs.sort(key=lambda x: x["relevance"], reverse=True)
    for i in range(min(len(concept_avgs), n_tags)):
        in_docs = list(
            map(
                lambda x: mesh.doc_cache[x[0]]._.title,
                mesh.graph.in_edges(concept_avgs[i]["name"]),
            )
        )
        concept_avgs[i]["in_docs"] = in_docs
    return concept_avgs[: min(n_tags, len(concept_avgs) - 1)]


def find_most_sim(mesh, doc_id, top_n=10):
    """Find documents most similar to the given document."""
    doc = mesh.doc_cache[doc_id]
    results = []
    doc_conc = list(map(lambda x: x[1], mesh.graph.out_edges(doc_id)))
    for other_doc in mesh.doc_cache.values():
        if other_doc._.id != doc_id:
            other_doc_conc = list(map(lambda x: x[1], mesh.graph.out_edges(other_doc._.id)))
            inter = [conc for conc in doc_conc if conc in other_doc_conc]
            results.append(
                {
                    "id": other_doc._.id,
                    "sim": doc.similarity(other_doc),
                    "related": inter,
                    "title": other_doc._.title,
                }
            )
    results.sort(key=lambda x: x["sim"], reverse=True)
    return results[: min(len(results) - 1, top_n)]


def search_q(mesh, q, top_n=10):
    """Search for given query inside the graph."""
    results = []
    potent_concepts = mesh.get_existing_doc_concepts(q)
    for doc2 in mesh.doc_cache.values():
        doc_concepts = list(map(lambda x: x[1], mesh.graph.out_edges(doc2._.id)))
        inter = [conc for conc in doc_concepts if conc in potent_concepts]
        sim = doc2.similarity(q)
        if sim:
            results.append(
                {
                    "id": doc2._.id,
                    "sim": q.similarity(doc2),
                    "related": inter,
                    "title": doc2._.title,
                }
            )
    max_inter = 1

    if results:
        # integrate number of related concepts as a factor of the score - hyperparams need tuning here
        sim_norm = [0, 0]
        for result in results:
            max_inter = max(max_inter, len(result["related"]))
            sim_norm[0] = max(sim_norm[0], result["sim"])
            sim_norm[1] = min(sim_norm[1], result["sim"])
        for result in results:
            result["sim"] = (result["sim"] - sim_norm[1]) / (
                sim_norm[0] - sim_norm[1]
            ) * 18 + (
                len(result["related"]) / max_inter
            )  # normalize similarity and add interconnections
        results.sort(key=lambda x: x["sim"], reverse=True)
        return results[: min(len(results) - 1, top_n)]
    return []


def process_markdown(content):
    STOPWORDS = [
        "a",
        "about",
        "an",
        "are",
        "and",
        "as",
        "at",
        "be",
        "but",
        "by",
        "com",
        "do",
        "don't",
        "for",
        "from",
        "has",
        "have",
        "he",
        "his",
        "i",
        "i'm",
        "in",
        "is",
        "it",
        "it's",
        "just",
        "like",
        "me",
        "my",
        "not",
        "of",
        "on",
        "or",
        "so",
        "t",
        "that",
        "the",
        "they",
        "this",
        "to",
        "was",
        "we",
        "were",
        "with",
        "you",
        "your",
    ]
    content = " ".join(filter(lambda x: not x in STOPWORDS, content.split()))
    content = re.sub(r"\[([^\]]*)\]\(http[^)]+\)", r"\1", content)  # remove links
    return content


def load_url(url, nlp):
    """
    Process url to get content for analysis. [WIP feature (see readme)]
    """
    try:
        url_request = requests.get(
            url,
            headers={"User-agent": f"Espial/v0.1"},
        )
    except Exception:
        return False
    html_doc = Document(url_request.text)
    content = html2text(html_doc.summary(), bodywidth=0)
    doc = nlp(content)
    doc._.id = url
    doc._.title = html_doc.short_title() or url
    return doc


def extract_urls(content):
    URL_REGEX = re.compile(
        "((?:https?):(?:(?://)|(?:\\\\))+(?:[\w\d:#@%/;$~_?\+-=\\\.&](?:#!)?)*)",
        re.DOTALL,
    )
    urls = re.findall(URL_REGEX, content)
    return urls
