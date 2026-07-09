import functools

from django import forms
from tinymce.widgets import TinyMCE

# ---------------------------------------------------------------------------
# Wagtail version-adaptive imports
# ---------------------------------------------------------------------------

# WidgetWithScript was the Wagtail <7 mixin that wired a widget's render_js_init
# call into the admin render pipeline.  It was removed in Wagtail 7 — the
# Telepath adapter mechanism now handles JS init entirely.
try:
    from wagtail.utils.widgets import WidgetWithScript as _WidgetWithScript
    _extra_bases: tuple = (_WidgetWithScript,)
except ImportError:
    _extra_bases = ()

# WidgetAdapter moved from wagtail.widget_adapters to
# wagtail.admin.telepath.widgets in Wagtail 7.  The old path still exists as a
# deprecation shim (RemovedInWagtail80Warning), so prefer the new one.
try:
    from wagtail.admin.telepath.widgets import WidgetAdapter
except ImportError:
    from wagtail.widget_adapters import WidgetAdapter  # noqa: F401  (Wagtail <7)

from wagtail.telepath import register


# ---------------------------------------------------------------------------
# Widget
# ---------------------------------------------------------------------------

class WagtailTinyMCE(*_extra_bases, TinyMCE):
    def __init__(
        self,
        content_language=None,
        attrs=None,
        menubar_options=None,
        toolbar_options=None,
        mce_config=None,
    ):
        mce_config = mce_config or {}
        if menubar_options is not None:
            mce_config["menubar"] = menubar_options
        if toolbar_options is not None:
            mce_config["toolbar"] = toolbar_options
        super().__init__(content_language, attrs, mce_config)


# ---------------------------------------------------------------------------
# Telepath adapter
# ---------------------------------------------------------------------------

class WagtailTinyMCEAdapter(WidgetAdapter):
    js_constructor = "wagtailtinymce.widgets.WagtailTinyMCE"

    @functools.cached_property
    def media(self):
        # In Wagtail 7+, WidgetAdapter.media is itself a cached_property that
        # returns the core Telepath JS.  Older Wagtail used Django's inner
        # Media class convention.  We merge whatever the parent provides with
        # our own adapter script so both code paths work.
        try:
            base = super().media
        except Exception:
            base = forms.Media()
        return base + forms.Media(js=["wagtailtinymce/js/tinymce-adapter.js"])


register(WagtailTinyMCEAdapter(), WagtailTinyMCE)
