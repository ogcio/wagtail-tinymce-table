import logging
import re

from wagtail_localize.segments import StringSegmentValue

from bs4 import BeautifulSoup, NavigableString

from wagtailtinymce.blocks import TinyMCEBlock

logger = logging.getLogger(__name__)

__all__ = [
    "TinyMCETableBlock",
]

# Registry key used by tinymce-adapter.js to look up the "Footer Row" toolbar
# button setup function.  The actual JS implementation lives in
# tinymce-adapter.js under window.wagtailTinyMCECallbacks['tablefooterrow'],
# keeping executable code out of serialised config strings.
_TFOOT_SETUP = "tablefooterrow"

# Matches literal <br>, <br/>, <br />, <BR/> etc. appearing as plain text
# inside a NavigableString rather than as a real HTML Tag element.  This
# happens when a previous faulty restore wrote the translated text (which
# contained literal "<br/>" characters typed by the translator) directly into
# the cell as a NavigableString.
_LITERAL_BR_RE = re.compile(r"<br\s*/?>", re.IGNORECASE)


def _normalize_br_text(text: str) -> str:
    """Replace any literal ``<br>`` / ``<br/>`` strings with ``\\n``.

    Cells whose content was corrupted by a previous round-trip (where a
    translator typed ``<br/>`` as literal characters rather than a real HTML
    element) contain ``<br/>`` inside their NavigableString text.
    ``get_text()`` faithfully returns those characters, so the extracted
    segment contains them too.  Normalising to ``\\n`` here makes the
    round-trip consistent regardless of whether the cell stores real ``<br>``
    Tags or legacy literal-text ``<br/>`` strings.
    """
    return _LITERAL_BR_RE.sub("\n", text)


def _replace_cell_text(cell_tag, translated_text):
    """Replace the visible text of a BeautifulSoup cell tag with *translated_text*.

    Three cases are distinguished after normalising literal ``<br>`` strings
    in ``translated_text`` to ``\\n``:

    - **Simple cell, no line breaks** — ``tag.string`` is not None (single-child
      chain) AND the normalised text contains no ``\\n``.  We call
      ``replace_with`` on the leaf NavigableString only, preserving any wrapper
      elements such as ``<p>`` or ``<a>`` in the chain.
    - **Multi-line cell** — either the cell has multiple children
      (``tag.string`` is None) OR the translated text contains ``\\n`` after
      normalisation.  This includes "simple" cells whose NavigableString content
      was corrupted by a previous restore cycle that wrote literal ``<br/>``
      characters as plain text; those cells have ``tag.string is not None`` but
      the extracted segment carries ``\\n`` markers after normalisation.  We
      clear the tag and reconstruct one real ``<br>`` element per split point.
    - **Single-line compound cell** — compound cell (``tag.string`` is None)
      whose translated text has no line breaks; we clear and insert plain text.
    """
    # Normalise literal <br> text in the translation before any path decision.
    # This handles both translators who typed '<br/>' and translation tools
    # that serialise newlines as '<br/>' in their output.
    normalized = _normalize_br_text(translated_text)

    if cell_tag.string is not None and "\n" not in normalized:
        # Happy path: leaf NavigableString, no line breaks — preserve wrappers.
        cell_tag.string.replace_with(translated_text)
    else:
        # Compound cell, or simple cell with \n (corrupted NavigableString
        # whose literal '<br/>' text was normalised to '\n' during extraction).
        cell_tag.clear()
        lines = normalized.split("\n")
        if len(lines) > 1:
            for i, line in enumerate(lines):
                cell_tag.append(NavigableString(line))
                if i < len(lines) - 1:
                    cell_tag.append(BeautifulSoup("<br/>", "html.parser").br)
        else:
            cell_tag.append(NavigableString(translated_text))


