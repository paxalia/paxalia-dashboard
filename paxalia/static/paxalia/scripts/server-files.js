(function () {
    "use strict";

    function submitFilter(control) {
        var form = control && control.form;
        if (!form) return;
        if (typeof form.requestSubmit === "function") {
            form.requestSubmit();
        } else {
            form.submit();
        }
    }

    function setValue(selector, value) {
        var element = document.querySelector(selector);
        if (element) element.value = value || "";
    }

    function getManagePanel() {
        return document.getElementById("sf-management-panel");
    }

    function openManagePanel(button) {
        var panel = getManagePanel();
        if (!panel || !button) return;

        var root = button.getAttribute("data-root") || "";
        var path = button.getAttribute("data-path") || "";
        var name = button.getAttribute("data-name") || "";
        var kind = button.getAttribute("data-kind") || "";
        var isFile = button.getAttribute("data-is-file") === "1";
        var parentPath = button.getAttribute("data-parent-path") || "";
        var displayPath = path ? "/" + path : "/";

        setValue("[data-sf-manage-root]", root);
        setValue("[data-sf-manage-path-input]", path);
        setValue("[data-sf-manage-rename]", name);
        setValue("[data-sf-manage-copy-root]", root);
        setValue("[data-sf-manage-copy-path]", path);
        setValue("[data-sf-manage-copy-name]", "copy-" + name);
        setValue("[data-sf-manage-move-root]", root);
        setValue("[data-sf-manage-move-path]", path);
        setValue("[data-sf-manage-move-name]", name);
        setValue("[data-sf-manage-delete-root]", root);
        setValue("[data-sf-manage-delete-path]", path);
        setValue("[data-sf-manage-target-path]", parentPath);

        var nameTarget = document.querySelector("[data-sf-manage-name]");
        var pathTarget = document.querySelector("[data-sf-manage-path]");
        if (nameTarget) nameTarget.textContent = name;
        if (pathTarget) pathTarget.textContent = kind ? kind + " · " + displayPath : displayPath;

        var target = document.querySelector("[data-sf-manage-target]");
        if (target) target.hidden = false;

        var copyForm = document.querySelector("[data-sf-manage-copy-form]");
        if (copyForm) copyForm.hidden = !isFile;

        panel.hidden = false;
        panel.setAttribute("aria-expanded", "true");
        panel.scrollIntoView({ behavior: "smooth", block: "start" });

        var renameInput = document.querySelector("[data-sf-manage-rename]");
        if (renameInput) renameInput.focus();
    }

    function closeManagePanel() {
        var panel = getManagePanel();
        if (!panel) return;
        panel.hidden = true;
        panel.setAttribute("aria-expanded", "false");
    }

    document.addEventListener("change", function (event) {
        var target = event.target;
        if (!target || !target.matches) return;

        if (target.matches(".sf-filter-bar input[type=\"checkbox\"]")) {
            submitFilter(target);
        }
    });

    document.addEventListener("click", function (event) {
        var manage = event.target && event.target.closest ? event.target.closest("[data-sf-manage]") : null;
        if (manage) {
            event.preventDefault();
            openManagePanel(manage);
            return;
        }

        var close = event.target && event.target.closest ? event.target.closest("[data-sf-manage-close]") : null;
        if (close) {
            event.preventDefault();
            closeManagePanel();
        }
    });

    document.addEventListener("submit", function (event) {
        var form = event.target;
        if (!(form instanceof HTMLFormElement)) return;

        var message = form.getAttribute("data-confirm");
        if (message && !window.confirm(message)) {
            event.preventDefault();
            return;
        }

        if (form.matches(".sf-filter-bar")) {
            var submit = form.querySelector("button[type=\"submit\"]");
            if (submit) {
                submit.disabled = true;
                submit.setAttribute("aria-busy", "true");
            }
        }

        if (form.matches(".sf-form, .sf-manage-form, .sf-reauth-form")) {
            var actionButton = form.querySelector("button[type=\"submit\"]");
            if (actionButton) {
                actionButton.disabled = true;
                actionButton.setAttribute("aria-busy", "true");
            }
        }
    });
}());
