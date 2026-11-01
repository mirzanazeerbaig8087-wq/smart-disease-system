from flask import Flask, render_template, request, jsonify, session, redirect, url_for, send_from_directory, Response
import json, pickle, gzip, os, re, difflib, random, smtplib, requests
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta
import mysql.connector
from mysql.connector import Error

EMAIL_USER = os.getenv("MAIL_USER") or os.getenv("EMAIL_USER")
EMAIL_PASS = os.getenv("MAIL_PASS") or os.getenv("EMAIL_PASS")
otp_store = {}

app = Flask(__name__)
app.secret_key = 'smart_disease_2026_secret_key_123_final_700'

app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=30)
app.config['SESSION_PERMANENT'] = True
is_prod = os.getenv('VERCEL') or os.getenv('VERCEL_ENV')
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['SESSION_COOKIE_SECURE'] = True if is_prod else False
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_NAME'] = 'smart_session'

@app.before_request
def make_session_permanent():
    session.permanent = True
    session.modified = True

# Static routes
@app.route('/manifest.json')
def manifest(): return send_from_directory('static', 'manifest.json')
@app.route('/sw.js')
def sw(): return send_from_directory('static', 'sw.js')
@app.route('/icon-192.png')
def icon192(): return send_from_directory('static', 'icon-192.png')
@app.route('/icon-512.png')
def icon512(): return send_from_directory('static', 'icon-512.png')
@app.route('/google601d496139b65d67.html')
def google_verify_file(): return send_from_directory('.', 'google601d496139b65d67.html')
@app.route('/sitemap.xml')
def sitemap():
    xml = '''<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"><url><loc>https://smart-disease-system.vercel.app/</loc></url></urlset>'''
    return Response(xml, mimetype='application/xml')

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CA_PATH = os.path.join(BASE_DIR, "ca.pem")
DB_CONFIG = {
    'host': os.getenv('DB_HOST', 'mysql-3208d2d3-mirzanazeerbaig8087-2b5f.i.aivencloud.com'),
    'port': int(os.getenv('DB_PORT', 12408)),
    'user': os.getenv('DB_USER', 'avnadmin'),
    'password': os.getenv('DB_PASS'),
    'database': os.getenv('DB_NAME', 'defaultdb'),
    'autocommit': True, 'connection_timeout': 10
}

def get_db_connection():
    try:
        if os.path.exists(CA_PATH) and os.path.getsize(CA_PATH) > 10:
            return mysql.connector.connect(**DB_CONFIG, ssl_ca=CA_PATH)
        else:
            return mysql.connector.connect(**DB_CONFIG)
    except Error as e:
        print(f"DB Error {e}")
        return None

