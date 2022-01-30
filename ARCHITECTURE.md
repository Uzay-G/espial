This document is a technical outline of Espial's structure and the underlying algorithm that allows it to discover connections and concepts in your knowledge base. Reading through details on the algorithm can help you fine tune the settings for better discovery.

# Overview

Espial is a command line interface that processes your local data and serves it through a web interface. It uses the python programming language and a number of libraries.

Espial uses insights from Natural Language Processing—the study of algorithms to process, generate and understand text. Espial relies on the [Spacy](https://spacy.io) library for some of these NLP algorithms.

Espial's main data structure is a Python class called [`ConceptMesh`](/espial/datastruct.py): it's the underlying graph of connections between concepts and documents that all of the interface's widgets use.

## Loading

Espial has to compute quite a few things on your knowledge, so it tries to cache as much as it can using Spacy's cache format and JSON dumps. The library computes a hash of each document which it then compares to the old hashes. If it notices any differences, it reruns its analysis algorithm to find new concepts and links.

Each document is analyzed with Spacy in batches, the higher the `ANALYSIS["batch_size"]` you set the higher the memory consumption. It's only analyzed once thanks to caching, even on subsequent runs.

## Initial Concept Detection


As you add each document, Espial extracts its noun chunks and "Named Entities" ie cities, people, organizations, etc... 

Each of these is added as a "concept" in your graph. An edge is created between each concept and the doc it was discovered in.

We apply slightly different criteria for these two types of concepts: nouns and Named Entities.

Examples from [Spacy visualization](https://spacy.io/usage/visualizers#dep):

![dependency parse](https://d33wubrfki0l68.cloudfront.net/b57d19e46f7e43783140807e1fdb48d130419d3a/8401e/displacy-3504502e1d5463ede765f0a789717424.svg)

![entities](/img/entities.png)

This gives us tens/hundreds of thousands of concepts, and a similar order of magnitude for links between concepts and documents.

## Removal of low-value concepts and links

That amount of information is way too high to be useful and there's lots of meaningless information linkage in it. What makes Espial special is its filtering algorithm that aims at cutting off everything but the concepts and ideas that **show you interesting patterns in your knowledge**.

This process has two steps.

### 1. Edge Analysis: Frequency and Count Filtering

Espial begins with an analysis of the relevance of specific links between documents and concepts. It uses [term-frequency — inverse document frequency](https://en.wikipedia.org/wiki/Tf%E2%80%93idf) to remove edges that don't signal much about these connections.

```
tf_idf = number of times concept appeared in a document * log(total_documents / number of documents concept is mentioned in)
```

Basically: tf-idf tells us if this specific concept is actually relevant to the document in terms of its frequency **and how much it's used in other documents**. This heuristic is maximized if the concept occurs a lot in the given document and doesn't occur too much in other documents — we want to avoid generality with concepts like `thing`.

The cutoff for this step is set in `ANALYSIS["cutoffs"]["min_edge_ent_tf_idf"]` / `ANALYSIS["cutoffs"]["min_edge_noun_tf_idf"]`

During this round, we also save the average tf_idf score of a concept to its linked documents.

### Concept Analysis

With those links removed, we then compute a series of heuristics to decide which concepts (not links!) stay in the graph.

Before we get into the algorithm, it's important to understand the idea of a [word embedding](https://en.wikipedia.org/wiki/Word_embedding).

A word embedding is a vector of real numbers that represents a word's meaning, often obtained by studying the distribution and position of words in a dataset. 

Representing semantic meaning as a vector allows you to use many basic mathematical properties of vectors for example to calculate the similarity of words.

You can also average word vectors to create document vectors, a measure of the semantic meaning of a document.

Espial uses the following measures to decide which concepts get kicked and which don't:

Let X be the concept we're studying, and D its associated documents after Step 1.

- **Average Grouped Similarity**: Espial calculates the one-to-one similarity of each document in D and then averages it. If it's too low it means documents grouped by X aren't that related. We can infer that X is thus not super interesting as a concept, if D's elements don't have some commonality. Although this isn't always true, it's a useful approximation. `cutoffs['min_avg_children_sim']`
- **Average Word Similarity**: For each document in D, we calculate the similarity of the document to the word embedding of our concept X. We average this and if it's too low we can determine that X isn't really relevant to the documents it's linked to. `cutoffs['min_avg_ent_sim'/'min_avg_noun_sim']`
- **Average TF-IDF**: It works better to lower the TF-IDF threshold in step 1, and then increase the cutoff for the **average TF-IDF** score of the concept. This is intuitive: we want X to have meaning in our knowledge base **overall**, but sometimes a quick mention of X in a document that isn't directly focused on X can be useful. If our concept is `databases`, we don't strictly want it to link to posts strictly focused on databases, we're also interested in matches that mention databases on the side. To prevent noise, we allow this type of loose link and enforce instead that the **concept itself is on average not used too liberally — it is statistically important for enough notes.** (`cutoffs[min_avg_ent_tf_idf/min_avg_noun_tf_idf]`)
- Minimum Linkage: We also check that X is linked to at least a certain threshold of documents in D. (`cutoffs['min_links']`)

## Display

Espial then renders its insights using Flask and the D3.JS library for the graph visualization.
