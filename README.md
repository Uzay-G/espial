## Installation
- clone repo
- `pip install requirements.txt`
- `python -m spacy download en_core_web_md`
- `pip install .`

## Usage
- `mesh run --help`
- `mesh run <data-dir>`
- open http://localhost:5002/force.html for network graph (click on nodes for more info)
- open https://localhost:5002/best_tags for highest weighted tags (considered most interesting, however there is a bias towards generality here that limits the worth

## More Useful Routes
- `/view_tag/<tag>` -> shows you the links' score and its associated documents. Example: `/view_tag/nature` 
- `/view_doc/id` -> the id is the sha256 of the document content. Click on the nodes in the graph view to have this open. Shows you associated tags.
- `/best_tags` -> ranking of tags based on certain heuristics (this page is not solid because time has not been spent on refining its criteria).
- `/most_sim/id` -> find most similar docs to a given doc. Not quite fast enough yet, although works faster on concurrent requests (i need to look into better vectors to make these more accurate).
