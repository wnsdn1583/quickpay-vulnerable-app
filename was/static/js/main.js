const ACCOUNT_API_BASE = 'http://account';

// Function to handle API requests
async function apiRequest(path, options = {}, followRedirects = true) {
    const token = sessionStorage.getItem('jwt');
    const headers = new Headers(options.headers || {});

    if (token) {
        headers.append('Authorization', `Bearer ${token}`);
    }

    options.headers = headers;
    // By default, fetch does not follow redirects. We need to handle them manually.
    options.redirect = 'manual'; 

    const response = await fetch(path, options);

    // Handle 302 Redirect
    if (response.status === 302 && followRedirects) {
        const location = response.headers.get('Location');
        if (location) {
            console.log(`Redirecting to ${location}`);
            // For cross-origin redirects, we can't make the request from JS.
            // Instead, we navigate the browser to the new URL.
            window.location.href = location;
            return; // Stop further processing
        }
    }
    
    const responseData = await response.json().catch(() => ({}));

    if (!response.ok) {
        const errorMessage = responseData.message || `Error: ${response.status} ${response.statusText}`;
        throw new Error(errorMessage);
    }

    // For login, the actual redirect_to might come in the body
    if (responseData.redirect_to) {
        // If it's a payment URL, show a success message
        if (responseData.redirect_to.includes('/payment')) {
            alert('결제 성공 했습니다');
        }
        window.location.href = responseData.redirect_to;
        return;
    }

    return responseData;
}


// --- Form Handlers ---

// Login Form
const loginForm = document.getElementById('login-form');
if (loginForm) {
    loginForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const formData = new FormData(loginForm);
        const data = Object.fromEntries(formData.entries());
        const errorMessageDiv = document.getElementById('error-message');
        
        try {
            const redirectTo = data.redirect_to ? `?redirect_to=${encodeURIComponent(data.redirect_to)}` : '';
            const response = await apiRequest(`${ACCOUNT_API_BASE}/account/login${redirectTo}`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ user_id: data.user_id, password: data.password }),
            });

            if (response.JWT) {
                sessionStorage.setItem('jwt', response.JWT);
                window.location.href = '/web/main';
            }
        } catch (error) {
            errorMessageDiv.textContent = error.message;
        }
    });
}

// Register Form
const registerForm = document.getElementById('register-form');
if (registerForm) {
    registerForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const formData = new FormData(registerForm);
        const data = Object.fromEntries(formData.entries());
        const errorMessageDiv = document.getElementById('error-message');

        try {
            await apiRequest(`${ACCOUNT_API_BASE}/account/register`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ user_id: data.user_id, password: data.password }),
            });
            window.location.href = '/web/login';
        } catch (error) {
            errorMessageDiv.textContent = error.message;
        }
    });
}

// Deposit Form
const depositForm = document.getElementById('deposit-form');
if (depositForm) {
    depositForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const formData = new FormData(depositForm);
        const amount = parseFloat(formData.get('amount'));
        const errorMessageDiv = document.getElementById('error-message');
        
        if (isNaN(amount)) {
            errorMessageDiv.textContent = '입금 금액을 입력해주세요';
            return;
        }
        if (amount <= 0) {
            errorMessageDiv.textContent = '양수만 입력가능합니다';
            return;
        }
        if (amount > 100) {
            errorMessageDiv.textContent = '최대 입력 값은 100원 입니다';
            return;
        }

        try {
            await apiRequest(`${ACCOUNT_API_BASE}/account/deposit`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ amount: amount }),
            });
            alert('입금 성공');
            window.location.href = '/web/main';
        } catch (error) {
            errorMessageDiv.textContent = error.message;
        }
    });
}

// Withdraw Form
const withdrawForm = document.getElementById('withdraw-form');
if (withdrawForm) {
    withdrawForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const formData = new FormData(withdrawForm);
        const amount = parseFloat(formData.get('amount'));
        const errorMessageDiv = document.getElementById('error-message');

        if (isNaN(amount)) {
            errorMessageDiv.textContent = '출금 금액을 입력해주세요';
            return;
        }
        if (amount <= 0) {
            errorMessageDiv.textContent = '양수만 입력가능합니다';
            return;
        }

        try {
            await apiRequest(`${ACCOUNT_API_BASE}/account/withdraw`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ amount: amount }),
            });
            alert('출금 성공');
            window.location.href = '/web/main';
        } catch (error) {
            errorMessageDiv.textContent = error.message;
        }
    });
}


// --- Page Load and Auth Logic ---

// Logout Button
const logoutButton = document.getElementById('logout-button');
if (logoutButton) {
    logoutButton.addEventListener('click', async () => {
        try {
            // The request might fail if the token is already invalid, but we proceed with logout anyway
            await apiRequest(`${ACCOUNT_API_BASE}/auth/logout`, {}, false);
        } catch (error) {
            console.warn("Logout API call failed, but proceeding with client-side logout.", error.message);
        } finally {
            sessionStorage.removeItem('jwt');
            window.location.href = '/web/login';
        }
    });
}

// On page load, if user is logged in, fetch balance
document.addEventListener('DOMContentLoaded', () => {
    const userInfo = document.getElementById('user-info');
    if (userInfo) {
        const userId = userInfo.textContent.split(':')[1].trim();
        const balanceSpan = document.getElementById('balance-info');
        
        apiRequest(`${ACCOUNT_API_BASE}/account/balance?user_id=${userId}`)
            .then(data => {
                if (data.balance !== undefined) {
                    balanceSpan.textContent = `Balance: ${data.balance}`;
                } else {
                    balanceSpan.textContent = 'Balance: N/A';
                }
            })
            .catch(error => {
                console.error('Failed to fetch balance:', error);
                balanceSpan.textContent = 'Balance: Error';
            });
    }
});
