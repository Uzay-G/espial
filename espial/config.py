from hashlib import sha256
from pathlib import Path
import re

class Config(object):

    def __init__(self):
        self.data_dir = ""
        self.ANALYSIS = {
            "openness": 0,
            "max_concepts": 500,
            "batch_size": 40,
            "rerun": 0
        }
        self.port = 5002
        self.host = "127.0.0.1"

    def get_id(self, item):
        return sha256(item["content"].encode()).hexdigest()

    def get_title(self, path, contents):
        return path.parts[-1]

    def get_link(self, item):
        return f"{config.host}:{config.port}/view_item/{item['id']}"

    def create_tag(self, concept, mesh):
        for doc, concept, data in mesh.graph.in_edges(concept, data=True):
            path = Path(mesh.graph.nodes[doc]["path"])
            matching_occurs = data["orig"] # edge['orig'] stores the words in the original text that caused the link
            print(matching_occurs)
            tag_re = re.compile(rf"(^|\n| )({'|'.join(matching_occurs)})($|\n| )", re.IGNORECASE)
            print(rf"(^|\n| )({'|'.join(matching_occurs)})($|\n| )")
            contents = tag_re.sub(rf"\1#{concept}\3" ,path.open("r").read())
            with path.open("w") as f:
                f.write(contents)

