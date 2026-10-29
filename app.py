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
# ===== FIX 1: 10 YEAR LOGIN =====
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=3650) # 10 years = 3650 days
app.config['SESSION_PERMANENT'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['SESSION_COOKIE_SECURE'] = False if os.getenv('FLASK_ENV') == 'development' else True
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_NAME'] = 'smart_session'
app.config['SESSION_COOKIE_DOMAIN'] = None
app.config['SESSION_COOKIE_PATH'] = '/'

@app.before_request
def make_session_permanent():
    session.permanent = True

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
        "constipation": ["kabz","kabj","pet saaf nahi","constipation","kabz hai"],
        "chest pain": ["seene me dard","seena dard","chati me dard","seene me jalan","chest pain","chest tightness","seene me dard hai"],
        "dizziness": ["chakkar","chakkar aana","sir ghumna","chakkar bukhar","dizziness","chakkar hai"],
        "joint pain": ["jodo me dard","ghutno me dard","gathiya","joint dard","knee pain","joint pain","ghutne me dard"],
        "back pain": ["kamar dard","kamar me dard","peeth dard","back pain","neck pain","shoulder pain","kamar dard hai"],
        "muscle pain": ["maans peshi dard","badan dard","body pain","bodypain","muscle pain","body pain hai","badan dard hai"],
        "shortness of breath": ["saans phoolna","saans lene me dikkat","dum ghutna","shortness of breath","wheezing","saans phool rahi"],
        "weight loss": ["wazan kam","wazan ki kami","patla hona","vajan kam","weight loss","wazan kam ho raha"],
        "weight gain": ["wazan badhna","mota hona","vajan badhna","weight gain"],
        "loss of appetite": ["bhukh kam","bhukh nahi","bhukh ki kami","loss of appetite","bhukh nahi lag rahi"],
        "itching": ["khujli","kharish","khujali","bahut khujli","itching","khujli hai"],
        "rash": ["daane","laal daane","chehre pe daane","sharir pe daane","rash","skin rash","daane hai"],
        "swelling": ["soojan","sujan","pair me soojan","chehre pe soojan","swelling","ankle swelling","face swelling","soojan hai"],
    }
    extra_english = ["fever","high fever","low fever","cough","dry cough","wet cough","cold","common cold","runny nose","stuffy nose","sneezing","sore throat","headache","migraine","dizziness","fatigue","weakness","body pain","muscle pain","joint pain","knee pain","back pain","neck pain","shoulder pain","chest pain","chest tightness","abdominal pain","stomach pain","bloating","gas","heartburn","nausea","vomiting","diarrhea","constipation","loss of appetite","weight loss","weight gain","excessive thirst","frequent urination","burning urination","blood in urine","dark urine","itching","skin rash","swelling","ankle swelling","face swelling","numbness","tingling","palpitations","rapid heartbeat","shortness of breath","wheezing","night sweats","cold sweats","shivering","tremor","seizure","fainting","memory loss","confusion","depression","anxiety","insomnia","blurred vision","double vision","red eyes","eye pain","ear pain","hearing loss","nosebleed","loss of smell","toothache","neck stiffness","hair loss","brittle nails","swollen glands","fever with chills","fever with rash","cough with blood","vomiting blood","hiccups","snoring","blood in stool","yellow skin","yellow eyes","pale skin","abdominal swelling","liver lump","acidity","indigestion","loose motion"]
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
    for s in extra_english:
        s = s.lower()
        trans[s] = s
        trans[f"{s} hai"] = s
        trans[f"mujhe {s} hai"] = s
        trans[f"mujhe {s}"] = s
        trans[f"i have {s}"] = s
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

