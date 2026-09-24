(function () {
    'use strict';

    var authBody = document.body;

    function attr(name, fallback) {
        return authBody ? (authBody.getAttribute(name) || fallback) : fallback;
    }

    function csrfToken() {
        var meta = document.querySelector('meta[name="csrf-token"]');
        if (meta && meta.content && meta.content !== 'NOTPROVIDED') return meta.content;
        var match = document.cookie.match(/(?:^|; )csrftoken=([^;]+)/);
        return match ? decodeURIComponent(match[1]) : '';
    }

    var defaultShow = attr('data-auth-password-show', 'Show');
    var defaultHide = attr('data-auth-password-hide', 'Hide');
    var defaultShowLabel = attr('data-auth-password-show-label', 'Show password');
    var defaultHideLabel = attr('data-auth-password-hide-label', 'Hide password');
    var genericError = attr('data-auth-generic-error', 'The request could not be completed.');

    document.querySelectorAll('[data-password-toggle]').forEach(function (button) {
        var target = document.getElementById(button.getAttribute('data-password-toggle'));
        if (!target) return;
        var showText = button.getAttribute('data-show-label') || defaultShow;
        var hideText = button.getAttribute('data-hide-label') || defaultHide;
        button.addEventListener('click', function () {
            var visible = target.type === 'text';
            target.type = visible ? 'password' : 'text';
            button.textContent = visible ? showText : hideText;
            button.setAttribute('aria-label', visible ? defaultShowLabel : defaultHideLabel);
            button.setAttribute('aria-pressed', String(!visible));
        });
    });

    var otpGrid = document.querySelector('[data-otp-grid]');
    if (otpGrid) {
        var hidden = document.getElementById('paxaliaOtpToken');
        var digits = Array.prototype.slice.call(otpGrid.querySelectorAll('.paxalia-otp-digit'));
        digits.forEach(function (input, index) {
            input.addEventListener('input', function () {
                input.value = (input.value || '').replace(/\D/g, '').slice(0, 1);
                if (input.value && index < digits.length - 1) digits[index + 1].focus();
                if (hidden) hidden.value = digits.map(function (field) { return field.value; }).join('');
            });
            input.addEventListener('keydown', function (event) {
                if (event.key === 'Backspace' && !input.value && index > 0) {
                    digits[index - 1].value = '';
                    digits[index - 1].focus();
                    event.preventDefault();
                } else if (event.key === 'ArrowLeft' && index > 0) {
                    digits[index - 1].focus();
                    event.preventDefault();
                } else if (event.key === 'ArrowRight' && index < digits.length - 1) {
                    digits[index + 1].focus();
                    event.preventDefault();
                }
            });
            input.addEventListener('paste', function (event) {
                var clipboard = event.clipboardData || window.clipboardData;
                event.preventDefault();
                var text = ((clipboard && clipboard.getData('text')) || '').replace(/\D/g, '').slice(0, digits.length);
                text.split('').forEach(function (character, idx) {
                    if (digits[idx]) digits[idx].value = character;
                });
                if (hidden) hidden.value = digits.map(function (field) { return field.value; }).join('');
                var next = digits.findIndex(function (field) { return !field.value; });
                var focusTarget = digits[next >= 0 ? next : digits.length - 1] || input;
                focusTarget.focus();
            });
        });

        var form = otpGrid.closest('form');
        if (form) {
            form.addEventListener('submit', function (event) {
                if (hidden) hidden.value = digits.map(function (field) { return field.value; }).join('');
                if (!hidden || hidden.value.length !== digits.length) {
                    event.preventDefault();
                    var target = document.querySelector('[data-auth-error]');
                    if (target) {
                        target.textContent = otpGrid.closest('[data-auth-step="2fa"]') ?
                            (otpGrid.closest('[data-auth-step="2fa"]').getAttribute('data-otp-incomplete-message') || 'Enter the complete verification code.') :
                            'Enter the complete verification code.';
                        target.hidden = false;
                    }
                }
            });
        }
    }

    function copyText(value) {
        if (navigator.clipboard && window.isSecureContext) {
            return navigator.clipboard.writeText(value);
        }
        return new Promise(function (resolve, reject) {
            var area = document.createElement('textarea');
            area.value = value;
            area.setAttribute('readonly', '');
            area.style.position = 'fixed';
            area.style.opacity = '0';
            document.body.appendChild(area);
            area.select();
            try {
                var copied = document.execCommand('copy');
                document.body.removeChild(area);
                if (copied) resolve(); else reject(new Error('copy-failed'));
            } catch (error) {
                document.body.removeChild(area);
                reject(error);
            }
        });
    }

    document.querySelectorAll('[data-copy-value], [data-copy-target]').forEach(function (button) {
        button.addEventListener('click', function () {
            var value = button.getAttribute('data-copy-value') || '';
            if (!value) {
                var target = document.getElementById(button.getAttribute('data-copy-target') || '');
                value = target ? target.textContent.replace(/\\s+/g, '') : '';
            }
            if (!value) return;
            var original = button.textContent;
            var copiedLabel = button.getAttribute('data-copy-success') || 'Copied';
            var errorLabel = button.getAttribute('data-copy-error') || 'Copy failed';
            copyText(value).then(function () {
                button.textContent = copiedLabel;
                window.setTimeout(function () { button.textContent = original; }, 1800);
            }).catch(function () {
                button.textContent = errorLabel;
                window.setTimeout(function () { button.textContent = original; }, 1800);
            });
        });
    });

    document.querySelectorAll('[data-download-recovery]').forEach(function (button) {
        button.addEventListener('click', function () {
            var selector = button.getAttribute('data-recovery-selector') || '.paxalia-recovery-grid code';
            var codes = Array.prototype.map.call(
                document.querySelectorAll(selector),
                function (element) { return (element.textContent || '').trim(); }
            ).filter(Boolean);
            if (!codes.length) return;

            var content = codes.join('\n') + '\n';
            var blob = new Blob([content], { type: 'text/plain;charset=utf-8' });
            var url = URL.createObjectURL(blob);
            var link = document.createElement('a');
            link.href = url;
            link.download = button.getAttribute('data-download-name') || 'paxalia-backup-codes.txt';
            link.style.display = 'none';
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);
            window.setTimeout(function () { URL.revokeObjectURL(url); }, 1000);
        });
    });

    document.querySelectorAll('.paxalia-auth-form').forEach(function (form) {
        form.addEventListener('submit', function () {
            var button = form.querySelector('.paxalia-auth-submit[type="submit"]');
            if (button) {
                button.disabled = true;
                button.setAttribute('aria-busy', 'true');
            }
        });
    });

    window.PaxaliaAuth = {
        csrfToken: csrfToken,
        postJson: function (url, payload) {
            return fetch(url, {
                method: 'POST',
                credentials: 'same-origin',
                headers: {
                    'Content-Type': 'application/json',
                    'Accept': 'application/json',
                    'X-CSRFToken': csrfToken(),
                    'X-Requested-With': 'XMLHttpRequest'
                },
                body: JSON.stringify(payload || {})
            }).then(function (response) {
                return response.json().catch(function () { return {}; }).then(function (data) {
                    if (!response.ok) {
                        var error = new Error(data.detail || genericError);
                        error.status = response.status;
                        throw error;
                    }
                    return data;
                });
            });
        }
    };
}());

