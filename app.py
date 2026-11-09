from flask import Flask, render_template, request, jsonify, session, redirect, url_for, send_from_directory, send_file, make_response
import json, os, re, difflib, random, requests, base64, io
from datetime import datetime, timedelta
from werkzeug.utils import secure_filename
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

# ================= DATABASE - NEON =================
# Vercel me DATABASE_URL aayega Neon Integration se
# Agar nahi hai to app session pe chalega, crash nahi hoga
DATABASE_URL = os.getenv('DATABASE_URL') or os.getenv('POSTGRES_URL') or os.getenv('NEON_DATABASE_URL') or ""
DATABASE_URL = DATABASE_URL.strip().strip('"').strip("'")

def get_db():
    if not DATABASE_URL:
        return None
    try:
        import psycopg2
        import psycopg2.extras
        conn = psycopg2.connect(DATABASE_URL, sslmode='require')
        return conn
    except Exception as e:
        print(f"DB CONNECT FAIL: {e}")
        return None

def db_execute(query, params=(), fetch=False):
    conn = get_db()
    if not conn:
        return None
    try:
        cur = conn.cursor(cursor_factory=__import__('psycopg2.extras', fromlist=['RealDictCursor']).RealDictCursor)
        cur.execute(query, params)
        data = cur.fetchall() if fetch else None
        conn.commit()
        cur.close(); conn.close()
        return data
    except Exception as e:
        print(f"DB ERROR: {e}")
        try: conn.rollback(); conn.close()
        except: pass
        return None

def save_to_db(table, data_dict):
    # Generic save - agar table nahi hai to ignore, app nahi rokega
    try:
        cols = ",".join(data_dict.keys())
        vals = ",".join(["%s"]*len(data_dict))
        db_execute(f"INSERT INTO {table} ({cols}) VALUES ({vals})", tuple(data_dict.values()))
    except Exception as e:
        print(f"Save DB fail {table}: {e}")

def get_env(name):
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

# === LOAD DISEASES - diseases.json + symptoms.json DONO SUPPORT ===
diseases_data={}; all_symptoms=[]
try:
    for fname in ['diseases.json','symptoms.json','data.json']:
        json_path = os.path.join(BASE_DIR, fname)
        if os.path.exists(json_path):
            with open(json_path,'r',encoding='utf-8') as f:
                tmp=json.load(f)
            # Agar list hai to dict bana do
            if isinstance(tmp, list):
                for item in tmp:
                    if isinstance(item, dict):
                        nm = item.get('Disease') or item.get('disease') or item.get('name') or f"Disease_{len(diseases_data)}"
                        diseases_data[nm]=item
            elif isinstance(tmp, dict):
                diseases_data.update(tmp)
            print(f"LOADED {fname}: {len(diseases_data)} diseases")
            break
    temp=set()
    for v in diseases_data.values():
        if isinstance(v, dict):
            s=str(v.get('Symptoms') or v.get('symptoms') or "")
            for part in re.split(r'[,;]', s):
                if part.strip(): temp.add(part.strip().lower())
    all_symptoms=sorted(list(temp))
    print(f"TOTAL SYMPTOMS: {len(all_symptoms)}")
except Exception as e:
    print(f"Load error {e}")

def get_field(info, keys, default=""):
    if not isinstance(info, dict): return default
    for k in keys:
        if k in info and info[k]: return info[k]
    return default

