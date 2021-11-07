## Installation
- clone repo
- `pip install requirements.txt`
- `python -m spacy download en_core_web_md`

## Usage
- `python motif_mesh/nlp_light.py run --help`
- `python motif_mesh/nlp_light.py <data-dir>`
- open http://localhost:5002/force.html for network graph (click on nodes for more info)
- open https://localhost:5002/best_tags for highest weighted tags (considered most interesting, however there is a bias towards generality here that limits the worth
