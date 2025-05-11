document.addEventListener('DOMContentLoaded', () => {
    // Agregar estilo para el toast de información si no existe
    if (!document.getElementById('toast-styles')) {
        const toastStyles = document.createElement('style');
        toastStyles.id = 'toast-styles';
        toastStyles.textContent = `
            .info-toast {
                position: fixed;
                bottom: 20px;
                left: 50%;
                transform: translateX(-50%) translateY(100px);
                background-color: #3498db;
                color: white;
                padding: 12px 20px;
                border-radius: 50px;
                box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
                display: flex;
                align-items: center;
                justify-content: center;
                gap: 8px;
                z-index: 10000;
                opacity: 0;
                transition: transform 0.3s ease, opacity 0.3s ease;
                font-family: 'Poppins', sans-serif;
                font-size: 14px;
            }
            .info-toast i {
                font-size: 18px;
            }
            .info-toast.show {
                opacity: 1;
                transform: translateX(-50%) translateY(0);
            }
        `;
        document.head.appendChild(toastStyles);
    }
    
    // UI Elements
    const promptInput = document.getElementById('prompt-input');
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
    
    // Reference image elements
    const addReferenceBtn = document.getElementById('add-reference-btn');
    const referenceImageInput = document.getElementById('reference-image-input');
    const referenceImagePreview = document.getElementById('reference-image-preview');
    
    // Image data storage
    let referenceImageData = null;
    let currentGeneratedSticker = null;
    let templateStickers = [];
    
    // S3 state tracking
    let s3Enabled = true;  // Default assumption
    let s3StatusChecked = false;
    
    // Check S3 status on page load
    checkS3Status();
    
    // Function to check S3 status
    function checkS3Status() {
        fetch('/debug-s3')
            .then(response => response.json())
            .then(data => {
                s3Enabled = data.s3_enabled === true;
                s3StatusChecked = true;
                console.log(`S3 status checked: ${s3Enabled ? 'enabled' : 'disabled'}`);
            })
            .catch(error => {
                console.error('Error checking S3 status:', error);
                s3Enabled = false;  // Assume disabled on error
                s3StatusChecked = true;
            });
    }
    
    // Function to get image URL - siempre usa la ruta '/img/' que redirige a S3
    function getImageUrl(filename) {
        return `/img/${filename}`;
    }
    
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
            const imgWrapper = document.createElement('div');
            imgWrapper.className = 'template-image-wrapper';
            imgWrapper.style.width = '100%';
            imgWrapper.style.height = '150px';
            imgWrapper.style.display = 'flex';
            imgWrapper.style.alignItems = 'center';
            imgWrapper.style.justifyContent = 'center';
            imgWrapper.style.position = 'relative';
            
            // Agregar indicador de carga
            const loadingSpinner = document.createElement('div');
            loadingSpinner.className = 'spinner';
            loadingSpinner.style.width = '30px';
            loadingSpinner.style.height = '30px';
            loadingSpinner.style.border = '3px solid rgba(124, 93, 250, 0.1)';
            loadingSpinner.style.borderRadius = '50%';
            loadingSpinner.style.borderTopColor = 'var(--primary-color)';
            loadingSpinner.style.animation = 'spin 1s ease-in-out infinite';
            imgWrapper.appendChild(loadingSpinner);
            
            const img = document.createElement('img');
            img.alt = 'Template sticker';
            img.style.display = 'none';
            img.style.maxWidth = '100%';
            img.style.maxHeight = '100%';
            img.style.objectFit = 'contain';
            
            // Intentar cargar desde caché local primero
            const cachedSrc = localStorage.getItem(`img_cache_${filename}`);
            if (cachedSrc) {
                img.src = cachedSrc;
                console.log(`Using cached image for template: ${filename}`);
            } else {
                // Siempre usar la ruta /img/ que redirige a S3
                img.src = getImageUrl(filename);
                console.log(`Loading template image: ${filename} from ${img.src}`);
            }
            
            // Cuando la imagen carga correctamente
            img.onload = function() {
                // Guardar en caché para futuras cargas
                try {
                    localStorage.setItem(`img_cache_${filename}`, img.src);
                } catch (e) {
                    console.warn('Error caching template image:', e);
                }
                
                // Mostrar imagen y ocultar spinner
                loadingSpinner.style.display = 'none';
                img.style.display = 'block';
            };
            
            // Manejar errores de carga
            img.onerror = function() {
                console.error(`Error loading template image: ${filename}`);
                
                // Limpiar caché si la URL era inválida
                localStorage.removeItem(`img_cache_${filename}`);
                
                // Mostrar un placeholder de error
                loadingSpinner.style.display = 'none';
                const errorIcon = document.createElement('div');
                errorIcon.innerHTML = '<i class="ri-image-line" style="font-size: 40px; color: #ccc;"></i>';
                imgWrapper.appendChild(errorIcon);
            };
            
            imgWrapper.appendChild(img);
            stickerItem.appendChild(imgWrapper);
            
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
        
        // Mostrar un indicador de carga mientras se procesa el template
        const loadingToast = document.createElement('div');
        loadingToast.className = 'info-toast show';
        loadingToast.innerHTML = '<i class="ri-loader-4-line ri-spin"></i> Generando template...';
        document.body.appendChild(loadingToast);
        
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
            if (loadedCount === totalExpectedImages) {
                // Eliminar el toast de carga
                document.body.removeChild(loadingToast);
                
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
        
        // Función para obtener la imagen directamente mediante fetch para evitar problemas CORS
        const fetchImageAsBlob = async (url) => {
            try {
                // Usamos el endpoint /img/ para obtener la redirección a S3
                const response = await fetch(url, { mode: 'cors' });
                if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
                const blob = await response.blob();
                return URL.createObjectURL(blob);
            } catch (error) {
                console.error(`Error fetching image: ${error}`);
                return null;
            }
        };
        
        // Función para cargar y dibujar la imagen en el canvas
        const loadAndDrawImage = async (filename, index) => {
            // Posición donde se dibujará esta imagen
            const col = index % columns;
            const row = Math.floor(index / columns);
            const x = padding + col * (stickerWidth + padding);
            const y = padding + row * (stickerHeight + padding);
            
            try {
                // Primero intentamos usar la URL en caché, pero pasando por fetch para evitar CORS
                const cachedSrc = localStorage.getItem(`img_cache_${filename}`);
                let blobUrl;
                
                if (cachedSrc) {
                    // Intentar usar la URL cacheada pero obteniéndola como blob
                    blobUrl = await fetchImageAsBlob(cachedSrc);
                }
                
                // Si no hay URL en caché o falló, intentar con la ruta directa
                if (!blobUrl) {
                    blobUrl = await fetchImageAsBlob(`/img/${filename}`);
                    
                    // Si se obtuvo la URL, guardarla en caché
                    if (blobUrl) {
                        try {
                            localStorage.setItem(`img_cache_${filename}`, `/img/${filename}`);
                        } catch (e) {
                            console.warn('Error caching image URL:', e);
                        }
                    }
                }
                
                if (blobUrl) {
                    // Crear y cargar la imagen desde la URL del blob
                    const img = new Image();
                    img.onload = () => {
                        ctx.drawImage(img, x, y, stickerWidth, stickerHeight);
                        URL.revokeObjectURL(blobUrl); // Liberar memoria
                        loadedCount++;
                        drawTemplateAndDownload();
                    };
                    img.onerror = () => {
                        console.error(`Failed to load blob URL for ${filename}`);
                        drawPlaceholder(x, y);
                        URL.revokeObjectURL(blobUrl); // Liberar memoria
                        loadedCount++;
                        drawTemplateAndDownload();
                    };
                    img.src = blobUrl;
                } else {
                    // Si no se pudo obtener la imagen, dibujar un placeholder
                    drawPlaceholder(x, y);
                    loadedCount++;
                    drawTemplateAndDownload();
                }
            } catch (error) {
                console.error(`Error processing image ${filename}:`, error);
                drawPlaceholder(x, y);
                loadedCount++;
                drawTemplateAndDownload();
            }
        };
        
        // Función para dibujar un placeholder
        const drawPlaceholder = (x, y) => {
            // Dibujar un cuadro gris con un ícono de error
            ctx.fillStyle = '#f0f0f0';
            ctx.fillRect(x, y, stickerWidth, stickerHeight);
            ctx.fillStyle = '#cccccc';
            ctx.font = '48px sans-serif';
            ctx.textAlign = 'center';
            ctx.textBaseline = 'middle';
            ctx.fillText('?', x + stickerWidth/2, y + stickerHeight/2);
        };
        
        // Iniciar la carga de todas las imágenes
        stickerInstances.forEach((filename, index) => {
            loadAndDrawImage(filename, index);
        });
        
        // Si después de 15 segundos no se ha completado, forzar la descarga con lo que se tenga
        setTimeout(() => {
            if (loadedCount < totalExpectedImages) {
                console.warn(`Timeout reached. Forcing download with ${loadedCount}/${totalExpectedImages} images loaded`);
                // Dibujar placeholders para las imágenes restantes
                for (let i = loadedCount; i < totalExpectedImages; i++) {
                    const col = i % columns;
                    const row = Math.floor(i / columns);
                    const x = padding + col * (stickerWidth + padding);
                    const y = padding + row * (stickerHeight + padding);
                    drawPlaceholder(x, y);
                }
                loadedCount = totalExpectedImages;
                drawTemplateAndDownload();
            }
        }, 15000);
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
    
    // Modal de imagen ampliada
    const imagePreviewModal = document.getElementById('image-preview-modal');
    const enlargedImage = document.getElementById('enlarged-image');
    const imageModalCloseBtn = document.getElementById('image-modal-close-btn');
    
    // Función para mostrar la imagen ampliada
    function showEnlargedImage(imgSrc) {
        // Asegurarnos de que no haya eventos previos registrados
        enlargedImage.onload = null;
        enlargedImage.onerror = null;
        
        // Agregar clase de carga
        const imageContainer = imagePreviewModal.querySelector('.image-container');
        imageContainer.classList.add('loading');
        
        // Configurar la imagen para mostrar el indicador de carga hasta que esté lista
        enlargedImage.onload = function() {
            imageContainer.classList.remove('loading');
        };
        
        enlargedImage.onerror = function() {
            imageContainer.classList.remove('loading');
            // Usar un timeout para evitar mostrar errores si el modal está cerrándose
            if (!imagePreviewModal.classList.contains('hidden')) {
                showError('Error loading image');
                closeImagePreviewModal();
            }
        };
        
        // Establecer la fuente de la imagen y mostrar el modal
        enlargedImage.src = imgSrc;
        imagePreviewModal.classList.remove('hidden');
        
        // Pequeño delay para iniciar la animación
        requestAnimationFrame(() => {
            imagePreviewModal.classList.add('visible');
        });
        
        // Deshabilitar scroll en el body mientras el modal está abierto
        document.body.style.overflow = 'hidden';
    }
    
    // Función para cerrar el modal de imagen ampliada
    function closeImagePreviewModal() {
        imagePreviewModal.classList.remove('visible');
        
        // Esperar a que termine la animación antes de ocultar completamente
        setTimeout(() => {
            imagePreviewModal.classList.add('hidden');
            
            // Eliminar los event handlers antes de limpiar la fuente de la imagen
            // para evitar que se dispare el onerror
            enlargedImage.onload = null;
            enlargedImage.onerror = null;
            enlargedImage.src = '';
            
            // Restaurar scroll
            document.body.style.overflow = '';
        }, 300);
    }
    
    // Evento para cerrar el modal cuando se hace clic en el botón de cerrar
    imageModalCloseBtn.addEventListener('click', closeImagePreviewModal);
    
    // Evento para cerrar el modal cuando se hace clic en el fondo
    imagePreviewModal.addEventListener('click', (e) => {
        // Solo cerramos si el clic fue en el backdrop o en el contenedor del modal, no en la imagen
        if (e.target === imagePreviewModal || e.target.classList.contains('modal-backdrop') || e.target.classList.contains('modern-image-modal')) {
            closeImagePreviewModal();
        }
    });
    
    // Evento para cerrar el modal con la tecla ESC
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape' && !imagePreviewModal.classList.contains('hidden')) {
            closeImagePreviewModal();
        }
    });
    
    // Add reference image button handler
    addReferenceBtn.addEventListener('click', (e) => {
        e.preventDefault();
        referenceImageInput.click();
    });
    
    // Reference image input change handler
    referenceImageInput.addEventListener('change', handleFileSelect);
    
    // Hacer clic en la miniatura para ver la imagen ampliada
    referenceImagePreview.addEventListener('click', (e) => {
        // Solo activar si se hizo clic en la imagen, no en el botón de cerrar
        if (!e.target.closest('.remove-thumbnail-btn')) {
            const img = referenceImagePreview.querySelector('img');
            if (img && img.src) {
                showEnlargedImage(img.src);
            }
        }
    });
    
    // Remove reference image handler
    referenceImagePreview.querySelector('.remove-thumbnail-btn').addEventListener('click', () => {
        referenceImagePreview.classList.add('hidden');
        referenceImageData = null;
        // Reiniciar el input de archivo para permitir la selección del mismo archivo nuevamente
        referenceImageInput.value = '';
    });
    
    // Function to handle file selection for reference image
    function handleFileSelect(e) {
        const file = e.target.files[0];
        if (!file) return;
        
        // Only process image files
        if (!file.type.match('image.*')) {
            showError('Please select an image file');
            return;
        }
        
        // Check file size - limit to 5MB
        if (file.size > 5 * 1024 * 1024) {
            showError('Image size must be less than 5MB');
            return;
        }
        
        const reader = new FileReader();
        
        reader.onload = function(event) {
            const img = referenceImagePreview.querySelector('img');
            img.src = event.target.result;
            referenceImageData = event.target.result;
            
            // Show the preview
            referenceImagePreview.classList.remove('hidden');
            // El CSS ajustará automáticamente los paddings
        };
        
        reader.readAsDataURL(file);
    }
    
    // Get selected quality
    function getSelectedQuality() {
        const qualityValue = document.querySelector('input[name="quality"]:checked').value;
        return qualityValue;
    }
    
    // Generate sticker
    async function generateSticker() {
        // Get prompt and check if reference image is present
        const prompt = promptInput.value.trim();
        const hasReferenceImage = referenceImageData !== null;
        
        // Validate input
        if (!prompt) {
            showError('Please enter a description for your sticker');
            shakElement(promptInput);
            return;
        }
        
        // Get quality level and determine coin cost
        const quality = getSelectedQuality();
        let coinCost = 10;  // Default for low quality
        
        if (quality === 'medium') {
            coinCost = 25;
        } else if (quality === 'high') {
            coinCost = 100;
        }
        
        // Check if user has enough coins
        if (currentCoins < coinCost) {
            showError(`Not enough coins. You need ${coinCost} coins. Current: ${currentCoins}`);
            return;
        }
        
        // Show loading state
        loadingSpinner.classList.remove('hidden');
        generateBtn.disabled = true;
        stickerResult.style.display = 'none';
        
        try {
            // Prepare form data for API request
            const formData = new FormData();
            formData.append('prompt', prompt);
            formData.append('quality', quality);
            
            // Add reference image if available
            if (hasReferenceImage) {
                formData.append('mode', 'reference');
                formData.append('reference_image', dataURItoBlob(referenceImageData));
            } else {
                formData.append('mode', 'simple');
            }
            
            // Make API request
            const response = await fetch('/generate', {
                method: 'POST',
                body: formData
            });
            
            if (!response.ok) {
                throw new Error('Failed to generate sticker');
            }
            
            const data = await response.json();
            
            if (data.success) {
                // Update UI with generated sticker
                currentGeneratedSticker = data.filename;
                stickerImage.src = getImageUrl(data.filename);
                downloadBtn.href = getImageUrl(data.filename);
                downloadBtn.download = 'sticker-' + data.filename;
                
                // Show result
                stickerResult.style.display = 'flex';
                
                // Deduct coins
                await deductCoins(coinCost);
                
                // Scroll to result
                resultsSection.scrollIntoView({ behavior: 'smooth' });
                
                // Show success message
                if (hasReferenceImage) {
                    showSuccess('Sticker generated with reference image!');
                } else {
                    showSuccess('Sticker generated successfully!');
                }
                
                // Update UI if no coins left
                if (currentCoins <= 0) {
                    generateBtn.disabled = true;
                }
            } else {
                showError(data.error || 'Failed to generate sticker');
            }
        } catch (error) {
            console.error('Error generating sticker:', error);
            showError('Error generating sticker. Please try again.');
        } finally {
            // Hide loading state
            loadingSpinner.classList.add('hidden');
            generateBtn.disabled = false;
        }
    }
    
    // Helper function to convert Data URI to Blob
    function dataURItoBlob(dataURI) {
        const byteString = atob(dataURI.split(',')[1]);
        const mimeString = dataURI.split(',')[0].split(':')[1].split(';')[0];
        const ab = new ArrayBuffer(byteString.length);
        const ia = new Uint8Array(ab);
        
        for (let i = 0; i < byteString.length; i++) {
            ia[i] = byteString.charCodeAt(i);
        }
        
        return new Blob([ab], {type: mimeString});
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
    
    // Function to handle coin purchase submission
    async function handleCoinsPurchase(e) {
        e.preventDefault();
        
        if (!selectedPackage) {
            showError('Please select a coin package first.');
            return;
        }
        
        if (!mp) {
            showError("Payment system is not available. Please check configuration.");
            return;
        }
        
        const name = coinsNameInput.value.trim();
        const email = coinsEmailInput.value.trim();
        
        // Frontend validation
        let isValid = true;
        if (!name) {
            showError("Please enter your name.");
            shakElement(coinsNameInput);
            isValid = false;
        }
        
        if (!email || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
            showError("Please enter a valid email address.");
            shakElement(coinsEmailInput);
            isValid = false;
        }
        
        if (!isValid) {
            return;
        }
        
        // Disable button and show loading state
        finalizeCoinsBtn.disabled = true;
        finalizeCoinsBtn.innerHTML = '<i class="ri-loader-4-line ri-spin"></i> Processing...';
        
        try {
            // Get any coupon code from the form
            const couponCode = coinsCouponDirectInput.value.trim();
            
            // Call backend to create preference
            const response = await fetch('/purchase-coins', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    name: name,
                    email: email,
                    package: selectedPackage,
                    coupon: couponCode
                })
            });
            
            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.error || 'Failed to create coin purchase preference.');
            }
            
            const data = await response.json();
            
            if (data.success && data.preference_id) {
                // Hide modal before redirecting
                hideCoinsModal();
                
                // Redirect to Mercado Pago Checkout
                mp.checkout({
                    preference: {
                        id: data.preference_id
                    },
                    autoOpen: true
                });
            } else {
                throw new Error('Could not process payment at this time.');
            }
            
        } catch (error) {
            console.error("Coin purchase error:", error);
            showError(`Purchase failed: ${error.message}`);
            
            // Re-enable button
            finalizeCoinsBtn.disabled = false;
            finalizeCoinsBtn.innerHTML = '<i class="ri-secure-payment-line"></i> Purchase Coins';
        }
    }
    
    // Coins purchase form submission
    coinsForm.addEventListener('submit', handleCoinsPurchase);
    
    // Click outside to close the modal
    coinsModal.addEventListener('click', (e) => {
        if (e.target === coinsModal) {
            hideCoinsModal();
        }
    });

    // Generate button event listener
    generateBtn.addEventListener('click', generateSticker);
}); 