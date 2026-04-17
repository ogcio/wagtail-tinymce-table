import bleach
from django import forms
from django.utils.safestring import mark_safe
from wagtail.blocks import RawHTMLBlock

from .widgets import WagtailTinyMCE


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
        return bleach.clean(value, **kwargs)

    def value_from_form(self, value):
        if self.sanitize_input:
            value = self.sanitize(value)
        return mark_safe(value)  # nosec
