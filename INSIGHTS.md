## Misc

- browser extension something similar to revery except show WHY it's similar too [done]
- pretty graph visualization [done]
- search interface [done]
- automated backlink recommender [~]
- fix zoom force graph (nodes cut off) [fixed]
- extension mechanisms (add ways to morph with knowledge base) [X with config.py]
- archivy plugin
- espial ingest different knowledge => surface best links
- auto integrate links (extract_urls) => problem, takes time (can we run this as a background task?)

## Algorithm Issues

- ingest multiple parameters
- PROBLEM: avg_tf_idf countering works but it's over-aggressive in some regards => docs without any links, how to fix
- imbalance between "wrong" entities getting easier criteria => Problem
- sense2vec utility (too large)
- fix biases towards generality [did this using improvement to algorithm: instead of analysing individual links to content, take avg tf_idf and ensure it's high enough => why? this allows you to keep discrete tagging with certain posts while maintaining quality concepts, ensure doesn't create tag overload]
