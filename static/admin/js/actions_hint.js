document.addEventListener('DOMContentLoaded', function() {
    const actionSelect = document.querySelector('select[name="action"]');
    const runButton = document.querySelector('.actions button[type="submit"]');

    if (!runButton || !actionSelect) return;

    // Создаем подсказку
    const hint = document.createElement('div');
    hint.id = 'run-hint';
    hint.innerHTML = 'Нажмите здесь для запуска<div id="hint-arrow"></div>';

    // Добавляем в body, чтобы избежать проблем с overflow родительских блоков
    document.body.appendChild(hint);

    function positionHint() {
        const rect = runButton.getBoundingClientRect();
        const hintRect = hint.getBoundingClientRect();

        // Позиционируем по центру кнопки с учетом прокрутки
        hint.style.top = (rect.top + window.scrollY - hintRect.height - 12) + 'px';
        hint.style.left = (rect.left + window.scrollX + (rect.width / 2) - (hintRect.width / 2)) + 'px';
    }

    function toggleHint() {
        const checkboxes = document.querySelectorAll('input.action-select:checked');
        const isActionChosen = actionSelect.value !== '';

        if (checkboxes.length > 0 && isActionChosen) {
            hint.classList.add('visible');
            positionHint();
            runButton.classList.add('pulse-active');
        } else {
            hint.classList.remove('visible');
            runButton.classList.remove('pulse-active');
        }
    }

    // Пересчитываем позицию при изменении окна или скролле
    window.addEventListener('resize', positionHint);
    window.addEventListener('scroll', positionHint);

    actionSelect.addEventListener('change', toggleHint);
    document.addEventListener('change', function(e) {
        if (e.target.classList.contains('action-select') || e.target.id === 'action-toggle') {
            toggleHint();
        }
    });
});