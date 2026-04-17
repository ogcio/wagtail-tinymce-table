# Changelog

All notable changes to `wagtail-tinymce` are documented here.

---

## [0.2.2] — 2026-04-17

Security hardening release. No functional changes to the editing experience.

### Security fixes

- **bleach 6.x compatibility** (`blocks.py`)  
  `TinyMCEBlock.sanitize()` previously passed `tags=None` and
  `attributes=None` directly to `bleach.clean()`. In bleach 6.x this raises
  `TypeError`; in bleach 5.x it silently fell back to bleach's built-in
  defaults rather than the subclass allowlists. Both kwargs are now only
  forwarded when the subclass has explicitly set them.

- **Django CVE floor** (`pyproject.toml`)  
  `django>=4.2.15` added as an explicit dependency. Django was previously
  only a transitive dependency via wagtail, allowing pip to resolve versions
  with unpatched CVEs (including CVE-2024-27351, CVE-2024-38875,
  CVE-2024-39329/39330/39614, CVE-2024-41989/41990/41991,
  CVE-2024-53907/53908). `4.2.15` is the first 4.2 LTS release where all
  CVEs through mid-2024 are patched.

- **`eval()` removed from `tinymce-adapter.js`**  
  TinyMCE callback options (e.g. `setup`) were serialised as JavaScript
  function expressions and `eval()`'d at initialisation time. Replaced with
  a named callback registry (`window.wagtailTinyMCECallbacks`). The Footer
  Row button setup function moved from a serialised Python string into
  `tinymce-adapter.js` where executable code belongs. Arbitrary expressions
  in `mce_conf` are now rejected with `console.warn` rather than executed.
  Consuming projects can register custom callbacks via:
  ```js
  window.wagtailTinyMCECallbacks['mySetup'] = function(editor) { ... };
  ```

- **`sanitize_input=False` made loud** (`blocks.py`)  
  Instantiating any `TinyMCEBlock` subclass with `sanitize_input=False` now
  emits `SanitizationDisabledWarning` (a `UserWarning` subclass) at
  construction time. Previously this silently disabled all HTML sanitization
  and passed raw editor input to `mark_safe()` with no indication of the
  risk. The warning surfaces in Django logs, pytest output, and any CI
  configuration that escalates warnings.

- **Inline CSS filtering enforced** (`blocks.py`, `pyproject.toml`)  
  `bleach.clean()` was called without a `CSSSanitizer`, causing bleach to
  emit `NoCssSanitizerWarning` and leave inline CSS properties unfiltered.
  `sanitize()` now constructs a
  `CSSSanitizer(allowed_css_properties=self.allowed_styles)` whenever
  `allowed_styles` is declared. For `TinyMCETableBlock` this means only
  `width` and `border-collapse` survive; all other properties are stripped.
  Requires `bleach[css]` (pulls in `tinycss2`).

- **Structured logging in `restore_translated_segments()`** (`core/table_block.py`)  
  Two bare `print(e)` calls in exception handlers replaced with
  `logger.exception()` using a module-level logger
  (`wagtailtinymce.core.table_block`). Errors now route through Django's
  configurable logging pipeline at `ERROR` level with full tracebacks,
  rather than writing raw exception messages to stdout.

- **Reverse tabnabbing prevention** (`blocks.py`)  
  `TinyMCETableBlock` permitted the `target` attribute on `<a>` tags but did
  not enforce `rel=noopener` on `target="_blank"` links. A new
  `_enforce_link_safety()` post-processor runs after `bleach.clean()` and
  sets `rel="noopener noreferrer"` on every `<a target="_blank">`, including
  overwriting any attacker-supplied `rel="opener"`.

### Dependency changes

| Package | Before | After |
|---|---|---|
| `bleach` | `>=6.0` | `bleach[css]>=6.0,<7` |
| `django` | *(transitive)* | `>=4.2.15` (explicit minimum) |

### Dev dependency additions

- `pip-audit` added to the `[dev]` optional group for CVE scanning in CI.

### Upgrade notes

After upgrading run:

```bash
pip install "bleach[css]>=6.0,<7"   # pulls in tinycss2 for CSSSanitizer
pip install "django>=5.0.11"         # if on the 5.0.x series
```

---

## [0.2.1] — 2026-04-01

### Bug fixes

- **Table header rows now produce `<th>` elements**  
  Set `table_header_type: "sectionCells"` in `TinyMCETableBlock`'s default
  TinyMCE config. The previous default (`"section"`) moved rows into
  `<thead>` but kept `<td>` elements, so header rows had no semantic `<th>`
  markup.

- **Table captions included in translatable segments**  
  `get_translatable_segments()` and `restore_translated_segments()` in
  `TinyMCETableBlock` now process `<caption>` elements. Captions are
  extracted before cells (matching the DOM order) and restored to the
  correct segment index so subsequent cell translations are not offset.

---

## [0.2.0] — 2026-03-15

### Changes

- Upgraded to `django-tinymce>=5.0` (TinyMCE 7.8).
- `wagtail-localize>=1.5` made a required dependency.
- README updated with end-to-end usage example and legacy install notes.
- Fixed `setuptools` package-dir configuration so `pip install` from a Git
  URL correctly resolves the `wagtailtinymce` module.
