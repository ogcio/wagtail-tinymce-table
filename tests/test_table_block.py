"""
Tests for TinyMCETableBlock:
  - Class-level configuration (allowed_tags, mce_config, toolbar)
  - sort_segment()
  - get_translatable_segments()
  - restore_translated_segments()
"""

import pytest
from bs4 import BeautifulSoup

from wagtailtinymce.core.table_block import TinyMCETableBlock, _TFOOT_SETUP


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class _FakeString:
    def __init__(self, data):
        self.data = data


class MockSegment:
    """Stand-in for wagtail_localize.segments.StringSegmentValue."""

    def __init__(self, path, text, order=0):
        self.path = path
        self.string = _FakeString(text)
        self.order = order


@pytest.fixture
def block(monkeypatch):
    """A TinyMCETableBlock with StringSegmentValue replaced by MockSegment
    so tests do not depend on the real wagtail-localize internals."""
    monkeypatch.setattr(
        "wagtailtinymce.core.table_block.StringSegmentValue",
        MockSegment,
    )
    return TinyMCETableBlock()


# Alias so existing test methods that used ``localize_block`` continue to work
# without any other changes.
localize_block = block


# ---------------------------------------------------------------------------
# Configuration tests  (no Django I/O required)
# ---------------------------------------------------------------------------


class TestConfiguration:
    def test_tfoot_in_allowed_tags(self):
        assert "tfoot" in TinyMCETableBlock.allowed_tags

    def test_thead_in_allowed_tags(self):
        assert "thead" in TinyMCETableBlock.allowed_tags

    def test_tbody_in_allowed_tags(self):
        assert "tbody" in TinyMCETableBlock.allowed_tags

    def test_th_in_allowed_tags(self):
        assert "th" in TinyMCETableBlock.allowed_tags

    def test_td_in_allowed_tags(self):
        assert "td" in TinyMCETableBlock.allowed_tags

    def test_setup_key_in_mce_config(self):
        assert "setup" in TinyMCETableBlock.custom_mce_config

    def test_setup_value_is_tfoot_setup(self):
        assert TinyMCETableBlock.custom_mce_config["setup"] is _TFOOT_SETUP

    def test_tfoot_setup_is_callback_registry_key(self):
        """_TFOOT_SETUP is a named callback-registry key, not an executable
        string.  The JS adapter looks up window.wagtailTinyMCECallbacks[key]
        rather than eval()-ing the string, so the value must not contain '('."""
        assert "(" not in _TFOOT_SETUP

    def test_tfoot_setup_registers_tablefooterrow_button(self):
        assert "tablefooterrow" in _TFOOT_SETUP

    def test_tablefooterrow_in_toolbar(self):
        assert "tablefooterrow" in TinyMCETableBlock.custom_mce_config["toolbar"]

    def test_table_plugin_enabled(self):
        assert "table" in TinyMCETableBlock.custom_mce_config["plugins"]

    def test_table_header_type_is_section_cells(self):
        """tablerowheader must produce <thead> + <th>, not just <thead> + <td>.
        The default TinyMCE value 'section' keeps <td> elements — 'sectionCells'
        is required to get proper <th> markup in header rows."""
        assert TinyMCETableBlock.custom_mce_config.get("table_header_type") == "sectionCells"

    def test_colspan_allowed_on_td(self):
        assert "colspan" in TinyMCETableBlock.allowed_attributes["td"]

    def test_rowspan_allowed_on_td(self):
        assert "rowspan" in TinyMCETableBlock.allowed_attributes["td"]

    def test_scope_allowed_on_th(self):
        assert "scope" in TinyMCETableBlock.allowed_attributes["th"]


# ---------------------------------------------------------------------------
# sort_segment()
# ---------------------------------------------------------------------------


