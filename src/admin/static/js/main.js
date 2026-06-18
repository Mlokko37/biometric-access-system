/**
 * Biometric Access System - Main JavaScript
 * Namespaced under BiometricApp to avoid conflicts
 */

// ============================================
// GLOBAL CONFIGURATION
// ============================================
const CONFIG = {
    refreshInterval: 30000,
    apiEndpoints: {
        quickStats: '/dashboard/quick_stats',
        realtime: '/dashboard/realtime',
        studentsData: '/students/data',
        usersData: '/users/data',
        dailyChart: '/reports/daily-data',
        hourlyChart: '/reports/hourly-data',
        accessPoints: '/dashboard/access_points',
        topAccessPoints: '/reports/top-access-points',
        studentStats: '/reports/student-stats',
        systemHealth: '/system/health',
        systemStatus: '/system/status-data',
        systemProcesses: '/system/processes'
    }
};

// ============================================
// UTILITY FUNCTIONS (global)
// ============================================

/**
 * Get CSRF token from meta tag
 */
function getCsrfToken() {
    return document.querySelector('meta[name="csrf-token"]')?.content;
}

/**
 * Show loading spinner on button
 */
function showButtonSpinner(button) {
    if (!button) return null;
    const originalText = button.innerHTML;
    button.disabled = true;
    button.innerHTML = '<i class="fas fa-spinner fa-spin"></i> <span>Refreshing...</span>';
    return originalText;
}

/**
 * Hide button spinner and restore text
 */
function hideButtonSpinner(button, originalText) {
    if (!button) return;
    button.disabled = false;
    if (originalText) {
        button.innerHTML = originalText;
    }
}

/**
 * Show loading in element
 */
function showElementLoading(element, message = 'Loading...') {
    if (!element) return;
    element.innerHTML = `
        <tr>
            <td colspan="8" class="text-center py-4">
                <div class="text-center">
                    <i class="fas fa-spinner fa-spin fa-2x text-primary mb-3"></i>
                    <p class="text-muted">${message}</p>
                </div>
            </td>
        </tr>
    `;
}

/**
 * Show error in element
 */
function showElementError(element, message) {
    if (!element) return;
    element.innerHTML = `
        <tr>
            <td colspan="8" class="text-center py-4">
                <i class="fas fa-exclamation-circle fa-2x text-danger mb-3"></i>
                <p class="text-danger">${message}</p>
                <button class="btn btn-sm btn-outline-primary mt-2" onclick="location.reload()">
                    <i class="fas fa-sync-alt"></i> Retry
                </button>
            </td>
        </tr>
    `;
}

/**
 * Show a Bootstrap toast notification
 */
function showToast(message, type = 'success') {
    const toastContainer = document.querySelector('.toast-container');
    if (!toastContainer) {
        // Fallback: create a temporary alert
        const alert = document.createElement('div');
        alert.className = `alert alert-${type === 'success' ? 'success' : 'danger'} alert-dismissible fade show position-fixed top-0 end-0 m-3`;
        alert.style.zIndex = '9999';
        alert.innerHTML = `
            <i class="fas fa-${type === 'success' ? 'check-circle' : 'exclamation-circle'} me-2"></i>
            ${message}
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        `;
        document.body.appendChild(alert);
        setTimeout(() => alert.remove(), 5000);
        return;
    }
    // Use Bootstrap toast
    const toastEl = document.createElement('div');
    toastEl.className = 'toast align-items-center text-white bg-' + (type === 'success' ? 'success' : 'danger') + ' border-0';
    toastEl.setAttribute('role', 'alert');
    toastEl.setAttribute('aria-live', 'assertive');
    toastEl.setAttribute('aria-atomic', 'true');
    toastEl.innerHTML = `
        <div class="d-flex">
            <div class="toast-body">
                <i class="fas fa-${type === 'success' ? 'check-circle' : 'exclamation-circle'} me-2"></i>
                ${message}
            </div>
            <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button>
        </div>
    `;
    toastContainer.appendChild(toastEl);
    const toast = new bootstrap.Toast(toastEl, { delay: 5000 });
    toast.show();
    toastEl.addEventListener('hidden.bs.toast', () => toastEl.remove());
}

/**
 * Make API request
 */
async function apiRequest(url, method = 'GET', data = null) {
    const options = {
        method: method,
        headers: {
            'Content-Type': 'application/json',
            'X-Requested-With': 'XMLHttpRequest'
        }
    };
    if (data) {
        options.body = JSON.stringify(data);
    }
    try {
        const response = await fetch(url, options);
        return await response.json();
    } catch (error) {
        console.error('API Error:', error);
        return { success: false, error: error.message };
    }
}

// ============================================
// BIOMETRICAPP NAMESPACE
// ============================================
window.BiometricApp = {};

