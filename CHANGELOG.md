# Changelog

All notable changes to `wagtail-tinymce` are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

---

## [Unreleased]

---

## [0.2.7] — 2026-05-05

### Fixed

- **`<br>` tags in table cells no longer lost or rendered as literal text during
  translation** (`core/table_block.py`)

  `get_translatable_segments()` previously used `get_text(separator=" ")`, which
  collapsed every `<br>` tag into a space and discarded it. The extracted segment
  text contained no line-break information, so translators either lost the
  formatting entirely or manually typed `<br/>` as literal characters. After
  restore, those literal characters appeared verbatim on the published page instead
  of rendering as HTML line breaks.

  Two targeted changes fix the full cycle:

  1. **Extraction** — `get_text(separator="\n")` is now used for every cell and
     caption lookup (both in `get_translatable_segments` and in the cell-matching
     logic inside `restore_translated_segments`). Each `<br>` boundary in the
     original HTML becomes a `\n` in the segment text, giving translators a natural
     line-break marker to preserve.

  2. **Restore** — `_replace_cell_text` now detects `\n` characters in the
     translated text and reconstructs real `<br>` elements at each split point
     instead of writing a plain `NavigableString`. Cells with no `\n` are
     unchanged (plain text inserted as before).

- **Stale test corrected** (`tests/test_table_block.py`)

  `test_tfoot_setup_contains_open_paren` asserted that `_TFOOT_SETUP` contained
  `"("` — a remnant from when the setup value was an `eval()`-able function
  expression. After the 0.2.2 security hardening replaced `eval()` with a named
  callback registry, `_TFOOT_SETUP` became a plain registry key (`"tablefooterrow"`)
  with no parentheses. The test now asserts the correct invariant: that `"("` is
  **not** present in the registry key.

### Added

- **`TestBrReconstruction`** (`tests/test_replace_cell_text.py`) — 8 new unit
  tests covering `_replace_cell_text` when `translated_text` contains `\n`:
  single newline → one `<br>`; multiple newlines → multiple `<br>` elements;
  reconstructed `<br>` is a real HTML element not literal text; no-newline path
  unchanged; edge cases for leading/trailing text nodes and many lines.

- **`TestBrTagPreservation`** (`tests/test_table_block.py`) — 10 new integration
  tests covering the complete extraction → translation → restoration cycle for
  cells with `<br>`: segment text contains `\n` not literal `<br/>`; restored HTML
  contains real `<br>` tags; correct text on each side of reconstructed break;
  adjacent plain cells and segment indices unaffected; duplicate multi-line cells
  de-duplicated correctly.

---

## [0.2.6] — 2026-04-20

### Changed

- `table_default_styles` set to `{}`. Previously `{"border-collapse": "collapse", "width": "100%"}` was
  written as an inline `style` attribute on every new `<table>`. Inline styles carry the highest CSS
  specificity and were silently overriding any site-level table rules. New tables are now stored as plain
  `<table>` elements with no inline style, giving the host app's stylesheet full, unobstructed control.
