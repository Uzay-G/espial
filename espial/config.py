from hashlib import sha256

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
