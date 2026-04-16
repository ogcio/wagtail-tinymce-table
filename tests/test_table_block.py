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

    def test_tfoot_setup_contains_open_paren(self):
        """JS adapter evals the setup string only when it contains '('."""
        assert "(" in _TFOOT_SETUP

    def test_tfoot_setup_registers_tablefooterrow_button(self):
        assert "tablefooterrow" in _TFOOT_SETUP

    def test_tablefooterrow_in_toolbar(self):
        assert "tablefooterrow" in TinyMCETableBlock.custom_mce_config["toolbar"]

    def test_table_plugin_enabled(self):
        assert "table" in TinyMCETableBlock.custom_mce_config["plugins"]

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
