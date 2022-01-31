![logo](/espial/static/logo.svg)
[Live Demo](http://espial.uzpg.me)

Espial is **an engine for automated organization and discovery in knowledge bases**. It can be adapted to run with any knowledge base software, but currently works best with file-based knowledge bases.

Espial uses Natural Language Processing and AI to improve the way you find new links in your knowledge, enhancing the organization of your thoughts to help you discover new ones.

From the [explanatory blog post](https://uzpg.me/2022/01/29/redefining-PKM-with-nlp.html):

> Espial can cultivate a form of intended serendipity by suggesting a link between your thoughts instead of simply reminding you of a pathway you had already created. It aims to make discovery and the act of connection —fundamental to the way we think— more efficient.

> It can help you surface domains, ideas, and directions to brainstorm and explore, related to your current note-taking activity

See [Architecture](/ARCHITECTURE.md) for a more technical overview of Espial's algorithm.
 
![demo gif](/img/espial.gif)

### Espial's current features:

- **automated graph**: Espial generates a graph of auto-detected concepts and maps how they link to your different documents. This maps both the meaning of your documents into a visual space and allows you to see how those documents relate to each other with a high-level view.
- **document similarity**: you can query for a given document in your knowledge base and get most related and relevant notes that you could link / relate to it, and through which concepts. This similarity is on a semantic level (on meaning), not on the words used.
- **external search**: Espial has a semantic search engine and I’ve built a web extension that uses it to find items related to the page you’re currently on. You can run submit search queries and webpages to compare them to your knowledge base.
- **transformation of exploration into concrete structure**: when you view the tags and concepts that the program has surfaced, you can pick those you want to become part of your knowledge base’s structure. They can then become tags or even concept notes (a note that describes a concept and links to related notes).
- **extensive customizability**: Espial can be easily plugged into many different knowledge base software, although it was first built for [Archivy](https://archivy.github.io). Writing plugins and extensions for other tools is simple.

### Future Goals / In Progress Features:

Espial is a nascent project and will be getting many improvements, including:

- commands to compare and integrate two entire knowledge bases
- an option to download all the articles referenced in the knowledge base as documents
- enhance the algorithm so that it learns and detects existing hierarchies in your knowledge
- coordinate launch of Espial plugins for major knowledge base software
- improve load time for large KBs

If there are things you want added to Espial, [create an issue](https://github.com/Uzay-G/espial/issues)!

## Installation
- have pip and Python installed
- Run `pip install espial`
- Run `python -m spacy download en_core_web_md`

## Usage
```
Usage: espial run [OPTIONS] DATA_DIR

Options:
  --rerun         Regenerate existing concept graph
  --port INTEGER  Port to run server on.
  --host TEXT     Host to run server on.
  --help          Show this message and exit.
```
- run `espial run <the directory with your files>` and then open http://localhost:5002 to access the interface. **Warning: if you're running Espial on a low-ram device, lower `batch_size` in the config (see below).**

## Configuration

Espial's configuration language is Python. See [espial/config.py](/espial/config.py) to see what you can configure. Run `espial config <data-dir>` to set up your configuration.

If you like the software, consider [sponsoring me](https://github.com/Uzay-G/espial). I'm a student and the support is really useful. If you use it in your own projects, please credit the original library.

If you have ideas for the project and how to make it better, please open an issue or contact me.

