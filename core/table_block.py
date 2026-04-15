from wagtail_localize.segments import StringSegmentValue

from bs4 import BeautifulSoup, NavigableString

from wagtailtinymce.blocks import TinyMCEBlock

__all__ = [
    "TinyMCETableBlock",
]

# JavaScript function (serialised as a string) that registers a custom TinyMCE
# toolbar button which toggles the currently selected row between <tbody> and
# <tfoot>.  The JS adapter in tinymce-adapter.js evals any setup value that
# contains a "(" character, so a plain arrow-function expression is sufficient.
_TFOOT_SETUP = (
    "(editor) => {"
    "  editor.ui.registry.addButton('tablefooterrow', {"
    "    text: 'Footer Row',"
    "    tooltip: 'Toggle selected row as table footer',"
    "    onAction: () => {"
    "      const node = editor.selection.getNode();"
    "      const row = editor.dom.getParent(node, 'tr');"
    "      if (!row) return;"
    "      const parent = row.parentNode;"
    "      const table = editor.dom.getParent(row, 'table');"
    "      if (!table) return;"
    "      if (parent.tagName.toLowerCase() === 'tfoot') {"
    "        let tbody = table.querySelector('tbody');"
    "        if (!tbody) { tbody = editor.dom.create('tbody'); table.appendChild(tbody); }"
    "        tbody.appendChild(row);"
    "        if (!parent.hasChildNodes()) parent.remove();"
    "      } else {"
    "        let tfoot = table.querySelector('tfoot');"
    "        if (!tfoot) { tfoot = editor.dom.create('tfoot'); table.appendChild(tfoot); }"
    "        tfoot.appendChild(row);"
    "        if (!parent.hasChildNodes()) parent.remove();"
    "      }"
    "    }"
    "  });"
    "}"
)


def _replace_cell_text(cell_tag, translated_text):
    """Replace the visible text of a BeautifulSoup cell tag with *translated_text*.

    Two cases:
    - Simple cell: the tag has a single NavigableString child (``tag.string`` is
      not None).  We call ``replace_with`` directly on that string.
    - Compound cell: the tag contains child elements (e.g. ``<p>``, ``<strong>``).
      ``tag.string`` is None for such tags in BeautifulSoup.  We clear the tag and
      insert the translated plain text as a new NavigableString, which intentionally
      drops inner formatting because the translation system operates on plain text.
    """
    if cell_tag.string is not None:
        cell_tag.string.replace_with(translated_text)
    else:
        cell_tag.clear()
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
        "table_default_styles": {"border-collapse": "collapse", "width": "100%"},
        "table_sizing_mode": "relative",
        "table_advtab": False,
        "table_cell_advtab": False,
        "table_row_advtab": False,
        "language": "en",
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
            rows = table.find_all("tr")
            for row in rows:
                # Include both <td> (body/footer cells) and <th> (header cells).
                cells = row.find_all(["td", "th"])
                for elem in cells:
                    text = elem.get_text(separator=" ").strip()
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
                rows = table.find_all("tr")
                for row in rows:
                    # Mirror the same cell selector used in get_translatable_segments.
                    cells = row.find_all(["td", "th"])
                    for ele in cells:
                        text = ele.get_text(separator=" ").strip()
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
                        except Exception as e:
                            print(e)

            return str(soup)
