(function($) {
    'use strict';
    $(document).on('formset:added', function(event, $row, formsetName) {
        let maxOrder = 0;
        $('.field-order input').each(function() {
            let val = parseInt($(this).val());
            if (!isNaN(val) && val > maxOrder) {
                maxOrder = val;
            }
        });
        let orderInput = $row.find('.field-order input');
        if (orderInput.length) {
            orderInput.val(maxOrder + 1);
        }
    });
})(django.jQuery);