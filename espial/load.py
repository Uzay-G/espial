import time
import json
from spacy.tokens import DocBin, Doc
from espial.datastruct import ConceptMesh
from espial.analysis import process_markdown
import networkx
import spacy
from pathlib import Path
from hashlib import sha256

hash_fn = lambda item: sha256(item["content"].encode()).hexdigest()


def load_mesh(config):
    data_dir = Path(config.data_dir)
    openness = config.ANALYSIS["openness"]
    rerun = config.ANALYSIS["rerun"]
    nlp = spacy.load("en_core_web_md")
    Doc.set_extension("title", default=None)
    Doc.set_extension("id", default=None)
    Doc.set_extension("path", default=None)
    Doc.set_extension("hash", default=None)
    items = {}
    for path in data_dir.rglob("*.md"):
        if any([path.parent == data_dir / p for p in config.IGNORE]):
            continue
        content = path.open("r").read()
        item = {
            "content": content,
            "title": config.get_title(path, content),
            "path": str(path),
        }
        item["hash"] = hash_fn(item)
        items[config.get_item_id(item)] = item
    saved_graph = data_dir / ".graph.json"
    doc_cache = {}
    a = time.time()
    docs = []
    dumped_annot = data_dir / ".doc_annotations"
    if dumped_annot.exists():
        with dumped_annot.open("rb") as f:
            doc_bin = DocBin(store_user_data=True).from_bytes(f.read())
            deleted_docs = False
            for doc in doc_bin.get_docs(nlp.vocab):
                doc._.id = str(doc._.id)
                excluded_path = any(
                    [Path(doc._.path).parent == data_dir / p for p in config.IGNORE]
                )
                if (
                    doc._.id in items
                    and doc._.hash == items[doc._.id]["hash"]
                    and not excluded_path
                    and Path(doc._.path).exists()
                ):
                    docs.append(doc)
                else:
                    deleted_docs = True
            if deleted_docs:  # we need to rerun the analysis
                rerun = 1
                doc_bin = DocBin(store_user_data=True)
                for doc in docs:
                    doc_bin.add(doc)
            doc_cache = {doc._.id: doc for doc in docs}
    else:
        doc_bin = DocBin(store_user_data=True)

    mesh = ConceptMesh(config.ANALYSIS, doc_cache)
    mesh.nb_docs = len(docs)

    unseen_docs = []
    for id, item in items.items():
        item["content"] = process_markdown(item["content"])
        if not id in doc_cache and len(item["content"]) < 1000000:
            unseen_docs.append(
                (
                    item["content"],
                    {
                        "id": id,
                        "title": item["title"],
                        "path": item["path"],
                        "hash": item["hash"],
                    },
                )
            )
    if unseen_docs:
        rerun = 1

    if saved_graph.exists() and not rerun:
        loaded_graph = networkx.json_graph.node_link_graph(
            json.load(saved_graph.open("r"))
        )
        if openness != loaded_graph.graph["openness"]:
            rerun = 1
        else:
            for node in loaded_graph.nodes():
                if loaded_graph.nodes[node]["type"] == "concept":
                    mesh.concept_cache[
                        node
                    ] = None  # we want to access concepts in concept_cache but don't need the vector emb
            mesh.graph = loaded_graph
    else:
        rerun = 1

    list(map(lambda x: mesh.process_document(x, index_concepts=rerun), docs))
    print(f"{len(unseen_docs)} new docs.")
    i = 0
    for doc, ctx in nlp.pipe(
        unseen_docs,
        as_tuples=True,
        disable=["textcat"],
        batch_size=config.ANALYSIS["batch_size"],
    ):
        i += 1
        if i % config.ANALYSIS["batch_size"] == 0:
            print(f"{i} docs processed.")
        doc._.title = ctx["title"]
        doc._.id = ctx["id"]
        doc._.path = ctx["path"]
        doc._.hash = ctx["hash"]
        doc_bin.add(doc)
        if (
            ctx["id"] in doc_cache and ctx["id"] in mesh.graph
        ):  # update old documents that have changed
            mesh.remove_doc(ctx["id"])
        mesh.process_document(doc)

    print(
        time.time() - a, f"time spent to process docs, of {len(unseen_docs)} new ones."
    )
    if len(unseen_docs):
        with dumped_annot.open("wb") as f:
            f.write(doc_bin.to_bytes())
    return mesh, nlp, rerun
