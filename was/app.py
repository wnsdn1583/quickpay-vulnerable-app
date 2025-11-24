import os
import secrets
from flask import Flask, render_template, request, g, redirect, url_for, jsonify, flash, send_from_directory
from werkzeug.utils import secure_filename
import requests 
from wand.image import Image

app = Flask(__name__, static_folder='static')
app.config['SECRET_KEY'] = 'a_very_insecure_key_for_testing'
UPLOAD_FOLDER = '/tmp/uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

def is_allowed_file(filename):
    """업로드 허용 확장자 검사 (간단한 필터링만 적용하여 우회 여지 남김)"""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ['png', 'jpg', 'jpeg', 'gif', 'svg', 'pdf', 'mvg']

def vulnerable_image_processing(filepath):
    """
    CVE-2016-3714 (ImageTragick) 취약점을 포함하는 이미지 처리 함수.
    Wand를 통해 ImageMagick 바이너리를 호출하도록 유도합니다.
    """
    app.logger.info(f"ImageMagick 처리 시작: {filepath}")
    
    try:
        with Image(filename=filepath) as img:
            user_folder = os.path.join(app.config['UPLOAD_FOLDER'], str(g.user_id))
            output_path = os.path.join(
                app.config['UPLOAD_FOLDER'], str(g.user_id),
                f"processed_{secrets.token_hex(4)}.pdf"
            )
            os.makedirs(user_folder, exist_ok=True) 
            img.save(filename=output_path)
            
        app.logger.info(f"ImageMagick 처리 성공 및 저장: {output_path}")
        return True, "문서 업로드 및 이미지 처리에 성공했습니다."

    except Exception as e:
        app.logger.error(f"ImageMagick 처리 중 오류 발생: {e}")
        return False, f"문서 처리 오류 발생: {e}"

@app.before_request
def before_request():
    # 요청 받을 때 X-User-ID 확인
    # X-User-ID 유무에 따라 navbar 우측 layout이 달라짐 (layout.html 확인)
    g.user_id = request.headers.get('X-User-ID') 
    if g.user_id:
        api_url = f"http://account:5000/account/balance?user_id={g.user_id}"
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
    if not g.user_id:
        return redirect(url_for('login'))
    return render_template('deposit.html')

@app.route('/web/withdraw')
def withdraw():
    if not g.user_id:
        return redirect(url_for('login'))
    return render_template('withdraw.html')

@app.route('/web/fund', methods=['GET', 'POST'])
def fund():
    # 1. 초기 로그인 및 잔액 확인 (가장 먼저 처리)
    if not g.user_id:
        return redirect(url_for('login'))

    # 사모펀드 페이지는 잔액 700조 이상 사용자만 접근 가능
    try:
        # 700조를 상수로 정의하여 가독성 개선 (기존 코드의 값 유지: 700,000,000,000,000)
        REQUIRED_BALANCE = 700000000000000
        if int(g.user_balance) <= REQUIRED_BALANCE:
            return jsonify({"error": "INSUFFICIENT_FUNDS", "message": "잔액이 700조 이상인 고객만 이용가능합니다."}), 400
    except (ValueError, TypeError):
        # 잔액 정보가 없거나 숫자가 아닌 경우
        return jsonify({"error": "BALANCE_CHECK_FAILED", "message": "잔액 정보를 확인할 수 없습니다."}), 400

    # 2. filepath 정의 위치 변경 (요청 3 반영)
    # 현재 로그인된 사용자 ID를 기반으로 업로드 경로를 미리 정의합니다.
    upload_dir = os.path.join(app.config['UPLOAD_FOLDER'])
    # 초기화
    uploaded_files = [] 

    # 3. POST 요청 처리
    if request.method == 'POST':
        # 3.1 폼 데이터 및 파일 검증
        if 'file' not in request.files:
            flash('파일이 포함되지 않았습니다.', 'error')
        else:
            file = request.files['file']
            if file.filename == '':
                flash('선택된 파일이 없습니다.', 'error')
            elif not is_allowed_file(file.filename):
                flash('허용되지 않는 파일 확장자입니다.', 'error')
            else:
                # 3.2 파일 처리 로직 (기존 로직 유지)
                filename = secure_filename(file.filename)
                file_extension = filename.rsplit('.', 1)[1].lower()
                safe_filename = f"{secrets.token_hex(8)}.{file_extension}"
                
                # 사용자 ID별 디렉토리 생성 및 파일 저장
                # user_upload_dir 변수를 사용하여 경로를 일관되게 처리할 수 있습니다.
                filepath = os.path.join(upload_dir, safe_filename)
                
                # 디렉토리가 없으면 생성 (안전한 파일 저장 보장)
                os.makedirs(upload_dir, exist_ok=True) 
                file.save(filepath)

                # 이미지 처리
                success, message = vulnerable_image_processing(filepath)
                
                if success:
                    flash(message, 'success')
                else:
                    flash(message, 'error')
    
    # --- POST 요청 처리 종료 ---
    
    # 4. GET 요청 및 POST 요청 후 파일 목록 조회 (요청 1, 2 반영)
    # user_upload_dir 변수를 사용하여 파일 목록을 조회합니다.
    user_folder = os.path.join(app.config['UPLOAD_FOLDER'], str(g.user_id))
    if os.path.exists(user_folder):
        try:
            # 디렉토리 내의 파일 목록만 가져옵니다.
            uploaded_files = [
                f for f in os.listdir(user_folder) 
                if os.path.isfile(os.path.join(user_folder, f))
            ]
        except OSError:
            flash("사용자 파일 디렉토리를 읽는 중 오류가 발생했습니다.", 'error')

    # 5. 최종 템플릿 렌더링 (요청 1, 2 반영)
    # 모든 경로에서 이 하나의 return 문을 사용합니다.
    return render_template('fund.html', files=uploaded_files)

@app.route('/web/download/<path:filename>')
def download_file(filename):
    if not g.user_id:
        return redirect(url_for('login'))
    
    user_upload_dir = os.path.join(app.config['UPLOAD_FOLDER'], g.user_id)
    
    try:
        return send_from_directory(user_upload_dir, filename, as_attachment=True)
    except FileNotFoundError:
        # flash("파일을 찾을 수 없습니다.", 'error')
        return jsonify({"error": "NOT_FOUND", "message": "요청한 파일을 찾을 수 없습니다."}), 404

@app.route('/web/payment')
def payment():
    if not g.user_id:
        return redirect(url_for('login'))
    return render_template('payment.html')

@app.route('/web/settlement')
def settlement():
    if not g.user_id:
        return redirect(url_for('login'))
    return render_template('settlement.html')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8888, debug=True)
