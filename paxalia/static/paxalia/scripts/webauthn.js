(function () {
    'use strict';

    function bytesToBase64Url(bytes) {
        var binary = '';
        for (var i = 0; i < bytes.length; i++) binary += String.fromCharCode(bytes[i]);
        return btoa(binary).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/g, '');
    }

    function base64UrlToBytes(value) {
        var normalized = String(value || '').replace(/-/g, '+').replace(/_/g, '/');
        while (normalized.length % 4) normalized += '=';
        var binary = atob(normalized);
        var bytes = new Uint8Array(binary.length);
        for (var i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);
        return bytes;
    }

    function toBuffer(value) {
        return value instanceof Uint8Array ? value : base64UrlToBytes(value).buffer;
    }

    function prepareOptions(options, mode) {
        var prepared = Object.assign({}, options);
        prepared.challenge = toBuffer(options.challenge);
        if (mode === 'register' && options.user && options.user.id) {
            prepared.user = Object.assign({}, options.user, { id: toBuffer(options.user.id) });
        }
        var collectionKey = mode === 'register' ? 'excludeCredentials' : 'allowCredentials';
        if (Array.isArray(options[collectionKey])) {
            prepared[collectionKey] = options[collectionKey].map(function (item) {
                return Object.assign({}, item, { id: toBuffer(item.id) });
            });
        }
        return prepared;
    }

    function registrationPayload(credential) {
        return {
            id: credential.id,
            rawId: bytesToBase64Url(new Uint8Array(credential.rawId)),
            response: {
                clientDataJSON: bytesToBase64Url(new Uint8Array(credential.response.clientDataJSON)),
                attestationObject: bytesToBase64Url(new Uint8Array(credential.response.attestationObject)),
                transports: credential.response.getTransports ? credential.response.getTransports() : []
            },
            type: credential.type,
            authenticatorAttachment: credential.authenticatorAttachment || null,
            clientExtensionResults: credential.getClientExtensionResults ? credential.getClientExtensionResults() : {}
        };
    }

    function authenticationPayload(credential) {
        return {
            id: credential.id,
            rawId: bytesToBase64Url(new Uint8Array(credential.rawId)),
            response: {
                clientDataJSON: bytesToBase64Url(new Uint8Array(credential.response.clientDataJSON)),
                authenticatorData: bytesToBase64Url(new Uint8Array(credential.response.authenticatorData)),
                signature: bytesToBase64Url(new Uint8Array(credential.response.signature)),
                userHandle: credential.response.userHandle ? bytesToBase64Url(new Uint8Array(credential.response.userHandle)) : null
            },
            type: credential.type,
            authenticatorAttachment: credential.authenticatorAttachment || null,
            clientExtensionResults: credential.getClientExtensionResults ? credential.getClientExtensionResults() : {}
        };
    }

    function setStatus(element, text, kind) {
        if (!element) return;
        element.textContent = text;
        element.className = 'paxalia-auth-callout' + (kind ? ' paxalia-auth-callout--' + kind : '');
    }

    function start(card) {
        var mode = card.getAttribute('data-webauthn-mode');
        var optionsUrl = card.getAttribute('data-options-url');
        var verifyUrl = card.getAttribute('data-verify-url');
        var status = card.querySelector('#paxaliaWebAuthnStatus');
        var button = card.querySelector('#paxaliaWebAuthnButton');
        var nameInput = card.querySelector('#paxaliaDeviceName');
        if (!mode || !optionsUrl || !verifyUrl || !button) return;

        function message(name, fallback) {
            return (status && status.getAttribute('data-message-' + name)) || fallback;
        }

        if (card.getAttribute('data-webauthn-server-unavailable') === 'true') {
            setStatus(status, message('server-unavailable', 'The WebAuthn server dependency is not installed.'), 'danger');
            button.disabled = true;
            return;
        }

        if (card.getAttribute('data-webauthn-localhost-required') === 'true') {
            setStatus(status, message('localhost-required', 'For local development, open Paxalia Dashboard using http://localhost instead of a loopback IP such as 127.0.0.1.'), 'danger');
            button.disabled = true;
            return;
        }

        if (!window.PublicKeyCredential || !navigator.credentials || !window.isSecureContext) {
            setStatus(status, message('unsupported', 'A supported WebAuthn authenticator is required in a secure browser context.'), 'danger');
            button.disabled = true;
            return;
        }

        button.addEventListener('click', function () {
            button.disabled = true;
            button.setAttribute('aria-busy', 'true');
            setStatus(status, mode === 'register' ? message('prepare-register', 'Preparing secure device registration…') : message('prepare', 'Preparing secure authenticator verification…'));

            if (!window.PaxaliaAuth || typeof window.PaxaliaAuth.postJson !== 'function') {
                setStatus(status, message('client-unavailable', 'The Paxalia authentication client could not be loaded. Refresh the page and try again.'), 'danger');
                button.disabled = false;
                button.removeAttribute('aria-busy');
                return;
            }

            var startRequest;
            if (mode === 'register') {
                startRequest = window.PaxaliaAuth.postJson(optionsUrl, {
                    device_name: nameInput ? nameInput.value : ''
                });
            } else {
                startRequest = fetch(optionsUrl, {
                    credentials: 'same-origin',
                    headers: { 'Accept': 'application/json' }
                }).then(function (response) {
                    return response.json().then(function (data) {
                        if (!response.ok) {
                            var error = new Error(data.detail || 'Could not start authenticator verification.');
                            error.status = response.status;
                            throw error;
                        }
                        return data;
                    });
                });
            }

            startRequest.then(function (startData) {
                if (!startData.challenge_id || !startData.options) {
                    throw new Error(message('incomplete', 'The authenticator challenge was incomplete.'));
                }
                var publicKey = prepareOptions(startData.options, mode);
                setStatus(status, mode === 'register' ? message('ready-register', 'Complete the authenticator prompt to register this device.') : message('ready', 'Complete the authenticator prompt to verify this device.'));
                var ceremony = mode === 'register'
                    ? navigator.credentials.create({ publicKey: publicKey })
                    : navigator.credentials.get({ publicKey: publicKey });
                return Promise.resolve(ceremony).then(function (credential) {
                    if (!credential) throw new Error(message('no-response', 'No authenticator response was returned.'));
                    return window.PaxaliaAuth.postJson(verifyUrl, {
                        challenge_id: startData.challenge_id,
                        credential: mode === 'register' ? registrationPayload(credential) : authenticationPayload(credential)
                    });
                });
            }).then(function (result) {
                setStatus(status, message('complete', 'Verification complete. Redirecting…'));
                if (!result || !result.redirect) {
                    throw new Error('The server did not provide a valid Paxalia administrator destination.');
                }
                window.location.assign(result.redirect);
            }).catch(function (error) {
                var errorMessage = error && error.message ? error.message : message('error', 'The authenticator operation could not be completed.');
                if (error && error.name === 'NotAllowedError') {
                    errorMessage = message('not-allowed', 'The authenticator operation was cancelled, timed out, or was not allowed by the selected authenticator.');
                } else if (error && error.name === 'InvalidStateError') {
                    errorMessage = message('invalid-state', 'This authenticator is already registered for this administrator. Choose another authenticator.');
                } else if (error && error.name === 'ConstraintError') {
                    errorMessage = message('constraint', 'The selected authenticator cannot satisfy Paxalia’s required passkey and user-verification security policy.');
                }
                setStatus(status, errorMessage, 'danger');
                button.disabled = false;
                button.removeAttribute('aria-busy');
            });
        });
    }

    document.querySelectorAll('[data-webauthn-mode]').forEach(start);
}());