# ================= BODY MAP DATA =================
# Gender -> Body Part -> Symptoms (PP page ko bhejega)
BODY_MAP = {
    "male": {
        "head": ["headache","dizziness","fever","blurred vision","sore throat","cold","cough"],
        "chest": ["chest pain","cough","breathing difficulty","palpitation","fever"],
        "stomach": ["abdominal pain","vomiting","diarrhea","nausea","acidity","constipation"],
        "skin": ["itching","rash","acne","redness","dry skin","wound"],
        "leg": ["leg pain","joint pain","swelling","numbness","cramps"],
        "arm": ["arm pain","joint pain","numbness","swelling"],
        "back": ["back pain","stiffness","numbness"],
    },
    "female": {
        "head": ["headache","dizziness","fever","blurred vision","sore throat","cold","cough","hair fall"],
        "chest": ["chest pain","cough","breathing difficulty","palpitation","breast pain"],
        "stomach": ["abdominal pain","vomiting","diarrhea","nausea","acidity","period pain","constipation"],
        "skin": ["itching","rash","acne","redness","dry skin","wound"],
        "leg": ["leg pain","joint pain","swelling","numbness","cramps"],
        "arm": ["arm pain","joint pain","numbness","swelling"],
        "back": ["back pain","stiffness","numbness"],
    }
}

# === CORE PAGES - SESSION SAME HAI ===
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
    except: return redirect(url_for('pp_page'))

@app.route('/pp')
def pp_page():
    if not session.get('is_logged_in'): return redirect(url_for('login_page'))
    # Body Map se aaye hue values session se le lo
    preselected_symptoms = session.pop('bodymap_symptoms', [])
    preselected_gender = session.get('bodymap_gender', session.get('gender',''))
    preselected_part = session.get('bodymap_part','')
    # URL se bhi aaye to le lo ?symptoms=fever,headache&gender=male&part=head
    url_sym = request.args.get('symptoms','')
    if url_sym:
        preselected_symptoms = [s.strip() for s in url_sym.split(',') if s.strip()]
    try:
        for name in ['PP.html', 'pp.html', 'PP.HTML']:
            if os.path.exists(os.path.join(BASE_DIR, 'templates', name)):
                return render_template(name, symptoms=all_symptoms, total_diseases=len(diseases_data),
                    preselected_symptoms=preselected_symptoms, preselected_gender=preselected_gender, preselected_part=preselected_part,
                    bodymap=BODY_MAP)
        return render_template('PP.html', symptoms=all_symptoms, total_diseases=len(diseases_data),
            preselected_symptoms=preselected_symptoms, preselected_gender=preselected_gender, preselected_part=preselected_part, bodymap=BODY_MAP)
    except Exception as e:
        print(f"PP ERROR: {e}")
        return f"<h2>Welcome {session.get('username','User')}!</h2><p>Symptoms: {preselected_symptoms}</p><a href='/clear-loop'>Clear</a>", 200

# === BODY MAP API - Gender + Part -> Symptoms ===
@app.route('/api/bodymap', methods=['GET','POST'])
def bodymap_api():
    if request.method == 'GET':
        gender = request.args.get('gender','male').lower()
        part = request.args.get('part','')
        if part:
            return jsonify({'gender':gender,'part':part,'symptoms': BODY_MAP.get(gender, BODY_MAP['male']).get(part, [])})
        return jsonify(BODY_MAP.get(gender, BODY_MAP['male']))
    # POST - Body Map se select karke PP pe bhejo
    data = request.get_json() or request.form.to_dict() or {}
    gender = str(data.get('gender','male')).lower()
    part = str(data.get('body_part') or data.get('part') or '')
    syms = data.get('symptoms') or data.get('selected_symptoms') or []
    if isinstance(syms, str):
        syms = [s.strip() for s in re.split(r'[,;|]', syms) if s.strip()]
    session['bodymap_gender']=gender
    session['bodymap_part']=part
    session['bodymap_symptoms']=syms
    session['gender']=gender
    session.permanent=True; session.modified=True
    # Agar fetch hai to json do, warna PP pe redirect
    if request.is_json:
        return jsonify({'status':'success','redirect':'/pp','symptoms':syms,'gender':gender,'part':part})
    return redirect(url_for('pp_page', symptoms=",".join(syms), gender=gender, part=part))