- `table_default_attributes` remains `{}`. No CSS class is stamped on new tables by default. Integrating
  projects that use a class-based CSS framework (e.g. Bulma's `.table.is-bordered`) can opt in via a
  subclass — see the Customisation section of the README.

### Documentation

- **"Applying your site's table styles to new tables"** section added to the Customisation guide:
  - How to target TinyMCE tables from the host app's stylesheet using the `section.block-table` wrapper
    (framework-agnostic, no class required).
  - How to opt in to a CSS class hook via `table_default_attributes`.
  - How to mirror host-app styles inside the TinyMCE editor iframe via `content_css` / `content_style`.
  - Note on CSS specificity: class selectors override element selectors.

---

## [0.2.5] — 2026-04-20

### Documentation

- Initial "Mirroring your site's CSS inside the editor" section added to the Customisation guide,
  covering `content_css` (load a compiled stylesheet into the TinyMCE iframe) and `content_style`
  (inline a small rule block directly). Both options can be combined.

---

## [0.2.4] — 2026-04-20

### Changed

- `promotion: false` added to `TinyMCETableBlock`'s default TinyMCE config. This removes the
  self-hosted "Get all features" / Tiny Cloud upgrade banner from the top of the table editor UI.

---

## [0.2.3] — 2026-04-17

### Fixed

- **TinyMCE 7 editor initialisation** (`static/wagtailtinymce/js/tinymce-adapter.js`)  
  The Wagtail telepath adapter used `tinyMCE.editors[id]` to check whether an editor was already
  initialised. This property is not part of the TinyMCE 7 / django-tinymce ≥ 5 public API and always
  returns `undefined`. Replaced with `tinyMCE.get(id)`, the correct API for all supported versions.

---

## [0.2.2] — 2026-04-17

Security hardening release. No functional changes to the table editing experience.

### Security

- **bleach 6.x compatibility** (`blocks.py`)  
  `TinyMCEBlock.sanitize()` previously passed `tags=None` and `attributes=None` directly to
  `bleach.clean()`. In bleach 6.x this raises `TypeError`; in bleach 5.x it silently fell back to
  bleach's own defaults rather than the subclass allowlists. Both kwargs are now only forwarded when the
  subclass has explicitly set them.

- **Django CVE floor** (`pyproject.toml`)  
  `django>=4.2.15` added as an explicit dependency. Django was previously only a transitive dependency
  via Wagtail, allowing pip to resolve versions with unpatched CVEs (CVE-2024-27351, CVE-2024-38875,
  CVE-2024-39329/39330/39614, CVE-2024-41989/41990/41991, CVE-2024-53907/53908). `4.2.15` is the first
  4.2 LTS release where all CVEs through mid-2024 are patched.

- **`eval()` removed from `tinymce-adapter.js`**  
  TinyMCE callback options (e.g. `setup`) were serialised as JavaScript function expressions and
  `eval()`'d at initialisation time. Replaced with a named callback registry
  (`window.wagtailTinyMCECallbacks`). The Footer Row button setup function moved from a serialised
  Python string into `tinymce-adapter.js` where executable code belongs. Arbitrary expressions in
  `mce_conf` are now rejected with `console.warn` rather than executed. Consuming projects can register
  custom callbacks via:
  ```js
  window.wagtailTinyMCECallbacks['mySetup'] = function(editor) { ... };
  ```

- **`sanitize_input=False` made loud** (`blocks.py`)  
  Instantiating any `TinyMCEBlock` subclass with `sanitize_input=False` now emits
  `SanitizationDisabledWarning` (a `UserWarning` subclass) at construction time. Previously this
  silently disabled all HTML sanitisation and passed raw editor input to `mark_safe()` with no
  indication of the risk.

- **Inline CSS filtering enforced** (`blocks.py`, `pyproject.toml`)  
  `bleach.clean()` was called without a `CSSSanitizer`, causing bleach to emit
  `NoCssSanitizerWarning` and leave inline CSS properties unfiltered. `sanitize()` now constructs a
  `CSSSanitizer(allowed_css_properties=self.allowed_styles)` whenever `allowed_styles` is declared.
  For `TinyMCETableBlock` this means only `width` and `border-collapse` survive; all other properties
  are stripped. Requires `bleach[css]` (pulls in `tinycss2`).

- **Structured logging in `restore_translated_segments()`** (`core/table_block.py`)  
  Two bare `print(e)` calls in exception handlers replaced with `logger.exception()` using a
  module-level logger (`wagtailtinymce.core.table_block`). Errors now route through Django's
  configurable logging pipeline at `ERROR` level with full tracebacks.

- **Reverse tabnabbing prevention** (`blocks.py`)  
  `TinyMCETableBlock` permitted the `target` attribute on `<a>` tags but did not enforce `rel=noopener`
  on `target="_blank"` links. A new `_enforce_link_safety()` post-processor runs after `bleach.clean()`
  and sets `rel="noopener noreferrer"` on every `<a target="_blank">`, including overwriting any
  attacker-supplied `rel="opener"`.

### Changed

| Dependency | Before | After |
|---|---|---|
| `bleach` | `>=6.0` | `bleach[css]>=6.0,<7` |
| `django` | *(transitive)* | `>=4.2.15` (explicit minimum) |

### Added

- `pip-audit` added to the `[dev]` optional group for CVE scanning in CI.

### Upgrade notes

```bash
pip install "bleach[css]>=6.0,<7"   # pulls in tinycss2 for CSSSanitizer
pip install "django>=5.0.11"         # if on the Django 5.0.x series
```

---

## [0.2.1] — 2026-04-17

### Fixed

- **Table header rows now produce `<th>` elements** (`core/table_block.py`)  
  Set `table_header_type: "sectionCells"` in `TinyMCETableBlock`'s default TinyMCE config. The
  previous default (`"section"`) moved rows into `<thead>` but kept `<td>` elements, so header rows
  had no semantic `<th>` markup.

- **Table captions included in translatable segments** (`core/table_block.py`)  
  `get_translatable_segments()` and `restore_translated_segments()` in `TinyMCETableBlock` now process
  `<caption>` elements. Captions are extracted before cells (matching DOM order) and restored to the
  correct segment index so subsequent cell translations are not offset.

---

## [0.2.0] — 2026-04-16

### Changed

- Upgraded to `django-tinymce>=5.0` (bundles TinyMCE 7.8). **Breaking:** if you cannot upgrade
  `django-tinymce`, pin to the `v0.1.0` git tag (TinyMCE 6, django-tinymce ≥ 3.5).
- `wagtail-localize>=1.5` made a required dependency (was optional).

### Fixed

- Fixed build backend from `setuptools.backends.legacy:build` to `setuptools.build_meta` for
  compatibility with older setuptools versions.
- Fixed `package-dir` mapping so `pip install git+…` correctly resolves the `wagtailtinymce` module
  (previously the package was installed empty).

---

## [0.1.0] — 2026-04-15

Initial release.

### Added

- `TinyMCEBlock` — base StreamField block embedding a full TinyMCE rich-text editor in the Wagtail
  page editor.
- `TinyMCETableBlock` — table-focused block with Excel / Google Sheets paste support, header rows
  (`<thead>`), footer rows (`<tfoot>`), cell merging / splitting, and HTML sanitisation via bleach.
- Custom *Footer Row* toolbar button for toggling a row between `<tbody>` and `<tfoot>`.
- `wagtail-localize` segment extraction and restoration, with support for empty cells, merged cells
  with rich content, and `<th>` cells.
