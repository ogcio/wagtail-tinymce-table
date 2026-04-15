# wagtail-tinymce

A set of [Wagtail](https://wagtail.org/) StreamField blocks that embed a [TinyMCE](https://www.tiny.cloud/) editor directly inside the page editor. The headline feature is `TinyMCETableBlock`: a fully-featured table block that lets editors paste tables straight from Excel or Google Sheets, create header-only or footer-only tables, and merge cells — all without needing Wagtail's built-in table block.

---

## Features

- **Paste from Excel / Google Sheets** — TinyMCE's clipboard handling converts spreadsheet data to clean HTML tables automatically.
- **Header rows (`<thead>`) and footer rows (`<tfoot>`)** — a custom *Footer Row* toolbar button toggles the selected row between `<tbody>` and `<tfoot>`. Header rows use TinyMCE's built-in *Row Header* button.
- **Header-less tables** — nothing forces a header row; plain body tables work fine.
- **Cell merging and splitting** — `colspan`/`rowspan` via the built-in *Merge Cells* and *Split Cell* buttons.
- **`wagtail-localize` integration** — `TinyMCETableBlock` implements `get_translatable_segments` and `restore_translated_segments` so table content is fully translatable, including header cells (`<th>`), footer cells, empty cells, and merged cells.
- **HTML sanitization** — all output is passed through [bleach](https://bleach.readthedocs.io/) with a strict allowlist before being stored.
- **Customisable** — override `custom_mce_config`, `allowed_tags`, `allowed_attributes`, or pass `menubar_options` / `toolbar_options` per block instance.

---

## Requirements

| Package | Minimum version |
|---|---|
| Python | 3.9 |
| Django | 4.2 |
| Wagtail | 4.0 |
| django-tinymce | 3.5 |
| bleach | 6.0 |
| beautifulsoup4 | 4.12 |
| lxml | 4.9 |

`wagtail-localize` ≥ 1.5 is an **optional** dependency. Install it only if you use Wagtail's localisation features.

---

## Installation

### From PyPI

```bash
pip install wagtail-tinymce
# with localisation support:
pip install "wagtail-tinymce[localize]"
```

### From Git (clone URL and `master` branch)

You can install the package straight from the repository without publishing to PyPI. Point pip at the HTTPS git address and pin the `master` branch with `@master`:

```bash
pip install git+https://github.com/ogcio/wagtail-tinymce-table.git@master
```

With the optional `wagtail-localize` extra:

```bash
pip install "wagtail-tinymce[localize] @ git+https://github.com/ogcio/wagtail-tinymce-table.git@master"
```

In a `requirements.txt` file (PEP 508):

```text
wagtail-tinymce @ git+https://github.com/ogcio/wagtail-tinymce-table.git@master
```

With localisation:

```text
wagtail-tinymce[localize] @ git+https://github.com/ogcio/wagtail-tinymce-table.git@master
```

---

Add `"wagtailtinymce"` and `"tinymce"` to `INSTALLED_APPS`:

```python
INSTALLED_APPS = [
    ...
    "tinymce",
    "wagtailtinymce",
]
```

Add a minimal TinyMCE configuration to your Django settings (required by `django-tinymce`):

```python
TINYMCE_DEFAULT_CONFIG = {}
```

Add `STATIC_URL` if it is not already set:

```python
STATIC_URL = "/static/"
```

Run `collectstatic` so the Wagtail telepath adapter script is served:

```bash
python manage.py collectstatic
```

---

## Quick start

### Complete working example

The snippets below show every file you need to add or edit in a standard Wagtail project to get a table block working end-to-end.

#### 1. `settings.py`

```python
INSTALLED_APPS = [
    # --- Wagtail core ---
    "wagtail.contrib.forms",
    "wagtail.contrib.redirects",
    "wagtail.embeds",
    "wagtail.sites",
    "wagtail.users",
    "wagtail.snippets",
    "wagtail.documents",
    "wagtail.images",
    "wagtail.search",
    "wagtail.admin",
    "wagtail",
    # --- Django ---
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # --- Third-party ---
    "tinymce",          # django-tinymce must come before wagtailtinymce
    "wagtailtinymce",   # this package
]

# Required by django-tinymce (may be an empty dict if you rely on block-level config)
TINYMCE_DEFAULT_CONFIG = {}
```

#### 2. `myapp/models.py`

```python
from wagtail.models import Page
from wagtail.fields import StreamField
from wagtail.admin.panels import FieldPanel

from wagtailtinymce.core.table_block import TinyMCETableBlock


class TableDemoPage(Page):
    """A page that contains one or more TinyMCE table blocks."""

    body = StreamField(
        [
            ("table", TinyMCETableBlock()),
        ],
        blank=True,
        use_json_field=True,
        verbose_name="Page body",
    )

    content_panels = Page.content_panels + [
        FieldPanel("body"),
    ]

    class Meta:
        verbose_name = "Table demo page"
```

#### 3. `myapp/templates/myapp/table_demo_page.html`

```html
{% extends "base.html" %}
{% load wagtailcore_tags %}

{% block content %}
  <article>
    <h1>{{ page.title }}</h1>

    {% for block in page.body %}
      {% if block.block_type == "table" %}
        {# The block value is already sanitised HTML — render it directly #}
        <div class="table-wrapper">
          {{ block.value }}
        </div>
      {% endif %}
    {% endfor %}
  </article>
{% endblock %}
```

> **Tip:** use `{% include_block page.body %}` instead of the manual loop if you do not need to wrap individual blocks in extra markup.

#### 4. Optional: add basic table styles

The block stores a plain `<table>` element. Add CSS so it displays nicely:

```css
/* static/css/content.css  (load this in your base template) */
.table-wrapper {
    overflow-x: auto;          /* horizontal scroll on small screens */
}

.table-wrapper table {
    border-collapse: collapse;
    width: 100%;
}

.table-wrapper th,
.table-wrapper td {
    border: 1px solid #d1d5db;
    padding: 0.5rem 0.75rem;
    text-align: left;
    vertical-align: top;
}

.table-wrapper thead th {
    background-color: #f3f4f6;
    font-weight: 600;
}

.table-wrapper tfoot td {
    background-color: #f9fafb;
    font-style: italic;
}
```

---

### Table block (minimal)

```python
from wagtail.models import Page
from wagtail.fields import StreamField
from wagtail.admin.panels import FieldPanel
from wagtailtinymce.core.table_block import TinyMCETableBlock

class MyPage(Page):
    body = StreamField(
        [("table", TinyMCETableBlock())],
        blank=True,
        use_json_field=True,
    )

    content_panels = Page.content_panels + [
        FieldPanel("body"),
    ]
```

Render the block in a template as you would any other StreamField block:

```html
{% load wagtailcore_tags %}
{% include_block page.body %}
```

### Generic TinyMCE block

`TinyMCEBlock` is the base class. Use it directly when you need a full rich-text editor without the table-specific toolbar:

```python
from wagtailtinymce.blocks import TinyMCEBlock

class MyPage(Page):
    body = StreamField(
        [("rich_text", TinyMCEBlock())],
        blank=True,
        use_json_field=True,
    )
```

---

## Customisation

### Per-instance toolbar / menubar

Pass `toolbar_options` or `menubar_options` when declaring the block:

```python
TinyMCETableBlock(
    toolbar_options="bold italic | table tablemergecells",
    menubar_options="",          # hide the menubar
)
```

### Subclassing for a project-wide config

```python
from wagtailtinymce.core.table_block import TinyMCETableBlock

class MyTableBlock(TinyMCETableBlock):
    custom_mce_config = {
        **TinyMCETableBlock.custom_mce_config,
        "language": "ga",        # Irish
        "content_css": "/static/css/editor.css",
    }

    allowed_tags = TinyMCETableBlock.allowed_tags + ["figure", "figcaption"]
```

### Disabling sanitization

Set `sanitize_input=False` if you need to allow arbitrary HTML (only do this when the editor is trusted):

```python
TinyMCETableBlock(sanitize_input=False)
```

---

## Toolbar reference

The default `TinyMCETableBlock` toolbar groups are:

| Group | Buttons |
|---|---|
| Formatting | `bold` `italic` `link` `unlink` |
| Table structure | `table` `tablecaption` `tablecolheader` `tablerowheader` `tablefooterrow`* |
| Cell operations | `tablecellprops` `tablemergecells` `tablesplitcells` |
| Row operations | `tableinsertrowbefore` `tableinsertrowafter` `tabledeleterow` |
| Column operations | `tableinsertcolbefore` `tableinsertcolafter` `tabledeletecol` |

\* `tablefooterrow` is a custom button added by this package. Clicking it moves the selected row into `<tfoot>` (or back to `<tbody>` if it is already a footer row).

---

## `wagtail-localize` integration

When `wagtail-localize` is installed, `TinyMCETableBlock` implements the segment protocol so translators see each non-empty cell as an individual string segment.

**Behaviour:**
- Empty cells are skipped and do not consume a segment index.
- Duplicate cell values are extracted once and restored to all matching cells.
- `<th>` (header) cells, `<tbody>` cells, and `<tfoot>` cells are all included.
- Cells that contain a nested table are skipped entirely.
- Merged cells (`colspan`/`rowspan`) are treated as a single cell.

No configuration is needed. Install the optional extra and Wagtail Localize will pick up the segments automatically:

```bash
pip install "wagtail-tinymce[localize]"
```

---

## Project structure

```
wagtailtinymce/
├── __init__.py                        # version
├── apps.py                            # Django AppConfig
├── blocks.py                          # TinyMCEBlock (base class)
├── widgets.py                         # WagtailTinyMCE widget + telepath adapter
├── core/
│   └── table_block.py                 # TinyMCETableBlock
└── static/
    └── wagtailtinymce/js/
        └── tinymce-adapter.js         # Wagtail telepath registration
```

---

## Running the tests

```bash
pip install "wagtail-tinymce[dev]"
pytest
```

The test suite has **75 tests** covering:

- `_replace_cell_text` helper (simple and compound cell paths)
- `TinyMCETableBlock` configuration (allowed tags, toolbar, TinyMCE `setup` callback)
- `get_translatable_segments` (empty cells, duplicates, `<th>`, `<tfoot>`, merged cells, round-trip)
- `restore_translated_segments` (index correctness, compound cells, `<tfoot>`, duplicates)
- `TinyMCEBlock.sanitize` (XSS, allowed tags/attributes, inline formatting)
- `TinyMCEBlock.value_from_form` (`SafeData`, bypass mode)
- `WagtailTinyMCE` widget (config merging and overrides)
- `WagtailTinyMCEAdapter` (telepath registration)

---

## Changelog

### 0.1.0

- Initial release.
- `TinyMCEBlock` and `TinyMCETableBlock` StreamField blocks.
- Excel / Google Sheets paste support via TinyMCE's clipboard plugin.
- Custom *Footer Row* toolbar button for `<tfoot>` support.
- `wagtail-localize` segment extraction and restoration, with fixes for empty cells, merged cells with rich content, and `<th>` cells.

---

## Licence

MIT