class TestSortSegment:
    def test_already_sorted(self, block):
        segs = [MockSegment("", "a", 0), MockSegment("", "b", 1), MockSegment("", "c", 2)]
        result = block.sort_segment(segs)
        assert [s.string.data for s in result] == ["a", "b", "c"]

    def test_reverse_order(self, block):
        segs = [MockSegment("", "c", 2), MockSegment("", "b", 1), MockSegment("", "a", 0)]
        result = block.sort_segment(segs)
        assert [s.string.data for s in result] == ["a", "b", "c"]

    def test_non_contiguous_indices(self, block):
        segs = [MockSegment("", "z", 10), MockSegment("", "a", 0), MockSegment("", "m", 5)]
        result = block.sort_segment(segs)
        assert [s.string.data for s in result] == ["a", "m", "z"]

    def test_single_segment(self, block):
        segs = [MockSegment("", "only", 0)]
        result = block.sort_segment(segs)
        assert result[0].string.data == "only"

    def test_empty_list(self, block):
        assert block.sort_segment([]) == []


# ---------------------------------------------------------------------------
# get_translatable_segments()
# ---------------------------------------------------------------------------


class TestGetTranslatableSegments:
    def test_basic_cells_extracted(self, localize_block):
        html = "<table><tbody><tr><td>A</td><td>B</td></tr></tbody></table>"
        segs = localize_block.get_translatable_segments(html)
        texts = [s.string.data for s in segs]
        assert "A" in texts
        assert "B" in texts

    def test_empty_cells_not_extracted(self, localize_block):
        html = "<table><tbody><tr><td></td><td>Text</td></tr></tbody></table>"
        segs = localize_block.get_translatable_segments(html)
        texts = [s.string.data for s in segs]
        assert "" not in texts
        assert "Text" in texts
        assert len(segs) == 1

    def test_empty_cell_does_not_shift_index(self, localize_block):
        """
        The first empty cell must NOT be added as a segment (Bug A).
        If it were, the order of subsequent segments would be off by one.
        """
        html = (
            "<table><tbody>"
            "<tr><td></td><td>First</td><td>Second</td></tr>"
            "</tbody></table>"
        )
        segs = localize_block.get_translatable_segments(html)
        # Empty cell at col=0 must be skipped; First → order=1, Second → order=2
        assert len(segs) == 2
        orders = {s.string.data: s.order for s in segs}
        assert orders["First"] == 1
        assert orders["Second"] == 2

    def test_duplicate_cells_extracted_once(self, localize_block):
        html = (
            "<table><tbody>"
            "<tr><td>Same</td><td>Same</td><td>Different</td></tr>"
            "</tbody></table>"
        )
        segs = localize_block.get_translatable_segments(html)
        texts = [s.string.data for s in segs]
        assert texts.count("Same") == 1
        assert "Different" in texts

    def test_th_cells_extracted(self, localize_block):
        html = (
            "<table>"
            "<thead><tr><th>Header A</th><th>Header B</th></tr></thead>"
            "<tbody><tr><td>Data</td><td>More</td></tr></tbody>"
            "</table>"
        )
        segs = localize_block.get_translatable_segments(html)
        texts = [s.string.data for s in segs]
        assert "Header A" in texts
        assert "Header B" in texts

    def test_tfoot_cells_extracted(self, localize_block):
        html = (
            "<table>"
            "<tbody><tr><td>Body</td></tr></tbody>"
            "<tfoot><tr><td>Footer total</td></tr></tfoot>"
            "</table>"
        )
        segs = localize_block.get_translatable_segments(html)
        texts = [s.string.data for s in segs]
        assert "Footer total" in texts

    def test_cell_containing_nested_table_skipped(self, localize_block):
        """
        The OUTER <td> that directly contains a nested table is skipped
        (``elem.find("table")`` guard).  However, ``table.find_all("tr")`` is
        recursive, so the inner table's rows are also visited; the cells
        *inside* the nested table are still extracted.
        """
        html = (
            "<table><tbody><tr>"
            "<td><table><tr><td>Nested</td></tr></table></td>"
            "<td>Outer</td>"
            "</tr></tbody></table>"
        )
        segs = localize_block.get_translatable_segments(html)
        texts = [s.string.data for s in segs]
        # Inner cells of the nested table ARE extracted via recursive tr search
        assert "Nested" in texts
        # The plain outer cell is also extracted
        assert "Outer" in texts

    def test_multiple_tables_all_extracted(self, localize_block):
        html = (
            "<table><tbody><tr><td>Table1Cell</td></tr></tbody></table>"
            "<table><tbody><tr><td>Table2Cell</td></tr></tbody></table>"
        )
        segs = localize_block.get_translatable_segments(html)
        texts = [s.string.data for s in segs]
        assert "Table1Cell" in texts
        assert "Table2Cell" in texts

    def test_merged_cell_extracted_once(self, localize_block):
        html = (
            "<table><tbody>"
            '<tr><td colspan="2">Merged</td></tr>'
            "</tbody></table>"
        )
        segs = localize_block.get_translatable_segments(html)
        texts = [s.string.data for s in segs]
        assert texts.count("Merged") == 1

    def test_order_values_are_positional(self, localize_block):
        """Order reflects column position in the raw iteration, including empty cols."""
        html = (
            "<table><tbody>"
            "<tr><td>Alpha</td><td></td><td>Gamma</td></tr>"
            "</tbody></table>"
        )
        segs = localize_block.get_translatable_segments(html)
        by_text = {s.string.data: s.order for s in segs}
        # Alpha is col 0, empty skipped at col 1, Gamma is col 2
        assert by_text["Alpha"] == 0
        assert by_text["Gamma"] == 2

    def test_whitespace_only_cell_skipped(self, localize_block):
        html = "<table><tbody><tr><td>   </td><td>Real</td></tr></tbody></table>"
        segs = localize_block.get_translatable_segments(html)
        texts = [s.string.data for s in segs]
        assert len(segs) == 1
        assert "Real" in texts

    def test_caption_extracted(self, localize_block):
        html = (
            "<table>"
            "<caption>Annual Report</caption>"
            "<tbody><tr><td>Data</td></tr></tbody>"
            "</table>"
        )
        segs = localize_block.get_translatable_segments(html)
        texts = [s.string.data for s in segs]
        assert "Annual Report" in texts

    def test_caption_order_before_cells(self, localize_block):
        """Caption must receive a lower order value than the first cell."""
        html = (
            "<table>"
            "<caption>My Caption</caption>"
            "<tbody><tr><td>Cell</td></tr></tbody>"
            "</table>"
        )
        segs = localize_block.get_translatable_segments(html)
        by_text = {s.string.data: s.order for s in segs}
        assert by_text["My Caption"] < by_text["Cell"]

    def test_empty_caption_not_extracted(self, localize_block):
        html = (
            "<table>"
            "<caption></caption>"
            "<tbody><tr><td>Data</td></tr></tbody>"
            "</table>"
        )
        segs = localize_block.get_translatable_segments(html)
        texts = [s.string.data for s in segs]
        assert "" not in texts
        assert len(segs) == 1