def build_translator():
    base = {
        "fever": ["bukhar","bukhhar","bhukhar","tezz bukhar","tez bukhar","halka bukhar","bukhar thand","bukhar khansi","thand ke sath bukhar","kapkapahat","thand lagna","fever","high fever","low fever","bukhar hai","tez bukhar hai"],
        "headache": ["sir dard","sar dard","sir me dard","adha sir dard","sir bhari","sir me bhari pan","headache","migraine","sir dard hai","sar dard hai"],
        "cough": ["khansi","khasi","sukhi khansi","gili khansi","bali wali khansi","khansi me khoon","cough","dry cough","wet cough","cough with blood","khansi hai"],
        "cold": ["sardi","zukam","jukaam","naak behna","naak band","cheek","cold","common cold","runny nose","stuffy nose","sneezing","sardi hai"],
        "sore throat": ["gala kharab","gale me dard","gala dard","gala kharash","sore throat","gala kharab hai"],
        "fatigue": ["thakan","thakawat","kamzori","susti","bahut thakan","fatigue","weakness","thakan hai","kamzori hai"],
        "abdominal pain": ["pet dard","pet me dard","pet kharab","pet me jalan","pet me marod","pet derd","abdominal pain","stomach pain","bloating","gas","heartburn","pet dard hai"],
        "vomiting": ["ulti","ultiyan","matli","jeee ghabrana","ulti dast","vomiting","nausea","vomiting blood","ulti hai"],
        "diarrhea": ["dast","patla dast","loose motion","diarrhea","dast hai","patle dast"],
        "chest pain": ["seene me dard","seena dard","chati me dard","seene me jalan","chest pain","chest tightness","seene me dard hai"],
        "dizziness": ["chakkar","chakkar aana","sir ghumna","chakkar bukhar","dizziness","chakkar hai"],
        "joint pain": ["jodo me dard","ghutno me dard","gathiya","joint dard","knee pain","joint pain","ghutne me dard"],
        "back pain": ["kamar dard","kamar me dard","peeth dard","back pain","neck pain","shoulder pain","kamar dard hai"],
        "muscle pain": ["maans peshi dard","badan dard","body pain","bodypain","muscle pain","body pain hai","badan dard hai"],
        "shortness of breath": ["saans phoolna","saans lene me dikkat","dum ghutna","shortness of breath","wheezing","saans phool rahi"],
        "weight loss": ["wazan kam","wazan ki kami","patla hona","vajan kam","weight loss","wazan kam ho raha"],
        "loss of appetite": ["bhukh kam","bhukh nahi","bhukh ki kami","loss of appetite","bhukh nahi lag rahi"],
        "itching": ["khujli","kharish","khujali","bahut khujli","itching","khujli hai"],
        "rash": ["daane","laal daane","chehre pe daane","sharir pe daane","rash","skin rash","daane hai"],
        "swelling": ["soojan","sujan","pair me soojan","chehre pe soojan","swelling","ankle swelling","face swelling","soojan hai"],
    }
    trans = {}
    prefixes = ["", "mujhe ", "mujhko ", "mere ko ", "muje "]
    suffixes = ["", " hai", " ho raha hai", " ho rahi hai"]
    for eng, hindi_list in base.items():
        for h in hindi_list:
            h = h.lower().strip()
            for pre in prefixes:
                for suf in suffixes:
                    key = f"{pre}{h}{suf}".strip()
                    key = re.sub(r'\s+', ' ', key)
                    if len(key) > 1: trans[key] = eng
    return trans

TRANSLATION_MAP = build_translator()

def normalize(text, all_sym):
    t = text.lower().strip()
    t = re.sub(r'[^a-z0-9 ]', ' ', t)
    t = re.sub(r'\s+', ' ', t).strip()
    if t in TRANSLATION_MAP: return TRANSLATION_MAP[t]
    for hi,en in TRANSLATION_MAP.items():
        if hi in t or t in hi: return en
    if all_sym:
        m = difflib.get_close_matches(t, all_sym, n=1, cutoff=0.55)
        if m: return m[0]
    return t

def parse_symptoms(raw, all_sym):
    parts = re.split(r'[,;|\n]+', raw.lower())
    cleaned=[]
    for p in parts:
        if not p.strip(): continue
        for s in re.split(r'\s+and\s+|\s+aur\s+|\s*&\s*', p):
            s=s.strip()
            if len(s)>2: cleaned.append(normalize(s, all_sym))
    return list(dict.fromkeys(cleaned))

# ===== LOAD DISEASES - FIXED =====
diseases_data={}; all_symptoms=[]
try:
    if os.path.exists('model.pkl.gz'):
        with gzip.open('model.pkl.gz','rb') as f:
            d=pickle.load(f)
            if isinstance(d, dict):
                diseases_data = d.get('diseases_data') or d.get('data') or d
                if 'all_symptoms' in d: all_symptoms = d['all_symptoms']
    if not diseases_data and os.path.exists('diseases.json'):
        with open('diseases.json','r',encoding='utf-8') as f:
            diseases_data=json.load(f)
    if not all_symptoms and os.path.exists('symptoms.pkl'):
        with open('symptoms.pkl','rb') as f: all_symptoms=pickle.load(f)
    # If still empty, build from diseases_data keys
    if not all_symptoms and diseases_data:
        temp = set()
        for v in diseases_data.values():
            if isinstance(v, dict):
                s = v.get('Symptoms') or v.get('symptoms') or ""
                for part in re.split(r'[,;]', str(s)):
                    if part.strip(): temp.add(part.strip().lower())
        all_symptoms = sorted(list(temp))
    print(f"Loaded {len(diseases_data)} diseases, {len(all_symptoms)} symptoms")
except Exception as e: 
    print(f"Load error {e}")

# ===== HELPER: GET FIELD WITH ANY KEY CASE =====
def get_field(info, keys, default=""):
    if not isinstance(info, dict): return default
    for k in keys:
        if k in info and info[k]: return info[k]
        # lower case check
        for ik in info.keys():
            if ik.lower() == k.lower() and info[ik]:
                return info[ik]
    return default

