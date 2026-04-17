"""
Tests for TinyMCEBlock (blocks.py) and WagtailTinyMCE widget (widgets.py).

  - TinyMCEBlock.sanitize()      — bleach-based HTML sanitization
  - TinyMCEBlock.value_from_form() — sanitize + mark_safe
  - WagtailTinyMCE.__init__      — mce_config merging
  - WagtailTinyMCEAdapter        — telepath registration
"""

import pytest
from django.utils.safestring import SafeData

from wagtailtinymce.blocks import SanitizationDisabledWarning, TinyMCEBlock
from wagtailtinymce.core.table_block import TinyMCETableBlock
from wagtailtinymce.widgets import WagtailTinyMCE, WagtailTinyMCEAdapter


# ---------------------------------------------------------------------------
# TinyMCEBlock.sanitize()
# We test via TinyMCETableBlock because TinyMCEBlock.sanitize() uses
# self.allowed_tags / allowed_attributes which are defined on the subclass.
# ---------------------------------------------------------------------------


@pytest.fixture
def table_block():
    return TinyMCETableBlock()


class TestSanitize:
    def test_strips_script_tag(self, table_block):
        dirty = "<table><tbody><tr><td><script>alert(1)</script>Safe</td></tr></tbody></table>"
        result = table_block.sanitize(dirty)
        assert "<script>" not in result
        assert "Safe" in result

    def test_strips_onclick_attribute(self, table_block):
        dirty = '<table><tbody><tr><td onclick="evil()">Click</td></tr></tbody></table>'
        result = table_block.sanitize(dirty)
        assert "onclick" not in result
        assert "Click" in result

    def test_strips_html_comments(self, table_block):
        dirty = "<table><!-- hidden --><tbody><tr><td>Data</td></tr></tbody></table>"
        result = table_block.sanitize(dirty)
        assert "<!--" not in result
        assert "Data" in result

    def test_preserves_allowed_table_tags(self, table_block):
        html = (
            "<table><thead><tr><th>H</th></tr></thead>"
            "<tbody><tr><td>D</td></tr></tbody>"
            "<tfoot><tr><td>F</td></tr></tfoot></table>"
        )
        result = table_block.sanitize(html)
        for tag in ("table", "thead", "tbody", "tfoot", "tr", "th", "td"):
            assert f"<{tag}" in result, f"Expected <{tag}> to be preserved"

    def test_preserves_colspan_on_td(self, table_block):
        html = '<table><tbody><tr><td colspan="2">Merged</td></tr></tbody></table>'
        result = table_block.sanitize(html)
        assert 'colspan="2"' in result

    def test_preserves_rowspan_on_td(self, table_block):
        html = '<table><tbody><tr><td rowspan="3">Tall</td></tr></tbody></table>'
        result = table_block.sanitize(html)
        assert 'rowspan="3"' in result

    def test_preserves_scope_on_th(self, table_block):
        html = '<table><thead><tr><th scope="col">Column</th></tr></thead></table>'
        result = table_block.sanitize(html)
        assert 'scope="col"' in result

    def test_strips_disallowed_div_tag(self, table_block):
        dirty = "<table><tbody><tr><td><div>wrapped</div></td></tr></tbody></table>"
        result = table_block.sanitize(dirty)
        assert "<div>" not in result
        assert "wrapped" in result

    def test_preserves_inline_formatting(self, table_block):
        html = (
            "<table><tbody><tr><td>"
            "<strong>Bold</strong> and <em>italic</em>"
            "</td></tr></tbody></table>"
        )
        result = table_block.sanitize(html)
        assert "<strong>" in result
        assert "<em>" in result

    def test_preserves_anchor_href(self, table_block):
        html = (
            '<table><tbody><tr><td>'
            '<a href="https://example.com">Link</a>'
            "</td></tr></tbody></table>"
        )
        result = table_block.sanitize(html)
        assert 'href="https://example.com"' in result

    def test_strips_javascript_href(self, table_block):
        html = (
            "<table><tbody><tr><td>"
            '<a href="javascript:alert(1)">XSS</a>'
            "</td></tr></tbody></table>"
        )
        result = table_block.sanitize(html)
        assert "javascript:" not in result

    def test_preserves_allowed_inline_styles(self, table_block):
        # width and border-collapse are in TinyMCETableBlock.allowed_styles
        html = '<table style="width:100%;border-collapse:collapse"><tbody><tr><td>X</td></tr></tbody></table>'
        result = table_block.sanitize(html)
        assert "width" in result
        assert "border-collapse" in result

    def test_strips_disallowed_inline_styles(self, table_block):
        # color and background-color are NOT in allowed_styles — must be stripped
        html = '<table style="color:red;background-color:blue"><tbody><tr><td>X</td></tr></tbody></table>'
        result = table_block.sanitize(html)
        assert "color" not in result
        assert "background-color" not in result

    def test_no_css_sanitizer_warning_when_allowed_styles_set(self, table_block):
        import warnings as _warnings
        html = '<table style="width:50%"><tbody><tr><td>X</td></tr></tbody></table>'
        with _warnings.catch_warnings():
            _warnings.simplefilter("error")
            # Should not raise NoCssSanitizerWarning when allowed_styles is set
            table_block.sanitize(html)


