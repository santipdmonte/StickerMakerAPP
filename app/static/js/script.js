document.addEventListener('DOMContentLoaded', () => {
    // UI Elements
    const promptInput = document.getElementById('prompt-input');
    const referencePromptInput = document.getElementById('reference-prompt-input');
    const generateBtn = document.getElementById('generate-btn');
    const resultsSection = document.getElementById('results-section');
    const loadingSpinner = document.getElementById('loading-spinner');
    const stickerImage = document.getElementById('sticker-image');
    const downloadBtn = document.getElementById('download-btn');
    const stickerResult = document.querySelector('.sticker-result');
    const container = document.querySelector('.container');
    
    // Template elements
    const addToTemplateBtn = document.getElementById('add-to-template-btn');
    const templateSection = document.getElementById('template-section');
    const templateGrid = document.getElementById('template-grid');
    const downloadTemplateBtn = document.getElementById('download-template-btn');
    const clearTemplateBtn = document.getElementById('clear-template-btn');
    const buyStickersBtn = document.getElementById('buy-stickers-btn');
    const emptyTemplateMessage = document.querySelector('.empty-template-message');
    
    // Checkout Modal elements
    const checkoutModal = document.getElementById('checkout-modal');
    const modalCloseBtn = document.getElementById('modal-close-btn');
    const checkoutForm = document.getElementById('checkout-form');
    const finalizePaymentBtn = document.getElementById('finalize-payment-btn');
    
    
    // Coins elements
    const buyCoinsHeaderBtn = document.getElementById('buy-coins-btn-header');
    const coinsCountHeader = document.getElementById('coins-count-header');
    const coinsModal = document.getElementById('coins-modal');
    const coinsModalCloseBtn = document.getElementById('coins-modal-close-btn');
    const coinsPackages = document.querySelectorAll('.coins-package');
    const packageSelectBtns = document.querySelectorAll('.package-select-btn');
    const coinsForm = document.getElementById('coins-form');
    const selectedPackageName = document.getElementById('selected-package-name');
    const selectedPackageAmount = document.getElementById('selected-package-amount');
    const selectedPackagePrice = document.getElementById('selected-package-price');
    const backToPackagesBtn = document.getElementById('back-to-packages-btn');
    const finalizeCoinsBtn = document.getElementById('finalize-coins-btn');
    const coinsNameInput = document.getElementById('coins-name');
    const coinsEmailInput = document.getElementById('coins-email');
    const coinsCouponDirectInput = document.getElementById('coins-coupon-direct');
    const applyCouponDirectBtn = document.getElementById('apply-coupon-direct-btn');
    const couponDirectStatus = document.getElementById('coupon-direct-status');
    
    // Coin packages data
    const coinPackagesData = {
        'small': { name: 'Small Package', amount: 100, price: 500.00 },
        'medium': { name: 'Medium Package', amount: 300, price: 1000.00 },
        'large': { name: 'Large Package', amount: 500, price: 1500.00 }
    };
    
    // Current selected package
    let selectedPackage = null;
    
    // Current coins amount
    let currentCoins = 0;
    
    // Coupon state
    let couponApplied = false;
    let additionalCoins = 0;
    
    // --- Mercado Pago SDK Initialization ---
    // The public key is now injected from Flask via the template
    // const mpPublicKey is already defined before this script loads
    let mp = null;
    if (mpPublicKey && mpPublicKey !== '') {
        try {
            mp = new MercadoPago(mpPublicKey, {
                locale: 'es-AR' // Adjust locale if needed (e.g., 'es-MX', 'pt-BR')
            });
            console.log("Mercado Pago SDK Initialized.");
        } catch (error) {
            console.error("Failed to initialize Mercado Pago SDK:", error);
            showError("Payment system could not be initialized.");
            // Disable payment button if SDK fails
            finalizePaymentBtn.disabled = true;
            finalizePaymentBtn.textContent = "Payment Unavailable";
        }
    } else {
        console.warn("Mercado Pago Public Key not set. Payment processing will not work.");
        // Optionally disable the finalize button if the key isn't set
        finalizePaymentBtn.disabled = true;
        finalizePaymentBtn.innerHTML = '<i class="ri-error-warning-line"></i> Payment Key Missing';
    }
    // ---
    
    // Quality selectors
    const qualityRadios = document.querySelectorAll('input[name="quality"]');
    const qualityRefRadios = document.querySelectorAll('input[name="quality-ref"]');
    
    // Mode switching elements
    const modeBtns = document.querySelectorAll('.mode-btn');
    const simpleMode = document.getElementById('simple-mode');
    const referenceMode = document.getElementById('reference-mode');
    
    // Image upload elements
    const referenceImageInput = document.getElementById('reference-image-input');
    const referenceImagePreview = document.getElementById('reference-image-preview');
    const referenceImageUpload = document.getElementById('reference-image-upload');
    
    // Image data storage
    let referenceImageData = null;
    let currentMode = 'simple';
    let currentGeneratedSticker = null;
    let templateStickers = [];
    
    // Initially hide the sticker result
    stickerResult.style.display = 'none';
    
    // Add animation to container on load
    setTimeout(() => {
        container.style.opacity = '1';
        container.style.transform = 'translateY(0)';
        
        // Make template section visible
        templateSection.classList.add('active');
    }, 100);

    // Initial focus on the prompt input with delay for better UX
    setTimeout(() => {
        promptInput.focus();
    }, 500);
    
    // Load template stickers on page load
    loadTemplate();
    
    // Load user's coins on page load
    loadCoins();
    
    // Buy Stickers button click handler
    buyStickersBtn.addEventListener('click', () => {
        if (templateStickers.length === 0) {
            showError('Template is empty. Add stickers first!');
            return;
        }
        
        handleBuyStickers();
    });
    
    // Close modal listeners
    modalCloseBtn.addEventListener('click', hideModal);
    checkoutModal.addEventListener('click', (e) => {
        // Close if clicked outside the modal content
        if (e.target === checkoutModal) {
            hideModal();
        }
    });
    
    // Handle checkout form submission
    checkoutForm.addEventListener('submit', (e) => {
        e.preventDefault(); // Prevent default form submission
        handleFinalizePayment();
    });
    
    function showModal() {
        checkoutModal.classList.remove('hidden');
        // Use setTimeout to allow the display change to render before adding the class for transition
        setTimeout(() => {
            checkoutModal.classList.add('visible');
        }, 10); // Small delay
    }
    
    function hideModal() {
        checkoutModal.classList.remove('visible');
        // Wait for the transition to finish before setting display: none
        setTimeout(() => {
            checkoutModal.classList.add('hidden');
            // Optionally clear form fields when closing
            checkoutForm.reset();
        }, 300); // Matches the CSS transition duration
    }

    function handleBuyStickers() {
        // Count total stickers (considering quantities)
        const totalStickers = templateStickers.reduce((count, sticker) => {
            const quantity = typeof sticker === 'string' ? 1 : (sticker.quantity || 1);
            return count + quantity;
        }, 0);
        
        // Show the checkout modal instead of the success message
        showModal();
        
        // You could pre-fill modal info if needed, e.g.:
        // const modalInfo = checkoutModal.querySelector('.modal-info');
        // modalInfo.textContent = `You are about to purchase ${totalStickers} stickers.`;
    }
    
    async function handleFinalizePayment() {
        if (!mp) {
            showError("Payment system is not available. Please check configuration.");
            return;
        }

        const nameInput = document.getElementById('checkout-name');
        const emailInput = document.getElementById('checkout-email');
        const addressInput = document.getElementById('checkout-address');
        
        const name = nameInput.value.trim();
        const email = emailInput.value.trim();
        const address = addressInput.value.trim();
        
        // Frontend validation
        let isValid = true;
        if (!name) {
            showError("Please enter your name.");
            shakElement(nameInput);
            isValid = false;
        }
        if (!email || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) { // Simple email regex
            showError("Please enter a valid email address.");
            shakElement(emailInput);
             isValid = false;
        }
        if (!address) {
             showError("Please enter your address.");
             shakElement(addressInput);
            isValid = false;
        }
        
        if (!isValid) {
            return; // Stop if validation fails
        }
        
        // Disable button and show loading state
        finalizePaymentBtn.disabled = true;
        finalizePaymentBtn.innerHTML = '<i class="ri-loader-4-line ri-spin"></i> Processing...';

        try {
            // 1. Call backend to create the preference
            const response = await fetch('/create_preference', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ name, email, address }) // Send user details
            });

            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.error || 'Failed to create payment preference on server.');
            }

            const data = await response.json();
            const preferenceId = data.preference_id;

            if (!preferenceId) {
                throw new Error('Preference ID not received from server.');
            }
            
            // Log the preference ID
            console.log("Received Preference ID:", preferenceId);

            // 2. Hide the modal *before* redirecting
            hideModal(); 

            // 3. Redirect to Mercado Pago Checkout using the preference ID
            // The SDK handles the redirection
            mp.checkout({
                preference: {
                    id: preferenceId
                },
                // Optional: Render the button in a container if you don't want immediate redirect
                // render: {
                //    container: '.checkout-btn-container', // Class name of the container where the payment button will be placed
                //    label: 'Pagar com Mercado Pago'
                // },
                // Using autoOpen will redirect immediately after preference is loaded by SDK
                 autoOpen: true, 
            });
            
             // Note: Execution stops here if autoOpen is true as the page redirects.
             // If not using autoOpen, re-enable the button after SDK renders.
             // finalizePaymentBtn.disabled = false;
             // finalizePaymentBtn.innerHTML = '<i class="ri-secure-payment-line"></i> Finalize Payment';

        } catch (error) {
            console.error("Checkout Error:", error);
            showError(`Checkout failed: ${error.message}`);
            // Re-enable button on error
            finalizePaymentBtn.disabled = false;
            finalizePaymentBtn.innerHTML = '<i class="ri-secure-payment-line"></i> Finalize Payment';
        }
    }
    
    // Template Functions
    function loadTemplate() {
        fetch('/get-template')
            .then(response => response.json())
            .then(data => {
                templateStickers = data.template_stickers;
                updateTemplateDisplay();
            })
            .catch(error => {
                console.error('Error loading template:', error);
            });
    }
    
    function updateTemplateDisplay() {
        console.log("Current template stickers:", templateStickers);
        
        // Clear existing stickers
        while (templateGrid.firstChild) {
            templateGrid.removeChild(templateGrid.firstChild);
        }
        
        // Show empty message if no stickers
        if (templateStickers.length === 0) {
            templateGrid.appendChild(emptyTemplateMessage);
            templateGrid.classList.add('empty');
            return;
        }
        
        // Remove empty message and class
        templateGrid.classList.remove('empty');
        if (emptyTemplateMessage.parentNode === templateGrid) {
            templateGrid.removeChild(emptyTemplateMessage);
        }
        
        // Add stickers to template
        templateStickers.forEach(stickerData => {
            // Create the sticker item container
            const stickerItem = document.createElement('div');
            stickerItem.className = 'template-item';
            
            // Get filename and quantity from sticker data
            const filename = typeof stickerData === 'string' ? stickerData : stickerData.filename;
            const quantity = typeof stickerData === 'string' ? 1 : (stickerData.quantity || 1);
            
            console.log(`Sticker: ${filename}, Quantity: ${quantity}`);
            
            // Create the image element
            const img = document.createElement('img');
            img.src = `/static/imgs/${filename}`;
            img.alt = 'Template sticker';
            
            // Create quantity controls
            const quantityControl = document.createElement('div');
            quantityControl.className = 'quantity-control';
            
            const decreaseBtn = document.createElement('button');
            decreaseBtn.className = 'quantity-btn decrease';
            decreaseBtn.innerHTML = '<i class="ri-subtract-fill"></i>';
            decreaseBtn.disabled = quantity <= 1;
            decreaseBtn.type = 'button'; // Prevent form submission
            
            const quantityValue = document.createElement('span');
            quantityValue.className = 'quantity-value';
            quantityValue.textContent = quantity;
            
            const increaseBtn = document.createElement('button');
            increaseBtn.className = 'quantity-btn increase';
            increaseBtn.innerHTML = '<i class="ri-add-fill"></i>';
            increaseBtn.type = 'button'; // Prevent form submission
            
            // Add event listeners to quantity buttons
            decreaseBtn.addEventListener('click', (e) => {
                e.stopPropagation();
                e.preventDefault();
                if (quantity > 1) {
                    updateStickerQuantity(filename, quantity - 1);
                }
            });
            
            increaseBtn.addEventListener('click', (e) => {
                e.stopPropagation();
                e.preventDefault();
                updateStickerQuantity(filename, quantity + 1);
            });
            
            // Add quantity controls to the UI
            quantityControl.appendChild(decreaseBtn);
            quantityControl.appendChild(quantityValue);
            quantityControl.appendChild(increaseBtn);
            
            // Create the remove button
            const removeBtn = document.createElement('button');
            removeBtn.className = 'remove-btn';
            removeBtn.innerHTML = '<i class="ri-close-line"></i>';
            removeBtn.dataset.filename = filename;
            removeBtn.type = 'button'; // Prevent form submission
            
            removeBtn.addEventListener('click', function(e) {
                e.stopPropagation();
                e.preventDefault();
                removeFromTemplate(filename);
            });
            
            // Add elements to the sticker item
            stickerItem.appendChild(img);
            stickerItem.appendChild(quantityControl);
            stickerItem.appendChild(removeBtn);
            templateGrid.appendChild(stickerItem);
        });
    }
    
    function addToTemplate(filename) {
        fetch('/add-to-template', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ filename }),
        })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    templateStickers = data.template_stickers;
                    updateTemplateDisplay();
                    showSuccess('Sticker added to template');
                    
                    // Scroll to template section
                    templateSection.scrollIntoView({ behavior: 'smooth' });
                }
            })
            .catch(error => {
                console.error('Error adding to template:', error);
                showError('Failed to add sticker to template');
            });
    }
    
    function removeFromTemplate(filename) {
        fetch('/remove-from-template', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ filename }),
        })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    templateStickers = data.template_stickers;
                    updateTemplateDisplay();
                }
            })
            .catch(error => {
                console.error('Error removing from template:', error);
                showError('Failed to remove sticker from template');
            });
    }
    
    function clearTemplate() {
        fetch('/clear-template', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            }
        })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    templateStickers = [];
                    updateTemplateDisplay();
                    showSuccess('Template cleared');
                }
            })
            .catch(error => {
                console.error('Error clearing template:', error);
                showError('Failed to clear template');
            });
    }
    
    function downloadTemplateAsImage() {
        if (templateStickers.length === 0) {
            showError('Template is empty. Add stickers first!');
            return;
        }
        
        // Create a temporary canvas for the template
        const canvas = document.createElement('canvas');
        const ctx = canvas.getContext('2d');
        
        // Calculate total stickers count (accounting for quantities)
        const totalStickers = templateStickers.reduce((count, sticker) => {
            const quantity = typeof sticker === 'string' ? 1 : (sticker.quantity || 1);
            return count + quantity;
        }, 0);
        
        // Calculate template size
        const columns = Math.min(3, Math.ceil(Math.sqrt(totalStickers)));
        const rows = Math.ceil(totalStickers / columns);
        
        const stickerWidth = 300;
        const stickerHeight = 300;
        const padding = 20;
        
        canvas.width = columns * (stickerWidth + padding) + padding;
        canvas.height = rows * (stickerHeight + padding) + padding;
        
        // Fill with white background
        ctx.fillStyle = 'white';
        ctx.fillRect(0, 0, canvas.width, canvas.height);
        
        // Load and draw all stickers
        let loadedCount = 0;
        let totalExpectedImages = 0;
        let loadError = false;
        
        // Create an array with all sticker instances, accounting for quantities
        const stickerInstances = [];
        templateStickers.forEach(stickerData => {
            const filename = typeof stickerData === 'string' ? stickerData : stickerData.filename;
            const quantity = typeof stickerData === 'string' ? 1 : (stickerData.quantity || 1);
            
            for (let i = 0; i < quantity; i++) {
                stickerInstances.push(filename);
            }
        });
        
        totalExpectedImages = stickerInstances.length;
        
        const drawTemplateAndDownload = () => {
            if (loadedCount === totalExpectedImages && !loadError) {
                // Create download link
                const dataUrl = canvas.toDataURL('image/png');
                const downloadLink = document.createElement('a');
                downloadLink.href = dataUrl;
                downloadLink.download = `sticker_template_${Date.now()}.png`;
                document.body.appendChild(downloadLink);
                downloadLink.click();
                document.body.removeChild(downloadLink);
                
                showSuccess('Template downloaded');
            }
        };
        
        stickerInstances.forEach((filename, index) => {
            const img = new Image();
            img.crossOrigin = 'anonymous';
            img.src = `/static/imgs/${filename}`;
            
            img.onload = () => {
                const col = index % columns;
                const row = Math.floor(index / columns);
                const x = padding + col * (stickerWidth + padding);
                const y = padding + row * (stickerHeight + padding);
                
                ctx.drawImage(img, x, y, stickerWidth, stickerHeight);
                loadedCount++;
                drawTemplateAndDownload();
            };
            
            img.onerror = () => {
                loadError = true;
                showError('Error loading sticker images');
            };
        });
    }
    
    // Event listeners for template buttons
    addToTemplateBtn.addEventListener('click', () => {
        if (currentGeneratedSticker) {
            addToTemplate(currentGeneratedSticker);
        } else {
            showError('No sticker to add. Generate one first!');
        }
    });
    
    clearTemplateBtn.addEventListener('click', clearTemplate);
    downloadTemplateBtn.addEventListener('click', downloadTemplateAsImage);
    
    // Sync quality settings between modes
    function syncQualitySettings(fromMode, toMode) {
        const fromRadios = fromMode === 'simple' ? qualityRadios : qualityRefRadios;
        const toRadios = toMode === 'simple' ? qualityRadios : qualityRefRadios;
        
        // Find selected quality in current mode
        let selectedQuality = 'low'; // Default
        let selectedRadio = null;
        
        for (const radio of fromRadios) {
            if (radio.checked) {
                selectedQuality = radio.value;
                break;
            }
        }
        
        // Set the same quality in target mode
        for (const radio of toRadios) {
            if (radio.value === selectedQuality) {
                radio.checked = true;
                selectedRadio = radio;
                break;
            }
        }
        
        // Explicitly update the slider position for the target mode
        if (selectedRadio) {
            updateQualitySlider(selectedRadio, toMode);
        }
    }
    
    // Mode switching
    modeBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            const mode = btn.dataset.mode;
            const previousMode = currentMode;
            
            // Update active button
            modeBtns.forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            
            // Sync the prompt text between modes
            if (mode === 'simple') {
                // Save the reference prompt text and copy it to simple mode
                if (referencePromptInput.value.trim()) {
                    promptInput.value = referencePromptInput.value;
                }
                
                simpleMode.classList.remove('hidden');
                referenceMode.classList.add('hidden');
                currentMode = 'simple';
                setTimeout(() => promptInput.focus(), 100);
            } else {
                // Save the simple prompt text and copy it to reference mode
                if (promptInput.value.trim()) {
                    referencePromptInput.value = promptInput.value;
                }
                
                simpleMode.classList.add('hidden');
                referenceMode.classList.remove('hidden');
                currentMode = 'reference';
                setTimeout(() => referencePromptInput.focus(), 100);
            }
            
            // Sync quality settings
            syncQualitySettings(previousMode, mode);
        });
    });
    
    // Handle file uploads and previews
    referenceImageInput.addEventListener('change', handleFileSelect);
    
    function handleFileSelect(e) {
        const file = e.target.files[0];
        if (!file) return;
        
        const reader = new FileReader();
        const previewElement = referenceImagePreview;
        const uploadBox = referenceImageUpload;
        
        reader.onload = function(event) {
            const img = previewElement.querySelector('img');
            img.src = event.target.result;
            referenceImageData = event.target.result;
            
            previewElement.classList.remove('hidden');
            uploadBox.classList.add('hidden');
        };
        
        reader.readAsDataURL(file);
    }
    
    // Handle remove buttons for uploaded images
    document.querySelectorAll('.remove-btn').forEach(btn => {
        btn.addEventListener('click', function() {
            const previewContainer = this.parentElement;
            referenceImageUpload.classList.remove('hidden');
            
            previewContainer.classList.add('hidden');
            previewContainer.querySelector('img').src = '';
            
            referenceImageData = null;
            referenceImageInput.value = '';
        });
    });
    
    // Add special effects when selecting high quality
    qualityRadios.forEach(radio => {
        radio.addEventListener('change', function() {
            updateQualitySlider(this, 'simple');
        });
    });
    
    qualityRefRadios.forEach(radio => {
        radio.addEventListener('change', function() {
            updateQualitySlider(this, 'reference');
        });
    });
    
    // Initialize slider positions
    updateQualitySlider(document.querySelector('input[name="quality"]:checked'), 'simple');
    updateQualitySlider(document.querySelector('input[name="quality-ref"]:checked'), 'reference');
    
    // Function to update the quality slider indicator position
    function updateQualitySlider(radio, mode) {
        const optionsContainer = radio.closest('.quality-options');
        const position = radio.value === 'low' ? 0 : 
                         radio.value === 'medium' ? 1 : 2;
        
        const slider = optionsContainer;
        // Calculate the position based on index
        const leftPosition = position === 0 ? '5px' : 
                            position === 1 ? 'calc(33.33% + 5px)' : 
                            'calc(66.66% + 5px)';
                            
        // Update the ::after pseudo-element position using a style tag
        let styleId = `quality-style-${mode}`;
        let styleTag = document.getElementById(styleId);
        
        if (!styleTag) {
            styleTag = document.createElement('style');
            styleTag.id = styleId;
            document.head.appendChild(styleTag);
        }
        
        const selector = mode === 'simple' ? 
            '.quality-options:first-of-type::after' : 
            '#reference-mode .quality-options::after';
            
        styleTag.textContent = `${selector} { left: ${leftPosition}; }`;
    }
    
    // Add placeholder animation
    const placeholders = [
        "a cute cat with a crown on a transparent background",
        "a colorful robot sticker with rainbow colors",
        "a watercolor landscape with mountains",
        "a cartoon pizza character with sunglasses",
        "an astronaut floating in space with stars"
    ];
    
    let placeholderIndex = 0;
    setInterval(() => {
        if (document.activeElement !== promptInput) {
            promptInput.setAttribute('placeholder', `Describe your sticker... (e.g., '${placeholders[placeholderIndex]}')`)
            placeholderIndex = (placeholderIndex + 1) % placeholders.length;
        }
    }, 3000);
    
    // Generate sticker when button is clicked
    generateBtn.addEventListener('click', generateSticker);
    
    // Also generate when Enter key is pressed while holding Ctrl
    promptInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && e.ctrlKey) {
            e.preventDefault(); // Prevent newline
            generateSticker();
        }
    });
    
    referencePromptInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && e.ctrlKey) {
            e.preventDefault(); // Prevent newline
            generateSticker();
        }
    });
    
    // Function to get selected quality based on current mode
    function getSelectedQuality() {
        const radios = currentMode === 'simple' ? qualityRadios : qualityRefRadios;
        for (const radio of radios) {
            if (radio.checked) {
                return radio.value;
            }
        }
        return 'low'; // Default fallback
    }
    
    // Function to generate the sticker
    async function generateSticker() {
        let prompt = '';
        
        // Validate inputs based on current mode
        if (currentMode === 'simple') {
            prompt = promptInput.value.trim();
            if (!prompt) {
                showError('Please enter a description for your sticker.');
                shakElement(promptInput);
                return;
            }
        } else {
            prompt = referencePromptInput.value.trim();
            if (!referenceImageData) {
                showError('Please upload a reference image.');
                shakElement(referenceImageUpload);
                return;
            }
            if (!prompt) {
                showError('Please enter a description for your sticker.');
                shakElement(referencePromptInput);
                return;
            }
        }
        
        // Get selected quality and determine cost
        const quality = getSelectedQuality();
        const qualityCost = {
            'low': 10,
            'medium': 25,
            'high': 100
        };
        
        const coinCost = qualityCost[quality] || 10;
        
        // Check if user has enough coins
        if (currentCoins < coinCost) {
            showError(`Not enough coins! You need ${coinCost} coins for a ${quality} quality sticker. Buy more coins.`);
            setTimeout(() => {
                showCoinsModal();
            }, 1500);
            return;
        }
        
        // Show loading spinner
        loadingSpinner.classList.remove('hidden');
        stickerResult.style.display = 'none';
        generateBtn.disabled = true;
        generateBtn.innerHTML = '<i class="ri-loader-4-line ri-spin"></i> Generating...';
        
        try {
            let endpoint = currentMode === 'simple' ? '/generate' : '/generate-with-reference';
            let requestData = { 
                prompt,
                quality 
            };
            
            // Add reference image data if in reference mode
            if (currentMode === 'reference') {
                requestData.referenceImage = referenceImageData;
            }
            
            const response = await fetch(endpoint, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(requestData)
            });
            
            if (response.ok) {
                const data = await response.json();
                
                if (data.success) {
                    // Deduct coins
                    await deductCoins(coinCost);
                    
                    // Update the current sticker reference
                    currentGeneratedSticker = data.filename;
                    
                    // Display the result
                    loadingSpinner.classList.add('hidden');
                    stickerResult.style.display = 'flex';
                    stickerResult.classList.add('pulse');
                    
                    // Set the image source
                    stickerImage.src = `/static/imgs/${data.filename}`;
                    
                    // Enable download button
                    downloadBtn.href = `/static/imgs/${data.filename}`;
                    downloadBtn.download = data.filename;
                    
                    // Remove animation class after animation completes
                    setTimeout(() => {
                        stickerResult.classList.remove('pulse');
                    }, 600);
                    
                    // Scroll to results section
                    resultsSection.scrollIntoView({behavior: 'smooth'});
                    
                    // Show success message with cost
                    showSuccess(`Sticker generated! Used ${coinCost} coins.`);
                } else {
                    throw new Error(data.error || 'Failed to generate sticker');
                }
            } else {
                throw new Error('Failed to generate sticker');
            }
        } catch (error) {
            showError(error.message);
            loadingSpinner.classList.add('hidden');
        } finally {
            generateBtn.disabled = false;
            generateBtn.innerHTML = '<i class="ri-magic-line"></i> Generate Sticker';
        }
    }
    
    // Function to deduct coins
    async function deductCoins(amount) {
        try {
            const response = await fetch('/update-coins', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    amount: -amount // Negative amount for deduction
                })
            });
            
            if (response.ok) {
                const data = await response.json();
                if (data.success) {
                    currentCoins = data.coins;
                    updateCoinsDisplay();
                    return true;
                }
            }
            return false;
        } catch (error) {
            console.error('Error deducting coins:', error);
            return false;
        }
    }
    
    // Function to show errors
    function showError(message) {
        const errorToast = document.createElement('div');
        errorToast.className = 'error-toast';
        errorToast.innerHTML = `<i class="ri-error-warning-line"></i> ${message}`;
        document.body.appendChild(errorToast);
        
        setTimeout(() => {
            errorToast.classList.add('show');
            setTimeout(() => {
                errorToast.classList.remove('show');
                setTimeout(() => {
                    document.body.removeChild(errorToast);
                }, 300);
            }, 3000);
        }, 10);
    }
    
    // Function to shake an element
    function shakElement(element) {
        element.classList.add('shake');
        setTimeout(() => element.classList.remove('shake'), 600);
    }
    
    // Add confetti effect to download button
    downloadBtn.addEventListener('click', () => {
        // Simple confetti effect (assuming we're just showing feedback)
        showSuccess('Sticker downloaded successfully!');
    });
    
    // Function to show success messages
    function showSuccess(message) {
        const successToast = document.createElement('div');
        successToast.className = 'success-toast';
        successToast.innerHTML = `<i class="ri-check-line"></i> ${message}`;
        document.body.appendChild(successToast);
        
        setTimeout(() => {
            successToast.classList.add('show');
            setTimeout(() => {
                successToast.classList.remove('show');
                setTimeout(() => {
                    document.body.removeChild(successToast);
                }, 300);
            }, 3000);
        }, 10);
    }
    
    // Function to update sticker quantity
    function updateStickerQuantity(filename, newQuantity) {
        console.log(`Updating quantity for ${filename} to ${newQuantity}`);
        
        fetch('/update-quantity', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ 
                filename: filename,
                quantity: newQuantity 
            }),
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                console.log("Quantity updated successfully:", data.template_stickers);
                templateStickers = data.template_stickers;
                updateTemplateDisplay();
            } else {
                console.error("Error updating quantity:", data.error);
                showError(data.error || 'Failed to update quantity');
            }
        })
        .catch(error => {
            console.error('Error updating quantity:', error);
            showError('Failed to update sticker quantity');
        });
    }

    // Coins Functions
    function loadCoins() {
        fetch('/get-coins')
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    currentCoins = data.coins;
                    updateCoinsDisplay();
                }
            })
            .catch(error => {
                console.error('Error loading coins:', error);
            });
    }
    
    function updateCoinsDisplay() {
        coinsCountHeader.textContent = currentCoins;
    }
    
    function showCoinsModal() {
        // Reset coupon direct input and status
        coinsCouponDirectInput.value = '';
        coinsCouponDirectInput.disabled = false;
        applyCouponDirectBtn.disabled = false;
        applyCouponDirectBtn.innerHTML = 'Apply';
        couponDirectStatus.textContent = '';
        couponDirectStatus.className = 'coupon-status';
        
        // Show packages and coupon section
        document.querySelector('.coins-packages').classList.remove('hidden');
        document.querySelector('.coupon-section').classList.remove('hidden');
        
        // Hide the form
        coinsForm.classList.add('hidden');
        
        // Reset selected package
        selectedPackage = null;
        
        coinsModal.classList.remove('hidden');
        setTimeout(() => {
            coinsModal.classList.add('visible');
        }, 10);
    }
    
    function hideCoinsModal() {
        coinsModal.classList.remove('visible');
        setTimeout(() => {
            coinsModal.classList.add('hidden');
        }, 300);
    }
    
    function selectPackage(packageType) {
        if (!coinPackagesData[packageType]) return;
        
        selectedPackage = packageType;
        const packageData = coinPackagesData[packageType];
        
        // Update UI with selected package details
        selectedPackageName.textContent = packageData.name;
        selectedPackageAmount.textContent = packageData.amount;
        selectedPackagePrice.textContent = packageData.price.toFixed(2);
        
        // Reset coupon state when changing packages
        resetCouponState();
        
        // Hide packages and coupon section
        document.querySelector('.coins-packages').classList.add('hidden');
        document.querySelector('.coupon-section').classList.add('hidden');
        
        // Show form
        coinsForm.classList.remove('hidden');
    }
    
    function resetCouponState() {
        couponApplied = false;
        additionalCoins = 0;
        coinsCouponDirectInput.value = '';
        coinsCouponDirectInput.disabled = false;
        applyCouponDirectBtn.disabled = false;
        applyCouponDirectBtn.innerHTML = 'Apply';
        couponDirectStatus.textContent = '';
        couponDirectStatus.className = 'coupon-status';
    }
    
    async function validateDirectCoupon() {
        const couponCode = coinsCouponDirectInput.value.trim();
        
        if (!couponCode) {
            couponDirectStatus.textContent = "Please enter a coupon code.";
            couponDirectStatus.className = 'coupon-status error';
            return;
        }
        
        // Disable the input and button while checking
        coinsCouponDirectInput.disabled = true;
        applyCouponDirectBtn.disabled = true;
        applyCouponDirectBtn.innerHTML = '<i class="ri-loader-4-line ri-spin"></i>';
        
        try {
            // Call the backend to validate and apply the coupon directly
            const response = await fetch('/purchase-coins', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    coupon: couponCode,
                    direct_apply: true  // Indicate this is a direct coupon application
                })
            });
            
            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.error || 'Invalid coupon code.');
            }
            
            const data = await response.json();
            
            if (data.success && data.coins_added) {
                // Update the UI to show success
                couponDirectStatus.textContent = `Success! ${data.coins_added} coins have been added to your account.`;
                couponDirectStatus.className = 'coupon-status success';
                
                applyCouponDirectBtn.innerHTML = '<i class="ri-check-line"></i> Applied';
                
                // Hide the packages section
                document.querySelector('.coins-packages').classList.add('hidden');
                
                // Update the current coins
                currentCoins = data.current_coins;
                updateCoinsDisplay();
                
                // Show a success message
                showSuccess(`Coupon redeemed! ${data.coins_added} coins have been added to your account.`);
                
                // After a delay, close the modal
                setTimeout(() => {
                    hideCoinsModal();
                }, 3000);
            } else {
                throw new Error('Failed to apply coupon.');
            }
            
        } catch (error) {
            console.error("Error validating coupon:", error);
            couponDirectStatus.textContent = error.message || "Error applying coupon. Please try again.";
            couponDirectStatus.className = 'coupon-status error';
            
            // Re-enable the input and button
            coinsCouponDirectInput.disabled = false;
            applyCouponDirectBtn.disabled = false;
            applyCouponDirectBtn.innerHTML = 'Apply';
        }
    }
    
    // Event Listeners for Coins
    buyCoinsHeaderBtn.addEventListener('click', showCoinsModal);
    coinsModalCloseBtn.addEventListener('click', hideCoinsModal);
    
    // Event listeners for package selection
    packageSelectBtns.forEach(btn => {
        btn.addEventListener('click', function(e) {
            e.stopPropagation();
            const packageType = this.closest('.coins-package').dataset.package;
            selectPackage(packageType);
        });
    });
    
    // Coupon validation
    applyCouponDirectBtn.addEventListener('click', validateDirectCoupon);
    
    // Make the entire package card clickable
    coinsPackages.forEach(pkg => {
        pkg.addEventListener('click', function() {
            const packageType = this.dataset.package;
            selectPackage(packageType);
        });
    });
    
    // Back button
    backToPackagesBtn.addEventListener('click', () => {
        document.querySelector('.coins-packages').classList.remove('hidden');
        document.querySelector('.coupon-section').classList.remove('hidden');
        coinsForm.classList.add('hidden');
        selectedPackage = null;
    });
    
    // Coins purchase form submission
    coinsForm.addEventListener('submit', handleCoinsPurchase);
    
    // Click outside to close the modal
    coinsModal.addEventListener('click', (e) => {
        if (e.target === coinsModal) {
            hideCoinsModal();
        }
    });
}); 