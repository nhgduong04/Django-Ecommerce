document.addEventListener('DOMContentLoaded', function () {
    // Helper to get CSRF token
    function getCookie(name) {
        if (!document.cookie) return null;
        const cookies = document.cookie.split(';')
            .map(c => c.trim())
            .filter(c => c.startsWith(name + '='));
        if (!cookies.length) return null;
        return decodeURIComponent(cookies[0].split('=')[1]);
    }

    // ===== Price Slider =====
    var minSlider = document.getElementById('price-min');
    var maxSlider = document.getElementById('price-max');
    var minLabel = document.getElementById('price-min-label');
    var maxLabel = document.getElementById('price-max-label');
    var range = document.getElementById('price-slider-range');
    var sliderMax = 2000000;

    function formatPrice(val) {
        return parseInt(val).toLocaleString('en-US') + 'đ';
    }

    function updateSliderUI() {
        if (!minSlider || !maxSlider) return;
        var minVal = parseInt(minSlider.value);
        var maxVal = parseInt(maxSlider.value);
        if (minVal > maxVal) {
            var tmp = minVal;
            minSlider.value = maxVal;
            maxSlider.value = tmp;
            minVal = parseInt(minSlider.value);
            maxVal = parseInt(maxSlider.value);
        }
        if (minLabel) minLabel.textContent = formatPrice(minVal);
        if (maxLabel) maxLabel.textContent = formatPrice(maxVal);
        // tỉ lệ phần trăm để vẽ thanh màu
        if (range) {
            var percentMin = (minVal / sliderMax) * 100;
            var percentMax = (maxVal / sliderMax) * 100;
            range.style.left = percentMin + '%';
            range.style.width = (percentMax - percentMin) + '%';
        }
    }
    var sliderTimeout = null;
    function handleSliderInput() {
        updateSliderUI();
        clearTimeout(sliderTimeout);
        sliderTimeout = setTimeout(function() {
            applyFilters();
        }, 1000);
    }
    if (minSlider) minSlider.addEventListener('input', handleSliderInput);
    if (maxSlider) maxSlider.addEventListener('input', handleSliderInput);

    // ===== Gather current filters from UI =====
    function getFilters() {
        var params = new URLSearchParams();
        // Keyword
        var kwInput = document.getElementById('search-keyword');
        var kw = kwInput ? kwInput.value.trim() : '';
        if (kw) params.set('keyword', kw);
        // Price
        if (minSlider && maxSlider) {
            var minVal = parseInt(minSlider.value);
            var maxVal = parseInt(maxSlider.value);
            if (minVal > maxVal) { var t = minVal; minVal = maxVal; maxVal = t; }
            if (minVal > 0) params.set('min_price', minVal);
            if (maxVal < sliderMax) params.set('max_price', maxVal);
        }
        // Colors
        document.querySelectorAll('.filter-color:checked').forEach(function (cb) {
            params.append('color', cb.value);
        });
        // Sizes
        document.querySelectorAll('.filter-size:checked').forEach(function (cb) {
            params.append('size', cb.value);
        });
        // Sort
        var activeSort = document.querySelector('.sort-option.active');
        var sortVal = activeSort ? activeSort.getAttribute('data-sort') : 'latest';
        if (sortVal && sortVal !== 'latest') params.set('sort', sortVal);
        return params;
    }

    // ===== AJAX fetch =====
    var fetchController = null;
    function fetchProducts(params, pushState) {
        if (fetchController) fetchController.abort();
        fetchController = new AbortController();

        var qs = params.toString();
        var basePath = window.location.pathname;
        var url = basePath + (qs ? '?' + qs : '');

        if (pushState !== false) {
            history.pushState(null, '', url);
        }

        const csrftoken = getCookie('csrftoken');
        fetch(url, {
            headers: { 
                'X-Requested-With': 'XMLHttpRequest',
                ...(csrftoken ? { 'X-CSRFToken': csrftoken } : {})
            },
            signal: fetchController.signal
        })
            .then(function (res) { return res.json(); })
            .then(function (data) {
                var container = document.getElementById('filtered-products-container');
                if (container) {
                    container.innerHTML = data.html;
                    bindPaginationEvents();
                }
            })
            .catch(function (err) {
                if (err.name !== 'AbortError') console.error(err);
            });
    }

    function applyFilters() {
        var params = getFilters();
        fetchProducts(params);
    }

    // ===== Event: Color / Size checkboxes =====
    document.querySelectorAll('.filter-color, .filter-size').forEach(function (cb) {
        cb.addEventListener('change', applyFilters);
    });

    // ===== Event: Search =====
    var searchBtn = document.getElementById('search-btn');
    if (searchBtn) searchBtn.addEventListener('click', applyFilters);
    var searchKw = document.getElementById('search-keyword');
    if (searchKw) {
        searchKw.addEventListener('keydown', function (e) {
            if (e.key === 'Enter') { e.preventDefault(); applyFilters(); }
        });
    }

    // ===== Event: Sort dropdown =====
    var SORT_LABELS = { latest: 'Latest', popularity: 'Popularity', price_asc: 'Price: Low to High', price_desc: 'Price: High to Low' };
    document.querySelectorAll('.sort-option').forEach(function (item) {
        item.addEventListener('click', function (e) {
            e.preventDefault();
            document.querySelectorAll('.sort-option').forEach(function (el) { el.classList.remove('active'); });
            this.classList.add('active');
            var trigger = document.getElementById('triggerId');
            if (trigger) trigger.textContent = SORT_LABELS[this.getAttribute('data-sort')] || 'Sort by';
            applyFilters();
        });
    });

    // ===== Event: Pagination (delegated) =====
    function bindPaginationEvents() {
        document.querySelectorAll('.page-nav').forEach(function (link) {
            link.addEventListener('click', function (e) {
                e.preventDefault();
                var page = this.getAttribute('data-page');
                var params = getFilters();
                params.set('page', page);
                fetchProducts(params);
            });
        });
    }
    bindPaginationEvents();

    // ===== Browser back/forward =====
    window.addEventListener('popstate', function () {
        syncUIFromURL();
        var params = new URLSearchParams(window.location.search);
        fetchProducts(params, false);
    });

    // ===== Sync UI controls from URL params =====
    function syncUIFromURL() {
        var params = new URLSearchParams(window.location.search);
        var kwInput = document.getElementById('search-keyword');
        if (kwInput) kwInput.value = params.get('keyword') || '';
        
        if (minSlider) minSlider.value = params.get('min_price') || 0;
        if (maxSlider) maxSlider.value = params.get('max_price') || sliderMax;
        updateSliderUI();

        var selColors = params.getAll('color');
        document.querySelectorAll('.filter-color').forEach(function (cb) {
            cb.checked = selColors.includes(cb.value);
        });

        var selSizes = params.getAll('size');
        document.querySelectorAll('.filter-size').forEach(function (cb) {
            cb.checked = selSizes.includes(cb.value);
        });

        var sortVal = params.get('sort') || 'latest';
        document.querySelectorAll('.sort-option').forEach(function (el) {
            el.classList.toggle('active', el.getAttribute('data-sort') === sortVal);
        });
        var trigger = document.getElementById('triggerId');
        if (trigger) trigger.textContent = SORT_LABELS[sortVal] || 'Sort by';
    }

    syncUIFromURL();

    // ===== Quick Add To Cart Modal Logic =====

    const productsContainer = document.getElementById('filtered-products-container');
    const quickModal = document.getElementById('quickAddModal');
    const quickModalBody = document.getElementById('quick-add-modal-body');
    const quickLoading = document.getElementById('quick-add-loading');

    function initQuickAddModalInteractions() {
        if (!quickModalBody) return;
        const root = quickModalBody.querySelector('#quick-add-root');
        if (!root) return;

        const variantsScript = root.querySelector('#quick-variants-json');
        let variantsData = [];
        if (variantsScript) {
            try {
                variantsData = JSON.parse(variantsScript.textContent || '[]');
            } catch (e) {
                console.error('Invalid variants JSON', e);
            }
        }

        const btnMinus = root.querySelector('.quick-btn-minus');
        const btnPlus = root.querySelector('.quick-btn-plus');
        const qtyDisplay = root.querySelector('#quick-qty-display');
        const hiddenInput = root.querySelector('#quick-hidden-quantity');
        const form = root.querySelector('#quick-add-to-cart-form');
        const variantIdInput = root.querySelector('#quick-selected-variant-id');
        const priceDisplay = root.querySelector('#quick-product-price');

        const optionNames = new Set();
        root.querySelectorAll('.swatch-input').forEach(function (input) {
            optionNames.add(input.name);
        });

        let currentMaxStock = null;

        function resetQuantity() {
            if (hiddenInput) hiddenInput.value = '1';
            if (qtyDisplay) qtyDisplay.textContent = '1';
        }

        function updateSelectedVariant() {
            const selectedOptions = {};
            root.querySelectorAll('.swatch-input:checked').forEach(function (input) {
                selectedOptions[input.name] = input.value;
            });

            let matchedVariant = null;
            if (Object.keys(selectedOptions).length > 0 && Object.keys(selectedOptions).length === optionNames.size) {
                matchedVariant = variantsData.find(function (v) {
                    for (const key in selectedOptions) {
                        if (Object.prototype.hasOwnProperty.call(selectedOptions, key)) {
                            if (v.options[key] !== selectedOptions[key]) return false;
                        }
                    }
                    return true;
                });
            } else if (optionNames.size === 0 && variantsData.length > 0) {
                matchedVariant = variantsData[0];
            }

            const newStock = matchedVariant ? matchedVariant.stock : null;
            if (newStock !== currentMaxStock) {
                currentMaxStock = newStock;
                resetQuantity();
            }

            const inStockControls = root.querySelector('#quick-in-stock-controls');
            const outOfStockBadge = root.querySelector('#quick-out-of-stock-badge');

            if (matchedVariant) {
                if (variantIdInput) variantIdInput.value = matchedVariant.id;
                if (priceDisplay) {
                    priceDisplay.textContent = new Intl.NumberFormat('en-US').format(matchedVariant.price) + 'đ';
                }

                const originalPriceDisplay = root.querySelector('#quick-product-original-price');
                const discountPercentDisplay = root.querySelector('#quick-product-discount-percent');

                if (originalPriceDisplay) {
                    if (matchedVariant.original_price > matchedVariant.price) {
                        originalPriceDisplay.style.display = 'block';
                        originalPriceDisplay.innerHTML = '<del>' + new Intl.NumberFormat('en-US').format(matchedVariant.original_price) + 'đ</del>';
                        priceDisplay && priceDisplay.classList.add('text-danger');
                        if (discountPercentDisplay) {
                            const discount = Math.round((matchedVariant.original_price - matchedVariant.price) / matchedVariant.original_price * 100);
                            discountPercentDisplay.style.display = 'block';
                            discountPercentDisplay.textContent = '-' + discount + '%';
                        }
                    } else {
                        originalPriceDisplay.style.display = 'none';
                        priceDisplay && priceDisplay.classList.remove('text-danger');
                        if (discountPercentDisplay) discountPercentDisplay.style.display = 'none';
                    }
                }

                if (matchedVariant.stock <= 0) {
                    if (inStockControls) inStockControls.style.display = 'none';
                    if (outOfStockBadge) outOfStockBadge.style.display = 'block';
                } else {
                    if (inStockControls) inStockControls.style.display = '';
                    if (outOfStockBadge) outOfStockBadge.style.display = 'none';
                }
            } else {
                if (variantIdInput) variantIdInput.value = '';
                if (inStockControls) inStockControls.style.display = '';
                if (outOfStockBadge) outOfStockBadge.style.display = 'none';
            }
        }

        root.querySelectorAll('.swatch-input').forEach(function (input) {
            input.addEventListener('change', updateSelectedVariant);
        });

        root.querySelectorAll('.d-flex.flex-wrap').forEach(function (group) {
            const radios = group.querySelectorAll('.swatch-input');
            if (radios.length === 1) {
                radios[0].checked = true;
            }
        });

        updateSelectedVariant();

        if (btnMinus && btnPlus && qtyDisplay && hiddenInput) {
            btnMinus.addEventListener('click', function () {
                let currentVal = parseInt(hiddenInput.value, 10) || 1;
                if (currentVal > 1) {
                    currentVal--;
                    hiddenInput.value = String(currentVal);
                    qtyDisplay.textContent = String(currentVal);
                }
            });

            btnPlus.addEventListener('click', function () {
                let currentVal = parseInt(hiddenInput.value, 10) || 1;
                if (currentMaxStock !== null && currentVal >= currentMaxStock) {
                    if (typeof showToast === 'function') showToast('You can only purchase a maximum of ' + currentMaxStock + ' items', 'warning');
                    return;
                }
                currentVal++;
                hiddenInput.value = String(currentVal);
                qtyDisplay.textContent = String(currentVal);
            });
        }

        if (form) {
            form.addEventListener('submit', function (e) {
                if (!window.fetch) return;
                e.preventDefault();

                if (optionNames.size > 0 && (!variantIdInput || !variantIdInput.value)) {
                    const selectedCount = root.querySelectorAll('.swatch-input:checked').length;
                    if (selectedCount < optionNames.size) {
                         if (typeof showToast === 'function') showToast('Please select all variants before adding to cart.', 'warning');
                    } else {
                         if (typeof showToast === 'function') showToast('No matching variant found for your selection. Please try again.', 'danger');
                    }
                    return;
                }

                const url = form.getAttribute('action');
                const formData = new FormData(form);
                const csrftoken = getCookie('csrftoken');

                fetch(url, {
                    method: 'POST',
                    headers: {
                        'X-Requested-With': 'XMLHttpRequest',
                        ...(csrftoken ? { 'X-CSRFToken': csrftoken } : {})
                    },
                    body: formData,
                    credentials: 'same-origin'
                })
                    .then(function (response) {
                        return response.json().then(function (data) {
                            return { ok: response.ok, status: response.status, data: data };
                        }).catch(function () {
                            return { ok: response.ok, status: response.status, data: null };
                        });
                    })
                    .then(function (res) {
                        const data = res.data;
                        if (!data) {
                            if (typeof showToast === 'function') showToast('An error occurred.', 'danger');
                            return;
                        }

                        if (res.ok && data.success) {
                            const cartBadge = document.getElementById('cart-badge');
                            if (cartBadge) {
                                cartBadge.innerText = data.cart_quantity;
                                if (data.cart_quantity > 0) {
                                    cartBadge.classList.remove('site-action-badge--hidden');
                                }
                            }
                            if (window.jQuery && $('#quickAddModal').modal) {
                                $('#quickAddModal').modal('hide');
                            } else if (quickModal) {
                                quickModal.classList.remove('show');
                            }
                            if (typeof showToast === 'function') showToast('Product added to cart successfully!', 'success');
                            return;
                        }

                        if (res.status === 409 && data.error === 'out_of_stock') {
                            if (typeof showToast === 'function') showToast('Product out of stock or insufficient inventory.', 'warning');
                            return;
                        }

                        if (typeof showToast === 'function') showToast(data.message || data.error || 'Unable to add to cart.', 'danger');
                    })
                    .catch(function (err) {
                        console.error(err);
                        if (typeof showToast === 'function') showToast('Connection to server failed.', 'danger');
                    });
            });
        }
    }

    function openQuickAddModal(url) {
        if (!quickModal || !quickModalBody) return;

        quickModalBody.innerHTML = '';
        if (quickLoading) {
            quickLoading.classList.remove('d-none');
            quickModalBody.appendChild(quickLoading);
        }

        if (window.jQuery && $('#quickAddModal').modal) {
            $('#quickAddModal').modal('show');
        }

        const csrftoken = getCookie('csrftoken');
        fetch(url, {
            headers: { 
                'X-Requested-With': 'XMLHttpRequest',
                ...(csrftoken ? { 'X-CSRFToken': csrftoken } : {})
            },
        })
            .then(function (res) { return res.json(); })
            .then(function (data) {
                if (!data || !data.html) throw new Error('Invalid response');
                quickModalBody.innerHTML = data.html;
                initQuickAddModalInteractions();
            })
            .catch(function (err) {
                console.error(err);
                quickModalBody.innerHTML = '<p class="text-center text-danger mb-0">Unable to load product information.</p>';
            });
    }

    if (productsContainer) {
        productsContainer.addEventListener('click', function (e) {
            const btn = e.target.closest('.js-quick-add-btn');
            if (!btn) return;
            e.preventDefault();
            const url = btn.getAttribute('data-quick-url');
            if (!url) {
                const fallback = btn.getAttribute('href');
                if (fallback) window.location.href = fallback;
                return;
            }
            openQuickAddModal(url);
        });
    }
});
