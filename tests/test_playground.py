"""Local playground contracts."""
from geowebcollector.playground import catalog
def test_extractor_registered():
    ops = catalog()
    assert "extract_html" in ops
    assert ops["extract_html"]["example"]["selectors"] == {"title": "h1"}