class TinyMCETableBlock(TinyMCEBlock):
    custom_mce_config = {
        "plugins": "table link",
        "menubar": "",
        # tablefooterrow is a custom button registered via the setup callback below.
        "toolbar": (
            "bold italic link unlink"
            " | table tablecaption tablecolheader tablerowheader tablefooterrow"
            " | tablecellprops tablemergecells tablesplitcells"
            " | tableinsertrowbefore tableinsertrowafter tabledeleterow"
            " | tableinsertcolbefore tableinsertcolafter tabledeletecol"
        ),
        "table_appearance_options": False,
        "table_default_attributes": {},
        "table_default_styles": {},
        "table_sizing_mode": "relative",
        "table_advtab": False,
        "table_cell_advtab": False,
        "table_row_advtab": False,
        # "sectionCells" moves the row into <thead> AND converts <td> → <th>.
        # The default "section" only moves the row but keeps <td> elements,
        # which is why header rows appeared without <th> markup.
        "table_header_type": "sectionCells",
        "language": "en",
        "license_key": "gpl",
        "promotion": False,
        "setup": _TFOOT_SETUP,
    }

    class Meta:
        label = "Table"
        icon = "table"

    allowed_tags = [
        "table",
        "thead",
        "tbody",
        "tfoot",
        "br",
        "colgroup",
        "col",
        "caption",
        "tr",
        "th",
        "td",
        "p",
        "strong",
        "b",
        "em",
        "i",
        "a",
    ]

    allowed_attributes = {
        "table": ["class", "id", "style"],
        "col": ["span", "class"],
        "th": [
            "align",
            "valign",
            "class",
            "scope",
            "abbr",
            "colspan",
            "rowspan",
            "headers",
        ],
        "td": ["align", "valign", "class", "colspan", "rowspan", "headers"],
        "a": ["class", "href", "target", "title"],
    }

    allowed_styles = ["width", "border-collapse"]

    def get_translatable_segments(self, data, **kwargs):
        duplicate_elements = []
        segments = []
        soup = BeautifulSoup(data, features="lxml")
        tables = soup.find_all("table")
        col = 0
        for table in tables:
            # <caption> is a direct child of <table>, not inside any <tr>, so it
            # must be handled explicitly before the row loop.
            caption = table.find("caption")
            if caption is not None:
                text = _normalize_br_text(caption.get_text(separator="\n")).strip()
                if text and text not in duplicate_elements:
                    segments.append(StringSegmentValue("", text, order=col))
                    duplicate_elements.append(text)
                col += 1

            rows = table.find_all("tr")
            for row in rows:
                # Include both <td> (body/footer cells) and <th> (header cells).
                cells = row.find_all(["td", "th"])
                for elem in cells:
                    text = _normalize_br_text(elem.get_text(separator="\n")).strip()
                    # Skip empty cells and cells that contain nested tables.
                    # The truthiness guard (bool(text)) ensures the first empty
                    # cell is not mistakenly added as a segment, which would
                    # shift every subsequent segment index by one during restore.
                    if text and text not in duplicate_elements and not elem.find("table"):
                        segments.append(StringSegmentValue("", text, order=col))
                        duplicate_elements.append(text)
                    col += 1

        return segments

    def sort_segment(self, segments) -> list:
        seg_dict = {}
        first_list = []
        for s in segments:
            seg_dict[s.order] = s
            first_list.append(s.order)
        first_list.sort()
        return [seg_dict[elem] for elem in first_list]

    def restore_translated_segments(self, block_value, segments):
        duplicate_elements = {}
        soup = BeautifulSoup(block_value, "html.parser")
        tables = soup.find_all("table")
        cell = 0
        sorted_segment = self.sort_segment(segments)

        if tables:
            for table in tables:
                # Restore caption before processing rows, mirroring extraction order.
                caption = table.find("caption")
                if caption is not None:
                    text = _normalize_br_text(caption.get_text(separator="\n")).strip()
                    if text:
                        try:
                            translated = sorted_segment[cell].string.data
                            if text not in duplicate_elements and text not in duplicate_elements.values():
                                duplicate_elements[text] = translated
                                _replace_cell_text(caption, translated)
                                cell += 1
                            elif text not in duplicate_elements.values():
                                _replace_cell_text(caption, duplicate_elements[text])
                        except Exception:
                            logger.exception(
                                "Failed to restore translation segment at index %d "
                                "(caption '%s'). Segment count may not match table structure.",
                                cell,
                                text,
                            )

                rows = table.find_all("tr")
                for row in rows:
                    # Mirror the same cell selector used in get_translatable_segments.
                    cells = row.find_all(["td", "th"])
                    for ele in cells:
                        text = _normalize_br_text(ele.get_text(separator="\n")).strip()
                        if not text or ele.find("table"):
                            continue
                        try:
                            translated = sorted_segment[cell].string.data
                            if text not in duplicate_elements and text not in duplicate_elements.values():
                                duplicate_elements[text] = translated
                                _replace_cell_text(ele, translated)
                                cell += 1
                            elif text not in duplicate_elements.values():
                                _replace_cell_text(ele, duplicate_elements[text])
                        except Exception:
                            logger.exception(
                                "Failed to restore translation segment at index %d "
                                "(cell '%s'). Segment count may not match table structure.",
                                cell,
                                text,
                            )

            return str(soup)
