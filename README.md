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
| django-tinymce | 5.0 |
| bleach | 6.0 |
| beautifulsoup4 | 4.12 |
| lxml | 4.9 |

`wagtail-localize` ≥ 1.5 is a **required** dependency and is installed automatically.

---

## Installation

`wagtail-localize` is a **required** dependency — it is always installed automatically. No extra flags are needed.

### From PyPI

```bash
pip install wagtail-tinymce
```

### From Git (`master` branch — TinyMCE 7, django-tinymce ≥ 5.0)

```bash
pip install git+https://github.com/ogcio/wagtail-tinymce-table.git@master
```

In a `requirements.txt` file (PEP 508):

```text
wagtail-tinymce @ git+https://github.com/ogcio/wagtail-tinymce-table.git@master
```

### Legacy version (TinyMCE 6, django-tinymce ≥ 3.5)

If your project requires  (TinyMCE 6), install the  tag instead:

```bash
pip install git+https://github.com/ogcio/wagtail-tinymce-table.git@v0.1.0
```

In a `requirements.txt` file (PEP 508):

```text
wagtail-tinymce @ git+https://github.com/ogcio/wagtail-tinymce-table.git@v0.1.0
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

No configuration is needed. `wagtail-localize` is installed automatically with the package, and Wagtail Localize will pick up the segments automatically.

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
pip install "wagtail-tinymce[dev]"   # adds pytest + pytest-django
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

### 0.2.4

#### Behaviour

- **`TinyMCETableBlock` disables the TinyMCE self-hosted upgrade banner.** The default editor config now sets `promotion: false`, which removes the “Get all features” / Tiny Cloud promotion link from the top of the table editor UI.

### 0.2.3

#### Bug fixes

- **TinyMCE 7 editor initialisation.** The Wagtail telepath adapter now uses `tinyMCE.get(id)` instead of `tinyMCE.editors[id]` when checking whether an editor instance already exists, matching the django-tinymce / TinyMCE 7 API.

### 0.2.2

Security hardening release (no change to table editing features). For step-by-step upgrade notes and fuller context, see [`CHANGELOG.md`](CHANGELOG.md).

#### Security and robustness

- **bleach 6.x** — `TinyMCEBlock.sanitize()` no longer passes `tags=None` or `attributes=None` into `bleach.clean()` (which breaks on bleach 6.x and could bypass allowlists on 5.x).
- **Django minimum** — `django>=4.2.15` is declared explicitly so pip cannot resolve an older, known-vulnerable Django via Wagtail alone.
- **No `eval()` in the adapter** — TinyMCE callbacks (e.g. `setup`) are resolved through `window.wagtailTinyMCECallbacks` (or `window.<name>`); unknown keys log a warning instead of executing arbitrary strings.
- **`sanitize_input=False` is visible** — constructing a block with `sanitize_input=False` emits `SanitizationDisabledWarning` so disabling sanitisation is never silent.
- **Inline CSS filtering** — when `allowed_styles` is set, sanitisation uses bleach’s `CSSSanitizer` so only allowlisted properties survive (for `TinyMCETableBlock`, `width` and `border-collapse`). Requires `bleach[css]`.
- **Translation errors** — `restore_translated_segments()` uses `logger.exception()` instead of printing to stdout.
- **Targeted links** — after sanitisation, `<a target="_blank">` gets `rel="noopener noreferrer"` to mitigate reverse tabnabbing.

#### Dependencies

- `bleach[css]>=6.0,<7` (was `bleach>=6.0` without the CSS extra).
- `django>=4.2.15` added as an explicit requirement.
- Optional dev extra: `pip-audit` for CVE scanning.

### 0.2.1

#### Bug fixes

- **Header rows now produce `<th>` elements.** The default TinyMCE `table_header_type` was changed from `"section"` to `"sectionCells"`. The former moved rows into `<thead>` but kept `<td>` cells; the latter also converts those cells to `<th>`.
- **Table `<caption>` text is included in translatable segments.** `get_translatable_segments()` and `restore_translated_segments()` process `<caption>` in DOM order (before row cells) so captions appear in Wagtail Localize and segment indices stay aligned with cell content.

### 0.2.0

#### Breaking changes
- **Requires `django-tinymce >= 5.0`** (previously 3.5). This bundles **TinyMCE 7.8** instead of TinyMCE 6.x. If you cannot upgrade `django-tinymce`, pin to the `v0.1.0` git tag.
- **`wagtail-localize >= 1.5` is now a required dependency** (previously optional).

#### Packaging
- Fixed build backend from `setuptools.backends.legacy:build` to `setuptools.build_meta` for compatibility with older setuptools versions.
- Fixed `package-dir` mapping so `pip install git+…` correctly installs the `wagtailtinymce` module (previously the package was silently installed empty).

### 0.1.0

- Initial release.
- `TinyMCEBlock` and `TinyMCETableBlock` StreamField blocks.
- Excel / Google Sheets paste support via TinyMCE's clipboard plugin.
- Custom *Footer Row* toolbar button for `<tfoot>` support.
- `wagtail-localize` segment extraction and restoration, with fixes for empty cells, merged cells with rich content, and `<th>` cells.

---

## Licence

MIT
