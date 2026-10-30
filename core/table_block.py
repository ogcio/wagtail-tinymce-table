import difflib
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

# Block-level tags that warrant a line break in extracted PO text.  Inline
# siblings (e.g. plain text next to <a>) must not — see _cell_translatable_text.
_BLOCK_TAGS = frozenset({"p", "div", "li", "h1", "h2", "h3", "h4", "h5", "h6"})
# One ``find`` for the common inline-only cell (text + ``<a>`` with no ``<br>``/blocks).
_CELL_STRUCTURE_TAGS = ("br", "table", *_BLOCK_TAGS)


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


def _cell_translatable_text(cell) -> str:
    """Cell plain text for extract/restore, with ``\\n`` only for ``<br>`` and blocks.

    Plain ``get_text()`` is enough when the cell has no ``<br>``, block wrapper,
    or nested table. Only ``get_text(separator='\\n')`` wrongly breaks between
    inline siblings (text and ``<a>``).
    """
    if cell.find(_CELL_STRUCTURE_TAGS) is None:
        return _normalize_br_text(cell.get_text()).strip()

    chunks: list[str] = []
    pending = list(cell.children)
    while pending:
        child = pending.pop(0)
        if isinstance(child, NavigableString):
            chunks.append(str(child))
        elif child.name == "br":
            chunks.append("\n")
        elif child.name == "table":
            continue
        elif child.name in _BLOCK_TAGS:
            if chunks and not chunks[-1].endswith("\n"):
                chunks.append("\n")
            pending[0:0] = list(child.children)
            if chunks and not chunks[-1].endswith("\n"):
                chunks.append("\n")
        else:
            pending[0:0] = list(child.children)
    return _normalize_br_text("".join(chunks)).strip()


def _translated_link_span(words: list[str], cursor: int, old: str) -> tuple[int, int]:
    """Word range in *words* for one existing link, searched in order.

    The PO string is one sentence, so the link boundaries are not marked.
    Reuse the English label when it is still there. Otherwise score a few
    nearby words ("HSE" → "FSS", "An Bord Pleanála" → "Bord Pleanála").
    """
    old_words = old.split()
    if not old_words:
        return cursor, cursor

    word_count = len(words)
    old_len = len(old_words)
    limit = min(word_count, cursor + old_len + 3)
    for idx in range(cursor, max(cursor, limit - old_len + 1)):
        if words[idx: idx + old_len] == old_words:
            return idx, idx + old_len

    old_lower = old.lower()
    lo, hi = (1, 1) if old_len == 1 else (max(1, old_len - 1), old_len + 1)
    best_rank = None
    best = (cursor, min(cursor + 1, word_count))
    for idx in range(cursor, limit):
        for span in range(lo, hi + 1):
            end = idx + span
            if end > word_count:
                break
            phrase = " ".join(words[idx:end]).lower()
            score = difflib.SequenceMatcher(None, old_lower, phrase).ratio()
            rank = (score, -abs(span - old_len))
            if best_rank is None or rank > best_rank:
                best_rank = rank
                best = (idx, end)
                if score >= 1.0:
                    return best
    return best


def _replace_text_keeping_anchors(cell_tag, translated_text) -> bool:
    """Keep every ``<a href>``. Do not rebuild the cell as ``<br>`` text.

    Cells with no link return False and still use ``_replace_cell_text_plain``.
    """
    anchors = [anchor for anchor in cell_tag.find_all("a") if anchor.has_attr("href")]
    if not anchors:
        return False

    normalized = _normalize_br_text(translated_text)
    # A link is not a line break. Only a real <br> keeps newlines.
    if cell_tag.find("br") is None:
        normalized = " ".join(normalized.split())

    # The cell's only words are the link. Put the translation in the <a>
    # and leave wrappers such as <p> in place.
    if len(anchors) == 1 and anchors[0].get_text().split() == cell_tag.get_text().split():
        anchors[0].clear()
        anchors[0].append(NavigableString(normalized))
        return True

    # Same span lookup for every link, then the words between spans stay as text.
    words = normalized.split()
    spans = []
    cursor = 0
    for anchor in anchors:
        start, end = _translated_link_span(words, cursor, anchor.get_text().strip())
        spans.append((start, end))
        cursor = end

    runs = [" ".join(words[: spans[0][0]])]
    for index, (start, end) in enumerate(spans):
        anchors[index].clear()
        anchors[index].append(NavigableString(" ".join(words[start:end])))
        nxt = spans[index + 1][0] if index + 1 < len(spans) else len(words)
        runs.append(" ".join(words[end:nxt]))

    nodes = [
        node
        for node in cell_tag.descendants
        if isinstance(node, NavigableString) and node.find_parent("a") is None
    ]
    if len(nodes) == len(runs):
        for node, text in zip(nodes, runs):
            orig = str(node)
            if text and orig[:1].isspace() and not text[:1].isspace():
                text = " " + text
            if text and orig[-1:].isspace() and not text[-1:].isspace():
                text += " "
            node.replace_with(NavigableString(text))
    return True


def _replace_cell_text_plain(cell_tag, translated_text):
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


def _replace_cell_text(cell_tag, translated_text):
    """Apply *translated_text*.

    Link cells keep their ``<a href>``. Every other cell uses the original
    plain-text restore, including cells whose only line breaks are real ``<br>``.
    """
    if _replace_text_keeping_anchors(cell_tag, translated_text):
        return

    _replace_cell_text_plain(cell_tag, translated_text)


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
                text = _cell_translatable_text(caption)
                if text and text not in duplicate_elements:
                    segments.append(StringSegmentValue("", text, order=col))
                    duplicate_elements.append(text)
                col += 1

            rows = table.find_all("tr")
            for row in rows:
                # Include both <td> (body/footer cells) and <th> (header cells).
                cells = row.find_all(["td", "th"])
                for elem in cells:
                    text = _cell_translatable_text(elem)
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
                    text = _cell_translatable_text(caption)
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
                        text = _cell_translatable_text(ele)
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