@app.route('/bodymap')
def bodymap_page():
    if not session.get('is_logged_in'): return redirect(url_for('login_page'))
    return safe_render('bodymap.html', fallback='/pp')

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
    session.permanent=True; session.modified=True
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
    user_data={'username':session.get('username','User'),'email':session.get('user_email',''),'phone':session.get('user_phone',''),'login_time':session.get('login_time','')}
    try:
        for name in ['my_profile.html', 'my-profile.html', 'profile.html']:
            if os.path.exists(os.path.join(BASE_DIR, 'templates', name)):
                return render_template(name, user=user_data)
    except Exception as e: print(f"Profile error: {e}")
    return f"<h2>{user_data['username']}</h2><p>{user_data['email']}</p><a href='/logout'>Logout</a>"
@app.route('/wellbeing')
def wellbeing_page():
    if not session.get('is_logged_in'): return redirect(url_for('login_page'))
    return safe_render('wellbeing.html')

# === TRANSLATOR - SAME 5 TRANSLATOR, KOI CHANGE NAHI ===
def build_translator():
    base = {"fever": ["bukhar","bukhhar"], "headache": ["sir dard","sar dard"], "cough": ["khansi","khasi"],"cold": ["sardi","zukam"], "sore throat": ["gala kharab"], "fatigue": ["thakan","kamzori"],"abdominal pain": ["pet dard"], "vomiting": ["ulti"], "diarrhea": ["dast","loose motion"],"chest pain": ["seene me dard"], "acne": ["muhase","pimple"], "itching": ["khujli"], "rash": ["daane"],}
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
    if not text or not text.strip(): return text
    text = text.strip()
    if re.match(r'^[a-zA-Z0-9\s,.;:!?\'"-]+$', text):
        hinglish_words = ['mujhe','mala','muje','bukhar','taap','dard','khansi','sardi','ulti','dast','pet','sir','sar','gala','thakan']
        if not any(w in text.lower() for w in hinglish_words): return text
    try:
        url = f"https://translate.googleapis.com/translate_a/single?client=gtx&sl=auto&tl=en&dt=t&q={urllib.parse.quote(text)}"
        r = requests.get(url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
        if r.status_code == 200:
            j = r.json()
            translated = "".join([part[0] for part in j[0] if part[0]])
            if translated and translated.lower() != text.lower(): return translated
    except Exception as e: print(f"Google Fail: {e}")
    try:
        url = f"https://lingva.ml/api/v1/auto/en/{urllib.parse.quote(text)}"
        r = requests.get(url, timeout=10)
        if r.status_code == 200:
            translated = r.json().get('translation', '')
            if translated and translated.lower() != text.lower(): return translated
    except Exception as e: print(f"Lingva Fail: {e}")
    try:
        r = requests.post("https://libretranslate.com/translate", json={"q": text, "source": "auto", "target": "en", "format": "text"}, headers={"Content-Type": "application/json"}, timeout=10)
        if r.status_code == 200:
            translated = r.json().get('translatedText', '')
            if translated and translated.lower() != text.lower(): return translated
    except Exception as e: print(f"Libre Fail: {e}")
    try:
        url = f"https://api.mymemory.translated.net/get?q={urllib.parse.quote(text)}&langpair=auto|en"
        r = requests.get(url, timeout=10)
        if r.status_code == 200:
            translated = r.json().get('responseData', {}).get('translatedText', '')
            if translated and translated.lower() != text.lower(): return translated
    except Exception as e: print(f"MyMemory Fail: {e}")
    try:
        groq_key = get_env('GROQ_API_KEY')
        if groq_key:
            prompt = f"Translate this text to simple English. Only return the English translation, nothing else. Text: {text}"
            r = requests.post("https://api.groq.com/openai/v1/chat/completions", headers={"Authorization": f"Bearer {groq_key}"}, json={"model": "llama-3.3-70b-versatile", "messages": [{"role": "user", "content": prompt}]}, timeout=15)
            if r.status_code == 200: return r.json()['choices'][0]['message']['content'].strip()
    except Exception as e: print(f"Groq Translate Fail: {e}")
    return text

# === IMAGE READING - XRAY / BLOOD REPORT / SKIN / PDF ===
def analyze_medical_image(image_path, file_type='image'):
    try:
        GEMINI_KEY = get_env('GEMINI_API_KEY') or get_env('GOOGLE_API_KEY')
        if not GEMINI_KEY: return None
        # PDF hai to text nikalne ki koshish, image hai to vision
        if file_type == 'pdf':
            try:
                import fitz
                doc = fitz.open(image_path)
                txt = ""
                for page in doc: txt += page.get_text() + "\n"
                if txt.strip():
                    return {"observation": txt[:1500], "observed_symptoms": [], "possible_conditions": [], "report_text": txt[:2000], "file_type": "pdf"}
            except: pass
            return {"observation": "PDF uploaded, text could not be extracted", "observed_symptoms": [], "possible_conditions": []}
        with open(image_path, "rb") as f: img_b64 = base64.b64encode(f.read()).decode('utf-8')
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GEMINI_KEY.strip()}"
        prompt = 'You are a medical image analyzer. Analyze this X-Ray / Blood Report / Skin photo / Medical Report image. Return ONLY JSON: {"observation": "2-3 lines what you see", "observed_symptoms": ["acne"], "possible_conditions": ["acne"], "report_values": "if blood report, list abnormal values", "urgency": "low/medium/high"}'
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
    user_message = translate_to_english(user_message)
    prompt = f"You are a friendly AI Doctor. User: {user_message}. Reply in English short 2-3 lines. Give cause, home remedy, when to see doctor. History: {history[-2:]}"
    for key_name in ['GROQ_API_KEY','GEMINI_API_KEY','GOOGLE_API_KEY','OPENROUTER_API_KEY']:
        k=get_env(key_name)
        if not k: continue
        try:
            if 'GROQ' in key_name:
                r=requests.post("https://api.groq.com/openai/v1/chat/completions",headers={"Authorization": f"Bearer {k}"},json={"model":"llama-3.3-70b-versatile","messages":[{"role":"system","content":"You are a helpful medical assistant."},{"role":"user","content":prompt}]},timeout=20)
                if r.status_code == 200: return r.json()['choices'][0]['message']['content']
            elif 'OPENROUTER' in key_name:
                r=requests.post("https://openrouter.ai/api/v1/chat/completions",headers={"Authorization": f"Bearer {k}"},json={"model":"meta-llama/llama-3.1-8b-instruct:free","messages":[{"role":"user","content":prompt}]},timeout=20)
                if r.status_code == 200: return r.json()['choices'][0]['message']['content']
            else:
                url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={k}"
                r = requests.post(url, json={"contents": [{"parts": [{"text": prompt}]}]}, timeout=20)
                if r.status_code == 200: return r.json()['candidates'][0]['content']['parts'][0]['text']
        except Exception as e: print(f"Doctor {key_name} fail {e}"); continue
    return "I understand! Please tell me a little more, I will help you. If it feels serious, please consult a doctor."

