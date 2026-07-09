import warnings

import bleach
from bleach.css_sanitizer import CSSSanitizer
from bs4 import BeautifulSoup
from django import forms
from django.utils.safestring import mark_safe
from wagtail.blocks import RawHTMLBlock

from .widgets import WagtailTinyMCE


def _enforce_link_safety(html: str) -> str:
    """Add rel="noopener noreferrer" to every <a target="_blank"> link.

    A link that opens in a new tab gives the opened page access to
    window.opener, allowing it to redirect the parent tab (tabnabbing).
    Adding rel="noopener noreferrer" severs that reference.

    This runs after bleach.clean() so the HTML structure is already
    normalised and safe to parse as a fragment.
    """
    soup = BeautifulSoup(html, "html.parser")
    for a_tag in soup.find_all("a"):
        if a_tag.get("target") == "_blank":
            a_tag["rel"] = "noopener noreferrer"
    return str(soup)


class SanitizationDisabledWarning(UserWarning):
    """Emitted when a TinyMCEBlock is instantiated with sanitize_input=False.

    Disabling sanitization means all HTML submitted by editors is passed
    directly to mark_safe() without any filtering.  Only use this flag in
    environments where every editor account is fully trusted and the rendered
    output is never shown to untrusted users.
    """


class TinyMCEBlock(RawHTMLBlock):

    # Set to override all or part of the default tinymce config
    # from TINYMCE_DEFAULT_CONFIG
    mce_config = None

    # Set to override sanitization options passed to bleach
    # when sanitize_input=True
    allowed_tags = None
    allowed_attributes = None
    allowed_styles = None

    def __init__(
        self,
        required=False,
        help_text=None,
        menubar_options=None,
        toolbar_options=None,
        sanitize_input=True,
        validators=(),
        **kwargs,
    ):
        # ``menubar_options`` and ``toolbar_options`` are provided as a means to
        # customize those parts of the tinymce config for specific block instances
        self.menubar_options = menubar_options
        self.toolbar_options = toolbar_options
        self.sanitize_input = sanitize_input

        if not sanitize_input:
            warnings.warn(
                f"{self.__class__.__name__} was instantiated with sanitize_input=False. "
                "All HTML submitted by editors will be passed to mark_safe() without "
                "any sanitization. Only use this in fully trusted environments where "
                "every editor account is trusted and output is never shown to "
                "untrusted users.",
                SanitizationDisabledWarning,
                stacklevel=2,
            )

        super().__init__(required=required, help_text=help_text, validators=validators, **kwargs)

        # RawHTMLBlock initializes the field in the init function so we have
        # to reinitialize as a WagtailTinyMCE widget.
        # https://github.com/wagtail/wagtail/blob/main/wagtail/core/blocks/field_block.py#L706
        self.field = forms.CharField(
            widget=WagtailTinyMCE(
                menubar_options=self.menubar_options,
                toolbar_options=self.toolbar_options,
                mce_config=self.custom_mce_config,
            )
        )

    def sanitize(self, value):
        # bleach 6.x raises TypeError when tags or attributes is None rather
        # than falling back to its built-in defaults.  Only forward these
        # kwargs when the subclass has explicitly set them.
        kwargs: dict = {"strip": True, "strip_comments": True}
        if self.allowed_tags is not None:
            kwargs["tags"] = self.allowed_tags
        if self.allowed_attributes is not None:
            kwargs["attributes"] = self.allowed_attributes
        # Without a CSSSanitizer, bleach emits NoCssSanitizerWarning and does
        # not filter inline CSS — any property an editor injects would survive.
        # Build one from the subclass allowlist when styles are declared.
        if self.allowed_styles is not None:
            kwargs["css_sanitizer"] = CSSSanitizer(
                allowed_css_properties=self.allowed_styles
            )
        result = bleach.clean(value, **kwargs)
        return _enforce_link_safety(result)

    def value_from_form(self, value):
        if self.sanitize_input:
            value = self.sanitize(value)
        return mark_safe(value)  # nosec
