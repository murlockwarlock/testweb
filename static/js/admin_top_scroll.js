document.addEventListener("DOMContentLoaded", function () {
    const resultsDiv = document.querySelector('.results');
    if (!resultsDiv) return;

    // Создаем контейнер для верхнего скролла
    const topScroll = document.createElement('div');
    topScroll.className = 'top-scroll-container';
    topScroll.style.overflowX = 'auto';
    topScroll.style.overflowY = 'hidden';
    topScroll.style.width = '100%';
    topScroll.style.marginBottom = '0px'; // Отступ от таблицы
    topScroll.style.position = 'sticky';
    topScroll.style.top = '0';
    topScroll.style.zIndex = '100';

    // Внутренний блок для эмуляции ширины контента
    const innerDiv = document.createElement('div');
    innerDiv.style.width = resultsDiv.scrollWidth + 'px';
    innerDiv.style.height = '1px'; // Минимальная высота для отображения скролла

    topScroll.appendChild(innerDiv);

    // Вставляем скролл перед блоком .results
    resultsDiv.parentNode.insertBefore(topScroll, resultsDiv);

    // Синхронизация скролла (сверху -> вниз)
    topScroll.addEventListener('scroll', function () {
        resultsDiv.scrollLeft = topScroll.scrollLeft;
    });

    // Синхронизация скролла (снизу -> вверх)
    resultsDiv.addEventListener('scroll', function () {
        topScroll.scrollLeft = resultsDiv.scrollLeft;
    });

    // Обновление ширины при изменении размера окна
    window.addEventListener('resize', function () {
        innerDiv.style.width = resultsDiv.scrollWidth + 'px';
    });
});