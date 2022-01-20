from hashlib import sha256
from pathlib import Path
import re

class Config(object):

    def __init__(self):
        self.data_dir = ""
        self.ANALYSIS = {
            "openness": 0, # Positive values (eg -1) will lower the thresholds motif mesh uses when deciding whether to add links / ideas to the graph or not. This is better for exploration. Negative values will make it more strict (less concepts, higher quality).
            "max_concepts": 500, # Upper bound on number of concepts saved in graph. 
            "batch_size": 40, # Processes documents by batches. If running on large documents, you may want to reduce batch size so as not to overload memory.
            "rerun": 0,
            "cutoffs": # criteria used to remove a concept
            {
                "min_links": 2, # min number of doc-concept links
                "min_avg_children_sim": 0.6, # avg similarty of the child of a concept
                "min_avg_word_sim": 0.4, # min avg similartiy of concept vector, if it's a word, with its children
                "min_avg_ent_sim": 0.3, # same but for entities
                "min_avg_word_tf_idf": 0.075,
                "min_avg_ent_tf_idf": 0.01
            }
        }
        self.port = 5002
        self.host = "127.0.0.1"
        self.IGNORE = []

    def get_item_id(self, item):
        return sha256(item["content"].encode()).hexdigest()

    def get_title(self, path, contents):
        return path.parts[-1]

    def get_link(self, item):
        return f"[{item._.title}](http://{self.host}:{self.port}/view_item/{item._.id})"

    def create_tag(self, concept, mesh):
        for doc, concept, data in mesh.graph.in_edges(concept, data=True):
            path = Path(mesh.graph.nodes[doc]["path"])
            matching_occurs = data["orig"] # edge['orig'] stores the words in the original text that caused the link
            tag_re = re.compile(rf"(^|\n| )({'|'.join(matching_occurs)})($|\n| )", re.IGNORECASE)
            contents = tag_re.sub(rf"\1#{concept}\3" ,path.open("r").read())
            with path.open("w") as f:
                f.write(contents)


    def create_concept_note(self, concept, mesh):
        contents = f"# {concept}\n"
        for doc, concept, data in mesh.graph.in_edges(concept, data=True):
            doc = mesh.doc_cache[doc]
            contents += f"- {self.get_link(doc)}: Mentioned {data['count']} times.\n"
        conc_dir = Path(self.data_dir) / "concepts"
        conc_dir.mkdir(exist_ok=True)
        with open(conc_dir / f"{concept}.md", "w") as f:
            f.write(contents)