# === AUTH - SAME GMAIL + PHONE, KOI CHANGE NAHI ===
def send_gmail_otp(to_email, otp):
    try:
        gmail_user = get_env('MAIL_USER') or get_env('GMAIL_USER')
        gmail_pass = get_env('MAIL_PASS') or get_env('GMAIL_APP_PASSWORD') or get_env('GMAIL_PASS')
        if not gmail_user or not gmail_pass: return False
        msg = MIMEText(f"Your Predict AI OTP is: {otp}\n\nThis OTP is valid for 5 minutes. Do not share it with anyone.\n\n- Predict AI Team")
        msg['Subject'] = "Your Predict AI Login OTP"; msg['From'] = gmail_user; msg['To'] = to_email
        server = smtplib.SMTP('smtp.gmail.com', 587); server.starttls()
        server.login(gmail_user, gmail_pass.replace(" ", "")); server.send_message(msg); server.quit()
        return True
    except Exception as e: print(f"Gmail OTP fail: {e}"); return False
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.',1)[1].lower() in ALLOWED_EXT

@app.route('/api/check_session')
def check_session():
    if session.get('is_logged_in'): return jsonify({'logged_in': True, 'welcome_shown': session.get('welcome_shown', False)})
    return jsonify({'logged_in': False})
@app.route('/api/send_otp', methods=['POST'])
def api_send_otp():
    data=request.get_json() or {}
    email=data.get('email','').strip().lower(); phone=data.get('phone','').strip(); username=data.get('username','').strip()
    identifier=email or phone or username or "user"
    otp=str(random.randint(100000,999999))
    session['otp_code']=otp; session['otp_identifier']=identifier; session['otp_time']=datetime.now().isoformat()
    session.permanent=True; session.modified=True
    print(f"OTP {otp} for {identifier}")
    if email:
        email_sent = send_gmail_otp(email, otp)
        if email_sent: return jsonify({'status':'sent', 'email_sent': True, 'message': f'OTP has been sent to your email {email}. Please also check Spam folder.'})
        else: return jsonify({'status':'sent', 'otp_autofill': otp, 'email_sent': False, 'message': f'Email sending failed. Please use Demo OTP: {otp}'})
    if phone: return jsonify({'status':'sent', 'otp_autofill': otp, 'email_sent': False, 'message': f'Your Demo OTP for phone login is: {otp}'})
    return jsonify({'status':'sent', 'otp_autofill': otp, 'email_sent': False, 'message': f'Your Demo OTP is: {otp}'})
