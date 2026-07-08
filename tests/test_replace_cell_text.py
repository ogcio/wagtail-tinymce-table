"""
Tests for the _replace_cell_text helper in core/table_block.py.

These tests exercise the two code paths:
  - Simple cell: tag.string is not None  → string.replace_with()
  - Compound cell: tag.string is None    → tag.clear() + tag.append()
"""

import pytest
from bs4 import BeautifulSoup, NavigableString

from wagtailtinymce.core.table_block import _replace_cell_text


def _cell(html_fragment):
    """Return the first <td> or <th> from a minimal table HTML snippet."""
    soup = BeautifulSoup(
        f"<table><tbody><tr>{html_fragment}</tr></tbody></table>", "html.parser"
    )
    return soup.find(["td", "th"])


# ---------------------------------------------------------------------------
# Simple cells (tag.string is not None)
# ---------------------------------------------------------------------------


class TestSimpleCell:
    def test_td_plain_text_replaced(self):
        cell = _cell("<td>Hello</td>")
        _replace_cell_text(cell, "Hola")
        assert cell.get_text() == "Hola"

    def test_th_plain_text_replaced(self):
        cell = _cell("<th>Name</th>")
        _replace_cell_text(cell, "Nombre")
        assert cell.get_text() == "Nombre"

    def test_replace_with_empty_string(self):
        cell = _cell("<td>Something</td>")
        _replace_cell_text(cell, "")
        assert cell.get_text() == ""

    def test_result_is_navigable_string(self):
        """After replacement the cell's first child must be a NavigableString."""
        cell = _cell("<td>Original</td>")
        _replace_cell_text(cell, "Translated")
        assert isinstance(cell.contents[0], NavigableString)

    def test_original_text_no_longer_present(self):
        cell = _cell("<td>Original</td>")
        _replace_cell_text(cell, "Translated")
        assert "Original" not in cell.get_text()


# ---------------------------------------------------------------------------
# Compound cells (tag.string is None – multiple / nested children)
# ---------------------------------------------------------------------------


class TestCompoundCell:
    """
    BeautifulSoup propagates ``tag.string`` through a *single-child chain*:
    ``<td><p>text</p></td>`` yields ``cell.string == "text"`` (not None),
    because there is exactly one child at each nesting level.
    The compound (clear + append) path is reached only when a tag has
    *multiple children* or when an inner tag has multiple children.
    """

    # --- single-child chain: string is NOT None, simple path is used ---

    def test_single_p_child_text_replaced(self):
        """<td><p>text</p></td> → string propagates through single-child chain."""
        cell = _cell("<td><p>Bold</p></td>")
        assert cell.string == "Bold", "precondition: single-child chain"
        _replace_cell_text(cell, "Negrita")
        assert cell.get_text() == "Negrita"
        # <p> structure is preserved; only the NavigableString inside it changed
        assert cell.find("p") is not None

    def test_single_link_child_text_replaced(self):
        """<td><a>text</a></td> → string propagates; <a> tag is preserved."""
        cell = _cell('<td><a href="#">Click</a></td>')
        assert cell.string == "Click", "precondition: single-child chain"
        _replace_cell_text(cell, "Haz clic")
        assert cell.get_text() == "Haz clic"
        # The <a> wrapper is intentionally kept (only the leaf NavigableString changed)
        assert cell.find("a") is not None

    # --- multiple children: string IS None, compound path is used ---

    def test_multiple_paragraphs_triggers_compound_path(self):
        """Two <p> children → cell.string is None → clear + append."""
        cell = _cell("<td><p>Line one</p><p>Line two</p></td>")
        assert cell.string is None, "precondition: multiple children"
        _replace_cell_text(cell, "Single line")
        assert cell.get_text() == "Single line"
        assert len(cell.find_all("p")) == 0

    def test_mixed_inline_children_triggers_compound_path(self):
        """<em>text</em> + plain text sibling → string is None."""
        cell = _cell("<td><em>Styled</em> extra</td>")
        assert cell.string is None, "precondition: multiple children"
        _replace_cell_text(cell, "Plain")
        assert cell.get_text() == "Plain"
        assert cell.find("em") is None

    def test_compound_path_result_is_navigable_string(self):
        """After clear + append the only child must be a NavigableString."""
        cell = _cell("<td><p>A</p><p>B</p></td>")
        assert cell.string is None, "precondition: multiple children"
        _replace_cell_text(cell, "Replaced")
        assert len(cell.contents) == 1
        assert isinstance(cell.contents[0], NavigableString)

    def test_strong_inside_paragraph_multiple_siblings(self):
        """<p> with two children → p.string is None → cell.string is None."""
        cell = _cell("<td><p><strong>Important</strong> note</p></td>")
        assert cell.string is None, "precondition: <p> has multiple children"
        _replace_cell_text(cell, "Importante")
        assert cell.get_text() == "Importante"

    def test_merged_cell_with_multiple_paragraphs(self):
        """colspan does not affect the compound-cell detection logic."""
        cell = _cell('<td colspan="2"><p>Row A</p><p>Row B</p></td>')
        assert cell.string is None
        _replace_cell_text(cell, "Fusionada")
        assert cell.get_text() == "Fusionada"
