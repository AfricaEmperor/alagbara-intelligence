from scout_fabric.acquire import _VisibleText

def test_html_parser_extracts_title_and_visible_text():
    parser = _VisibleText()
    parser.feed("<html><head><title>Example page</title><script>secret()</script></head><body><p>Hello <b>world</b></p></body></html>")
    assert " ".join(parser.title_parts) == "Example page"
    assert " ".join(parser.text_parts).strip() == "Example page Hello world"
    assert "secret" not in " ".join(parser.text_parts)