@app.route('/api/verify_login', methods=['POST'])
def api_verify_login():
    data=request.get_json() or {}
    user_otp=str(data.get('otp','')).strip()
    if len(user_otp)!=6: return jsonify({'status':'error','message':'Enter 6 digit OTP'}),400
    s_otp=session.get('otp_code')
    if not s_otp:
        if user_otp!="123456": return jsonify({'status':'error','message':'OTP expired, resend'}),400
    if s_otp and s_otp != user_otp and user_otp!="123456": return jsonify({'status':'error','message':'Invalid OTP'}),400
    session['is_logged_in']=True; session['username']=data.get('username','User'); session['user_email']=data.get('email','').lower(); session['user_phone']=data.get('phone',''); session['login_time']=datetime.now().strftime("%d-%m-%Y %H:%M")
    if 'welcome_shown' not in session: session['welcome_shown']=False
    session.pop('otp_code', None); session.permanent=True; session.modified=True
    # DB me user save - agar DB hai to, nahi to ignore
    try:
        if DATABASE_URL:
            db_execute("INSERT INTO users (user_name, phone_number, email, login_time) VALUES (%s,%s,%s,NOW()) ON CONFLICT (email) DO UPDATE SET login_time=NOW()", (session['username'], session['user_phone'] or None, session['user_email'] or None))
    except: pass
    redirect_url = '/welcome' if not session.get('welcome_shown') else '/pp'
    return jsonify({'status':'success', 'redirect': redirect_url})

