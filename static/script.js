// static/script.js
document.addEventListener('DOMContentLoaded', () => {
    // --- Theme Toggle ---
    const themeToggleButton = document.getElementById('theme-toggle-btn');
    const body = document.body;

    const applyTheme = (theme) => {
        if (theme === 'dark') {
            body.classList.add('dark-mode');
            if (themeToggleButton) themeToggleButton.textContent = '☀️ Light Mode';
        } else {
            body.classList.remove('dark-mode');
            if (themeToggleButton) themeToggleButton.textContent = '🌓 Dark Mode';
        }
    };

    const savedTheme = localStorage.getItem('theme');
    if (savedTheme) {
        applyTheme(savedTheme);
    } else {
        applyTheme('light'); // Default to light
    }

    if (themeToggleButton) {
        themeToggleButton.addEventListener('click', () => {
            let currentTheme = body.classList.contains('dark-mode') ? 'dark' : 'light';
            if (currentTheme === 'dark') {
                applyTheme('light');
                localStorage.setItem('theme', 'light');
            } else {
                applyTheme('dark');
                localStorage.setItem('theme', 'dark');
            }
        });
    }

    // --- Job History Modal ---
    const jobHistoryModal = document.getElementById('job-history-modal');
    const jobHistoryBtn = document.getElementById('job-history-btn');    
    const jobHistoryModalCloseBtn = document.getElementById('job-history-modal-close-btn'); 

    if (jobHistoryBtn) {
        jobHistoryBtn.addEventListener('click', () => {
            if (jobHistoryModal) jobHistoryModal.style.display = 'block';
        });
    }

    if (jobHistoryModalCloseBtn) {
        jobHistoryModalCloseBtn.addEventListener('click', () => {
            if (jobHistoryModal) jobHistoryModal.style.display = 'none';
        });
    }

    window.addEventListener('click', (event) => {
        if (event.target === jobHistoryModal) {
            if (jobHistoryModal) jobHistoryModal.style.display = 'none';
        }
    });

    document.addEventListener('keydown', function(event) {
        if (event.key === "Escape" || event.key === "Esc") {
            if (jobHistoryModal && jobHistoryModal.style.display === 'block') {
                jobHistoryModal.style.display = 'none';
            }
        }
    });

    // --- AJAX for Container Selection & Dynamic Button Disabling ---
    const containerCards = document.querySelectorAll('.container-card'); 
    const selectedCountDisplay = document.getElementById('selected-count-display'); 
    const generateStackBtn = document.getElementById('generate-stack-btn');
    const generateIndividualsBtn = document.getElementById('generate-individuals-btn');

    async function toggleContainerSelection(containerId, containerName) {
        try {
            const response = await fetch('/api/toggle_selection', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ container_id: containerId, container_name: containerName })
            });

            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.error || `Server responded with ${response.status}`);
            }

            return await response.json();
        } catch (error) {
            console.error('Error toggling selection:', error);
            throw error;
        }
    }

    function updateUIAfterToggle(data, cardElement) {
        if (data.success) {
            console.log(`Container ${data.id} selection toggled. New state: ${data.selected}. Count: ${data.selected_count}`);
            if (selectedCountDisplay) {
                selectedCountDisplay.textContent = `Selected Containers: (${data.selected_count})`;
            }
            updateGenerateButtonsState(data.selected_count);

            cardElement.classList.toggle('selected', data.selected);
            const icon = cardElement.querySelector('.icon');
            if (icon) {
                icon.textContent = data.selected ? '✅' : '🔲';
            }
        } else {
            console.error('Error toggling selection:', data.error || 'Unknown server error');
            alert('Error updating selection on server: ' + (data.error || 'Unknown error'));
        }
    }

    function updateGenerateButtonsState(count) {
        const hasSelection = count > 0;
        console.log(`[Debug JS] updateGenerateButtonsState called with count: ${count}. Has selection: ${hasSelection}`);
        
        if (generateStackBtn) {
            console.log(`[Debug JS] generateStackBtn found. Current disabled: ${generateStackBtn.disabled}. Setting to: ${!hasSelection}`);
            generateStackBtn.disabled = !hasSelection;
        } else {
            console.log(`[Debug JS] generateStackBtn NOT found.`);
        }
        if (generateIndividualsBtn) {
            console.log(`[Debug JS] generateIndividualsBtn found. Current disabled: ${generateIndividualsBtn.disabled}. Setting to: ${!hasSelection}`);
            generateIndividualsBtn.disabled = !hasSelection;
        } else {
            console.log(`[Debug JS] generateIndividualsBtn NOT found.`);
        }
    }

    containerCards.forEach(card => {
        card.addEventListener('click', async function() {
            const containerId = this.dataset.containerId;
            const containerName = this.dataset.containerName;
            
            if (!containerId || !containerName) {
                console.error('Card is missing data-container-id or data-container-name');
                return;
            }

            try {
                this.classList.add('loading'); // Add loading state
                const result = await toggleContainerSelection(containerId, containerName);
                updateUIAfterToggle(result, this);
            } catch (error) {
                alert('Error updating selection: ' + error.message);
                // Revert the visual change if there was an error
                this.classList.toggle('selected');
                const icon = this.querySelector('.icon');
                if (icon) {
                    icon.textContent = this.classList.contains('selected') ? '✅' : '🔲';
                }
            } finally {
                this.classList.remove('loading'); // Remove loading state
            }
        });
    });

    // Initial state check for generate buttons
    if (selectedCountDisplay) {
        const match = selectedCountDisplay.textContent.match(/\((\d+)\)/);
        const initialCount = match ? parseInt(match[1], 10) : 0;
        updateGenerateButtonsState(initialCount);
    }

    // --- Job Initiation and Status Polling ---
    async function initiateJob(action, files) {
        try {
            const response = await fetch(`/${action}`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ files: files })
            });
            const data = await response.json();
            return data.job_id;
        } catch (error) {
            console.error(`Error initiating ${action}:`, error);
            throw error;
        }
    }

    async function checkJobStatus(jobId) {
        try {
            const response = await fetch(`/check_job_status/${jobId}`);
            return await response.json();
        } catch (error) {
            console.error('Error checking job status:', error);
            throw error;
        }
    }

    async function pollJobStatus(jobId, updateUI) {
        const status = await checkJobStatus(jobId);
        updateUI(status);
        if (status.status === 'in_progress') {
            setTimeout(() => pollJobStatus(jobId, updateUI), 1000);  // Poll every second
        } else if (status.status === 'completed' && status.message) {
            displayFlashMessage(status.message, status.category);
        }
    }

    document.getElementById('save-to-local-btn').addEventListener('click', async () => {
        try {
            const jobId = await initiateJob('save_to_local', getCurrentFiles());
            pollJobStatus(jobId, updateSaveToLocalUI);
        } catch (error) {
            alert('Error initiating save to local: ' + error.message);
        }
    });

    document.getElementById('upload-to-github-btn').addEventListener('click', async () => {
        try {
            const jobId = await initiateJob('upload_to_github', getCurrentFiles());
            pollJobStatus(jobId, updateUploadToGithubUI);
        } catch (error) {
            alert('Error initiating GitHub upload: ' + error.message);
        }
    });

    function updateSaveToLocalUI(status) {
        const statusElement = document.getElementById('save-to-local-status');
        statusElement.textContent = status.message;
        if (status.status === 'completed') {
            statusElement.classList.add('success');
        } else if (status.status === 'failed') {
            statusElement.classList.add('error');
        }
    }

    function updateUploadToGithubUI(status) {
        const statusElement = document.getElementById('upload-to-github-status');
        statusElement.textContent = status.message;
        if (status.status === 'completed') {
            statusElement.classList.add('success');
        } else if (status.status === 'failed') {
            statusElement.classList.add('error');
        }
    }

    function displayFlashMessage(message, category) {
        const flashContainer = document.createElement('div');
        flashContainer.className = `alert alert-${category}`;
        flashContainer.textContent = message;
        
        const flashMessageContainer = document.getElementById('flash-message-container');
        if (flashMessageContainer) {
            const existingFlash = flashMessageContainer.querySelector('.alert');
            if (existingFlash) {
                flashMessageContainer.removeChild(existingFlash);
            }
            flashMessageContainer.appendChild(flashContainer);
            
            setTimeout(() => {
                flashContainer.remove();
            }, 5000);  // Remove the flash message after 5 seconds
        }
    }

    function getCurrentFiles() {
        // Implement this function to return the current list of files to be saved/uploaded
        // This might involve getting the data from your current UI state
    }

    // Add this function to handle the column slider change
    function updateGridColumns(value) {
        document.documentElement.style.setProperty('--grid-columns', value);
        // Update the display of the current value
        const columnDisplay = document.getElementById('num_cols_display');
        if (columnDisplay) {
            columnDisplay.textContent = value;
        }

        // Send AJAX request to update server
        fetch('/update_columns', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ num_cols: value })
        }).then(response => response.json())
          .then(data => {
              if (data.success) {
                  console.log('Column update response:', data.message);
              } else {
                  console.error('Error updating columns:', data.message);
              }
          })
          .catch(error => console.error('Error updating columns:', error));
    }

    // Add an event listener for the column slider
    const columnSlider = document.getElementById('num_cols_slider');
    if (columnSlider) {
        columnSlider.addEventListener('input', function() {
            updateGridColumns(this.value);
        });

        // Initialize the grid with the current slider value
        updateGridColumns(columnSlider.value);
    }
});
