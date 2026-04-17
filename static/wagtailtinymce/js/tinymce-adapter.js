/* eslint-disable func-names */
(function() {
    // Named callback registry.  TinyMCE config options that require a real
    // function (setup, file_picker_callback, etc.) are serialised as plain
    // string keys in the JSON data attribute.  The adapter resolves each key
    // against this registry first, then against window.<key>, and rejects
    // anything else — no eval() is used.
    //
    // Consuming projects can register their own callbacks before TinyMCE
    // initialises by adding entries to window.wagtailTinyMCECallbacks:
    //
    //   window.wagtailTinyMCECallbacks = window.wagtailTinyMCECallbacks || {};
    //   window.wagtailTinyMCECallbacks['mySetup'] = function(editor) { ... };
    window.wagtailTinyMCECallbacks = window.wagtailTinyMCECallbacks || {};

    // Built-in: registers the "Footer Row" toolbar button for TinyMCETableBlock.
    // Python-side config references this by the key 'tablefooterrow'.
    window.wagtailTinyMCECallbacks['tablefooterrow'] = function(editor) {
        editor.ui.registry.addButton('tablefooterrow', {
            text: 'Footer Row',
            tooltip: 'Toggle selected row as table footer',
            onAction: () => {
                const node = editor.selection.getNode();
                const row = editor.dom.getParent(node, 'tr');
                if (!row) return;
                const parent = row.parentNode;
                const table = editor.dom.getParent(row, 'table');
                if (!table) return;
                if (parent.tagName.toLowerCase() === 'tfoot') {
                    let tbody = table.querySelector('tbody');
                    if (!tbody) {
                        tbody = editor.dom.create('tbody');
                        table.appendChild(tbody);
                    }
                    tbody.appendChild(row);
                    if (!parent.hasChildNodes()) parent.remove();
                } else {
                    let tfoot = table.querySelector('tfoot');
                    if (!tfoot) {
                        tfoot = editor.dom.create('tfoot');
                        table.appendChild(tfoot);
                    }
                    tfoot.appendChild(row);
                    if (!parent.hasChildNodes()) parent.remove();
                }
            },
        });
    };

    function initializeTinyMCE(el) {
        // initTinyMCE is not reachable outside of django-tinymce.
        // The alternative is to import admin/js/jquery.init.js. However, that breaks a lot more things in Wagtail editor.
        // Relevant issue: https://github.com/jazzband/django-tinymce/issues/385
        if (el.closest('.empty-form') === null) {  // Don't do empty inlines
            const mce_conf = JSON.parse(el.dataset.mceConf);

            // TinyMCE callback options cannot be passed as functions through
            // JSON, so they are serialised as string keys.  Resolve each key
            // via the named registry or window.<key>; never eval().
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
                if (typeof mce_conf[fn_name] === 'undefined') return;
                const key = mce_conf[fn_name];
                if (typeof window.wagtailTinyMCECallbacks[key] === 'function') {
                    mce_conf[fn_name] = window.wagtailTinyMCECallbacks[key];
                } else if (typeof window[key] === 'function') {
                    mce_conf[fn_name] = window[key];
                } else {
                    // Unknown key: warn and remove rather than silently fail or eval.
                    // Register custom callbacks via window.wagtailTinyMCECallbacks.
                    console.warn(
                        'wagtailTinyMCE: unknown callback key "' + key +
                        '" for option "' + fn_name + '" — ignored. ' +
                        'Register it via window.wagtailTinyMCECallbacks["' + key + '"].'
                    );
                    delete mce_conf[fn_name];
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
            if (!tinyMCE.get(id)) {
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
