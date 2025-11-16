from flask import Flask, request, Response, redirect
import requests
import os

app = Flask(__name__, static_folder=None)

# --- Service Hosts ---
WAS_HOST = os.environ.get("WAS_HOST", "http://was:5000")
AUTH_HOST = os.environ.get("AUTH_HOST", "http://auth:5000")
ACCOUNT_HOST = os.environ.get("ACCOUNT_HOST", "http://account:5000")
PAYMENT_HOST = os.environ.get("PAYMENT_HOST", "http://payment:5000")
SETTLEMENT_HOST = os.environ.get("SETTLEMENT_HOST", "http://settlement:5000")

# --- Public Paths ---
# Paths that are accessible without an Authorization header.
PUBLIC_PATHS = {'', 'web/main', 'web/login', 'web/register', 'account/register'}

def _forward_request(target_url, headers):
    """Forwards the incoming request to the target URL."""
    try:
        resp = requests.request(
            method=request.method,
            url=target_url,
            headers=headers,
            data=request.get_data(),
            cookies=request.cookies,
            allow_redirects=False
        )
        excluded_headers = ['content-encoding', 'content-length', 'transfer-encoding', 'connection']
        response_headers = [(name, value) for (name, value) in resp.raw.headers.items()
                            if name.lower() not in excluded_headers]
        return Response(resp.content, resp.status_code, response_headers)
    except requests.exceptions.RequestException as e:
        return Response(str(e), 503) # Service Unavailable

# --- Specific Routes ---

@app.route('/static/<path:path>')
def proxy_static(path):
    """Proxy for static files, no auth needed."""
    target_url = f"{WAS_HOST}/static/{path}"
    return _forward_request(target_url, {key: value for (key, value) in request.headers if key.lower() != 'host'})

@app.route('/auth/logout', methods=['POST'])
def logout():
    """Proxy for static files, no auth needed."""
    target_url = f"{AUTH_HOST}/auth/logout"
    return _forward_request(target_url, {key: value for (key, value) in request.headers if key.lower() != 'host'})

@app.route('/account/login', methods=['POST'])
def login():
    """Handles the special two-step login flow."""
    try:
        # 1. Forward to account service
        account_url = f"{ACCOUNT_HOST}/account/login"

        print(account_url)

        account_resp = requests.post(
            url=account_url,
            json=request.get_json(),
            headers={'Content-Type': 'application/json'}
        )

        # 2. If account service fails, return its response
        if account_resp.status_code != 200:
            return Response(account_resp.content, account_resp.status_code, dict(account_resp.headers))

        # 3. If account service succeeds, forward its response body to auth service
        auth_url = f"{AUTH_HOST}/auth/login"
        auth_resp = requests.post(
            url=auth_url,
            json=account_resp.json(),
            headers={'Content-Type': 'application/json'}
        )

        # 4. Return auth service's response
        excluded_headers = ['content-encoding', 'content-length', 'transfer-encoding', 'connection']
        response_headers = [(name, value) for (name, value) in auth_resp.raw.headers.items()
                            if name.lower() not in excluded_headers]
        return Response(auth_resp.content, auth_resp.status_code, response_headers)

    except requests.exceptions.RequestException as e:
        return Response(str(e), 503) # Service Unavailable

# --- Generic Proxy Route ---

@app.route('/', defaults={'path': ''})
@app.route('/<path:path>', methods=['GET', 'POST', 'PUT', 'DELETE'])
def proxy(path):
    """A generic proxy for all other requests."""
    
    # 1. Authenticate the user if a JWT cookie is present
    user_id = None
    jwt_token = request.cookies.get('jwt_token')

    if jwt_token:
        try:
            # Forward the cookie to the auth service for validation
            auth_resp = requests.post(
                f"{AUTH_HOST}/auth/validate", 
                cookies={'jwt_token': jwt_token}
            )
            if auth_resp.status_code == 200:
                user_id = auth_resp.json().get("user_id")
            # If the token is invalid (e.g., 401), we don't need to return immediately.
            # We just won't have a user_id, and the logic below will handle it.
        except requests.exceptions.RequestException as e:
            # Log the error but don't block the user, maybe the auth service is down
            print(f"Error connecting to auth service: {e}")

    # 2. Check for authorization for non-public paths
    if not user_id and path not in PUBLIC_PATHS:
        return redirect('/web/login')

    # 3. Determine target service
    target_url = None
    if path.startswith('web/') or path == '':
        target_url = f"{WAS_HOST}/{path}"
    elif path.startswith('account/'):
        target_url = f"{ACCOUNT_HOST}/{path}"
    elif path.startswith('payments'):
        target_url = f"{PAYMENT_HOST}/{path}"
    elif path.startswith('settlement/'):
        target_url = f"{SETTLEMENT_HOST}/{path}"

    if not target_url:
        return Response("Not Found", status=404)

    # 4. Prepare headers and forward the request
    headers = {key: value for (key, value) in request.headers if key.lower() != 'host'}
    if user_id:
        headers['X-User-ID'] = str(user_id)
        
    return _forward_request(target_url, headers)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)