# ---------------------------------------------------------------------------
# restore_translated_segments()
# ---------------------------------------------------------------------------


class TestRestoreTranslatedSegments:
    def _segs(self, *pairs):
        """Build a list of MockSegments from (text, order) pairs."""
        return [MockSegment("", text, order) for text, order in pairs]

    def test_basic_restoration(self, localize_block):
        html = "<table><tbody><tr><td>Hello</td><td>World</td></tr></tbody></table>"
        segs = self._segs(("Hola", 0), ("Mundo", 1))
        result = localize_block.restore_translated_segments(html, segs)
        soup = BeautifulSoup(result, "html.parser")
        cells = [td.get_text() for td in soup.find_all("td")]
        assert "Hola" in cells
        assert "Mundo" in cells

    def test_empty_cells_unchanged_and_counter_not_advanced(self, localize_block):
        """
        Empty cells must be skipped and must NOT advance the segment counter.
        This is the core Bug A regression test for restore.
        """
        html = (
            "<table><tbody>"
            "<tr><td></td><td>First</td><td>Second</td></tr>"
            "</tbody></table>"
        )
        # Segments at order=1 and order=2 (empty cell at col 0 was skipped)
        segs = self._segs(("Primero", 1), ("Segundo", 2))
        result = localize_block.restore_translated_segments(html, segs)
        soup = BeautifulSoup(result, "html.parser")
        cells = [td.get_text() for td in soup.find_all("td")]
        assert cells[0] == ""         # empty cell untouched
        assert cells[1] == "Primero"
        assert cells[2] == "Segundo"

    def test_th_cells_translated(self, localize_block):
        html = (
            "<table>"
            "<thead><tr><th>Name</th><th>Age</th></tr></thead>"
            "<tbody><tr><td>Alice</td><td>30</td></tr></tbody>"
            "</table>"
        )
        segs = self._segs(("Nombre", 0), ("Edad", 1), ("Alicia", 2), ("30", 3))
        result = localize_block.restore_translated_segments(html, segs)
        soup = BeautifulSoup(result, "html.parser")
        assert soup.find("th", string="Nombre") is not None
        assert soup.find("th", string="Edad") is not None

    def test_tfoot_cells_translated(self, localize_block):
        html = (
            "<table>"
            "<tbody><tr><td>Body</td></tr></tbody>"
            "<tfoot><tr><td>Total</td></tr></tfoot>"
            "</table>"
        )
        segs = self._segs(("Cuerpo", 0), ("Total_es", 1))
        result = localize_block.restore_translated_segments(html, segs)
        soup = BeautifulSoup(result, "html.parser")
        tfoot_cells = [td.get_text() for td in soup.find("tfoot").find_all("td")]
        assert "Total_es" in tfoot_cells

    def test_compound_cell_does_not_crash(self, localize_block):
        """
        Merged/compound cells with child elements must not raise AttributeError
        (Bug B regression).
        """
        html = (
            "<table><tbody>"
            '<tr><td colspan="2"><p><strong>Bold merged</strong></p></td></tr>'
            "</tbody></table>"
        )
        segs = self._segs(("Fusionada negrita", 0))
        result = localize_block.restore_translated_segments(html, segs)
        soup = BeautifulSoup(result, "html.parser")
        cell_text = soup.find("td").get_text()
        assert "Fusionada negrita" in cell_text

    def test_duplicate_cells_get_same_translation(self, localize_block):
        html = (
            "<table><tbody>"
            "<tr><td>Same</td><td>Same</td><td>Other</td></tr>"
            "</tbody></table>"
        )
        segs = self._segs(("Igual", 0), ("Otro", 2))
        result = localize_block.restore_translated_segments(html, segs)
        soup = BeautifulSoup(result, "html.parser")
        cells = [td.get_text() for td in soup.find_all("td")]
        # Both duplicate cells should be replaced with the same translation
        assert cells[0] == "Igual"
        assert cells[1] == "Igual"
        assert cells[2] == "Otro"

    def test_outer_td_containing_nested_table_not_directly_replaced(self, localize_block):
        """
        The outer <td> that wraps a nested table is skipped during translation
        (``elem.find("table")`` guard), but the cells INSIDE the nested table
        ARE translated because find_all("tr") is recursive.
        Segments: Nested→col 0, Outer→col 1.
        """
        html = (
            "<table><tbody><tr>"
            "<td><table><tr><td>Nested</td></tr></table></td>"
            "<td>Outer</td>"
            "</tr></tbody></table>"
        )
        segs = self._segs(("Anidado", 0), ("Exterior", 1))
        result = localize_block.restore_translated_segments(html, segs)
        soup = BeautifulSoup(result, "html.parser")
        # Inner nested cell is translated
        inner_tds = [td for td in soup.find_all("td") if not td.find("table")]
        texts = [td.get_text() for td in inner_tds]
        assert "Anidado" in texts
        assert "Exterior" in texts

    def test_caption_translated(self, localize_block):
        html = (
            "<table>"
            "<caption>Annual Report</caption>"
            "<tbody><tr><td>Revenue</td></tr></tbody>"
            "</table>"
        )
        segs = self._segs(("Informe Anual", 0), ("Ingresos", 1))
        result = localize_block.restore_translated_segments(html, segs)
        soup = BeautifulSoup(result, "html.parser")
        assert soup.find("caption").get_text() == "Informe Anual"
        assert soup.find("td").get_text() == "Ingresos"

    def test_caption_translated_before_cells(self, localize_block):
        """Caption segment is consumed first; cells use subsequent indices."""
        html = (
            "<table>"
            "<caption>Title</caption>"
            "<tbody><tr><td>A</td><td>B</td></tr></tbody>"
            "</table>"
        )
        segs = self._segs(("Título", 0), ("Alfa", 1), ("Beta", 2))
        result = localize_block.restore_translated_segments(html, segs)
        soup = BeautifulSoup(result, "html.parser")
        assert soup.find("caption").get_text() == "Título"
        cells = [td.get_text() for td in soup.find_all("td")]
        assert cells == ["Alfa", "Beta"]

    def test_missing_segment_logs_error_not_stdout(self, localize_block, caplog, capsys):
        """When segment count is short, the error must be logged via the Python
        logging system — not printed to stdout — so it reaches Django's log
        handlers and never leaks raw exception details to application output."""
        import logging
        html = "<table><tbody><tr><td>A</td><td>B</td></tr></tbody></table>"
        # Only one segment for two cells — index 1 will be out of range
        segs = self._segs(("Alfa", 0))
        with caplog.at_level(logging.ERROR, logger="wagtailtinymce.core.table_block"):
            localize_block.restore_translated_segments(html, segs)
        # Error must appear in the log
        assert any("Failed to restore translation segment" in r.message for r in caplog.records)
        # Nothing must be printed to stdout
        captured = capsys.readouterr()
        assert captured.out == ""

    def test_round_trip_extract_then_restore(self, localize_block):
        """Segments extracted from a table can be restored to produce the
        translated version without any index errors."""
        original = (
            "<table><tbody>"
            "<tr><td>Apple</td><td>Banana</td></tr>"
            "<tr><td></td><td>Cherry</td></tr>"
            "</tbody></table>"
        )
        extracted = localize_block.get_translatable_segments(original)
        # Build fake translated segments keeping the same order values
        translated = [
            MockSegment("", seg.string.data.upper(), seg.order)
            for seg in extracted
        ]
        result = localize_block.restore_translated_segments(original, translated)
        soup = BeautifulSoup(result, "html.parser")
        texts = [td.get_text() for td in soup.find_all("td")]
        assert "APPLE" in texts
        assert "BANANA" in texts
        assert "CHERRY" in texts
        # Empty cell must remain empty
        assert "" in texts


