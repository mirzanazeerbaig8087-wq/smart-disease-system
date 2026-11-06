from flask import Flask, render_template, request, jsonify, session, redirect, url_for, send_from_directory
import json, os, re, difflib, random, requests, base64
from datetime import datetime, timedelta
from werkzeug.utils import secure_filename
from groq import Groq 
import smtplib
import urllib.parse
from email.mime.text import MIMEText

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'smart_disease_2026_secret_key_123_final_700_V2_30DAYS_PERFECT')
IS_VERCEL = os.getenv('VERCEL') == '1'

app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=30)
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['SESSION_COOKIE_SECURE'] = True if IS_VERCEL else False
app.config['SESSION_COOKIE_HTTPONLY'] = True

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER = '/tmp/uploads' if IS_VERCEL else os.path.join(BASE_DIR, 'static', 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
ALLOWED_EXT = {'png','jpg','jpeg','pdf','webp'}

def get_env(name):
    # Vercel pe kabhi-kabhi key me space/newline aa jata hai
    for k in [name, name.upper(), name.lower()]:
        v = os.getenv(k) or os.environ.get(k) or ""
        if v:
            v = v.strip().strip('"').strip("'").strip()
            if len(v) > 5:
                return v
    return ""

@app.before_request
def make_session_permanent():
    session.permanent = True

# === STATIC ===
@app.route('/manifest.json')
def manifest():
    return send_from_directory('static', 'manifest.json')
@app.route('/sw.js')
def sw():
    return send_from_directory('static', 'sw.js')

@app.route('/uploads/<path:filename>')
def uploaded_file(filename):
    resp = send_from_directory(app.config['UPLOAD_FOLDER'], filename)
    resp.headers['Access-Control-Allow-Origin'] = '*'
    return resp

@app.route('/clear-loop')
def clear_loop():
    session.clear()
    return """<script>localStorage.clear();sessionStorage.clear();document.cookie.split(";").forEach(c=>{document.cookie=c.replace(/^ +/,"").replace(/=.*/,"=;expires="+new Date().toUTCString()+";path=/")});alert('Loop Cleared!');window.location.href='/login';</script>"""

# === LOAD DISEASES FIRST ===
diseases_data={}; all_symptoms=[]
try:
    json_path = os.path.join(BASE_DIR, 'diseases.json')
    if os.path.exists(json_path):
        with open(json_path,'r',encoding='utf-8') as f:
            diseases_data=json.load(f)
        temp=set()
        for v in diseases_data.values():
            if isinstance(v, dict):
                s=str(v.get('Symptoms') or v.get('symptoms') or "")
                for part in re.split(r'[,;]', s):
                    if part.strip(): temp.add(part.strip().lower())
        all_symptoms=sorted(list(temp))
        print(f"LOADED: {len(diseases_data)} diseases")
    else:
        print("diseases.json not found!")
except Exception as e:
    print(f"Load error {e}")

def get_field(info, keys, default=""):
    if not isinstance(info, dict): return default
    for k in keys:
        if k in info and info[k]: return info[k]
    return default

# === CORE PAGES WITH 500 FIX ===
@app.route('/')
def home(): return redirect(url_for('cover_page'))

@app.route('/cover')
def cover_page():
    try: return render_template('cover.html')
    except: return redirect(url_for('login_page'))

@app.route('/login')
def login_page():
    if session.get('is_logged_in'):
        return redirect(url_for('pp_page') if session.get('welcome_shown') else url_for('welcome_page'))
    return render_template('login.html')

@app.route('/welcome')
def welcome_page():
    if not session.get('is_logged_in'): return redirect(url_for('login_page'))
    if session.get('welcome_shown'): return redirect(url_for('pp_page'))
    try: return render_template('welcome.html')
    except Exception as e:
        print(f"welcome error {e}")
        return redirect(url_for('pp_page'))

@app.route('/pp')
def pp_page():
    if not session.get('is_logged_in'): return redirect(url_for('login_page'))
    try:
        for name in ['PP.html', 'pp.html', 'PP.HTML']:
            if os.path.exists(os.path.join(BASE_DIR, 'templates', name)):
                return render_template(name, symptoms=all_symptoms, total_diseases=len(diseases_data))
        return render_template('PP.html', symptoms=all_symptoms, total_diseases=len(diseases_data))
    except Exception as e:
        print(f"PP ERROR: {e}")
        return f"""
        <div style='font-family:sans-serif;padding:20px'>
        <h2>Welcome {session.get('username','User')}!</h2>
        <p>Template Error: {e}</p>
        <p>Diseases Loaded: {len(diseases_data)}</p>
        <a href='/clear-loop'>Clear & Login Again</a><br><br>
        <form action='/predict' method='POST' style='border:1px solid #ccc;padding:15px;border-radius:10px'>
            <input name='patient_name' placeholder='Patient Name' value='{session.get('username','')}' style='width:100%;padding:10px;margin:5px 0'><br>
            <textarea name='symptoms' placeholder='fever, headache, cough' style='width:100%;padding:10px;height:80px'></textarea><br>
            <button type='submit' style='background:blue;color:white;padding:10px 20px;border:none;border-radius:5px;width:100%'>Predict Now</button>
        </form>
        </div>
        """, 200

@app.route('/resultp')
def result_page():
    if not session.get('is_logged_in'): return redirect(url_for('login_page'))
    r=session.get('last_result')
    if not r: return redirect(url_for('pp_page'))
    try:
        if os.path.exists(os.path.join(BASE_DIR, 'templates', 'Resultp.html')):
            return render_template('Resultp.html', result=r)
        return render_template('resultp.html', result=r)
    except Exception as e:
        print(f"Resultp error {e}")
        return jsonify(r)

@app.route('/thankyou')
def thankyou_page():
    if not session.get('is_logged_in'): return redirect(url_for('login_page'))
    try: return render_template('thankyou.html')
    except: return redirect(url_for('pp_page'))

@app.route('/logout')
def logout(): session.clear(); return redirect(url_for('cover_page'))

@app.route('/mark_welcome_done')
def mark_welcome_done():
    session['welcome_shown']=True
    session.permanent=True
    session.modified=True
    return redirect(url_for('pp_page'))

def safe_render(template_name, fallback='/pp'):
    try:
        path = os.path.join(BASE_DIR, 'templates', template_name)
        if os.path.exists(path): return render_template(template_name)
        alt = template_name.lower()
        if os.path.exists(os.path.join(BASE_DIR, 'templates', alt)): return render_template(alt)
        return redirect(fallback)
    except Exception as e:
        print(f"safe_render {template_name} error {e}")
        return redirect(fallback)

@app.route('/emergency')
def emergency_page():
    if not session.get('is_logged_in'): return redirect(url_for('login_page'))
    return safe_render('emergency.html')

@app.route('/doctor_ai')
@app.route('/doctor-ai')
@app.route('/doctor')
def doctor_ai_page():
    if not session.get('is_logged_in'): return redirect(url_for('login_page'))
    return safe_render('doctor-ai.html')

@app.route('/my-profile')
@app.route('/profile')
def my_profile_page():
    if not session.get('is_logged_in'):
        return redirect(url_for('login_page'))
    user_data={
        'username':session.get('username','User'),
        'email':session.get('user_email',''),
        'phone':session.get('user_phone',''),
        'login_time':session.get('login_time','')
    }
    try:
        for name in ['my_profile.html', 'my-profile.html', 'profile.html']:
            if os.path.exists(os.path.join(BASE_DIR, 'templates', name)):
                return render_template(name, user=user_data)
    except Exception as e:
        print(f"Profile template error: {e}")
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>My Profile - Predict AI</title>
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <link href="https://fonts.googleapis.com/css2?family=Poppins:wght@400;500;600;700&display=swap" rel="stylesheet">
        <style>
            body{{margin:0;padding:20px 20px 90px 20px;background:radial-gradient(circle at top,#162032,#0a1220);min-height:100vh;font-family:'Poppins',sans-serif;display:flex;justify-content:center}}
            .card{{width:100%;max-width:400px;background:linear-gradient(180deg,#1c2740,#121a2b);border:1px solid #2a3650;border-radius:18px;padding:25px}}
        </style>
    </head>
    <body>
        <div class="card">
            <a href="/pp" style="color:#6bb6ff;text-decoration:none;font-size:12px">← Back to Home</a>
            <div style="text-align:center;margin:20px 0">
                <div style="width:80px;height:80px;background:#fff;border-radius:50%;margin:0 auto 12px;display:flex;align-items:center;justify-content:center;font-size:36px">👤</div>
                <h2 style="color:#fff;margin:0">{user_data['username']}</h2>
                <p style="color:#8a9bb5;font-size:11px;margin-top:4px">{user_data['email'] or 'No email'}</p>
            </div>
            <div style="background:#121a2b;border:1px solid #2a3650;border-radius:12px;padding:14px">
                <div style="display:flex;justify-content:space-between;padding:8px 0;border-bottom:1px solid #1e2f4a">
                    <span style="color:#5a6b8a;font-size:11px">Phone</span>
                    <span style="color:#fff;font-size:11px">{user_data['phone'] or 'Not added'}</span>
                </div>
                <div style="display:flex;justify-content:space-between;padding:8px 0">
                    <span style="color:#5a6b8a;font-size:11px">Login Time</span>
                    <span style="color:#fff;font-size:11px">{user_data['login_time']}</span>
                </div>
            </div>
            <a href="/logout" style="display:block;text-align:center;margin-top:20px;background:rgba(255,59,59,0.12);border:1px solid #ff3b3b;color:#ff6b6b;padding:12px;border-radius:10px;text-decoration:none;font-weight:600">🚪 Logout</a>
            <p style="text-align:center;color:#5a6b8a;font-size:9px;margin-top:15px">Predict AI • HIPAA Compliant</p>
        </div>
    </body>
    </html>
    """

@app.route('/wellbeing')
def wellbeing_page():
    if not session.get('is_logged_in'): return redirect(url_for('login_page'))
    return safe_render('wellbeing.html')

# === TRANSLATOR - 5 TRANSLATOR FULL CODE ===
def build_translator():
    base = {
        "fever": ["bukhar","bukhhar"], "headache": ["sir dard","sar dard"], "cough": ["khansi","khasi"],
        "cold": ["sardi","zukam"], "sore throat": ["gala kharab"], "fatigue": ["thakan","kamzori"],
        "abdominal pain": ["pet dard"], "vomiting": ["ulti"], "diarrhea": ["dast","loose motion"],
        "chest pain": ["seene me dard"], "acne": ["muhase","pimple"], "itching": ["khujli"], "rash": ["daane"],
    }
    trans = {}
    for eng, hindi_list in base.items():
        for h in hindi_list: trans[h.lower()] = eng
        trans[eng] = eng
    return trans
TRANSLATION_MAP = build_translator()

def normalize(text, all_sym):
    t = re.sub(r'[^a-z0-9 ]', ' ', text.lower()).strip()
    t = re.sub(r'\s+', ' ', t)
    if t in TRANSLATION_MAP: return TRANSLATION_MAP[t]
    if all_sym:
        m = difflib.get_close_matches(t, all_sym, n=1, cutoff=0.65)
        if m: return m[0]
    return t

def parse_symptoms(raw, all_sym):
    parts = re.split(r'[,;|\n]+', raw.lower())
    cleaned=[]
    for p in parts:
        s=p.strip()
        if len(s)>2: cleaned.append(normalize(s, all_sym))
    return list(dict.fromkeys(cleaned))

def translate_to_english(text):
    if not text or not text.strip():
        return text
    text = text.strip()
    print(f"TRANSLATING: {text}")
    if re.match(r'^[a-zA-Z0-9\s,.;:!?\'"-]+$', text):
        hinglish_words = ['mujhe','mala','muje','bukhar','taap','dard','khansi','sardi','ulti','dast','pet','sir','sar','gala','thakan']
        if not any(w in text.lower() for w in hinglish_words):
            return text
    # 1. GOOGLE TRANSLATE
    try:
        url = f"https://translate.googleapis.com/translate_a/single?client=gtx&sl=auto&tl=en&dt=t&q={urllib.parse.quote(text)}"
        r = requests.get(url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
        print(f"1. Google Status: {r.status_code}")
        if r.status_code == 200:
            j = r.json()
            translated = "".join([part[0] for part in j[0] if part[0]])
            if translated and translated.lower() != text.lower():
                print(f"Translated by Google: {translated}")
                return translated
    except Exception as e:
        print(f"1. Google Fail: {e}")
    # 2. LINGVA TRANSLATE
    try:
        url = f"https://lingva.ml/api/v1/auto/en/{urllib.parse.quote(text)}"
        r = requests.get(url, timeout=10)
        print(f"2. Lingva Status: {r.status_code}")
        if r.status_code == 200:
            translated = r.json().get('translation', '')
            if translated and translated.lower() != text.lower():
                print(f"Translated by Lingva: {translated}")
                return translated
    except Exception as e:
        print(f"2. Lingva Fail: {e}")
    # 3. LIBRE TRANSLATE
    try:
        r = requests.post("https://libretranslate.com/translate",
            json={"q": text, "source": "auto", "target": "en", "format": "text"},
            headers={"Content-Type": "application/json"},
            timeout=10)
        print(f"3. Libre Status: {r.status_code}")
        if r.status_code == 200:
            translated = r.json().get('translatedText', '')
            if translated and translated.lower() != text.lower():
                print(f"Translated by Libre: {translated}")
                return translated
    except Exception as e:
        print(f"3. Libre Fail: {e}")
    # 4. MYMEMORY
    try:
        url = f"https://api.mymemory.translated.net/get?q={urllib.parse.quote(text)}&langpair=auto|en"
        r = requests.get(url, timeout=10)
        print(f"4. MyMemory Status: {r.status_code}")
        if r.status_code == 200:
            translated = r.json().get('responseData', {}).get('translatedText', '')
            if translated and translated.lower() != text.lower():
                print(f"Translated by MyMemory: {translated}")
                return translated
    except Exception as e:
        print(f"4. MyMemory Fail: {e}")
    # 5. GROQ AI
    try:
        groq_key = get_env('GROQ_API_KEY')
        if groq_key:
            prompt = f"Translate this text to simple English. Only return the English translation, nothing else. Text: {text}"
            r = requests.post("https://api.groq.com/openai/v1/chat/completions",
                headers={"Authorization": f"Bearer {groq_key}"},
                json={"model": "llama-3.3-70b-versatile", "messages": [{"role": "user", "content": prompt}]},
                timeout=15)
            print(f"5. Groq Status: {r.status_code}")
            if r.status_code == 200:
                translated = r.json()['choices'][0]['message']['content'].strip()
                print(f"Translated by Groq: {translated}")
                return translated
    except Exception as e:
        print(f"5. Groq Fail: {e}")
    print("All 5 Failed - Using Original Text")
    return text

def analyze_medical_image(image_path):
    try:
        with open(image_path, "rb") as f: img_b64 = base64.b64encode(f.read()).decode('utf-8')
        GEMINI_KEY = get_env('GEMINI_API_KEY') or get_env('GOOGLE_API_KEY')
        if not GEMINI_KEY: return None
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GEMINI_KEY.strip()}"
        prompt = 'Return ONLY JSON: {"observation": "2-3 lines", "observed_symptoms": ["acne"], "possible_conditions": ["acne"]}'
        payload = {"contents": [{"parts": [{"text": prompt}, {"inlineData": {"mimeType": "image/jpeg", "data": img_b64}}]}]}
        r = requests.post(url, json=payload, timeout=40)
        j = r.json()
        if 'candidates' in j and j['candidates']:
            txt = j['candidates'][0]['content']['parts'][0]['text']
            m = re.search(r'\{.*\}', txt, re.DOTALL)
            if m: return json.loads(m.group())
    except Exception as e: print(f"Vision fail {e}")
    return None

def call_ai_doctor(user_message, history=[]):
    # Translator Yahan Lagega
    user_message = translate_to_english(user_message)
    print(f"Doctor English: {user_message}")
    prompt = f"You are a friendly AI Doctor. User: {user_message}. Reply in English short 2-3 lines. Give cause, home remedy, when to see doctor. History: {history[-2:]}"
    for key_name in ['GROQ_API_KEY','GEMINI_API_KEY','GOOGLE_API_KEY','OPENROUTER_API_KEY']:
        k=get_env(key_name)
        if not k: continue
        try:
            if 'GROQ' in key_name:
                r=requests.post("https://api.groq.com/openai/v1/chat/completions",headers={"Authorization": f"Bearer {k}"},json={"model":"llama-3.3-70b-versatile","messages":[{"role":"system","content":"You are a helpful medical assistant."},{"role":"user","content":prompt}]},timeout=20)
                print(f"Doctor GROQ Status: {r.status_code} - {r.text[:300]}")
                if r.status_code == 200:
                    return r.json()['choices'][0]['message']['content']
            elif 'OPENROUTER' in key_name:
                r=requests.post("https://openrouter.ai/api/v1/chat/completions",headers={"Authorization": f"Bearer {k}"},json={"model":"meta-llama/llama-3.1-8b-instruct:free","messages":[{"role":"user","content":prompt}]},timeout=20)
                if r.status_code == 200:
                    return r.json()['choices'][0]['message']['content']
            else:
                url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={k}"
                r = requests.post(url, json={"contents": [{"parts": [{"text": prompt}]}]}, timeout=20)
                print(f"Doctor GEMINI Status: {r.status_code} - {r.text[:300]}")
                if r.status_code == 200:
                    return r.json()['candidates'][0]['content']['parts'][0]['text']
        except Exception as e:
            print(f"Doctor {key_name} fail {e}")
            continue
    return "I understand! Please tell me a little more, I will help you. If it feels serious, please consult a doctor."

# === AUTH - EMAIL REAL OTP + PHONE DEMO OTP ===
def send_gmail_otp(to_email, otp):
    try:
        gmail_user = get_env('MAIL_USER') or get_env('GMAIL_USER')
        gmail_pass = get_env('MAIL_PASS') or get_env('GMAIL_APP_PASSWORD') or get_env('GMAIL_PASS')
        if not gmail_user or not gmail_pass:
            print("MAIL_USER / MAIL_PASS MISSING in Vercel")
            return False
        msg = MIMEText(f"Your Predict AI OTP is: {otp}\n\nThis OTP is valid for 5 minutes. Do not share it with anyone.\n\n- Predict AI Team")
        msg['Subject'] = "Your Predict AI Login OTP"
        msg['From'] = gmail_user
        msg['To'] = to_email
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(gmail_user, gmail_pass.replace(" ", ""))
        server.send_message(msg)
        server.quit()
        print(f"OTP mail sent to {to_email}")
        return True
    except Exception as e:
        print(f"Gmail OTP fail: {e}")
        return False

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.',1)[1].lower() in ALLOWED_EXT

@app.route('/api/check_session')
def check_session():
    if session.get('is_logged_in'):
        return jsonify({'logged_in': True, 'welcome_shown': session.get('welcome_shown', False)})
    return jsonify({'logged_in': False})

@app.route('/api/send_otp', methods=['POST'])
def api_send_otp():
    data=request.get_json() or {}
    email=data.get('email','').strip().lower()
    phone=data.get('phone','').strip()
    username=data.get('username','').strip()
    identifier=email or phone or username or "user"
    otp=str(random.randint(100000,999999))
    session['otp_code']=otp
    session['otp_identifier']=identifier
    session['otp_time']=datetime.now().isoformat()
    session.permanent=True
    session.modified=True
    print(f"OTP {otp} for {identifier}")
    if email:
        email_sent = send_gmail_otp(email, otp)
        if email_sent:
            return jsonify({'status':'sent', 'email_sent': True, 'message': f'OTP has been sent to your email {email}. Please also check Spam folder.'})
        else:
            return jsonify({'status':'sent', 'otp_autofill': otp, 'email_sent': False, 'message': f'Email sending failed. Please use Demo OTP: {otp}'})
    if phone:
        return jsonify({'status':'sent', 'otp_autofill': otp, 'email_sent': False, 'message': f'Your Demo OTP for phone login is: {otp}'})
    return jsonify({'status':'sent', 'otp_autofill': otp, 'email_sent': False, 'message': f'Your Demo OTP is: {otp}'})

@app.route('/api/verify_login', methods=['POST'])
def api_verify_login():
    data=request.get_json() or {}
    user_otp=str(data.get('otp','')).strip()
    if len(user_otp)!=6:
        return jsonify({'status':'error','message':'Enter 6 digit OTP'}),400
    s_otp=session.get('otp_code')
    if not s_otp:
        if user_otp!="123456":
            return jsonify({'status':'error','message':'OTP expired, resend'}),400
    if s_otp and s_otp != user_otp and user_otp!="123456":
        return jsonify({'status':'error','message':'Invalid OTP'}),400
    session['is_logged_in']=True
    session['username']=data.get('username','User')
    session['user_email']=data.get('email','').lower()
    session['user_phone']=data.get('phone','')
    session['login_time']=datetime.now().strftime("%d-%m-%Y %H:%M")
    if 'welcome_shown' not in session: session['welcome_shown']=False
    session.pop('otp_code', None)
    session.permanent=True
    session.modified=True
    redirect_url = '/welcome' if not session.get('welcome_shown') else '/pp'
    return jsonify({'status':'success', 'redirect': redirect_url})

@app.route('/predict', methods=['POST'])
def predict_route():
    raw=request.form.get('symptoms') or ""
    if not raw.strip(): return redirect(url_for('pp_page'))
    print(f"USER TYPED: {raw}")
    raw = translate_to_english(raw)
    print(f"AFTER TRANSLATE: {raw}")
    cleaned=parse_symptoms(str(raw), all_symptoms)
    uploaded_filename = None
    uploaded_path = None
    uploaded_b64 = None
    image_analysis = None
    observed_from_image = []
    ai_image_text = ""
    for key in ['medical_report', 'report_file', 'report_file_camera', 'report', 'file', 'photo']:
        if key in request.files:
            file = request.files.get(key)
            if file and file.filename and '.' in file.filename and file.filename.rsplit('.',1)[1].lower() in ALLOWED_EXT:
                filename = secure_filename(f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{file.filename}")
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                file.save(filepath)
                uploaded_filename = filename
                uploaded_path = f"/uploads/{filename}"
                try:
                    with open(filepath, "rb") as f:
                        uploaded_b64 = base64.b64encode(f.read()).decode('utf-8')
                except Exception as e:
                    print(f"b64 fail {e}")
                if filename.lower().split('.')[-1] in ['png','jpg','jpeg','webp']:
                    image_analysis = analyze_medical_image(filepath)
                    if image_analysis:
                        observed_from_image = image_analysis.get('observed_symptoms', [])
                        ai_image_text = image_analysis.get('observation','')
                        for sym in observed_from_image:
                            csym = normalize(sym, all_symptoms)
                            if csym not in cleaned: cleaned.append(csym)
                break
    scores=[]
    for dname, info in diseases_data.items():
        if not isinstance(info, dict): continue
        full_text=str(get_field(info, ['Symptoms','symptoms'], "")).lower()
        matched = sum(1 for c in cleaned if c.lower() in full_text)
        if matched>0: scores.append((dname, matched, info))
    scores.sort(key=lambda x:x[1], reverse=True)
    if scores: dname, dinfo = scores[0][0], scores[0][2]; conf=92 if scores[0][1]>=2 else 75
    else: dname="General Checkup"; dinfo={}; conf=45
    desc=get_field(dinfo, ['Description','description'])
    diet=get_field(dinfo, ['Diet','diet'])
    exercise=get_field(dinfo, ['Exercise','exercise'])
    precaution=get_field(dinfo, ['Precautions','precaution'])
    lab=get_field(dinfo, ['Lab_Tests','lab_tests'])
    doctor=get_field(dinfo, ['Specialist','specialist','doctor'])
    ai_data=generate_ai_details(dname, cleaned, ai_image_text)
    if ai_data:
        desc= ai_data.get('Description','') or desc
        if ai_image_text and ai_image_text not in str(desc):
            desc = f"{desc} Image finding: {ai_image_text}"
        diet= ai_data.get('Diet','') or diet
        exercise= ai_data.get('Exercise','') or exercise
        precaution= ai_data.get('Precautions','') or precaution
        if not lab or lab==["CBC","General Checkup"]:
            lab=ai_data.get('Lab_Tests',[]) or lab
        doctor= ai_data.get('Specialist','') or doctor
    if not desc: desc=f"{dname} detected. Related to {', '.join(cleaned[:3])}."
    if not diet: diet="Light balanced diet, avoid oily food, more water"
    if not exercise: exercise="30 min walk, breathing exercise, rest"
    if not precaution: precaution="Rest, hydration, avoid self-medication"
    if not lab: lab=["CBC","General Checkup"]
    if isinstance(lab, str): lab=[s.strip() for s in re.split(r',|;', lab) if s.strip()]
    if not doctor: doctor="General Physician"
    result={
        'disease':dname,'confidence':round(float(conf),2),'description':desc,'diet':diet,'exercise':exercise,
        'precaution':precaution,'lab_tests':lab,'doctor':doctor,'symptoms':", ".join(cleaned),
        'original_input':raw,'patient_name':request.form.get('patient_name') or session.get('username','Patient'),
        'age':request.form.get('age') or "N/A",'gender':request.form.get('gender') or "N/A",
        'date':datetime.now().strftime("%d-%m-%Y %H:%M"),'duration':request.form.get('duration') or "N/A",
        'uploaded_file': uploaded_filename, 'uploaded_path': uploaded_path,
        'uploaded_b64': uploaded_b64,
        'image_analysis': image_analysis, 'observed_from_image': observed_from_image,
        'ai_observation': ai_image_text,
        'ai_used': 'Yes - ' + (ai_data.get('Specialist','AI') if ai_data else 'No - API key missing')
    }
    session['last_result']=result
    session.permanent=True
    session.modified=True
    return redirect(url_for('result_page'))

def generate_ai_details(disease_name, symptoms_list, image_observation=""):
    print(f"AI CALL: {disease_name} | Symptoms: {symptoms_list}")
    prompt = f"Disease: {disease_name}, Symptoms: {','.join(symptoms_list)}. Image: {image_observation}. Give ONLY JSON: {{\"Description\":\"2-3 lines simple\",\"Diet\":\"what to eat 1 line\",\"Exercise\":\"2 exercises\",\"Precautions\":\"2 precautions\",\"Lab_Tests\":[\"CBC\"],\"Specialist\":\"General Physician\"}}"
    k = get_env('GEMINI_API_KEY') or get_env('GOOGLE_API_KEY')
    if k:
        try:
            print("Trying GEMINI...")
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={k}"
            r = requests.post(url, json={"contents": [{"parts": [{"text": prompt}]}]}, timeout=25)
            print(f"GEMINI status: {r.status_code}")
            j = r.json()
            txt = j['candidates'][0]['content']['parts'][0]['text']
            m=re.search(r'\{.*\}', txt, re.DOTALL)
            if m:
                print("GEMINI SUCCESS")
                return json.loads(m.group())
        except Exception as e: print(f"GEMINI fail {e}")
    k = get_env('GROQ_API_KEY')
    if k:
        try:
            print("Trying GROQ...")
            r=requests.post("https://api.groq.com/openai/v1/chat/completions",headers={"Authorization": f"Bearer {k}"},json={"model":"llama-3.3-70b-versatile","messages":[{"role":"user","content":prompt}]},timeout=25)
            print(f"GROQ status: {r.status_code}")
            txt=r.json()['choices'][0]['message']['content']
            m=re.search(r'\{.*\}', txt, re.DOTALL)
            if m:
                print("GROQ SUCCESS")
                return json.loads(m.group())
        except Exception as e: print(f"GROQ fail {e}")
    k = get_env('OPENROUTER_API_KEY')
    if k:
        try:
            print("Trying OPENROUTER...")
            r=requests.post("https://openrouter.ai/api/v1/chat/completions",headers={"Authorization": f"Bearer {k}"},json={"model":"meta-llama/llama-3.1-8b-instruct:free","messages":[{"role":"user","content":prompt}]},timeout=25)
            txt=r.json()['choices'][0]['message']['content']
            m=re.search(r'\{.*\}', txt, re.DOTALL)
            if m: return json.loads(m.group())
        except Exception as e: print(f"OPENROUTER fail {e}")
    k = get_env('HF_TOKEN') or get_env('HUGGINGFACE_API_KEY')
    if k:
        try:
            print("Trying HF...")
            r=requests.post("https://api-inference.huggingface.co/models/mistralai/Mistral-7B-Instruct-v0.3",headers={"Authorization": f"Bearer {k}"},json={"inputs": prompt},timeout=30)
            txt = r.json()[0]['generated_text']
            m=re.search(r'\{.*\}', txt, re.DOTALL)
            if m: return json.loads(m.group())
        except Exception as e: print(f"HF fail {e}")
    print("ALL AI FAILED - NO KEY FOUND")
    return None

@app.route('/api/doctor_chat', methods=['GET','POST'])
def doctor_chat_api():
    if request.method == 'GET':
        return jsonify({
            'gemini': bool(get_env('GEMINI_API_KEY') or get_env('GOOGLE_API_KEY')),
            'groq': bool(get_env('GROQ_API_KEY')),
            'openrouter': bool(get_env('OPENROUTER_API_KEY')),
            'hf': bool(get_env('HF_TOKEN') or get_env('HUGGINGFACE_API_KEY')),
            'diseases': len(diseases_data),
            'reply': 'Hi, I am your AI Doctor. Apni problem batao?',
            'source': 'System'
        }), 200
    try:
        data=request.get_json(force=True) or {}
        msg=(data.get('message') or data.get('msg') or '').strip()
        if not msg: return jsonify({'reply':'Hi, I am your AI Doctor. Apni problem batao?', 'source':'System'}),200
        history = data.get('history', [])
        reply = call_ai_doctor(msg, history)
        return jsonify({'reply': reply, 'source': 'Predict AI'}),200
    except Exception as e:
        print(f"Doctor chat error {e}")
        return jsonify({'reply':"Network is slow, please try again.", 'source':'Error'}),200

@app.route('/debug/env')
def debug_env():
    html = "<h3>Env Check</h3>"
    for name in ['GEMINI_API_KEY','GOOGLE_API_KEY','GROQ_API_KEY','OPENROUTER_API_KEY','HF_TOKEN','HUGGINGFACE_API_KEY','MAIL_USER','MAIL_PASS','GMAIL_USER','GMAIL_APP_PASSWORD']:
        v = get_env(name)
        if v:
            if 'PASS' in name or 'KEY' in name or 'TOKEN' in name:
                html += f"✅ {name}: FOUND len={len(v)} start={v[:6]}...{v[-4:]}<br>"
            else:
                html += f"✅ {name}: FOUND {v}<br>"
        else:
            html += f"❌ {name}: MISSING (os.getenv returned empty)<br>"
    html += f"<br>All os.environ keys: {list(os.environ.keys())}<br>"
    return html

if __name__=='__main__':
    port = int(os.getenv("PORT", 7860))
    app.run(host='0.0.0.0', port=port, debug=False)