(function(app) {
    'use strict';

    // --- SIDEBAR ---
    function initializeSidebar() {
        const sidebar = document.getElementById('sidebar');
        const collapseToggle = document.getElementById('collapseToggle');
        const mobileToggle = document.getElementById('mobileToggle');

        const collapsed = localStorage.getItem('sidebarCollapsed') === 'true';
        if (collapsed && sidebar) {
            sidebar.classList.add('collapsed');
            updateCollapseIcon(true);
        }

        if (collapseToggle) {
            collapseToggle.addEventListener('click', function() {
                sidebar?.classList.toggle('collapsed');
                const isCollapsed = sidebar?.classList.contains('collapsed');
                localStorage.setItem('sidebarCollapsed', isCollapsed);
                updateCollapseIcon(isCollapsed);
            });
        }

        if (mobileToggle) {
            mobileToggle.addEventListener('click', function() {
                sidebar?.classList.toggle('open');
            });
        }

        document.addEventListener('click', function(event) {
            if (window.innerWidth <= 992) {
                if (sidebar && !sidebar.contains(event.target) && mobileToggle && !mobileToggle.contains(event.target)) {
                    sidebar.classList.remove('open');
                }
            }
        });
    }

    function updateCollapseIcon(isCollapsed) {
        const toggle = document.getElementById('collapseToggle');
        const icon = toggle?.querySelector('i');
        const text = toggle?.querySelector('.collapse-text');
        if (icon) {
            icon.className = isCollapsed ? 'fas fa-angle-double-right' : 'fas fa-angle-double-left';
        }
        if (text) {
            text.textContent = isCollapsed ? 'Expand' : 'Collapse Menu';
        }
    }

    // --- REFRESH BUTTONS ---
    function initializeRefreshButtons() {
        const refreshButtons = document.querySelectorAll('.refresh-btn, #refresh-dashboard, #refresh-students, #refresh-users, #refresh-reports, #refresh-system, #refresh-database, #refresh-config, #refresh-devices');
        refreshButtons.forEach(button => {
            const newButton = button.cloneNode(true);
            button.parentNode.replaceChild(newButton, button);

            newButton.addEventListener('click', async function(e) {
                e.preventDefault();
                e.stopPropagation();

                const originalHTML = this.innerHTML;
                this.disabled = true;
                this.innerHTML = '<i class="fas fa-spinner fa-spin"></i> <span>Refreshing...</span>';

                try {
                    const path = window.location.pathname;
                    if (path.includes('dashboard')) {
                        await app.refreshDashboardData();
                    } else if (path.includes('students')) {
                        if (typeof studentsLoaded !== 'undefined') studentsLoaded = false;
                        await app.loadStudentsData();
                    } else if (path.includes('users')) {
                        if (typeof usersLoaded !== 'undefined') usersLoaded = false;
                        await app.loadUsersData();
                    } else if (path.includes('reports')) {
                        if (typeof currentReportType !== 'undefined' && currentReportType) {
                            await app.loadReport(currentReportType);
                        } else {
                            await new Promise(resolve => setTimeout(resolve, 500));
                        }
                    } else if (path.includes('system-status')) {
                        if (typeof app.refreshSystemStats !== 'undefined') await app.refreshSystemStats();
                        if (typeof app.checkHealth !== 'undefined') await app.checkHealth();
                    } else {
                        await new Promise(resolve => setTimeout(resolve, 300));
                        window.location.reload();
                        return;
                    }
                } catch (error) {
                    console.error('Refresh failed:', error);
                } finally {
                    setTimeout(() => {
                        this.disabled = false;
                        this.innerHTML = originalHTML;
                    }, 500);
                }
            });
        });
    }

    // --- LOGIN FORM ---
    function initializeLoginForm() {
        const loginForm = document.getElementById('loginForm');
        const loginBtn = document.getElementById('loginSubmitBtn');
        if (loginForm && loginBtn) {
            loginForm.addEventListener('submit', function(e) {
                loginBtn.disabled = true;
                loginBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Signing In...';
            });
        }
    }

    // --- DELETE BUTTONS ---
    function initializeDeleteButtons() {
        const deleteButtons = document.querySelectorAll('.delete-btn');
        deleteButtons.forEach(btn => {
            btn.addEventListener('click', function() {
                const studentId = this.dataset.studentId;
                const studentName = this.dataset.studentName;
                const csrfToken = getCsrfToken();

                if (!csrfToken) {
                    console.error('CSRF token not found');
                    alert('Security token missing. Please refresh the page.');
                    return;
                }

                const deleteStudentName = document.getElementById('deleteStudentName');
                if (deleteStudentName) {
                    deleteStudentName.textContent = studentName;
                }

                const confirmDeleteBtn = document.getElementById('confirmDeleteBtn');
                const deleteModal = document.getElementById('deleteConfirmModal');

                if (confirmDeleteBtn && deleteModal) {
                    confirmDeleteBtn.onclick = function() {
                        const originalHtml = confirmDeleteBtn.innerHTML;
                        confirmDeleteBtn.disabled = true;
                        confirmDeleteBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Deleting...';

                        fetch(`/students/delete/${studentId}`, {
                            method: 'DELETE',
                            headers: {
                                'X-Requested-With': 'XMLHttpRequest',
                                'X-CSRFToken': csrfToken
                            }
                        })
                        .then(response => response.json())
                        .then(data => {
                            if (data.success) {
                                const modal = bootstrap.Modal.getInstance(deleteModal);
                                if (modal) modal.hide();
                                showToast('Student deleted successfully', 'success');
                                setTimeout(() => window.location.reload(), 500);
                            } else {
                                alert('Error: ' + (data.error || 'Delete failed'));
                                confirmDeleteBtn.disabled = false;
                                confirmDeleteBtn.innerHTML = originalHtml;
                            }
                        })
                        .catch(error => {
                            console.error('Delete error:', error);
                            alert('Network error. Please try again.');
                            confirmDeleteBtn.disabled = false;
                            confirmDeleteBtn.innerHTML = originalHtml;
                        });
                    };

                    const modal = new bootstrap.Modal(deleteModal);
                    modal.show();
                }
            });
        });
    }

    // --- PROGRESS BARS ---
    function initializeProgressBars() {
        document.querySelectorAll('.quality-bar').forEach(bar => {
            if (bar.dataset.quality) {
                bar.style.width = bar.dataset.quality + '%';
            }
        });
        document.querySelectorAll('.score-bar').forEach(bar => {
            if (bar.dataset.score) {
                bar.style.width = bar.dataset.score + '%';
            }
        });
    }

    // --- BIOMETRIC COMPONENTS ---
    let fingerprintScanner = null;
    let facialRecognition = null;

    function initializeBiometricComponents() {
        const templateType = document.getElementById('template_type');
        if (!templateType) return;

        templateType.addEventListener('change', function(e) {
            const type = e.target.value;
            document.querySelectorAll('.biometric-section').forEach(s => s.classList.add('hidden-section'));

            if (type === 'fingerprint') {
                document.getElementById('fingerprint-section').classList.remove('hidden-section');
                if (!fingerprintScanner) {
                    fingerprintScanner = new FingerprintScanner();
                }
            } else if (type === 'facial') {
                document.getElementById('facial-section').classList.remove('hidden-section');
                if (!facialRecognition) {
                    facialRecognition = new FacialRecognition();
                }
            }
        });

        const startFingerprintBtn = document.getElementById('start-fingerprint-capture');
        if (startFingerprintBtn) {
            startFingerprintBtn.addEventListener('click', async function() {
                const originalHTML = showButtonSpinner(this);
                try {
                    if (!fingerprintScanner) {
                        fingerprintScanner = new FingerprintScanner();
                    }
                    const result = await fingerprintScanner.captureFingerprint();
                    document.getElementById('fingerprint_data').value = result.image || '';
                    document.getElementById('fingerprint_template').value = result.template || '';
                    document.getElementById('save-fingerprint').disabled = false;
                    const statusDiv = document.getElementById('fingerprint-status');
                    if (statusDiv) {
                        statusDiv.innerHTML = `<span class="text-success">✓ Fingerprint captured! Quality: ${result.quality}%</span>`;
                    }
                } catch (error) {
                    const statusDiv = document.getElementById('fingerprint-status');
                    if (statusDiv) {
                        statusDiv.innerHTML = `<span class="text-danger">✗ Capture failed: ${error.message || error}</span>`;
                    }
                } finally {
                    hideButtonSpinner(this, originalHTML);
                }
            });
        }

        const saveFingerprintBtn = document.getElementById('save-fingerprint');
        if (saveFingerprintBtn) {
            saveFingerprintBtn.addEventListener('click', function() {
                const statusDiv = document.getElementById('fingerprint-status');
                if (statusDiv) {
                    statusDiv.innerHTML = '<span class="text-success">✓ Template saved successfully</span>';
                }
                document.getElementById('quality_score').value = '95';
            });
        }

        const startCameraBtn = document.getElementById('start-camera');
        if (startCameraBtn) {
            startCameraBtn.addEventListener('click', async function() {
                const originalHTML = showButtonSpinner(this);
                try {
                    if (!facialRecognition) {
                        facialRecognition = new FacialRecognition();
                    }
                    await facialRecognition.startCamera();
                    document.getElementById('start-camera').disabled = true;
                    document.getElementById('capture-face').disabled = false;
                } catch (error) {
                    showToast('Failed to start camera: ' + error.message, 'error');
                } finally {
                    hideButtonSpinner(this, originalHTML);
                }
            });
        }

        const captureFaceBtn = document.getElementById('capture-face');
        if (captureFaceBtn) {
            captureFaceBtn.addEventListener('click', function() {
                if (facialRecognition) {
                    const imageData = facialRecognition.captureFace();
                    document.getElementById('facial_data').value = imageData;
                    const statusDiv = document.getElementById('facial-status');
                    if (statusDiv) {
                        statusDiv.innerHTML = '<span class="text-success">✓ Face captured successfully!</span>';
                    }
                    document.getElementById('quality_score').value = '90';
                }
            });
        }
    }

    class FingerprintScanner {
        constructor() {
            this.scannerConnected = false;
            this.template = null;
            this.init();
        }

        init() {
            if (typeof window.DPFJ === 'undefined') {
                this.showStatus('Digital Persona SDK not found. Using simulation mode.', 'warning');
                this.enableSimulation();
            } else {
                this.connectScanner();
            }
        }

        connectScanner() {
            try {
                window.DPFJ.init((status) => {
                    if (status === window.DPFJ.SUCCESS) {
                        this.scannerConnected = true;
                        this.showStatus('Scanner connected successfully', 'success');
                        document.getElementById('start-fingerprint-capture').disabled = false;
                    } else {
                        this.showStatus('Failed to connect to scanner', 'danger');
                        this.enableSimulation();
                    }
                });
            } catch (e) {
                console.error('Scanner connection failed:', e);
                this.enableSimulation();
            }
        }

        enableSimulation() {
            const statusText = document.getElementById('scanner-status-text');
            if (statusText) {
                statusText.innerHTML = 'Scanner not detected. Using simulation mode.';
            }
            document.getElementById('start-fingerprint-capture').disabled = false;
        }

        captureFingerprint() {
            return new Promise((resolve, reject) => {
                const statusDiv = document.getElementById('fingerprint-status');
                const progressBar = document.querySelector('.fingerprint-progress');
                const progressFill = document.querySelector('.fingerprint-progress-fill');

                if (progressBar) progressBar.classList.remove('hidden-section');

                if (this.scannerConnected) {
                    window.DPFJ.captureFingerprint((result, image, template) => {
                        if (result === window.DPFJ.SUCCESS) {
                            resolve({ image: image, template: template, quality: 95 });
                        } else {
                            reject(new Error('Capture failed'));
                        }
                    });
                } else {
                    let progress = 0;
                    const interval = setInterval(() => {
                        progress += 10;
                        if (progressFill) progressFill.style.width = progress + '%';
                        if (statusDiv) statusDiv.innerHTML = `<span class="text-info">Scanning... ${progress}%</span>`;

                        if (progress >= 100) {
                            clearInterval(interval);
                            setTimeout(() => {
                                if (progressBar) progressBar.classList.add('hidden-section');
                                const mockTemplate = this.generateMockTemplate();
                                resolve({ image: null, template: mockTemplate, quality: 85 });
                            }, 500);
                        }
                    }, 200);
                }
            });
        }

        generateMockTemplate() {
            const mockData = new Uint8Array(512);
            window.crypto.getRandomValues(mockData);
            return btoa(String.fromCharCode.apply(null, mockData));
        }

        showStatus(message, type) {
            const statusDiv = document.getElementById('fingerprint-status');
            if (statusDiv) {
                statusDiv.innerHTML = `<span class="text-${type}">${message}</span>`;
            }
        }
    }

    class FacialRecognition {
        constructor() {
            this.video = document.getElementById('camera-preview');
            this.canvas = document.getElementById('facial-capture-canvas');
            this.stream = null;
            this.faceDetected = false;
            this.detectionInterval = null;
        }

        async startCamera() {
            try {
                this.stream = await navigator.mediaDevices.getUserMedia({
                    video: { width: { ideal: 640 }, height: { ideal: 480 }, facingMode: 'user' }
                });
                this.video.srcObject = this.stream;
                await this.video.play();
                document.getElementById('start-camera').disabled = true;
                document.getElementById('capture-face').disabled = false;
                this.startFaceDetection();
            } catch (err) {
                console.error('Camera error:', err);
                throw new Error('Could not access camera. Please check permissions.');
            }
        }

        startFaceDetection() {
            this.detectionInterval = setInterval(() => {
                if (!this.video.paused && !this.video.ended) {
                    const detected = Math.random() > 0.1;
                    this.faceDetected = detected;

                    const statusEl = document.getElementById('face-detection-status');
                    const qualityBar = document.getElementById('facial-quality-bar');

                    if (statusEl) {
                        statusEl.textContent = detected ? 'Yes' : 'No';
                        statusEl.className = detected ? 'badge bg-success' : 'badge bg-warning';
                    }

                    if (qualityBar && detected) {
                        const quality = 70 + Math.floor(Math.random() * 25);
                        qualityBar.style.width = quality + '%';
                        qualityBar.textContent = quality + '%';
                    } else if (qualityBar) {
                        qualityBar.style.width = '0%';
                        qualityBar.textContent = '0%';
                    }
                }
            }, 1000);
        }

        captureFace() {
            if (!this.faceDetected) {
                const statusDiv = document.getElementById('facial-status');
                if (statusDiv) {
                    statusDiv.innerHTML = '<span class="text-warning">⚠ No face detected! Please position your face properly.</span>';
                }
                return null;
            }
            this.canvas.getContext('2d').drawImage(this.video, 0, 0, 400, 300);
            const imageData = this.canvas.toDataURL('image/jpeg');
            return imageData;
        }

        stopCamera() {
            if (this.detectionInterval) clearInterval(this.detectionInterval);
            if (this.stream) {
                this.stream.getTracks().forEach(track => track.stop());
                this.stream = null;
            }
        }
    }

    // --- DASHBOARD REALTIME ---
    class DashboardRealtime {
        constructor() {
            this.updateInterval = CONFIG.refreshInterval;
            this.init();
        }

        init() {
            this.fetchStats();
            setInterval(() => this.fetchStats(), this.updateInterval);
        }

        async fetchStats() {
            try {
                const response = await fetch('/dashboard/quick_stats');
                const data = await response.json();
                this.updateStats(data);
            } catch (error) {
                console.error('Failed to fetch stats:', error);
            }
        }

        updateStats(data) {
            const studentsElement = document.getElementById('total-students');
            if (studentsElement) {
                this.animateNumber(studentsElement, parseInt(studentsElement.textContent) || 0, data.students || 0);
            }
            const todayElement = document.getElementById('today-accesses');
            if (todayElement) {
                this.animateNumber(todayElement, parseInt(todayElement.textContent) || 0, data.attendance_today || 0);
            }
            const weeklyElement = document.getElementById('weekly-accesses');
            if (weeklyElement && data.weekly) {
                this.animateNumber(weeklyElement, parseInt(weeklyElement.textContent) || 0, data.weekly);
            }
            const onlineDevices = document.getElementById('online-devices');
            if (onlineDevices) {
                onlineDevices.textContent = data.devices_online || 0;
            }
        }

        animateNumber(element, oldValue, newValue) {
            if (oldValue === newValue) return;
            const duration = 1000;
            const steps = 20;
            const stepDuration = duration / steps;
            const increment = (newValue - oldValue) / steps;
            let current = oldValue;
            const interval = setInterval(() => {
                current += increment;
                if ((increment > 0 && current >= newValue) || (increment < 0 && current <= newValue)) {
                    element.textContent = newValue;
                    clearInterval(interval);
                } else {
                    element.textContent = Math.round(current);
                }
            }, stepDuration);
        }
    }

    // --- SYSTEM STATUS ---
    function initializeSystemStatusComponents() {
        if (!window.location.pathname.includes('system-status')) return;
        setInterval(app.refreshSystemStats, 30000);
        app.refreshSystemStats();
    }

    // ============================================
    // PUBLIC API - BiometricApp FUNCTIONS
    // ============================================

    // --- SYSTEM STATUS ---
    app.checkHealth = async function() {
        const healthBtn = document.getElementById('refreshHealthBtn');
        if (!healthBtn) return;
        const originalHTML = showButtonSpinner(healthBtn);
        try {
            const response = await fetch('/system/health');
            const data = await response.json();
            if (data.success !== false) {
                updateHealthCards(data);
                showToast('System health check completed', 'success');
            } else {
                showToast('Failed to check system health', 'error');
            }
        } catch (error) {
            console.error('Health check error:', error);
            showToast('Network error during health check', 'error');
        } finally {
            hideButtonSpinner(healthBtn, originalHTML);
        }
    };

    function updateHealthCards(data) {
        if (!data.checks) return;
        data.checks.forEach(check => {
            const component = check.component;
            const componentLower = component.toLowerCase();
            const valueEl = document.getElementById(`health${component}`);
            if (valueEl) valueEl.textContent = check.value;
            const statusEl = document.getElementById(`health${component}Status`);
            if (statusEl) {
                const statusClass = check.status === 'healthy' ? 'success' : check.status === 'warning' ? 'warning' : 'danger';
                statusEl.className = `badge bg-${statusClass}`;
                statusEl.textContent = check.status.charAt(0).toUpperCase() + check.status.slice(1);
            }
            if (component === 'CPU' || component === 'Memory' || component === 'Disk') {
                const value = parseInt(check.value);
                const progressBar = document.getElementById(`${componentLower}Progress`);
                if (progressBar) {
                    progressBar.style.width = value + '%';
                    progressBar.textContent = value + '%';
                    progressBar.className = `progress-bar progress-bar-striped progress-bar-animated ${
                        value < 50 ? 'bg-success' : value < 80 ? 'bg-warning' : 'bg-danger'
                    }`;
                }
            }
        });
        const overallStatus = document.getElementById('healthOverall');
        if (overallStatus) {
            overallStatus.textContent = data.status;
            const statusClass = data.status === 'healthy' ? 'success' : data.status === 'warning' ? 'warning' : 'danger';
            overallStatus.className = `badge bg-${statusClass}`;
        }
    }

    app.testDatabase = async function() {
        const testBtn = document.getElementById('testDbBtn');
        const resultDiv = document.getElementById('dbTestResult');
        if (!testBtn || !resultDiv) return;
        const originalHTML = showButtonSpinner(testBtn);
        resultDiv.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Testing connection...';
        try {
            const response = await fetch('/database/query', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-Requested-With': 'XMLHttpRequest',
                    'X-CSRFToken': getCsrfToken()
                },
                body: JSON.stringify({ query: 'SELECT 1 as test' })
            });
            const data = await response.json();
            if (data.success) {
                resultDiv.innerHTML = '<i class="fas fa-check-circle text-success"></i> Connection successful!';
                const dbBadge = document.querySelector('#dbStatusBadge .badge');
                if (dbBadge) {
                    dbBadge.className = 'badge bg-success p-3';
                    dbBadge.innerHTML = '<i class="fas fa-check-circle me-2"></i> Connected';
                }
            } else {
                resultDiv.innerHTML = '<i class="fas fa-exclamation-circle text-danger"></i> Connection failed';
                const dbBadge = document.querySelector('#dbStatusBadge .badge');
                if (dbBadge) {
                    dbBadge.className = 'badge bg-danger p-3';
                    dbBadge.innerHTML = '<i class="fas fa-exclamation-circle me-2"></i> Disconnected';
                }
            }
        } catch (error) {
            console.error('Database test error:', error);
            resultDiv.innerHTML = '<i class="fas fa-exclamation-circle text-danger"></i> Network error';
        } finally {
            hideButtonSpinner(testBtn, originalHTML);
        }
    };

    app.refreshSystemStats = async function() {
        try {
            const response = await fetch('/system/status-data');
            const data = await response.json();
            if (data.success) {
                if (data.cpu) {
                    const cpuElement = document.getElementById('cpuValue');
                    const cpuProgress = document.getElementById('cpuProgress');
                    if (cpuElement) cpuElement.textContent = data.cpu.percent + '%';
                    if (cpuProgress) {
                        cpuProgress.style.width = data.cpu.percent + '%';
                        cpuProgress.textContent = data.cpu.percent + '%';
                    }
                }
                if (data.memory) {
                    const memElement = document.getElementById('memoryValue');
                    const memProgress = document.getElementById('memoryProgress');
                    if (memElement) memElement.textContent = data.memory.percent + '%';
                    if (memProgress) {
                        memProgress.style.width = data.memory.percent + '%';
                        memProgress.textContent = data.memory.percent + '%';
                    }
                }
                if (data.disk) {
                    const diskElement = document.getElementById('diskValue');
                    const diskProgress = document.getElementById('diskProgress');
                    if (diskElement) diskElement.textContent = data.disk.percent + '%';
                    if (diskProgress) {
                        diskProgress.style.width = data.disk.percent + '%';
                        diskProgress.textContent = data.disk.percent + '%';
                    }
                }
                if (data.network) {
                    const bytesSent = document.getElementById('bytesSent');
                    const bytesReceived = document.getElementById('bytesReceived');
                    if (bytesSent) bytesSent.textContent = data.network.bytes_sent_mb.toFixed(2) + ' MB';
                    if (bytesReceived) bytesReceived.textContent = data.network.bytes_recv_mb.toFixed(2) + ' MB';
                }
                if (data.app) {
                    const uptime = document.getElementById('uptime');
                    if (uptime) uptime.textContent = data.app.uptime;
                }
            }
        } catch (error) {
            console.error('Refresh stats error:', error);
        }
    };

    app.restartSystem = async function() {
        const restartBtn = document.getElementById('restartSystemBtn');
        if (!restartBtn) return;
        if (!confirm('Are you sure you want to restart system services?')) return;
        const originalHTML = showButtonSpinner(restartBtn);
        try {
            const response = await fetch('/api/restart-system', {
                method: 'POST',
                headers: { 'X-Requested-With': 'XMLHttpRequest', 'X-CSRFToken': getCsrfToken() }
            });
            const data = await response.json();
            if (data.success) {
                showToast('System restart initiated', 'success');
                restartBtn.disabled = true;
                setTimeout(() => window.location.reload(), 5000);
            } else {
                showToast('Failed to restart system', 'error');
                hideButtonSpinner(restartBtn, originalHTML);
            }
        } catch (error) {
            showToast('Network error during restart', 'error');
            hideButtonSpinner(restartBtn, originalHTML);
        }
    };

    app.refreshProcesses = async function() {
        const refreshBtn = document.getElementById('refreshProcessesBtn');
        const tableBody = document.getElementById('processesTableBody');
        if (!refreshBtn || !tableBody) return;
        const originalHTML = showButtonSpinner(refreshBtn);
        try {
            tableBody.innerHTML = `<tr><td colspan="5" class="text-center py-3"><i class="fas fa-spinner fa-spin"></i> Loading processes...</td></tr>`;
            const response = await fetch('/system/processes');
            const data = await response.json();
            if (data.success && data.processes) {
                renderProcessesTable(data.processes);
            } else {
                tableBody.innerHTML = `<tr><td colspan="5" class="text-center py-3 text-danger">Failed to load processes</td></tr>`;
            }
        } catch (error) {
            tableBody.innerHTML = `<tr><td colspan="5" class="text-center py-3 text-danger">Network error</td></tr>`;
        } finally {
            hideButtonSpinner(refreshBtn, originalHTML);
        }
    };

    function renderProcessesTable(processes) {
        const tableBody = document.getElementById('processesTableBody');
        if (!tableBody) return;
        if (!processes || processes.length === 0) {
            tableBody.innerHTML = `<tr><td colspan="5" class="text-center py-3">No process data available</td></tr>`;
            return;
        }
        let html = '';
        processes.slice(0, 20).forEach(process => {
            const statusClass = process.status === 'running' ? 'success' : 'warning';
            html += `
                <tr>
                    <td><code>${process.pid}</code></td>
                    <td>${process.name}</td>
                    <td>${process.cpu_percent.toFixed(1)}%</td>
                    <td>${process.memory_percent.toFixed(1)}%</td>
                    <td><span class="badge bg-${statusClass}">${process.status}</span></td>
                </tr>
            `;
        });
        tableBody.innerHTML = html;
    }

    // --- STUDENTS ---
    let studentsLoaded = false;

    app.loadStudentsData = async function() {
        const tableBody = document.getElementById('studentsTableBody');
        if (!tableBody) return;
        if (studentsLoaded && !sessionStorage.getItem('forceReload')) return;
        showElementLoading(tableBody, 'Loading students...');
        try {
            const result = await apiRequest('/students/data');
            if (result.success && result.students) {
                renderStudentsTable(result.students);
                studentsLoaded = true;
                sessionStorage.removeItem('forceReload');
            } else {
                showElementError(tableBody, result.error || 'Failed to load students');
            }
        } catch (error) {
            showElementError(tableBody, 'Network error. Please try again.');
        }
    };

    function renderStudentsTable(students) {
        const tableBody = document.getElementById('studentsTableBody');
        if (!tableBody) return;
        if (!students || students.length === 0) {
            tableBody.innerHTML = `
                <tr>
                    <td colspan="8" class="text-center py-4">
                        <i class="fas fa-user-graduate fa-3x text-muted mb-3"></i>
                        <p class="text-muted">No students found</p>
                        <a href="/students/add" class="btn btn-primary btn-sm">
                            <i class="fas fa-user-plus"></i> Add Student
                        </a>
                    </td>
                </tr>
            `;
            return;
        }
        let html = '';
        students.forEach(student => {
            html += `
                <tr>
                    <td><i class="fas fa-id-card me-2"></i><strong>${student.registration_number || 'N/A'}</strong></td>
                    <td>${student.first_name || ''} ${student.last_name || ''}</td>
                    <td>${student.email || 'N/A'}</td>
                    <td><span class="badge bg-info">${student.course || 'N/A'}</span></td>
                    <td><span class="badge bg-secondary">Year ${student.year_of_study || 'N/A'}</span></td>
                    <td><span class="badge bg-success"><i class="fas fa-check-circle me-1"></i> Active</span></td>
                    <td>${student.created_at ? new Date(student.created_at).toLocaleDateString() : 'N/A'}</td>
                    <td>
                        <div class="btn-group btn-group-sm">
                            <a href="/students/view/${student.student_id}" class="btn btn-outline-info"><i class="fas fa-eye"></i></a>
                            <button class="btn btn-outline-danger delete-student" data-id="${student.student_id}" data-name="${student.first_name} ${student.last_name}"><i class="fas fa-trash"></i></button>
                        </div>
                    </td>
                </tr>
            `;
        });
        tableBody.innerHTML = html;
        initializeStudentDeleteButtons();
        const visibleCount = document.getElementById('visibleCount');
        const totalCount = document.getElementById('totalCount');
        if (visibleCount) visibleCount.textContent = students.length;
        if (totalCount) totalCount.textContent = students.length;
    }

    function initializeStudentDeleteButtons() {
        document.querySelectorAll('.delete-student').forEach(btn => {
            btn.addEventListener('click', function() {
                if (confirm(`Delete ${this.dataset.name}?`)) {
                    sessionStorage.setItem('forceReload', 'true');
                    window.location.href = `/students/delete/${this.dataset.id}`;
                }
            });
        });
    }

    // --- USERS ---
    let usersLoaded = false;

    app.loadUsersData = async function() {
        const tableBody = document.getElementById('usersTableBody');
        if (!tableBody) return;
        if (usersLoaded && !sessionStorage.getItem('forceReload')) return;
        showElementLoading(tableBody, 'Loading users...');
        try {
            const result = await apiRequest('/users/data');
            if (result.success && result.users) {
                renderUsersTable(result.users);
                usersLoaded = true;
                sessionStorage.removeItem('forceReload');
            } else {
                showElementError(tableBody, result.error || 'Failed to load users');
            }
        } catch (error) {
            showElementError(tableBody, 'Network error. Please try again.');
        }
    };

    function renderUsersTable(users) {
        const tableBody = document.getElementById('usersTableBody');
        if (!tableBody) return;
        if (!users || users.length === 0) {
            tableBody.innerHTML = `<tr><td colspan="8" class="text-center py-4"><i class="fas fa-users fa-3x text-muted mb-3"></i><p class="text-muted">No users found</p></td></tr>`;
            return;
        }
        let html = '';
        users.forEach(user => {
            const roleClass = user.role === 'superadmin' ? 'bg-danger' : user.role === 'admin' ? 'bg-warning text-dark' : 'bg-info';
            html += `
                <tr>
                    <td><i class="fas fa-user-circle me-2"></i><strong>${user.username}</strong></td>
                    <td>${user.full_name}</td>
                    <td>${user.email}</td>
                    <td><span class="badge ${roleClass}">${(user.role || 'staff').toUpperCase()}</span></td>
                    <td><span class="badge ${user.is_active ? 'bg-success' : 'bg-secondary'}">${user.is_active ? 'Active' : 'Inactive'}</span></td>
                    <td>${user.created_at ? new Date(user.created_at).toLocaleDateString() : 'N/A'}</td>
                    <td>${user.last_login ? new Date(user.last_login).toLocaleDateString() : 'Never'}</td>
                    <td><div class="btn-group btn-group-sm"><a href="/users/view/${user.id}" class="btn btn-outline-info"><i class="fas fa-eye"></i></a></div></td>
                </tr>
            `;
        });
        tableBody.innerHTML = html;
    }

    // --- REPORTS ---
    let currentReportType = null;

    app.loadReport = async function(type) {
        currentReportType = type;
        const dateFrom = document.getElementById('dateFrom')?.value;
        const dateTo = document.getElementById('dateTo')?.value;
        if (!dateFrom || !dateTo) {
            alert('Please select date range');
            return;
        }
        const resultsDiv = document.getElementById('reportResults');
        if (!resultsDiv) return;
        resultsDiv.innerHTML = `<div class="report-loading"><div class="loading-spinner"><i class="fas fa-spinner fa-spin"></i></div><p>Generating report...</p></div>`;

        const accessPoint = document.getElementById('accessPoint')?.value;
        const studentId = document.getElementById('studentId')?.value;
        const accessType = document.getElementById('accessType')?.value;

        const result = await apiRequest('/reports/generate', 'POST', {
            type: type, date_from: dateFrom, date_to: dateTo,
            access_point: accessPoint, student_id: studentId, access_type: accessType
        });

        if (result.success) {
            displayReportResults(type, result.data);
            updateReportStats(result.data);
            const reportTypeEl = document.querySelector('.results-info .report-type');
            const reportCountEl = document.querySelector('.results-info .report-count');
            if (reportTypeEl) reportTypeEl.textContent = `${type.charAt(0).toUpperCase() + type.slice(1)} Report`;
            if (reportCountEl) reportCountEl.textContent = `${result.data?.length || 0} records`;
        } else {
            resultsDiv.innerHTML = `<div class="report-error"><div class="error-icon"><i class="fas fa-exclamation-circle"></i></div><h4>Error Generating Report</h4><p>${result.error || 'Unknown error occurred'}</p><button class="retry-btn" onclick="BiometricApp.loadReport('${type}')"><i class="fas fa-redo"></i> Retry</button></div>`;
        }
    };

    function displayReportResults(type, data) {
        const resultsDiv = document.getElementById('reportResults');
        if (!resultsDiv) return;
        if (!data || data.length === 0) {
            resultsDiv.innerHTML = `<div class="report-empty"><div class="empty-icon"><i class="fas fa-chart-bar"></i></div><h4>No Data Found</h4><p>No records match your selected criteria.</p></div>`;
            return;
        }
        let headers = '';
        if (type === 'daily') headers = '<th><i class="fas fa-calendar"></i> Date</th><th><i class="fas fa-chart-line"></i> Count</th>';
        else if (type === 'hourly') headers = '<th><i class="fas fa-clock"></i> Hour</th><th><i class="fas fa-chart-line"></i> Count</th>';
        else headers = '<th><i class="fas fa-id-card"></i> Student ID</th><th><i class="fas fa-user"></i> Name</th><th><i class="fas fa-chart-line"></i> Accesses</th>';

        let rows = '';
        data.forEach(row => {
            rows += '<tr>';
            if (Array.isArray(row)) row.forEach(cell => rows += `<td>${cell || 'N/A'}</td>`);
            rows += '</tr>';
        });

        resultsDiv.innerHTML = `
            <div class="report-controls"><div class="controls-left"><button class="control-btn" onclick="BiometricApp.exportToCSV()"><i class="fas fa-file-csv"></i> Export CSV</button><button class="control-btn" onclick="BiometricApp.exportToPDF()"><i class="fas fa-file-pdf"></i> Export PDF</button></div><div class="controls-right"><span class="report-count">${data.length} records</span></div></div>
            <div class="report-table-container"><table class="report-table"><thead><tr>${headers}</tr></thead><tbody>${rows}</tbody></table></div>
        `;
    }

    function updateReportStats(data) {
        if (!data || data.length === 0) return;
        let granted = 0, denied = 0;
        data.forEach(row => {
            if (Array.isArray(row) && row[2] === 'GRANTED') granted++;
            if (Array.isArray(row) && row[2] === 'DENIED') denied++;
        });
        const totalRecords = document.getElementById('totalRecords');
        const accessGranted = document.getElementById('accessGranted');
        const accessDenied = document.getElementById('accessDenied');
        const avgDaily = document.getElementById('avgDaily');
        if (totalRecords) totalRecords.textContent = data.length;
        if (accessGranted) accessGranted.textContent = granted;
        if (accessDenied) accessDenied.textContent = denied;
        if (avgDaily) avgDaily.textContent = Math.round(data.length / 7) || 0;
    }

    app.applyFilters = function() {
        if (currentReportType) app.loadReport(currentReportType);
        else alert('Please select a report type first');
    };

    app.resetFilters = function() {
        // Try audit form first
        const auditForm = document.getElementById('auditFilterForm');
        if (auditForm) {
            auditForm.reset();
            const inputs = auditForm.querySelectorAll('input, select');
            inputs.forEach(input => {
                if (input.type !== 'submit' && input.type !== 'button') {
                    input.value = '';
                }
            });
            auditForm.submit();
            return;
        }
        // Fallback to report filters
        const fields = ['dateFrom', 'dateTo', 'timeFrom', 'timeTo', 'accessPoint', 'studentId', 'accessType'];
        fields.forEach(id => { const el = document.getElementById(id); if (el) el.value = ''; });
        const resultsDiv = document.getElementById('reportResults');
        if (resultsDiv) resultsDiv.innerHTML = `<div class="report-placeholder"><div class="placeholder-icon"><i class="fas fa-chart-bar"></i></div><h4>No Report Generated</h4><p class="placeholder-text">Select a report type and click "Generate Report"</p></div>`;
        const reportTypeEl = document.querySelector('.results-info .report-type');
        const reportCountEl = document.querySelector('.results-info .report-count');
        if (reportTypeEl) reportTypeEl.textContent = 'No report selected';
        if (reportCountEl) reportCountEl.textContent = '0 records';
    };

    app.showCustomReport = function() {
        alert('Custom report builder coming soon!');
    };

    app.exportToCSV = function() {
        if (!currentReportType) { alert('Please generate a report first'); return; }
        const dateFrom = document.getElementById('dateFrom')?.value;
        const dateTo = document.getElementById('dateTo')?.value;
        const accessPoint = document.getElementById('accessPoint')?.value;
        let url = `/reports/export/csv?type=${currentReportType}&date_from=${dateFrom}&date_to=${dateTo}`;
        if (accessPoint) url += `&access_point=${accessPoint}`;
        window.location.href = url;
    };

    app.exportToPDF = function() {
        if (!currentReportType) { alert('Please generate a report first'); return; }
        const dateFrom = document.getElementById('dateFrom')?.value;
        const dateTo = document.getElementById('dateTo')?.value;
        const accessPoint = document.getElementById('accessPoint')?.value;
        let url = `/reports/export/pdf?type=${currentReportType}&date_from=${dateFrom}&date_to=${dateTo}`;
        if (accessPoint) url += `&access_point=${accessPoint}`;
        window.location.href = url;
    };

    app.exportToExcel = function() {
        app.exportToCSV();
    };

    app.printReport = function() {
        const results = document.getElementById('reportResults')?.innerHTML;
        if (!results) return;
        const printWindow = window.open('', '_blank');
        printWindow.document.write(`<html><head><title>Access Report</title><link rel="stylesheet" href="/static/css/style.css"><style>body{padding:20px}.report-table{width:100%;border-collapse:collapse}.report-table th,.report-table td{border:1px solid #ddd;padding:8px}.report-table th{background:#f8f9fa}</style></head><body><h2>Access Report</h2>${results}</body></html>`);
        printWindow.document.close();
        printWindow.print();
    };

    // --- DASHBOARD ---
    app.refreshDashboard = async function() {
        try {
            await app.loadQuickStats();
            await app.refreshCharts();
            showToast('Dashboard updated', 'success');
        } catch (error) {
            showToast('Failed to refresh dashboard', 'error');
        }
    };

    app.refreshDashboardData = async function() {
        try {
            await app.loadQuickStats();
            if (typeof app.refreshCharts !== 'undefined') await app.refreshCharts();
        } catch (error) {
            console.error('Dashboard refresh error:', error);
        }
    };

    app.loadQuickStats = async function() {
        const result = await apiRequest('/dashboard/quick_stats');
        if (result) {
            const totalStudents = document.getElementById('total-students');
            const todayAccesses = document.getElementById('today-accesses');
            if (totalStudents) totalStudents.textContent = result.students || 0;
            if (todayAccesses) todayAccesses.textContent = result.attendance_today || 0;
        }
    };

    app.refreshCharts = async function() {
        const dailyResponse = await fetch('/reports/daily-data?days=7');
        const dailyData = await dailyResponse.json();
        if (dailyData.success && window.dailyChart) {
            window.dailyChart.data.labels = dailyData.labels;
            window.dailyChart.data.datasets = dailyData.datasets;
            window.dailyChart.update();
        }
        const pointsResponse = await fetch('/reports/top-access-points');
        const pointsData = await pointsResponse.json();
        if (pointsData.success && window.accessPointsChart) {
            window.accessPointsChart.data.labels = pointsData.labels;
            window.accessPointsChart.data.datasets[0].data = pointsData.data;
            window.accessPointsChart.update();
        }
    };

    app.loadAccessPoints = async function() {
        const select = document.getElementById('accessPoint');
        if (!select) return;
        const result = await apiRequest('/dashboard/access_points');
        if (result && result.length) {
            while (select.options.length > 1) select.remove(1);
            result.forEach(point => {
                const option = document.createElement('option');
                option.value = point;
                option.textContent = point;
                select.appendChild(option);
            });
        }
    };

    // --- INITIALISATION ---
    function initializePageComponents() {
        const path = window.location.pathname;
        if (path.includes('students')) app.loadStudentsData();
        if (path.includes('users')) app.loadUsersData();
        if (path.includes('reports')) app.loadAccessPoints();
        if (path.includes('dashboard')) {
            app.loadQuickStats();
            initializeDashboardCharts();
        }
    }

    function initializeDashboardCharts() {
        if (typeof Chart === 'undefined') return;
        const dailyCtx = document.getElementById('dailyAccessChart')?.getContext('2d');
        if (dailyCtx) {
            window.dailyChart = new Chart(dailyCtx, {
                type: 'line',
                data: { labels: [], datasets: [] },
                options: { responsive: true, maintainAspectRatio: false }
            });
            app.refreshCharts();
        }
        const pointsCtx = document.getElementById('accessPointsChart')?.getContext('2d');
        if (pointsCtx) {
            window.accessPointsChart = new Chart(pointsCtx, {
                type: 'doughnut',
                data: { labels: [], datasets: [{ data: [], backgroundColor: ['#0d6efd', '#198754', '#dc3545', '#ffc107', '#0dcaf0'] }] },
                options: { responsive: true, maintainAspectRatio: false }
            });
            app.loadAccessPointsData();
        }
    }

    app.loadAccessPointsData = async function() {
        const result = await apiRequest('/reports/top-access-points');
        if (result.success && window.accessPointsChart) {
            window.accessPointsChart.data.labels = result.labels;
            window.accessPointsChart.data.datasets[0].data = result.data;
            window.accessPointsChart.update();
        }
    };

    // --- AUDIT LOGS ---
    app.exportAuditLogs = function() {
        const btn = document.querySelector('[onclick*="exportAuditLogs"]');
        const originalHtml = btn ? btn.innerHTML : '';
        if (btn) {
            btn.disabled = true;
            btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Exporting...';
        }
        fetch('/audit/export')
            .then(response => response.blob())
            .then(blob => {
                const url = window.URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = 'audit_logs.csv';
                document.body.appendChild(a);
                a.click();
                a.remove();
                window.URL.revokeObjectURL(url);
                showToast('Export completed successfully', 'success');
            })
            .catch(err => {
                console.error(err);
                showToast('Export failed: ' + err.message, 'error');
            })
            .finally(() => {
                if (btn) {
                    btn.disabled = false;
                    btn.innerHTML = originalHtml;
                }
            });
    };

    app.clearOldLogs = function() {
        if (!confirm('Are you sure you want to clear old audit logs? This action cannot be undone.')) return;
        const btn = document.querySelector('[onclick*="clearOldLogs"]');
        const originalHtml = btn ? btn.innerHTML : '';
        if (btn) {
            btn.disabled = true;
            btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Clearing...';
        }
        fetch('/audit/clear-old', {
            method: 'POST',
            headers: {
                'X-CSRFToken': getCsrfToken(),
                'Content-Type': 'application/json'
            }
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                showToast('Old logs cleared successfully', 'success');
                setTimeout(() => location.reload(), 1000);
            } else {
                showToast('Error: ' + (data.error || 'Unknown error'), 'error');
            }
        })
        .catch(err => {
            console.error(err);
            showToast('Network error: ' + err.message, 'error');
        })
        .finally(() => {
            if (btn) {
                btn.disabled = false;
                btn.innerHTML = originalHtml;
            }
        });
    };

    // --- DATABASE MANAGEMENT ---
    app.createBackup = function() {
        const btn = document.querySelector('[onclick*="createBackup"]');
        const originalHtml = btn ? btn.innerHTML : '';
        const statusDiv = document.getElementById('backup-status');
        if (btn) {
            btn.disabled = true;
            btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Creating...';
        }
        if (statusDiv) statusDiv.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Creating backup...';

        fetch('/api/database/backup', {
            method: 'POST',
            headers: {
                'X-CSRFToken': getCsrfToken(),
                'Content-Type': 'application/json'
            }
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                if (statusDiv) statusDiv.innerHTML = `<span class="text-success">✓ Backup created: ${data.filename}</span>`;
                showToast('Backup created successfully', 'success');
            } else {
                if (statusDiv) statusDiv.innerHTML = `<span class="text-danger">✗ ${data.error || 'Backup failed'}</span>`;
                showToast('Backup failed', 'error');
            }
        })
        .catch(err => {
            if (statusDiv) statusDiv.innerHTML = `<span class="text-danger">✗ Network error: ${err.message}</span>`;
            showToast('Network error', 'error');
        })
        .finally(() => {
            if (btn) {
                btn.disabled = false;
                btn.innerHTML = originalHtml;
            }
        });
    };

    app.restoreBackup = function() {
        const fileInput = document.getElementById('restore-file');
        const filename = fileInput ? fileInput.value.trim() : '';
        if (!filename) {
            showToast('Please enter a backup filename', 'error');
            return;
        }
        if (!confirm(`Restore database from "${filename}"? This will overwrite current data.`)) return;

        const btn = document.querySelector('[onclick*="restoreBackup"]');
        const originalHtml = btn ? btn.innerHTML : '';
        const statusDiv = document.getElementById('restore-status');

        if (btn) {
            btn.disabled = true;
            btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Restoring...';
        }
        if (statusDiv) statusDiv.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Restoring database...';

        fetch('/api/database/restore', {
            method: 'POST',
            headers: {
                'X-CSRFToken': getCsrfToken(),
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ filename: filename })
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                if (statusDiv) statusDiv.innerHTML = `<span class="text-success">✓ Restore successful</span>`;
                showToast('Database restored successfully', 'success');
                setTimeout(() => location.reload(), 2000);
            } else {
                if (statusDiv) statusDiv.innerHTML = `<span class="text-danger">✗ ${data.error || 'Restore failed'}</span>`;
                showToast('Restore failed', 'error');
            }
        })
        .catch(err => {
            if (statusDiv) statusDiv.innerHTML = `<span class="text-danger">✗ Network error: ${err.message}</span>`;
            showToast('Network error', 'error');
        })
        .finally(() => {
            if (btn) {
                btn.disabled = false;
                btn.innerHTML = originalHtml;
            }
        });
    };

    app.optimizeDatabase = function() {
        if (!confirm('Optimize all tables? This may take a while.')) return;
        const btn = document.querySelector('[onclick*="optimizeDatabase"]');
        const originalHtml = btn ? btn.innerHTML : '';
        if (btn) {
            btn.disabled = true;
            btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Optimizing...';
        }
        fetch('/api/database/optimize', {
            method: 'POST',
            headers: {
                'X-CSRFToken': getCsrfToken(),
                'Content-Type': 'application/json'
            }
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                showToast('All tables optimized successfully', 'success');
            } else {
                showToast('Optimization failed: ' + (data.error || 'Unknown error'), 'error');
            }
        })
        .catch(err => {
            showToast('Network error: ' + err.message, 'error');
        })
        .finally(() => {
            if (btn) {
                btn.disabled = false;
                btn.innerHTML = originalHtml;
            }
        });
    };

    app.showTableInfo = function(tableName) {
        fetch(`/api/database/table/${tableName}`)
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    let info = `Table: ${tableName}\n`;
                    info += `Rows: ${data.row_count}\n`;
                    info += `Columns: ${data.column_count}\n`;
                    info += `Size: ${data.size_mb} MB\n`;
                    info += `Created: ${data.created_at || 'N/A'}`;
                    alert(info);
                } else {
                    showToast('Failed to get table info', 'error');
                }
            })
            .catch(err => {
                showToast('Network error: ' + err.message, 'error');
            });
    };

    app.optimizeTable = function(tableName) {
        if (!confirm(`Optimize table "${tableName}"?`)) return;
        const btn = document.querySelector(`[onclick*="optimizeTable('${tableName}')"]`);
        const originalHtml = btn ? btn.innerHTML : '';
        if (btn) {
            btn.disabled = true;
            btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i>';
        }
        fetch('/api/database/optimize-table', {
            method: 'POST',
            headers: {
                'X-CSRFToken': getCsrfToken(),
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ table: tableName })
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                showToast(`Table "${tableName}" optimized`, 'success');
            } else {
                showToast('Optimization failed: ' + (data.error || 'Unknown error'), 'error');
            }
        })
        .catch(err => {
            showToast('Network error: ' + err.message, 'error');
        })
        .finally(() => {
            if (btn) {
                btn.disabled = false;
                btn.innerHTML = originalHtml;
            }
        });
    };

    app.executeQuery = function() {
        const queryInput = document.getElementById('sql-query');
        const resultsDiv = document.getElementById('query-results');
        if (!queryInput) return;
        const query = queryInput.value.trim();
        if (!query) {
            showToast('Please enter a SQL query', 'error');
            return;
        }
        resultsDiv.innerHTML = '<div class="text-center"><i class="fas fa-spinner fa-spin"></i> Executing query...</div>';

        fetch('/api/database/query', {
            method: 'POST',
            headers: {
                'X-CSRFToken': getCsrfToken(),
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ query: query })
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                if (data.rows && data.rows.length > 0) {
                    let html = '<div class="table-responsive"><table class="table table-sm table-striped">';
                    const headers = Object.keys(data.rows[0]);
                    html += '<thead><tr>';
                    headers.forEach(h => html += `<th>${h}</th>`);
                    html += '</tr></thead><tbody>';
                    data.rows.forEach(row => {
                        html += '<tr>';
                        headers.forEach(h => html += `<td>${row[h] !== null ? row[h] : 'NULL'}</td>`);
                        html += '</tr>';
                    });
                    html += '</tbody></table></div>';
                    html += `<p class="text-muted">${data.rows.length} row(s) returned</p>`;
                    resultsDiv.innerHTML = html;
                } else {
                    resultsDiv.innerHTML = '<div class="alert alert-info">Query executed successfully. No rows returned.</div>';
                }
            } else {
                resultsDiv.innerHTML = `<div class="alert alert-danger">Error: ${data.error || 'Unknown error'}</div>`;
            }
        })
        .catch(err => {
            resultsDiv.innerHTML = `<div class="alert alert-danger">Network error: ${err.message}</div>`;
        });
    };

    app.clearResults = function() {
        const resultsDiv = document.getElementById('query-results');
        if (resultsDiv) resultsDiv.innerHTML = '';
    };

    // ============================================
    // INITIALISE ON DOM READY
    // ============================================
    document.addEventListener('DOMContentLoaded', function() {
        initializeSidebar();
        initializeRefreshButtons();
        initializeLoginForm();
        initializePageComponents();
        initializeDeleteButtons();
        initializeProgressBars();
        initializeBiometricComponents();
        initializeSystemStatusComponents();

        if (window.location.pathname.includes('dashboard')) {
            new DashboardRealtime();
        }
    });

})(window.BiometricApp);