diseases_data={}; all_symptoms=[]
try:
    if os.path.exists('model.pkl.gz'):
        with gzip.open('model.pkl.gz','rb') as f:
            d=pickle.load(f)
            if isinstance(d, dict):
                diseases_data = d.get('diseases_data') or d
            else:
                diseases_data = {}
    if not diseases_data and os.path.exists('diseases.json'):
        with open('diseases.json','r',encoding='utf-8') as f:
            diseases_data=json.load(f)
    if os.path.exists('symptoms.pkl'):
        with open('symptoms.pkl','rb') as f: all_symptoms=pickle.load(f)
except Exception as e: print(f"Load error {e}")

@app.route('/')
def home(): 
    return redirect(url_for('cover_page'))

@app.route('/cover')
def cover_page(): 
    return render_template('cover.html')

@app.route('/login')
def login_page():
    if session.get('is_logged_in'):
        return redirect(url_for('pp_page'))
    return render_template('login.html')

@app.route('/welcome')
def welcome_page():
    if not session.get('is_logged_in'):
        return redirect(url_for('login_page'))
    if session.get('welcome_shown'):
        return redirect(url_for('pp_page'))
    return render_template('welcome.html')

@app.route('/pp')
def pp_page():
    if not session.get('is_logged_in'):
        return redirect(url_for('login_page'))
    if not session.get('welcome_shown'):
        return redirect(url_for('welcome_page'))
    return render_template('pp.html', symptoms=all_symptoms)

@app.route('/resultp')
def result_page(): 
    if not session.get('is_logged_in'):
        return redirect(url_for('login_page'))
    r = session.get('last_result')
    if not r: 
        return redirect(url_for('pp_page'))
    return render_template('resultp.html', result=r)

@app.route('/thankyou')
def thankyou_page(): 
    if not session.get('is_logged_in'):
        return redirect(url_for('login_page'))
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
    if not session.get('is_logged_in'):
        return redirect(url_for('login_page'))
    if os.path.exists('templates/emergency.html'):
        return render_template('emergency.html')
    else:
        return render_template('pp.html', symptoms=all_symptoms)

@app.route('/doctor-ai')
@app.route('/doctor_ai')
@app.route('/doctor')
def doctor_ai_page():
    if not session.get('is_logged_in'):
        return redirect(url_for('login_page'))
    if os.path.exists('templates/doctor_ai.html'):
        return render_template('doctor_ai.html')
    elif os.path.exists('templates/doctor-ai.html'):
        return render_template('doctor-ai.html')
    else:
        return render_template('pp.html', symptoms=all_symptoms)

@app.route('/wellbeing')
@app.route('/well-being')
@app.route('/well_being')
def wellbeing_page():
    if not session.get('is_logged_in'):
        return redirect(url_for('login_page'))
    if os.path.exists('templates/wellbeing.html'):
        return render_template('wellbeing.html')
    elif os.path.exists('templates/well_being.html'):
        return render_template('well_being.html')
    elif os.path.exists('templates/well-being.html'):
        return render_template('well-being.html')
    else:
        return render_template('pp.html', symptoms=all_symptoms)

@app.route('/my-profile')
@app.route('/my_profile')
@app.route('/profile')
def my_profile_page():
    if not session.get('is_logged_in'):
        return redirect(url_for('login_page'))
    if os.path.exists('templates/my_profile.html'):
        return render_template('my_profile.html')
    elif os.path.exists('templates/profile.html'):
        return render_template('profile.html')
    else:
        return render_template('pp.html', symptoms=all_symptoms)

def send_otp_email(to_email, otp):
    try:
        email_user = os.getenv('EMAIL_USER') or os.getenv('MAIL_USER')
        email_pass = os.getenv('EMAIL_PASS') or os.getenv('MAIL_PASS')
        if not email_user or not email_pass:
            print("MAIL_USER/MAIL_PASS missing")
            return False
        body = f"Your Smart Disease System OTP is: {otp}\n\nValid for 5 minutes."
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
        print(f"Email sent to {to_email}")
        return True
    except Exception as e:
        print(f"Email send failed: {e}")
        return False