# ---------------------------------------------------------------------------
# TinyMCEBlock.value_from_form()
# ---------------------------------------------------------------------------


class TestValueFromForm:
    def test_sanitizes_when_sanitize_input_true(self, table_block):
        html = (
            "<table><tbody><tr>"
            "<td><script>bad()</script>Good</td>"
            "</tr></tbody></table>"
        )
        result = table_block.value_from_form(html)
        assert "<script>" not in result
        assert "Good" in result

    def test_returns_safe_string(self, table_block):
        html = "<table><tbody><tr><td>Safe</td></tr></tbody></table>"
        result = table_block.value_from_form(html)
        assert isinstance(result, SafeData)

    def test_skips_sanitize_when_disabled_and_emits_warning(self):
        # sanitize_input=False is intentionally dangerous — the block must
        # emit SanitizationDisabledWarning so misuse is never silent.
        with pytest.warns(SanitizationDisabledWarning, match="sanitize_input=False"):
            block = TinyMCETableBlock(sanitize_input=False)
        raw = "<table><tbody><tr><td><script>x</script></td></tr></tbody></table>"
        result = block.value_from_form(raw)
        assert "<script>" in result

    def test_empty_string_returns_safe_empty(self, table_block):
        result = table_block.value_from_form("")
        assert isinstance(result, SafeData)
        assert result == ""


# ---------------------------------------------------------------------------
# WagtailTinyMCE widget  (mce_config merging)
# ---------------------------------------------------------------------------


class TestWagtailTinyMCE:
    def test_no_options_uses_empty_config(self):
        widget = WagtailTinyMCE()
        # Should not raise; config is an empty dict by default
        assert widget is not None

    def test_menubar_options_merged_into_config(self):
        widget = WagtailTinyMCE(menubar_options="file edit")
        # django-tinymce stores the merged config; verify the menubar key made it in
        assert widget.mce_attrs.get("menubar") == "file edit"

    def test_toolbar_options_merged_into_config(self):
        widget = WagtailTinyMCE(toolbar_options="bold italic")
        assert widget.mce_attrs.get("toolbar") == "bold italic"

    def test_explicit_mce_config_passed_through(self):
        cfg = {"plugins": "link", "menubar": ""}
        widget = WagtailTinyMCE(mce_config=cfg)
        assert widget.mce_attrs.get("plugins") == "link"

    def test_menubar_options_overrides_mce_config_menubar(self):
        """menubar_options should win over a menubar key already in mce_config."""
        cfg = {"menubar": "original"}
        widget = WagtailTinyMCE(mce_config=cfg, menubar_options="override")
        assert widget.mce_attrs.get("menubar") == "override"

    def test_toolbar_options_overrides_mce_config_toolbar(self):
        cfg = {"toolbar": "original"}
        widget = WagtailTinyMCE(mce_config=cfg, toolbar_options="override")
        assert widget.mce_attrs.get("toolbar") == "override"


# ---------------------------------------------------------------------------
# WagtailTinyMCEAdapter
# ---------------------------------------------------------------------------


class TestWagtailTinyMCEAdapter:
    def test_js_constructor_name(self):
        adapter = WagtailTinyMCEAdapter()
        assert adapter.js_constructor == "wagtailtinymce.widgets.WagtailTinyMCE"

    def test_media_includes_adapter_js(self):
        adapter = WagtailTinyMCEAdapter()
        js_files = adapter.media._js
        assert any("tinymce-adapter.js" in f for f in js_files)
