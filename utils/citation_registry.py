# utils/citation_registry.py
_corpus = set()
def register_citations(items):
    _corpus.update(items)
def current():
    return _corpus.copy()