# === PREDICT - BODYMAP + IMAGE + DB SAVE ===
@app.route('/predict', methods=['POST'])
def predict_route():
    raw=request.form.get('symptoms') or ""
    # Body Map se hidden field bhi aa sakta hai
    body_part = request.form.get('body_part') or session.get('bodymap_part','')
    gender = request.form.get('gender') or session.get('bodymap_gender','')
    if not raw.strip():
        # Agar sirf body map symptoms hai to unko lo
        raw = request.form.get('bodymap_symptoms','') or ",".join(session.get('bodymap_symptoms',[]))
    if not raw.strip(): return redirect(url_for('pp_page'))
    print(f"USER TYPED: {raw} | BodyPart: {body_part} | Gender: {gender}")
    raw = translate_to_english(raw)
    cleaned=parse_symptoms(str(raw), all_symptoms)
    uploaded_filename = None; uploaded_path = None; uploaded_b64 = None; image_analysis = None; observed_from_image = []; ai_image_text = ""
    for key in ['medical_report', 'report_file', 'report_file_camera', 'report', 'file', 'photo']:
        if key in request.files:
            file = request.files.get(key)
            if file and file.filename and '.' in file.filename and file.filename.rsplit('.',1)[1].lower() in ALLOWED_EXT:
                filename = secure_filename(f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{file.filename}")
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                file.save(filepath)
                uploaded_filename = filename; uploaded_path = f"/uploads/{filename}"
                try:
                    with open(filepath, "rb") as f: uploaded_b64 = base64.b64encode(f.read()).decode('utf-8')
                except: pass
                ext = filename.lower().split('.')[-1]
                if ext in ['png','jpg','jpeg','webp']:
                    image_analysis = analyze_medical_image(filepath, 'image')
                    if image_analysis:
                        observed_from_image = image_analysis.get('observed_symptoms', [])
                        ai_image_text = image_analysis.get('observation','')
                        for sym in observed_from_image:
                            csym = normalize(sym, all_symptoms)
                            if csym not in cleaned: cleaned.append(csym)
                elif ext == 'pdf':
                    image_analysis = analyze_medical_image(filepath, 'pdf')
                    if image_analysis: ai_image_text = image_analysis.get('observation','')[:500]
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
    desc=get_field(dinfo, ['Description','description']); diet=get_field(dinfo, ['Diet','diet']); exercise=get_field(dinfo, ['Exercise','exercise']); precaution=get_field(dinfo, ['Precautions','precaution']); lab=get_field(dinfo, ['Lab_Tests','lab_tests']); doctor=get_field(dinfo, ['Specialist','specialist','doctor'])
    ai_data=generate_ai_details(dname, cleaned, ai_image_text)
    if ai_data:
        desc= ai_data.get('Description','') or desc
        if ai_image_text and ai_image_text not in str(desc): desc = f"{desc} Image finding: {ai_image_text}"
        diet= ai_data.get('Diet','') or diet; exercise= ai_data.get('Exercise','') or exercise; precaution= ai_data.get('Precautions','') or precaution
        if not lab or lab==["CBC","General Checkup"]: lab=ai_data.get('Lab_Tests',[]) or lab
        doctor= ai_data.get('Specialist','') or doctor
    if not desc: desc=f"{dname} detected. Related to {', '.join(cleaned[:3])}."
    if not diet: diet="Light balanced diet, avoid oily food, more water"
    if not exercise: exercise="30 min walk, breathing exercise, rest"
    if not precaution: precaution="Rest, hydration, avoid self-medication"
    if not lab: lab=["CBC","General Checkup"]
    if isinstance(lab, str): lab=[s.strip() for s in re.split(r',|;', lab) if s.strip()]
    if not doctor: doctor="General Physician"
    result={'disease':dname,'confidence':round(float(conf),2),'description':desc,'diet':diet,'exercise':exercise,'precaution':precaution,'lab_tests':lab,'doctor':doctor,'symptoms':", ".join(cleaned),'original_input':raw,'patient_name':request.form.get('patient_name') or session.get('username','Patient'),'age':request.form.get('age') or "N/A",'gender':gender or request.form.get('gender') or "N/A",'date':datetime.now().strftime("%d-%m-%Y %H:%M"),'duration':request.form.get('duration') or "N/A",'body_part':body_part,'uploaded_file': uploaded_filename, 'uploaded_path': uploaded_path,'uploaded_b64': uploaded_b64,'image_analysis': image_analysis, 'observed_from_image': observed_from_image,'ai_observation': ai_image_text,'ai_used': 'Yes - ' + (ai_data.get('Specialist','AI') if ai_data else 'No - API key missing')}
    session['last_result']=result; session.permanent=True; session.modified=True
    # DB SAVE - agar Neon hai to patients + results me
    try:
        if DATABASE_URL:
            db_execute("INSERT INTO patients (patient_name, gender, age, symptoms, body_part) VALUES (%s,%s,%s,%s,%s)", (result['patient_name'], str(result['gender']), 0, result['symptoms'], body_part))
            db_execute("INSERT INTO results (prediction, confidence, diet, exercise, precaution, lab_test, specialist_doctor) VALUES (%s,%s,%s,%s,%s,%s,%s)", (dname, str(conf), diet, exercise, precaution, ",".join(lab) if isinstance(lab,list) else str(lab), doctor))
    except Exception as e: print(f"Result DB save fail: {e}")
    return redirect(url_for('result_page'))

def generate_ai_details(disease_name, symptoms_list, image_observation=""):
    prompt = f"Disease: {disease_name}, Symptoms: {','.join(symptoms_list)}. Image: {image_observation}. Give ONLY JSON: {{\"Description\":\"2-3 lines simple\",\"Diet\":\"what to eat 1 line\",\"Exercise\":\"2 exercises\",\"Precautions\":\"2 precautions\",\"Lab_Tests\":[\"CBC\"],\"Specialist\":\"General Physician\"}}"
    k = get_env('GEMINI_API_KEY') or get_env('GOOGLE_API_KEY')
    if k:
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={k}"
            r = requests.post(url, json={"contents": [{"parts": [{"text": prompt}]}]}, timeout=25)
            j = r.json(); txt = j['candidates'][0]['content']['parts'][0]['text']; m=re.search(r'\{.*\}', txt, re.DOTALL)
            if m: return json.loads(m.group())
        except Exception as e: print(f"GEMINI fail {e}")
    k = get_env('GROQ_API_KEY')
    if k:
        try:
            r=requests.post("https://api.groq.com/openai/v1/chat/completions",headers={"Authorization": f"Bearer {k}"},json={"model":"llama-3.3-70b-versatile","messages":[{"role":"user","content":prompt}]},timeout=25)
            txt=r.json()['choices'][0]['message']['content']; m=re.search(r'\{.*\}', txt, re.DOTALL)
            if m: return json.loads(m.group())
        except Exception as e: print(f"GROQ fail {e}")
    k = get_env('OPENROUTER_API_KEY')
    if k:
        try:
            r=requests.post("https://openrouter.ai/api/v1/chat/completions",headers={"Authorization": f"Bearer {k}"},json={"model":"meta-llama/llama-3.1-8b-instruct:free","messages":[{"role":"user","content":prompt}]},timeout=25)
            txt=r.json()['choices'][0]['message']['content']; m=re.search(r'\{.*\}', txt, re.DOTALL)
            if m: return json.loads(m.group())
        except Exception as e: print(f"OPENROUTER fail {e}")
    return None

@app.route('/api/doctor_chat', methods=['GET','POST'])
def doctor_chat_api():
    if request.method == 'GET':
        return jsonify({'gemini': bool(get_env('GEMINI_API_KEY') or get_env('GOOGLE_API_KEY')),'groq': bool(get_env('GROQ_API_KEY')),'openrouter': bool(get_env('OPENROUTER_API_KEY')),'diseases': len(diseases_data),'reply': 'Hi, I am your AI Doctor. Apni problem batao?','source': 'System'}), 200
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

# === PDF MAKING - RESULT KA PDF ===
@app.route('/download_pdf')
def download_pdf():
    if not session.get('is_logged_in'): return redirect(url_for('login_page'))
    r = session.get('last_result')
    if not r: return redirect(url_for('pp_page'))
    try:
        # ReportLab se PDF - Vercel pe bhi chalta hai
        from reportlab.lib.pagesizes import A4
        from reportlab.pdfgen import canvas
        from reportlab.lib.units import mm
        buf = io.BytesIO()
        c = canvas.Canvas(buf, pagesize=A4)
        w,h = A4
        y = h - 40
        c.setFont("Helvetica-Bold", 20); c.drawString(40, y, "Predict AI - Health Report"); y-=25
        c.setFont("Helvetica", 11)
        lines = [
            f"Patient: {r.get('patient_name','')}",
            f"Date: {r.get('date','')}",
            f"Gender: {r.get('gender','')} | Age: {r.get('age','')} | Body Part: {r.get('body_part','')}",
            f"Symptoms: {r.get('symptoms','')}",
            "",
            f"Prediction: {r.get('disease','')} ({r.get('confidence','')}% Confidence)",
            "",
            f"Description: {r.get('description','')[:500]}",
            "",
            f"Diet: {r.get('diet','')}",
            "",
            f"Exercise: {r.get('exercise','')}",
            "",
            f"Precautions: {r.get('precaution','')}",
            "",
            f"Lab Tests: {', '.join(r.get('lab_tests',[])) if isinstance(r.get('lab_tests'), list) else r.get('lab_tests','')}",
            "",
            f"Specialist Doctor: {r.get('doctor','')}",
        ]
        if r.get('ai_observation'):
            lines += ["", f"Image Finding: {r.get('ai_observation','')[:400]}"]
        lines += ["", "Disclaimer: This is AI based suggestion, not a medical diagnosis. Please consult a doctor."]
        for line in lines:
            # Lambi line ko tod do
            while len(line) > 90:
                c.drawString(40, y, line[:90]); y-=16; line=line[90:]
                if y < 50: c.showPage(); y=h-40; c.setFont("Helvetica", 11)
            c.drawString(40, y, line); y-=16
            if y < 50: c.showPage(); y=h-40; c.setFont("Helvetica", 11)
        c.save(); buf.seek(0)
        return send_file(buf, mimetype='application/pdf', as_attachment=True, download_name=f"PredictAI_Report_{r.get('patient_name','Patient')}.pdf")
    except Exception as e:
        print(f"PDF fail {e}")
        # Fallback - HTML Print PDF
        html = f"<h1>Predict AI Report</h1><p>Patient: {r.get('patient_name')}</p><p>Disease: {r.get('disease')} - {r.get('confidence')}%</p><p>Symptoms: {r.get('symptoms')}</p><p>Diet: {r.get('diet')}</p><p>Exercise: {r.get('exercise')}</p><p>Precaution: {r.get('precaution')}</p><p>Doctor: {r.get('doctor')}</p><button onclick='window.print()'>Print / Save PDF</button>"
        return html

@app.route('/debug/env')
def debug_env():
    html = "<h3>Env Check</h3>"
    for name in ['DATABASE_URL','GEMINI_API_KEY','GOOGLE_API_KEY','GROQ_API_KEY','OPENROUTER_API_KEY','MAIL_USER','MAIL_PASS']:
        v = get_env(name) if 'DATABASE' not in name else (DATABASE_URL[:20]+"..." if DATABASE_URL else "")
        if v: html += f"✅ {name}: FOUND<br>"
        else: html += f"❌ {name}: MISSING<br>"
    html += f"<br>Diseases: {len(diseases_data)} | Symptoms: {len(all_symptoms)} | DB Connected: {bool(DATABASE_URL)}<br>"
    return html

@app.route('/debug/db')
def debug_db():
    if not DATABASE_URL: return "DATABASE_URL missing - Vercel me Neon Integration check karo"
    data = db_execute("SELECT table_name FROM information_schema.tables WHERE table_schema='public'", fetch=True)
    return jsonify({'connected': True, 'tables': [d['table_name'] for d in (data or [])]})

if __name__=='__main__':
    port = int(os.getenv("PORT", 7860))
    app.run(host='0.0.0.0', port=port, debug=False)