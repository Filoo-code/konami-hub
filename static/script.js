// Auth modal handling
const modal = document.getElementById('authModal');
const modalContent = document.getElementById('authFormContainer');
let currentAuthMode = 'login';

function showModal() {
    modal.classList.remove('hidden');
}

function hideModal() {
    modal.classList.add('hidden');
}

function renderAuthForm() {
    const title = currentAuthMode === 'login' ? '🔐 Login to Konami Hub' : '📝 Register new account';
    const buttonText = currentAuthMode === 'login' ? 'Login' : 'Register';
    const altText = currentAuthMode === 'login' ? 'No account? Register' : 'Already have account? Login';
    
    modalContent.innerHTML = `
        <h2>${title}</h2>
        <div id="authAlert"></div>
        <input type="text" id="authUsername" placeholder="Username" autocomplete="off">
        <input type="password" id="authPassword" placeholder="Password">
        <button id="authSubmitBtn">${buttonText}</button>
        <div class="toggle-auth" id="toggleAuthMode">${altText}</div>
    `;
    
    document.getElementById('authSubmitBtn').addEventListener('click', handleAuth);
    document.getElementById('toggleAuthMode').addEventListener('click', () => {
        currentAuthMode = currentAuthMode === 'login' ? 'register' : 'login';
        renderAuthForm();
    });
}

async function handleAuth() {
    const username = document.getElementById('authUsername').value.trim();
    const password = document.getElementById('authPassword').value.trim();
    const alertDiv = document.getElementById('authAlert');
    
    if (!username || !password) {
        alertDiv.innerHTML = "<div class='alert'>Both fields required.</div>";
        return;
    }
    
    const endpoint = currentAuthMode === 'login' ? '/api/login' : '/api/register';
    
    try {
        const response = await fetch(endpoint, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ username, password })
        });
        
        const data = await response.json();
        
        if (data.success) {
            hideModal();
            window.location.reload();
        } else {
            alertDiv.innerHTML = `<div class='alert'>${data.error}</div>`;
        }
    } catch (error) {
        alertDiv.innerHTML = "<div class='alert'>Connection error. Please try again.</div>";
    }
}

async function handleLogout() {
    try {
        await fetch('/api/logout', { method: 'POST' });
        window.location.reload();
    } catch (error) {
        console.error('Logout error:', error);
    }
}

async function addComment(postId, text) {
    try {
        const response = await fetch('/api/comments', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ post_id: postId, text: text })
        });
        
        const data = await response.json();
        
        if (data.success) {
            // Refresh page to show new comment
            window.location.reload();
        } else {
            alert(data.error || 'Failed to post comment');
        }
    } catch (error) {
        alert('Error posting comment. Please try again.');
    }
}

// Event listeners
document.addEventListener('DOMContentLoaded', () => {
    // Login/Register buttons
    const loginBtn = document.getElementById('showLoginBtn');
    const registerBtn = document.getElementById('showRegisterBtn');
    const logoutBtn = document.getElementById('logoutBtn');
    const closeModalBtn = document.querySelector('.close-modal');
    
    if (loginBtn) {
        loginBtn.addEventListener('click', () => {
            currentAuthMode = 'login';
            renderAuthForm();
            showModal();
        });
    }
    
    if (registerBtn) {
        registerBtn.addEventListener('click', () => {
            currentAuthMode = 'register';
            renderAuthForm();
            showModal();
        });
    }
    
    if (logoutBtn) {
        logoutBtn.addEventListener('click', handleLogout);
    }
    
    if (closeModalBtn) {
        closeModalBtn.addEventListener('click', hideModal);
    }
    
    // Close modal when clicking outside
    modal.addEventListener('click', (e) => {
        if (e.target === modal) hideModal();
    });
    
    // Comment submission
    const submitBtn = document.getElementById('submitCommentBtn');
    if (submitBtn) {
        const postId = submitBtn.getAttribute('data-post-id');
        submitBtn.addEventListener('click', () => {
            const textarea = document.getElementById('newCommentText');
            const text = textarea.value.trim();
            if (text) {
                addComment(postId, text);
            } else {
                alert('Please write a comment before posting.');
            }
        });
    }
    
    // Login prompt link in comments section
    const loginPrompt = document.getElementById('loginPromptLink');
    if (loginPrompt) {
        loginPrompt.addEventListener('click', (e) => {
            e.preventDefault();
            currentAuthMode = 'login';
            renderAuthForm();
            showModal();
        });
    }
});