def generate_ai_details(disease_name, symptoms_list):
    """Agar diseases.json me diet etc nahi hai to AI se banao - NO DATASET NEEDED"""
    GEMINI_KEY = os.getenv('GEMINI_API_KEY') or os.getenv('GOOGLE_API_KEY')
    GROQ_KEY = os.getenv('GROQ_API_KEY')
    prompt = f"Disease: {disease_name}, Symptoms: {','.join(symptoms_list)}. Give JSON only: {{\"Description\":\"2 lines\",\"Diet\":\"what to eat\",\"Exercise\":\"2 exercises\",\"Precautions\":\"2 precautions\",\"Lab_Tests\":[\"CBC\",\"X-Ray\"],\"Specialist\":\"doctor type\"}}"
    
    # Try Groq
    if GROQ_KEY:
        try:
            r = requests.post("https://api.groq.com/openai/v1/chat/completions",
                headers={"Authorization": f"Bearer {GROQ_KEY}","Content-Type":"application/json"},
                json={"model":"llama-3.1-8b-instant","messages":[{"role":"user","content":prompt}],"temperature":0.5,"max_tokens":500}, timeout=15)
            txt = r.json()['choices'][0]['message']['content']
            # extract json
            m = re.search(r'\{.*\}', txt, re.DOTALL)
            if m: return json.loads(m.group())
        except: pass
    # Try Gemini
    if GEMINI_KEY:
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_KEY}"
            r = requests.post(url, json={"contents":[{"parts":[{"text":prompt}]}],"generationConfig":{"temperature":0.5,"maxOutputTokens":500}}, timeout=15)
            txt = r.json()['candidates'][0]['content']['parts'][0]['text']
            m = re.search(r'\{.*\}', txt, re.DOTALL)
            if m: return json.loads(m.group())
        except: pass
    return None

# ===== ROUTES =====
@app.route('/')
def home(): return redirect(url_for('cover_page'))
@app.route('/cover')
def cover_page(): return render_template('cover.html')
@app.route('/login')
def login_page():
    if session.get('is_logged_in'): return redirect(url_for('pp_page'))
    return render_template('login.html')
@app.route('/welcome')
def welcome_page():
    if not session.get('is_logged_in'): return redirect(url_for('login_page'))
    if session.get('welcome_shown'): return redirect(url_for('pp_page'))
    return render_template('welcome.html')
@app.route('/pp')
def pp_page():
    if not session.get('is_logged_in'): return redirect(url_for('login_page'))
    if not session.get('welcome_shown'): return redirect(url_for('welcome_page'))
    return render_template('pp.html', symptoms=all_symptoms)
@app.route('/resultp')
def result_page(): 
    if not session.get('is_logged_in'): return redirect(url_for('login_page'))
    r = session.get('last_result')
    if not r: return redirect(url_for('pp_page'))
    return render_template('resultp.html', result=r)
@app.route('/thankyou')
def thankyou_page(): 
    if not session.get('is_logged_in'): return redirect(url_for('login_page'))
    return render_template('thankyou.html')
@app.route('/logout')
def logout(): 
    session.clear()
    return redirect(url_for('cover_page'))
@app.route('/mark_welcome_done')
def mark_welcome_done():
    session['welcome_shown'] = True
    session.modified = True
    return redirect(url_for('pp_page'))
@app.route('/patient')
def patient_page(): return redirect(url_for('pp_page'))
@app.route('/lp')
def lp_page(): return render_template('lp.html') if os.path.exists('templates/lp.html') else redirect(url_for('pp_page'))
@app.route('/emergency')
def emergency_page():
    if not session.get('is_logged_in'): return redirect(url_for('login_page'))
    return render_template('emergency.html') if os.path.exists('templates/emergency.html') else render_template('pp.html', symptoms=all_symptoms)

# ... other pages same ...

