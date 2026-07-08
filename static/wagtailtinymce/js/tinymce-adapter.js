/* eslint-disable func-names */
(function() {
    function initializeTinyMCE(el) {
        // This function is copied from:
        // https://github.com/jazzband/django-tinymce/blob/master/tinymce/static/django_tinymce/init_tinymce.js

        // initTinyMCE is not reachable outside of django-tinymce.
        // The alternative is to import admin/js/jquery.init.js. However, that breaks a lot more things in Wagtail editor.
        // Relevant issue: https://github.com/jazzband/django-tinymce/issues/385
        if (el.closest('.empty-form') === null) {  // Don't do empty inlines
            const mce_conf = JSON.parse(el.dataset.mceConf);

            // There is no way to pass a JavaScript function as an option
            // because all options are serialized as JSON.
            const fns = [
                'color_picker_callback',
                'file_browser_callback',
                'file_picker_callback',
                'images_dataimg_filter',
                'images_upload_handler',
                'paste_postprocess',
                'paste_preprocess',
                'setup',
                'urlconverter_callback',
            ];
            fns.forEach((fn_name) => {
                if (typeof mce_conf[fn_name] !== 'undefined') {
                    if (mce_conf[fn_name].includes('(')) {
                        // This is disabled since we are copying it from the django_tinymce package.
                        // eslint-disable-next-line no-eval
                        mce_conf[fn_name] = eval(`(${  mce_conf[fn_name]  })`);
                    } else {
                        mce_conf[fn_name] = window[mce_conf[fn_name]];
                    }
                }
            });

            const {id} = el;
            if ('elements' in mce_conf && mce_conf.mode === 'exact') {
                mce_conf.elements = id;
            }
            // The following eslint-disable-enxt-line no-undef
            // are set because those variables are defined via the JS files added
            // by the TinyMCE widget.
            if (el.dataset.mceGzConf && typeof tinyMCE_GZ !== 'undefined') {
                // eslint-disable-next-line no-undef
                tinyMCE_GZ.init(JSON.parse(el.dataset.mceGzConf));
            }
            // eslint-disable-next-line no-undef
            if (!tinyMCE.editors[id]) {
               // eslint-disable-next-line no-undef
               tinyMCE.init(mce_conf);
            }
        }
    }

    function WagtailTinyMCE(html, config) {
        this.html = html;
        this.baseConfig = config;
    }

    WagtailTinyMCE.prototype.render = function(placeholder, name, id, initialState) {
        placeholder.outerHTML = this.html.replace(/__NAME__/g, name).replace(/__ID__/g, id);

        const element = document.getElementById(id);
        element.value = initialState;

        initializeTinyMCE(element);

        // define public API functions for the widget:
        // https://docs.wagtail.io/en/latest/reference/streamfield/widget_api.html
        return {
            idForLabel: null,
            getValue() {
                return element.value;
            },
            getState() {
                return element.value;
            },
            setState() {
                throw new Error('WagtailTinyMCE.setState is not implemented');
            },
            getTextLabel(opts) {
                if (!element.value) return '';
                const maxLength = opts && opts.maxLength;
                const result = element.value;
                if (maxLength && result.length > maxLength) {
                    return `${result.substring(0, maxLength - 1)  }…`;
                }
                return result;
            },
            focus() {
                this.element.focus();
            }
        };
    };

    window.telepath.register('wagtailtinymce.widgets.WagtailTinyMCE', WagtailTinyMCE);
})();
