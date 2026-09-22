document.addEventListener('DOMContentLoaded', () => {
    const setBusy = (button, busy) => {
        if (!button) return;
        if (busy) {
            if (!button.dataset.originalLabel) button.dataset.originalLabel = button.textContent;
            button.disabled = true;
            button.setAttribute('aria-busy', 'true');
            if (button.dataset.busyLabel) button.textContent = button.dataset.busyLabel;
        } else {
            button.disabled = false;
            button.removeAttribute('aria-busy');
            if (button.dataset.originalLabel) button.textContent = button.dataset.originalLabel;
        }
    };

    const showError = (node, message) => {
        if (!node) return;
        node.textContent = message || '';
        node.hidden = !message;
        if (message) node.focus();
    };

    const showSuccess = (node, message) => {
        if (!node) return;
        node.textContent = message || '';
        node.hidden = !message;
    };

    const extractFilename = (contentDisposition) => {
        if (!contentDisposition) return '';
        const utf8 = contentDisposition.match(/filename\*=UTF-8''([^;]+)/i);
        if (utf8?.[1]) {
            try { return decodeURIComponent(utf8[1].replace(/^"|"$/g, '')); } catch (_) {}
        }
        const plain = contentDisposition.match(/filename="?([^";]+)"?/i);
        return plain?.[1] || '';
    };

    const downloadBlob = async (response) => {
        const blob = await response.blob();
        const url = URL.createObjectURL(blob);
        const anchor = document.createElement('a');
        anchor.href = url;
        anchor.download = extractFilename(response.headers.get('Content-Disposition')) || 'paxalia-package.paxalia';
        anchor.style.display = 'none';
        document.body.appendChild(anchor);
        anchor.click();
        anchor.remove();
        window.setTimeout(() => URL.revokeObjectURL(url), 1000);
    };

    const extractServerError = async (response, fallback = '') => {
        const contentType = (response.headers.get('Content-Type') || '').toLowerCase();
        if (!contentType.includes('text/html')) {
            return fallback;
        }
        try {
            const html = await response.text();
            const doc = new DOMParser().parseFromString(html, 'text/html');
            const node = doc.querySelector('[data-paxalia-export-error]:not([hidden])');
            const message = node?.textContent?.trim();
            if (message) return message;
            const djangoMessage = doc.querySelector('.analytics-message--error, .analytics-message--warning');
            if (djangoMessage?.textContent?.trim()) return djangoMessage.textContent.trim();
        } catch (_) {}
        return response.status >= 400 ? fallback : fallback;
    };

    const submitExportAsDownload = async (form, button, errorNode, successNode) => {
        const genericError = errorNode?.dataset.genericError || '';
        const networkError = errorNode?.dataset.networkError || genericError;
        const noDownload = errorNode?.dataset.noDownload || genericError;
        setBusy(button, true);
        showError(errorNode, '');
        showSuccess(successNode, '');
        try {
            const response = await fetch(form.action || window.location.href, {
                method: 'POST',
                body: new FormData(form),
                credentials: 'same-origin',
                cache: 'no-store',
                headers: { Accept: 'application/octet-stream, text/html;q=0.9' },
            });
            const disposition = response.headers.get('Content-Disposition') || '';
            const contentType = (response.headers.get('Content-Type') || '').toLowerCase();
            const isDownload = disposition.toLowerCase().includes('attachment') || contentType.includes('application/octet-stream');
            if (!response.ok) {
                throw new Error(await extractServerError(response, genericError));
            }
            if (!isDownload) {
                throw new Error(await extractServerError(response, noDownload));
            }
            await downloadBlob(response);
            showSuccess(successNode, successNode?.dataset.successLabel || '');
        } catch (error) {
            const message = error?.name === 'TypeError' ? networkError : (error?.message || genericError);
            showError(errorNode, message);
        } finally {
            setBusy(button, false);
        }
    };

    document.querySelectorAll('[data-paxalia-admin-list]').forEach((root) => {
        const selectAll = root.querySelector('[data-paxalia-select-all]');
        const selectionCount = root.querySelector('[data-paxalia-selection-count]');
        const actionSelect = root.querySelector('[data-paxalia-action-select]');
        const runButton = root.querySelector('[data-paxalia-run-action]');
        const exportButton = root.querySelector('[data-paxalia-export-selected]');
        const items = () => Array.from(root.querySelectorAll('[data-paxalia-select-item]'));

        const syncSelectionState = () => {
            const allItems = items();
            const selected = allItems.filter((item) => item.checked).length;
            if (selectAll) {
                selectAll.checked = allItems.length > 0 && selected === allItems.length;
                selectAll.indeterminate = selected > 0 && selected < allItems.length;
            }
            if (selectionCount) {
                const suffix = selectionCount.dataset.selectedSuffix || '';
                selectionCount.textContent = suffix ? `${selected} ${suffix}` : String(selected);
            }
            if (runButton) runButton.disabled = selected === 0 || !actionSelect?.value;
            if (exportButton) exportButton.disabled = selected === 0;
        };

        selectAll?.addEventListener('change', () => {
            items().forEach((item) => { item.checked = selectAll.checked; });
            syncSelectionState();
        });
        items().forEach((item) => item.addEventListener('change', syncSelectionState));
        actionSelect?.addEventListener('change', syncSelectionState);

        root.addEventListener('submit', (event) => {
            const submitter = event.submitter;
            const selected = items().filter((item) => item.checked);
            if (submitter?.matches('[data-paxalia-export-selected]')) {
                if (!selected.length) event.preventDefault();
                return;
            }
            if (submitter?.name === '_save' && submitter?.value === '1') {
                return;
            }
            const action = actionSelect?.value;
            if (!action || !selected.length) event.preventDefault();
        });
        syncSelectionState();
    });

    document.querySelectorAll('[data-pa-app-toggle]').forEach((button) => {
        const targetId = button.getAttribute('aria-controls');
        const target = targetId ? document.getElementById(targetId) : null;
        if (!target) return;
        const sync = () => {
            const expanded = button.getAttribute('aria-expanded') === 'true';
            target.hidden = !expanded;
            button.classList.toggle('is-open', expanded);
        };
        button.addEventListener('click', () => {
            button.setAttribute('aria-expanded', String(button.getAttribute('aria-expanded') !== 'true'));
            sync();
        });
        sync();
    });

    document.querySelectorAll('[data-paxalia-model-browser]').forEach((root) => {
        const input = root.querySelector('[data-pa-model-search]');
        const groups = () => Array.from(root.querySelectorAll('[data-pa-app-group]'));
        const resultCount = root.querySelector('[data-pa-model-result-count]');
        const emptyState = root.querySelector('[data-pa-model-empty-state]');
        const noResults = root.querySelector('[data-pa-model-no-results]');
        const showAll = root.querySelector('[data-pa-show-all-models]');
        const filter = () => {
            const query = (input?.value || '').trim().toLowerCase();
            let visible = 0;
            groups().forEach((group) => {
                let groupVisible = 0;
                group.querySelectorAll('[data-pa-model-card]').forEach((card) => {
                    const match = !query || card.dataset.modelSearch.includes(query);
                    card.hidden = !match;
                    if (match) groupVisible += 1;
                });
                group.hidden = groupVisible === 0;
                if (query && groupVisible > 0) {
                    const toggle = group.querySelector('[data-pa-app-toggle]');
                    if (toggle && toggle.getAttribute('aria-expanded') !== 'true') {
                        toggle.setAttribute('aria-expanded', 'true');
                        const panel = document.getElementById(toggle.getAttribute('aria-controls'));
                        if (panel) panel.hidden = false;
                    }
                }
                visible += groupVisible;
            });
            if (resultCount) resultCount.textContent = String(visible);
            if (emptyState) emptyState.hidden = visible !== 0;
            if (noResults) noResults.hidden = !query || visible !== 0;
        };
        input?.addEventListener('input', filter);
        showAll?.addEventListener('click', () => {
            groups().forEach((group) => {
                group.hidden = false;
                const toggle = group.querySelector('[data-pa-app-toggle]');
                const panel = document.getElementById(toggle?.getAttribute('aria-controls') || '');
                if (toggle) toggle.setAttribute('aria-expanded', 'true');
                if (panel) panel.hidden = false;
            });
            if (input) input.value = '';
            filter();
        });
        filter();
    });

    document.querySelectorAll('[data-paxalia-single-export]').forEach((root) => {
        const encrypted = root.querySelector('[data-single-export-encrypted]');
        const passwordWrap = root.querySelector('[data-single-export-password]');
        const password = root.querySelector('input[name="password"]');
        const submit = root.querySelector('[data-single-export-submit]');
        const error = root.querySelector('[data-single-export-error]');
        const success = root.querySelector('[data-single-export-success]');
        const sync = () => {
            const enabled = Boolean(encrypted?.checked);
            passwordWrap?.classList.toggle('is-visible', enabled);
            if (password) password.required = enabled;
        };
        encrypted?.addEventListener('change', sync);
        root.addEventListener('submit', (event) => {
            event.preventDefault();
            const protectedSelected = root.dataset.singleExportProtected === 'true';
            const requireEncryptionForProtected = root.dataset.singleExportRequireEncryption !== 'false';
            if (requireEncryptionForProtected && protectedSelected && !encrypted?.checked) {
                showError(error, error?.dataset.protectedRequired || '');
                encrypted?.focus();
                return;
            }
            if (encrypted?.checked && !password?.value.trim()) {
                showError(error, error?.dataset.passwordRequired || '');
                password?.focus();
                return;
            }
            submitExportAsDownload(root, submit, error, success);
        });
        sync();
    });

    document.querySelectorAll('[data-paxalia-package-export]').forEach((root) => {
        const boxes = () => Array.from(root.querySelectorAll('input[name="models"]'));
        const search = root.querySelector('[data-package-model-search]');
        const selectedCount = root.querySelector('[data-package-selected-count]');
        const submit = root.querySelector('[data-package-submit]');
        const error = root.querySelector('[data-paxalia-export-error]');
        const success = root.querySelector('[data-paxalia-export-success]');
        const encrypted = root.querySelector('input[name="encrypted"]');
        const password = root.querySelector('input[name="password"]');
        const passwordField = root.querySelector('[data-package-password-field]');
        const requireEncryptionForProtected = root.dataset.requireEncryptionForProtected === 'true';

        const sync = () => {
            const selected = boxes().filter((box) => box.checked).length;
            if (selectedCount) selectedCount.textContent = String(selected);
            if (submit) submit.disabled = selected === 0;
            if (encrypted && password) password.required = encrypted.checked;
            passwordField?.classList.toggle('is-required', Boolean(encrypted?.checked));
        };

        root.querySelector('[data-package-select-all]')?.addEventListener('click', () => {
            const visible = boxes().filter((box) => !box.closest('[data-package-model-row]')?.hidden);
            const next = !visible.length || visible.some((box) => !box.checked);
            visible.forEach((box) => { box.checked = next; });
            sync();
        });
        boxes().forEach((box) => box.addEventListener('change', sync));
        encrypted?.addEventListener('change', sync);
        search?.addEventListener('input', () => {
            const query = search.value.trim().toLowerCase();
            root.querySelectorAll('[data-package-model-row]').forEach((row) => {
                row.hidden = Boolean(query) && !row.dataset.packageModel.includes(query);
            });
            root.querySelectorAll('[data-package-app]').forEach((app) => {
                const visible = Array.from(app.querySelectorAll('[data-package-model-row]')).some((row) => !row.hidden);
                app.hidden = !visible;
                if (query && visible) app.open = true;
            });
        });
        root.addEventListener('submit', (event) => {
            event.preventDefault();
            const selected = boxes().filter((box) => box.checked);
            if (!selected.length) {
                showError(error, error?.dataset.selectionRequired || '');
                return;
            }
            const protectedSelected = selected.some((box) => box.dataset.packageProtected === 'true');
            if (requireEncryptionForProtected && protectedSelected && !encrypted?.checked) {
                showError(error, error?.dataset.protectedRequired || '');
                encrypted?.focus();
                return;
            }
            if (encrypted?.checked && !password?.value.trim()) {
                showError(error, error?.dataset.passwordRequired || '');
                password?.focus();
                return;
            }
            submitExportAsDownload(root, submit, error, success);
        });
        sync();
    });

    document.querySelectorAll('[data-paxalia-confirm-form]').forEach((form) => {
        form.addEventListener('submit', (event) => {
            const message = form.dataset.confirmMessage;
            if (message && !window.confirm(message)) event.preventDefault();
        });
    });

    document.querySelectorAll('[data-pa-translation-editor]').forEach((editor) => {
        const buttons = Array.from(editor.querySelectorAll('[data-pa-language-tab]'));
        const panes = Array.from(editor.querySelectorAll('[data-pa-language-pane]'));
        const activate = (code, focus = false) => {
            buttons.forEach((button) => {
                const active = button.dataset.paLanguageTab === code;
                button.setAttribute('aria-selected', String(active));
                button.setAttribute('tabindex', active ? '0' : '-1');
                button.classList.toggle('is-active', active);
                if (active && focus) button.focus();
            });
            panes.forEach((pane) => {
                const active = pane.dataset.paLanguagePane === code;
                pane.hidden = !active;
                if (active) pane.setAttribute('aria-hidden', 'false');
                else pane.setAttribute('aria-hidden', 'true');
            });
        };
        buttons.forEach((button, index) => {
            button.addEventListener('click', () => activate(button.dataset.paLanguageTab, false));
            button.addEventListener('keydown', (event) => {
                if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) return;
                event.preventDefault();
                let next = index;
                if (event.key === 'Home') next = 0;
                else if (event.key === 'End') next = buttons.length - 1;
                else if (event.key === 'ArrowRight') next = (index + 1) % buttons.length;
                else if (event.key === 'ArrowLeft') next = (index - 1 + buttons.length) % buttons.length;
                activate(buttons[next].dataset.paLanguageTab, true);
            });
        });
        activate(editor.dataset.defaultLanguage || buttons[0]?.dataset.paLanguageTab || '');
    });
});