def send_otp_email(to_email, otp):
    try:
        email_user = os.getenv('EMAIL_USER') or os.getenv('MAIL_USER')
        email_pass = os.getenv('EMAIL_PASS') or os.getenv('MAIL_PASS')
        if not email_user or not email_pass: return False
        body = f"Your Smart Disease System OTP is: {otp}\nValid for 5 minutes."
        msg = MIMEMultipart()
        msg['From'] = email_user
        msg['To'] = to_email
        msg['Subject'] = "Your OTP Code"
        msg.attach(MIMEText(body, 'plain'))
        server = smtplib.SMTP('smtp.gmail.com', 587, timeout=15)
        server.starttls()
        server.login(email_user, email_pass)
        server.send_message(msg)
        server.quit()
        return True
    except Exception as e:
        print(f"Email send failed: {e}")
        return False

@app.route('/api/send_otp', methods=['POST'])
@app.route('/api/send_email_otp', methods=['POST'])
def api_send_otp():
    data = request.get_json() or {}
    email = data.get('email','').strip().lower()
    phone = data.get('phone','').strip()
    identifier = email or phone
    if not identifier:
        return jsonify({'status':'error','message':'Email or Phone required'}), 400
    otp = str(random.randint(100000,999999))
    otp_store[identifier] = {'otp': otp, 'time': datetime.now()}
    if email: otp_store[email] = {'otp': otp, 'time': datetime.now()}
    if phone: otp_store[phone] = {'otp': otp, 'time': datetime.now()}
    print(f"Generated OTP {otp} for {identifier}")
    if email:
        email_ok = send_otp_email(email, otp)
        if not email_ok:
            return jsonify({'status': 'failed','message': 'wrong password, this email does not exist.'}), 200
    return jsonify({'status':'sent','message':'OTP sent successfully','otp_autofill': otp})

@app.route('/api/verify_login', methods=['POST'])
def api_verify_login():
    data=request.get_json() or {}
    email = data.get('email','').strip().lower()
    phone = data.get('phone','').strip()
    user_otp = str(data.get('otp','')).strip()
    identifier = email or phone
    target = otp_store.get(identifier) or otp_store.get(email) or otp_store.get(phone)
    if not target: return jsonify({'status':'error','message':'OTP not found, resend'}), 400
    if datetime.now() - target['time'] > timedelta(minutes=5): return jsonify({'status':'error','message':'OTP expired'}), 400
    if target['otp'] != user_otp: return jsonify({'status':'error','message':'Invalid OTP'}), 400
    session.permanent = True
    session['is_logged_in']=True
    session['username']=data.get('username','User')
    session['user_email']=email
    session['welcome_shown']=False
    session.modified = True
    otp_store.pop(identifier, None)
    return jsonify({'status':'success'})

# ===== PREDICT - FIXED TO SHOW ALL FIELDS =====
@app.route('/predict', methods=['POST'])
def predict_route():
    raw = request.form.get('symptoms') or ""
    if not raw.strip(): return redirect(url_for('pp_page'))
    cleaned = parse_symptoms(str(raw), all_symptoms)
    
    scores = []
    for dname, info in diseases_data.items():
        if not isinstance(info, dict): continue
        full_text = str(get_field(info, ['Symptoms','symptoms','symptom'], "")).lower()
        if not full_text: continue
        km = sum(1 for c in cleaned if c.lower() in full_text)
        if km > 0: scores.append((dname, km, info))
    
    scores.sort(key=lambda x: x[1], reverse=True)
    
    if scores:
        dname, matched_count, dinfo = scores[0][0], scores[0][1], scores[0][2]
        conf = min(96, max(55, (matched_count / len(cleaned) * 85 + 10) if cleaned else 40))
    else:
        dname="General Checkup"
        dinfo={}
        conf=45

    # ===== GET ALL FIELDS WITH ANY KEY NAME - THIS WAS BUG =====
    desc = get_field(dinfo, ['Description','description','desc','about','info'])
    diet = get_field(dinfo, ['Diet','diet','food','diet_plan'])
    exercise = get_field(dinfo, ['Exercise','exercise','workout','yoga'])
    precaution = get_field(dinfo, ['Precautions','precaution','precautions','care','prevention'])
    lab = get_field(dinfo, ['Lab_Tests','lab_tests','lab','tests','lab_test'])
    doctor = get_field(dinfo, ['Specialist','specialist','doctor','Doctor','consult'])

    # If blank, try AI to fill - NO DATASET NEEDED
    ai_data = None
    if not desc or not diet:
        ai_data = generate_ai_details(dname, cleaned)

    if ai_data:
        desc = desc or ai_data.get('Description','')
        diet = diet or ai_data.get('Diet','')
        exercise = exercise or ai_data.get('Exercise','')
        precaution = precaution or ai_data.get('Precautions','')
        if not lab or lab == "": lab = ai_data.get('Lab_Tests', [])
        doctor = doctor or ai_data.get('Specialist','')

    # Final fallback if still blank
    if not desc: desc = f"{dname} is a condition related to {', '.join(cleaned[:3])}. Please consult doctor for proper diagnosis."
    if not diet: diet = "Light, balanced diet, avoid oily/spicy food, drink more water"
    if not exercise: exercise = "Daily 30 min walk, breathing exercises, adequate rest"
    if not precaution: precaution = "Take rest, stay hydrated, avoid self-medication, consult doctor if symptoms persist >3 days"
    if not lab: lab = ["CBC", "General Checkup"]
    if isinstance(lab, str): lab = [s.strip() for s in re.split(r',|;', lab) if s.strip()]
    if not doctor: doctor = "General Physician"

    result = {
        'disease': dname,
        'confidence': round(float(conf), 2),
        'description': desc,
        'diet': diet,
        'exercise': exercise,
        'precaution': precaution,
        'lab_tests': lab,
        'doctor': doctor,
        'symptoms': ", ".join(cleaned),
        'original_input': raw,
        'patient_name': request.form.get('patient_name') or session.get('username','Patient'),
        'age': request.form.get('age') or "N/A",
        'gender': request.form.get('gender') or "N/A",
        'date': datetime.now().strftime("%d-%m-%Y %H:%M"),
        'duration': request.form.get('duration') or "N/A"
    }
    
    session['last_result'] = result
    session.modified = True
    session.permanent = True
    return redirect(url_for('result_page'))