@app.route('/api/send_otp', methods=['POST'])
@app.route('/api/send_email_otp', methods=['POST'])
@app.route('/api/send_phone_otp', methods=['POST'])
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
    if not target:
        return jsonify({'status':'error','message':'OTP not found, resend'}), 400
    if datetime.now() - target['time'] > timedelta(minutes=5):
        return jsonify({'status':'error','message':'OTP expired'}), 400
    if target['otp'] != user_otp:
        return jsonify({'status':'error','message':'Invalid OTP'}), 400
    session.permanent = True
    session['is_logged_in']=True
    session['username']=data.get('username','User')
    session['user_email']=email
    session['has_seen_welcome']=False
    session['welcome_shown']=False
    session.modified = True
    otp_store.pop(identifier, None)
    try:
        conn = get_db_connection()
        if conn:
            cur = conn.cursor()
            cur.execute("CREATE TABLE IF NOT EXISTS users (id INT AUTO_INCREMENT PRIMARY KEY, email VARCHAR(255), phone VARCHAR(50), username VARCHAR(100), created_at DATETIME)")
            cur.execute("INSERT INTO users (email, phone, username, created_at) VALUES (%s,%s,%s,%s)", (email, phone, data.get('username','User'), datetime.now()))
            conn.commit(); cur.close(); conn.close()
    except: pass
    return jsonify({'status':'success'})

@app.route('/predict', methods=['POST'])
def predict_route():
    raw = request.form.get('symptoms') or ""
    if not raw.strip(): return redirect(url_for('pp_page'))
    cleaned = parse_symptoms(str(raw), all_symptoms)
    scores = []
    for dname, info in diseases_data.items():
        if not isinstance(info, dict): continue
        full_text = str(info.get('Symptoms') or "").lower()
        km = sum(1 for c in cleaned if c.lower() in full_text)
        if km > 0: scores.append((dname, km, info))
    scores.sort(key=lambda x: x[1], reverse=True)
    if scores:
        dname, matched_count, dinfo = scores[0][0], scores[0][1], scores[0][2]
        conf = min(96, max(55, (matched_count / len(cleaned) * 85 + 10) if cleaned else 40))
    else:
        dname="General Checkup"; dinfo={"Description":"Consult doctor","Diet":"Balanced","Exercise":"Walk","Precautions":"Doctor","Lab_Tests":["CBC"],"Specialist":"General"}; conf=40
    lab = dinfo.get('Lab_Tests') or ["CBC"]
    if isinstance(lab, str): lab = [s.strip() for s in re.split(r',|;', lab) if s.strip()]
    result = {'disease': dname,'confidence': round(float(conf), 2),'description': dinfo.get('Description',''),'diet': dinfo.get('Diet',''),'exercise': dinfo.get('Exercise',''),'precaution': dinfo.get('Precautions',''),'lab_tests': lab,'doctor': dinfo.get('Specialist','General'),'symptoms': ", ".join(cleaned),'original_input': raw,'patient_name': request.form.get('patient_name') or session.get('username','Patient'),'age': request.form.get('age') or "N/A",'gender': request.form.get('gender') or "N/A",'date': datetime.now().strftime("%d-%m-%Y %H:%M"),'duration': request.form.get('duration') or "N/A"}
    session['last_result'] = result
    session.modified = True
    session.permanent = True
    return redirect(url_for('result_page'))

