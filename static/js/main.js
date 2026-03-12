(function ($) {
    "use strict";
    
    // Dropdown on mouse hover
    $(document).ready(function () {
        function toggleNavbarMethod() {
            if ($(window).width() > 992) {
                $('.navbar .dropdown').on('mouseover', function () {
                    $('.dropdown-toggle', this).trigger('click');
                }).on('mouseout', function () {
                    $('.dropdown-toggle', this).trigger('click').blur();
                });
            } else {
                $('.navbar .dropdown').off('mouseover').off('mouseout');
            }
        }
        toggleNavbarMethod();
        $(window).resize(toggleNavbarMethod);
    });
    
    
    // Back to top button
    $(window).scroll(function () {
        if ($(this).scrollTop() > 100) {
            $('.back-to-top').fadeIn('slow');
        } else {
            $('.back-to-top').fadeOut('slow');
        }
    });
    $('.back-to-top').click(function () {
        $('html, body').animate({scrollTop: 0}, 1500, 'easeInOutExpo');
        return false;
    });


    // Vendor carousel
    $('.vendor-carousel').owlCarousel({
        loop: true,
        margin: 29,
        nav: false,
        autoplay: true,
        smartSpeed: 1000,
        responsive: {
            0:{
                items:2
            },
            576:{
                items:3
            },
            768:{
                items:4
            },
            992:{
                items:5
            },
            1200:{
                items:6
            }
        }
    });


    // Related carousel
    $('.related-carousel').owlCarousel({
        loop: true,
        margin: 29,
        nav: false,
        autoplay: true,
        smartSpeed: 1000,
        responsive: {
            0:{
                items:1
            },
            576:{
                items:2
            },
            768:{
                items:3
            },
            992:{
                items:4
            }
        }
    });


    // Product Quantity
    $('.quantity button').on('click', function () {
        var button = $(this);
        var input = button.parent().parent().find('input');
        var oldValue = input.val();
        var minAttr = input.attr('min');
        var maxAttr = input.attr('max');
        var minVal = (minAttr !== undefined && minAttr !== null && minAttr !== '') ? parseFloat(minAttr) : 0;
        var maxVal = (maxAttr !== undefined && maxAttr !== null && maxAttr !== '') ? parseFloat(maxAttr) : null;

        var oldNum = parseFloat(oldValue);
        if (isNaN(oldNum)) oldNum = minVal;

        if (button.hasClass('btn-plus')) {
            var newVal = oldNum + 1;
        } else {
            var newVal = oldNum - 1;
        }

        if (newVal < minVal) newVal = minVal;
        if (maxVal !== null && !isNaN(maxVal) && newVal > maxVal) newVal = maxVal;

        input.val(newVal);
    });


    // ===== Search Autocomplete =====
    (function () {
        var $input    = $('#search-input');
        var $dropdown = $('#search-dropdown');
        var timer     = null;
        var activeIdx = -1;
        var xhr       = null;

        function formatPrice(val) {
            return parseInt(val).toLocaleString('vi-VN') + '₫';
        }

        function renderDropdown(data, query) {
            var items = data.suggestions;
            if (!items.length) {
                $dropdown.html('<div class="search-no-results">No products found</div>').slideDown(150);
                return;
            }
            var html = '';
            $.each(items, function (i, item) {
                var imgTag = item.image_url
                    ? '<img src="' + $('<span>').text(item.image_url).html() + '" alt="">'
                    : '<img src="" alt="" style="visibility:hidden">';
                html += '<a class="search-item" href="' + $('<span>').text(item.detail_url).html() + '">' +
                    imgTag +
                    '<div class="search-item-info">' +
                        '<div class="search-item-name">' + $('<span>').text(item.name).html() + '</div>' +
                        '<div class="search-item-meta">' + $('<span>').text(item.category).html() + ' &middot; ' + formatPrice(item.price) + '</div>' +
                    '</div></a>';
            });
            html += '<a class="search-view-all" href="/all-products/?keyword=' + encodeURIComponent(query) + '">View all results</a>';
            $dropdown.html(html).slideDown(150);
            activeIdx = -1;
        }

        $input.on('input', function () {
            var query = $(this).val().trim();
            if (query.length < 2) {
                $dropdown.slideUp(100);
                if (xhr) xhr.abort();
                return;
            }
            clearTimeout(timer);
            timer = setTimeout(function () {
                if (xhr) xhr.abort();
                xhr = $.ajax({
                    url: '/api/search-suggestions/',
                    data: { q: query },
                    dataType: 'json',
                    success: function (data) {
                        renderDropdown(data, query);
                    }
                });
            }, 300);
        });

        // Keyboard navigation
        $input.on('keydown', function (e) {
            var $items = $dropdown.find('.search-item');
            if (!$items.length || $dropdown.is(':hidden')) return;

            if (e.keyCode === 40) { // down
                e.preventDefault();
                activeIdx = Math.min(activeIdx + 1, $items.length - 1);
                $items.removeClass('active').eq(activeIdx).addClass('active');
            } else if (e.keyCode === 38) { // up
                e.preventDefault();
                activeIdx = Math.max(activeIdx - 1, 0);
                $items.removeClass('active').eq(activeIdx).addClass('active');
            } else if (e.keyCode === 13 && activeIdx >= 0) { // enter
                e.preventDefault();
                window.location.href = $items.eq(activeIdx).attr('href');
            }
        });

        // Close dropdown on click outside
        $(document).on('click', function (e) {
            if (!$(e.target).closest('.search-wrapper').length) {
                $dropdown.slideUp(100);
            }
        });

        // Re-show on focus if input has content
        $input.on('focus', function () {
            if ($dropdown.children().length && $(this).val().trim().length >= 2) {
                $dropdown.slideDown(150);
            }
        });
    })();
    
})(jQuery);

