from flask import Flask, render_template, request, g
import requests 

app = Flask(__name__)

@app.before_request
def before_request():
    g.user_id = request.headers.get('X-User-ID')
    if g.user_id:
        api_url = f"http://account/account/balance?user_id={g.user_id}"
    try:
        response = requests.get(api_url, timeout=5)
        response.raise_for_status() # HTTP 오류가 발생하면 예외 발생
        data = response.json()
        g.user_balance = data.get("balance", "N/A") # 'balance' 키의 값을 반환
    except requests.exceptions.RequestException as e:
        g.user_balance = " "

@app.route('/')
def index():
    return render_template('main.html')

@app.route('/web/main')
def main():
    return render_template('main.html')

@app.route('/web/login')
def login():
    redirect_to = request.args.get('redirect_to', '')
    return render_template('login.html', redirect_to=redirect_to)

@app.route('/web/register')
def register():
    return render_template('register.html')

@app.route('/web/deposit')
def deposit():
    return render_template('deposit.html')

@app.route('/web/withdraw')
def withdraw():
    return render_template('withdraw.html')

@app.route('/web/fund')
def fund():
    return render_template('fund.html')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8888)