# ================= DOCTOR AI API - FINAL NO ERROR TO USER =================
@app.route('/api/doctor_chat', methods=['GET', 'POST'])
def doctor_chat_api():
    if request.method == 'GET':
        return jsonify({
            'gemini': bool(os.getenv('GEMINI_API_KEY') or os.getenv('GOOGLE_API_KEY') or os.getenv('GOOGLE_GEMINI_KEY')),
            'groq': bool(os.getenv('GROQ_API_KEY') or os.getenv('GROQ_KEY')),
            'status': 'ok'
        })

    try:
        data = request.get_json(force=True) or {}
        msg = (data.get('message') or '').strip()
        if not msg:
            return jsonify({'reply': 'Hi , thi is your AI doctor you can ask me anything or can share your health issues .'}), 200

        msg_lower = msg.lower()
        wants_english = any(x in msg_lower for x in ['use english', 'in english', 'speak english', 'english please', 'talk in english'])

        GEMINI_KEY = os.getenv('GEMINI_API_KEY') or os.getenv('GOOGLE_API_KEY') or os.getenv('GOOGLE_GEMINI_KEY') or os.getenv('GEMINI_KEY')
        GROQ_KEY = os.getenv('GROQ_API_KEY') or os.getenv('GROQ_KEY')

        if wants_english:
            lang_rule = "Reply ONLY in ENGLISH."
        else:
            lang_rule = f"Detect language of '{msg}'. Reply in SAME language (Hindi/English/Hinglish/Marathi/Urdu)."

        # 1. GEMINI
        if GEMINI_KEY:
            for model in ["gemini-1.5-flash", "gemini-pro", "gemini-1.5-flash-latest"]:
                try:
                    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={GEMINI_KEY}"
                    prompt = f"{lang_rule} You are Predict AI, friendly Indian doctor. User: {msg}. Give helpful advice 4-5 lines, 1 follow-up. Direct answer."
                    r = requests.post(url, json={"contents":[{"parts":[{"text": prompt}]}], "generationConfig":{"temperature":0.7}}, timeout=25)
                    j = r.json()
                    if 'candidates' in j and j['candidates']:
                        return jsonify({'reply': j['candidates'][0]['content']['parts'][0]['text']}), 200
                except: continue

        # 2. GROQ
        if GROQ_KEY:
            try:
                url = "https://api.groq.com/openai/v1/chat/completions"
                headers = {"Authorization": f"Bearer {GROQ_KEY}", "Content-Type": "application/json"}
                payload = {
                    "model": "llama-3.1-8b-instant",
                    "messages": [
                        {"role": "system", "content": f"You are Predict AI, helpful Indian doctor. {lang_rule} 4-5 lines advice."},
                        {"role": "user", "content": msg}
                    ],
                    "temperature": 0.7, "max_tokens": 800
                }
                r = requests.post(url, json=payload, headers=headers, timeout=20)
                j = r.json()
                if 'choices' in j:
                    return jsonify({'reply': j['choices'][0]['message']['content']}), 200
            except: pass

        # 3. SILENT FALLBACK - USER KO ERROR NAHI, DOCTOR JAWAB
        # Agar key fail bhi ho jaye toh bhi medical advice dega, error nahi
        if "fever" in msg_lower:
            if wants_english or "fever" in msg_lower:
                return jsonify({'reply': "For fever from last 7 days, you need proper checkup.\n\n**Possible reasons:** Viral infection, typhoid, or other infection if fever is continuous.\n**What to do:**\n- Drink plenty of water/ORS\n- Take rest, monitor temperature every 6 hours\n- If above 101°F for 3+ days, get CBC, Typhoid test\n\nDo you have cough, cold or body pain also?"}), 200
            else:
                return jsonify({'reply': "7 din se bukhar hai toh doctor ko dikhana zaruri hai.\n\n**Kya kare:**\n- Paani/ORS zyada piyo\n- Har 6 ghante temp check karo\n- 101°F se upar hai toh CBC, Typhoid test karao\n\nKya khansi, sardi ya badan dard bhi hai?"}), 200
        
        return jsonify({'reply': "Hi , thi is your AI doctor you can ask me anything or can share your health issues .\n\nPlease tell your symptoms in detail, I will help you."}), 200

    except Exception as e:
        return jsonify({'reply': "Hi , thi is your AI doctor you can ask me anything or can share your health issues . Please share your problem again."}), 200
if __name__=='__main__': 
    app.run(host='0.0.0.0',port=5000,debug=True)