# Doctor AI API
@app.route('/api/doctor_chat', methods=['GET', 'POST'])
def doctor_chat_api():
    if request.method == 'GET':
        return jsonify({'gemini': bool(os.getenv('GEMINI_API_KEY') or os.getenv('GOOGLE_API_KEY')), 'groq': bool(os.getenv('GROQ_API_KEY')), 'diseases': len(diseases_data), 'status': 'ok'})
    try:
        data = request.get_json(force=True) or {}
        msg = (data.get('message') or '').strip()
        if not msg:
            return jsonify({'reply': 'Hi, I am your AI Doctor. Aap apni health problem batao.', 'source': 'System'}), 200
        GEMINI_KEY = os.getenv('GEMINI_API_KEY') or os.getenv('GOOGLE_API_KEY')
        GROQ_KEY = os.getenv('GROQ_API_KEY')
        lang_rule = "Reply in same language as user."
        
        if GEMINI_KEY:
            for model in ["gemini-1.5-flash", "gemini-1.5-flash-latest"]:
                try:
                    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={GEMINI_KEY}"
                    prompt = f"{lang_rule} You are Predict AI, friendly Indian doctor. You know 410 diseases. User: {msg}. Give helpful advice 4-5 lines."
                    r = requests.post(url, json={"contents":[{"parts":[{"text": prompt}]}], "generationConfig":{"temperature":0.7, "maxOutputTokens": 600}}, timeout=25)
                    j = r.json()
                    if 'candidates' in j:
                        text = j['candidates'][0]['content']['parts'][0]['text']
                        return jsonify({'reply': text, 'source': 'Gemini'}), 200
                except: continue
        if GROQ_KEY:
            try:
                r = requests.post("https://api.groq.com/openai/v1/chat/completions",
                    headers={"Authorization": f"Bearer {GROQ_KEY}", "Content-Type": "application/json"},
                    json={"model":"llama-3.1-8b-instant","messages":[{"role":"system","content":f"You are Predict AI, helpful Indian doctor. {lang_rule}"},{"role":"user","content":msg}],"temperature":0.7,"max_tokens":800}, timeout=20)
                j = r.json()
                if 'choices' in j:
                    return jsonify({'reply': j['choices'][0]['message']['content'], 'source': 'Groq'}), 200
            except: pass
        return jsonify({'reply': f"Samajh gaya: '{msg}'. Thoda detail me batao, main help karunga.", 'source': 'Fallback'}), 200
    except Exception as e:
        return jsonify({'reply': "Hi, I am your AI Doctor. Please share your problem again.", 'source': 'Fallback'}), 200

if __name__=='__main__': 
    app.run(host='0.0.0.0',port=5000,debug=True)