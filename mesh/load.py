import time
import json
from hashlib import sha256
from spacy.tokens import DocBin, Doc
from mesh.datastruct import ConceptMesh
import networkx
import re
import spacy
import sys

hash_fn = lambda item: sha256(item["content"].encode()).hexdigest()
def load_mesh(data_dir, rerun, openness, get_id=hash_fn):
    nlp = spacy.load("en_core_web_md")
    Doc.set_extension("title", default=None)
    Doc.set_extension("id", default=None)
    Doc.set_extension("path", default=None)
    Doc.set_extension("hash", default=None)
    items = {}
    for path in data_dir.rglob("*.md"):
        item = {"content": path.open("r").read(), "title": path.parts[-1], "path": str(path)}
        item["hash"] = hash_fn(item)
        items[get_id(item)] = item
    saved_graph = (data_dir / "graph.json")
    doc_cache = {}
    a = time.time()
    docs = []
    dumped_annot = data_dir / "serialized_annot"
    if dumped_annot.exists():
        with dumped_annot.open("rb") as f:
            doc_bin = DocBin(store_user_data=True).from_bytes(f.read())
            deleted_docs = False
            for doc in doc_bin.get_docs(nlp.vocab):
                doc._.id = str(doc._.id)
                if doc._.id in items and doc._.hash == items[doc._.id]["hash"]:
                    docs.append(doc)
                else:
                    deleted_docs = True
            if deleted_docs:
                rerun = 1
                doc_bin = DocBin(store_user_data=True)
                for doc in docs:
                    doc_bin.add(doc)
            doc_cache = {doc._.id: doc for doc in docs}
    else:
        doc_bin = DocBin(store_user_data=True)

    mesh = ConceptMesh(openness, doc_cache)
    mesh.nb_docs = len(docs)

    unseen_docs = []
    for id, item in items.items():
        STOPWORDS = [
                'a', 'about', 'an', 'are', 'and', 'as', 'at', 'be', 'but', 'by', 'com',
                'do', 'don\'t', 'for', 'from', 'has', 'have', 'he', 'his', 'i', 'i\'m',
                'in', 'is', 'it', 'it\'s', 'just', 'like', 'me', 'my', 'not', 'of',
                'on', 'or', 'so', 't', 'that', 'the', 'they', 'this', 'to', 'was',
                'we', 'were', 'with', 'you', 'your',
        ]
        item["content"] = " ".join(filter(lambda x: not x in STOPWORDS, item["content"].split()))
        item["content"] = re.sub(r"\[([^\]]*)\]\(http[^)]+\)", r"\1", item["content"])
        if not id in doc_cache:
            unseen_docs.append((item["content"], {"id": id, "title": item["title"], "path": item["path"], "hash": item["hash"]}))
    if unseen_docs:
        rerun = 1

    if saved_graph.exists() and not rerun:
        loaded_graph = networkx.json_graph.node_link_graph(json.load(saved_graph.open("r")))
        if openness != loaded_graph.graph["openness"]: rerun = 1
        else: 
            for node in loaded_graph.nodes():
                if loaded_graph.nodes[node]["type"] == "concept":
                    mesh.concept_cache[node] = None # don't load the NLP
            mesh.graph = loaded_graph
            print("loading graphs")
    else: rerun = 1

    list(map(lambda x: mesh.process_document(x, index_concepts=rerun), docs))
    print(f"{len(unseen_docs)} new docs.")
    i = 0
    for doc, ctx in nlp.pipe(unseen_docs, as_tuples=True, disable=["textcat"], batch_size=40):
        i += 1
        if i % 40 == 0: print(f"{i} docs processed.")
        doc._.title = ctx["title"]
        doc._.id = ctx["id"]
        doc._.path = ctx["path"]
        doc._.hash = ctx["hash"]
        doc_bin.add(doc)
        if ctx["id"] in doc_cache and ctx["id"] in mesh.graph:
            mesh.remove_doc(ctx["id"])
        mesh.process_document(doc)

    print(time.time() - a, f"time spent to process docs, of {len(unseen_docs)} new ones.")
    if len(unseen_docs):
        with dumped_annot.open("wb") as f:
            f.write(doc_bin.to_bytes())
    print(rerun)
    return mesh, nlp, rerun
