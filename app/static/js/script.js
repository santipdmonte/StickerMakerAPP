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
    
    // Initially hide the sticker result
    stickerResult.style.display = 'none';
    
    // Add animation to container on load
    setTimeout(() => {
        container.style.opacity = '1';
        container.style.transform = 'translateY(0)';
    }, 100);

    // Initial focus on the prompt input with delay for better UX
    setTimeout(() => {
        promptInput.focus();
    }, 500);
    
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
        
        // Get selected quality
        const quality = getSelectedQuality();
        
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
            
            const data = await response.json();
            
            if (!response.ok) {
                throw new Error(data.error || 'Failed to generate sticker');
            }
            
            // Update the image and download link
            stickerImage.src = `data:image/png;base64,${data.image}`;
            downloadBtn.href = `/static/imgs/${data.filename}`;
            
            // Hide loading spinner and show result
            loadingSpinner.classList.add('hidden');
            stickerResult.style.display = 'flex';
            
            // Add a subtle animation to the sticker image
            stickerImage.style.opacity = '0';
            stickerImage.style.transform = 'scale(0.9)';
            
            // Force reflow
            stickerImage.offsetHeight;
            
            // Apply animation
            stickerImage.style.transition = 'opacity 0.5s ease, transform 0.5s ease';
            stickerImage.style.opacity = '1';
            stickerImage.style.transform = 'scale(1)';
            
            // Add pulse animation to download button
            setTimeout(() => {
                downloadBtn.classList.add('pulse');
                setTimeout(() => downloadBtn.classList.remove('pulse'), 1000);
            }, 1000);
            
        } catch (error) {
            showError(error.message);
            loadingSpinner.classList.add('hidden');
        } finally {
            generateBtn.disabled = false;
            generateBtn.innerHTML = '<i class="ri-magic-line"></i> Generate Sticker';
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
}); 