# ---------------------------------------------------------------------------
# <br> tag preservation through the translation round-trip
# ---------------------------------------------------------------------------


class TestBrTagPreservation:
    """Tests that verify <br> tags inside cells survive extraction →
    translation → restoration without becoming literal text or being lost."""

    def test_br_cell_extracted_with_newline_separator(self, localize_block):
        """A cell with <br> must produce a segment whose text uses \\n as
        the line-break marker (not a space, and not literal '<br/>')."""
        html = "<table><tbody><tr><td>line1<br/>line2</td></tr></tbody></table>"
        segs = localize_block.get_translatable_segments(html)
        assert len(segs) == 1
        assert segs[0].string.data == "line1\nline2"

    def test_multi_br_cell_extracted_correctly(self, localize_block):
        """Multiple <br> elements inside one cell produce the right number
        of \\n markers in the extracted segment."""
        html = "<table><tbody><tr><td>a<br/>b<br/>c</td></tr></tbody></table>"
        segs = localize_block.get_translatable_segments(html)
        assert len(segs) == 1
        assert segs[0].string.data == "a\nb\nc"

    def test_br_cell_segment_contains_no_literal_br_tag(self, localize_block):
        """The extracted segment text must never contain the literal string
        '<br' — that would be the broken pre-fix behaviour."""
        html = "<table><tbody><tr><td>text1<br/>text2</td></tr></tbody></table>"
        segs = localize_block.get_translatable_segments(html)
        assert "<br" not in segs[0].string.data

    def test_restore_newline_produces_br_in_output(self, localize_block):
        """Restoring a segment whose text contains \\n must write a real
        <br> element into the cell, not plain text."""
        html = "<table><tbody><tr><td>line1<br/>line2</td></tr></tbody></table>"
        segs = [MockSegment("", "linea1\nlinea2", 0)]
        result = localize_block.restore_translated_segments(html, segs)
        soup = BeautifulSoup(result, "html.parser")
        td = soup.find("td")
        assert td.find("br") is not None

    def test_restore_br_text_correct_after_translation(self, localize_block):
        """Text on each side of the reconstructed <br> must match the
        translated text."""
        html = "<table><tbody><tr><td>before<br/>after</td></tr></tbody></table>"
        segs = [MockSegment("", "avant\naprès", 0)]
        result = localize_block.restore_translated_segments(html, segs)
        soup = BeautifulSoup(result, "html.parser")
        td = soup.find("td")
        assert td.get_text(separator="\n") == "avant\naprès"

    def test_restored_br_is_not_literal_text(self, localize_block):
        """After restore the <br> must not appear as the escaped string
        '&lt;br' or the literal characters '<br' inside a text node."""
        html = "<table><tbody><tr><td>a<br/>b</td></tr></tbody></table>"
        segs = [MockSegment("", "x\ny", 0)]
        result = localize_block.restore_translated_segments(html, segs)
        assert "&lt;br" not in result
        # The literal <br> or <br/> tag should be present in the HTML output
        assert "<br" in result

    def test_full_round_trip_preserves_br(self, localize_block):
        """End-to-end: extract a cell with <br>, produce translated segments
        that keep \\n, restore → the published HTML has a real <br>."""
        original = (
            "<table><tbody>"
            "<tr>"
            "<td>- First bullet<br/>- Second bullet<br/>- Third bullet</td>"
            "<td>Header</td>"
            "</tr>"
            "</tbody></table>"
        )
        extracted = localize_block.get_translatable_segments(original)
        by_text = {s.string.data: s for s in extracted}

        assert "- First bullet\n- Second bullet\n- Third bullet" in by_text
        assert "Header" in by_text

        translated = [
            MockSegment(
                "",
                "- Premier point\n- Deuxième point\n- Troisième point",
                by_text["- First bullet\n- Second bullet\n- Third bullet"].order,
            ),
            MockSegment("", "En-tête", by_text["Header"].order),
        ]
        result = localize_block.restore_translated_segments(original, translated)
        soup = BeautifulSoup(result, "html.parser")
        tds = soup.find_all("td")

        # Multi-line cell: two <br> elements, correct text
        assert len(tds[0].find_all("br")) == 2
        assert tds[0].get_text(separator="\n") == (
            "- Premier point\n- Deuxième point\n- Troisième point"
        )
        # Plain cell: unchanged structure
        assert tds[1].get_text() == "En-tête"

    def test_br_cell_alongside_plain_cell_indices_correct(self, localize_block):
        """A <br> cell must not disrupt the segment ordering of adjacent plain cells."""
        html = (
            "<table><tbody>"
            "<tr><td>plain</td><td>multi<br/>line</td><td>last</td></tr>"
            "</tbody></table>"
        )
        segs = localize_block.get_translatable_segments(html)
        by_text = {s.string.data: s.order for s in segs}
        assert by_text["plain"] == 0
        assert by_text["multi\nline"] == 1
        assert by_text["last"] == 2

    def test_duplicate_br_cells_get_same_translation(self, localize_block):
        """Duplicate multi-line cells must be de-duplicated and both receive
        the same translated text, matching the behaviour for plain cells."""
        html = (
            "<table><tbody>"
            "<tr><td>a<br/>b</td><td>a<br/>b</td><td>other</td></tr>"
            "</tbody></table>"
        )
        segs = localize_block.get_translatable_segments(html)
        # Only one segment for the duplicate
        assert len([s for s in segs if s.string.data == "a\nb"]) == 1

        translated = [
            MockSegment("", "x\ny", segs[0].order),
            MockSegment("", "otro", segs[1].order),
        ]
        result = localize_block.restore_translated_segments(html, translated)
        soup = BeautifulSoup(result, "html.parser")
        tds = soup.find_all("td")
        assert tds[0].get_text(separator="\n") == "x\ny"
        assert tds[1].get_text(separator="\n") == "x\ny"
        assert tds[2].get_text() == "otro"

    def test_plain_cell_unchanged_when_neighbour_has_br(self, localize_block):
        """Plain cells in the same row as a <br> cell must restore correctly."""
        html = (
            "<table><tbody>"
            "<tr><td>plain</td><td>multi<br/>line</td></tr>"
            "</tbody></table>"
        )
        segs = [MockSegment("", "llano", 0), MockSegment("", "multi\nlínea", 1)]
        result = localize_block.restore_translated_segments(html, segs)
        soup = BeautifulSoup(result, "html.parser")
        tds = soup.find_all("td")
        assert tds[0].get_text() == "llano"
        assert tds[1].find("br") is not None
        assert tds[1].get_text(separator="\n") == "multi\nlínea"


