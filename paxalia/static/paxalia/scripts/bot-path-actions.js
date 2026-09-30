document.addEventListener('DOMContentLoaded', function () {
    document.querySelectorAll('[data-bot-path-form]').forEach(function (form) {
        form.addEventListener('submit', function (event) {
            if (form.dataset.confirmed === '1') return;
            var input = form.querySelector('input[name="path"]');
            var remove = form.querySelector('input[name="remove_normal_views"]');
            var path = input ? input.value : '';
            var cleanup = !remove || remove.value !== '0';
            var message = cleanup
                ? 'Add "' + path + '" to Bot/Scanner path prefixes and remove matching normal page-view records in the current filtered scope?'
                : 'Add "' + path + '" to Bot/Scanner path prefixes?';
            if (!window.confirm(message)) {
                event.preventDefault();
                return;
            }
            form.dataset.confirmed = '1';
        });
    });
});