# ---------------------------------------------------------------------------
# Corrupted content: cells with literal '<br/>' NavigableString text
# ---------------------------------------------------------------------------


class TestLiteralBrTextNormalization:
    """Cells that went through the old (pre-0.2.7) restore cycle may have
    literal '<br/>' stored as NavigableString content instead of real <br>
    Tag elements.  Both extraction and restoration must normalise these."""

    def _make_corrupted_cell_html(self, content: str) -> str:
        """Build table HTML whose cell content is a plain NavigableString
        that includes literal '<br/>' characters — simulating the output of
        the old _replace_cell_text compound path."""
        from bs4 import BeautifulSoup as BS, NavigableString as NS
        soup = BS(
            "<table><tbody><tr><td></td></tr></tbody></table>", "html.parser"
        )
        td = soup.find("td")
        td.append(NS(content))
        return str(soup)

    def test_corrupted_cell_extracted_without_literal_br(self, localize_block):
        """A cell with literal '<br/>' NavigableString content must produce a
        segment whose text uses '\\n' — not the literal string '<br/>'."""
        html = self._make_corrupted_cell_html("line1 <br/> line2")
        segs = localize_block.get_translatable_segments(html)
        assert len(segs) == 1
        assert "<br" not in segs[0].string.data
        assert "\n" in segs[0].string.data

    def test_corrupted_cell_triple_br_extracted_correctly(self, localize_block):
        """The '<br/><br/><br/>' pattern from multiple corruption cycles must
        all be converted to '\\n' in the extracted segment text."""
        html = self._make_corrupted_cell_html(
            "- bullet1<br/><br/><br/>- bullet2"
        )
        segs = localize_block.get_translatable_segments(html)
        assert "<br" not in segs[0].string.data

    def test_literal_br_in_translated_text_restores_as_real_br(self, localize_block):
        """If the stored translation string itself contains literal '<br/>'
        (typed by a translator or output by a translation tool), restore must
        convert it to a real <br> element — not leave it as literal text."""
        html = "<table><tbody><tr><td>line1<br/>line2</td></tr></tbody></table>"
        # Translator typed literal '<br/>' rather than preserving '\\n'
        segs = [MockSegment("", "línea1<br/>línea2", 0)]
        result = localize_block.restore_translated_segments(html, segs)
        assert "&lt;br" not in result
        soup = BeautifulSoup(result, "html.parser")
        td = soup.find("td")
        assert td.find("br") is not None
        assert td.get_text(separator="\n") == "línea1\nlínea2"

    def test_full_round_trip_corrupted_source(self, localize_block):
        """End-to-end with a corrupted source cell: extract normalises literal
        '<br/>' to '\\n', translator preserves '\\n', restore writes real <br>."""
        html = self._make_corrupted_cell_html(
            "- First bullet <br/> - Second bullet <br/> - Third bullet"
        )
        extracted = localize_block.get_translatable_segments(html)
        assert len(extracted) == 1
        seg_text = extracted[0].string.data
        assert "<br" not in seg_text
        # Check newlines are present as the separator
        assert seg_text.count("\n") == 2

        # Build translated segments preserving the \\n structure
        lines = seg_text.split("\n")
        translated_lines = [f"[{l.strip()}]" for l in lines]
        translated_text = "\n".join(translated_lines)
        translated = [MockSegment("", translated_text, extracted[0].order)]

        result = localize_block.restore_translated_segments(html, translated)
        soup = BeautifulSoup(result, "html.parser")
        td = soup.find("td")
        assert len(td.find_all("br")) == 2
        assert "&lt;br" not in result
