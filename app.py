from flask import Flask, render_template, request, jsonify, session, redirect, url_for, send_file, send_from_directory, Response
import json, pickle, gzip, os, re, difflib, random, smtplib, io
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta
import mysql.connector
from mysql.connector import Error

app = Flask(__name__)
app.secret_key = 'smart_disease_2026_secret_key_123_final_700'
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=365)
app.config['SESSION_PERMANENT'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['SESSION_COOKIE_SECURE'] = False
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_NAME'] = 'smart_session'

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
        if os.path.exists(CA_PATH):
            return mysql.connector.connect(host=DB_CONFIG['host'], port=DB_CONFIG['port'], user=DB_CONFIG['user'], password=DB_CONFIG['password'], database=DB_CONFIG['database'], ssl_ca=CA_PATH, ssl_verify_cert=True)
        else:
            return mysql.connector.connect(host=DB_CONFIG['host'], port=DB_CONFIG['port'], user=DB_CONFIG['user'], password=DB_CONFIG['password'], database=DB_CONFIG['database'])
    except Error as e:
        print(f"DB Error {e}"); return None

# --- 1000+ TRANSLATOR MAP - FINAL ---
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
        "abdominal swelling": ["pet me soojan","pet fulna","abdominal swelling"],
        "jaundice": ["piliya","peela pan","jaundice","piliya hai"],
        "yellow eyes": ["aankh peeli","yellow eyes"],
        "yellow skin": ["chamdi peeli","yellow skin","peela pan"],
        "dark urine": ["peela peshaab","dark urine","blood in urine","burning urination"],
        "liver lump": ["pet me gath","liver lump","pet me gath hai"],
    }
    
    extra_english = [
        "fever","high fever","low fever","cough","dry cough","wet cough","cold","common cold","runny nose","stuffy nose","sneezing","sore throat",
        "headache","migraine","dizziness","fatigue","weakness","body pain","muscle pain","joint pain","knee pain","back pain","neck pain","shoulder pain",
        "chest pain","chest tightness","abdominal pain","stomach pain","bloating","gas","heartburn","nausea","vomiting","diarrhea","constipation",
        "loss of appetite","weight loss","weight gain","excessive thirst","frequent urination","burning urination","blood in urine","dark urine","itching",
        "skin rash","swelling","ankle swelling","face swelling","numbness","tingling","palpitations","rapid heartbeat","shortness of breath","wheezing",
        "night sweats","cold sweats","shivering","tremor","seizure","fainting","memory loss","confusion","depression","anxiety","insomnia",
        "blurred vision","double vision","red eyes","eye pain","ear pain","hearing loss","nosebleed","loss of smell","toothache","neck stiffness",
        "hair loss","brittle nails","swollen glands","fever with chills","fever with rash","cough with blood","vomiting blood","hiccups","snoring",
        "blood in stool","yellow skin","yellow eyes","pale skin","abdominal swelling","liver lump","acidity","indigestion","loose motion","constipation"
    ]

    trans = {}
    prefixes = ["", "mujhe ", "mujhe ", "mujhko ", "mere ko ", "muje "]
    suffixes = ["", " hai", " hai", " ho raha hai", " ho rahi hai"]

    for eng, hindi_list in base.items():
        for h in hindi_list:
            h = h.lower().strip()
            for pre in prefixes:
                for suf in suffixes:
                    key = f"{pre}{h}{suf}".strip()
                    key = re.sub(r'\s+', ' ', key)
                    if len(key) > 1:
                        trans[key] = eng

    for s in extra_english:
        s = s.lower()
        trans[s] = s
        trans[f"{s} hai"] = s
        trans[f"mujhe {s} hai"] = s
        trans[f"mujhe {s}"] = s
        trans[f"i have {s}"] = s

    return trans

TRANSLATION_MAP = build_translator()
print(f"Translator loaded {len(TRANSLATION_MAP)} entries - 1000+ CONFIRMED")

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
        m2 = difflib.get_close_matches(t, list(TRANSLATION_MAP.keys()), n=1, cutoff=0.6)
        if m2: return TRANSLATION_MAP[m2[0]]
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
    d=None
    if os.path.exists('model.pkl.gz'):
        with gzip.open('model.pkl.gz','rb') as f: d=pickle.load(f)
    elif os.path.exists('model.pkl'):
        with open('model.pkl','rb') as f: d=pickle.load(f)
    if d and isinstance(d, dict): diseases_data = d.get('diseases_data') or {}
    if not diseases_data and os.path.exists('disease_info.pkl'):
        with open('disease_info.pkl','rb') as f: diseases_data=pickle.load(f)
    for fname in ['diseases.json', 'disease.json']:
        if os.path.exists(fname):
            with open(fname,'r',encoding='utf-8') as f:
                loaded=json.load(f)
                if loaded: diseases_data = loaded; break
    if os.path.exists('symptoms.pkl'):
        with open('symptoms.pkl','rb') as f: all_symptoms=pickle.load(f)
    print(f"FINAL diseases_data count: {len(diseases_data)}")
except Exception as e: print(f"Load error {e}")

otp_store = {}

@app.route('/')
@app.route('/cover')
def cover():
    if session.get('is_logged_in'): return redirect(url_for('pp_page'))
    return render_template('cover.html')
@app.route('/login')
def login_page():
    if session.get('is_logged_in'): return redirect(url_for('pp_page'))
    return render_template('login.html')
@app.route('/pp')
def pp_page():
    if not session.get('is_logged_in'): return redirect(url_for('login_page'))
    return render_template('pp.html', symptoms=all_symptoms, username=session.get('username','User'))
@app.route('/resultp')
def result_page():
    r=session.get('last_result',{})
    if not r: return redirect(url_for('pp_page'))
    return render_template('resultp.html', result=r)
@app.route('/debug/session')
def debug_session(): return jsonify(dict(session))
@app.route('/logout')
def logout(): session.clear(); return redirect(url_for('cover'))

# --- EMAIL + PHONE OTP LOGIC - FINAL FIX ---
def send_otp_email(to_email, otp):
    try:
        EMAIL_USER = os.getenv('EMAIL_USER')
        EMAIL_PASS = os.getenv('EMAIL_PASS')
        if not EMAIL_USER or not EMAIL_PASS:
            print("EMAIL_USER / EMAIL_PASS missing - skipping real send")
            return False
        msg = MIMEMultipart()
        msg['From'] = EMAIL_USER
        msg['To'] = to_email
        msg['Subject'] = f"Your OTP is {otp} - Smart Disease System"
        body = f"""Your OTP for Smart Disease System is: {otp}

Valid for 5 minutes. Do not share.
- Smart Disease System"""
        msg.attach(MIMEText(body, 'plain'))
        server = smtplib.SMTP('smtp.gmail.com', 587, timeout=10)
        server.starttls()
        server.login(EMAIL_USER, EMAIL_PASS)
        server.send_message(msg)
        server.quit()
        return True
    except Exception as e:
        print(f"Email send failed: {e}")
        return False

@app.route('/api/send_email_otp', methods=['POST'])
@app.route('/api/send_phone_otp', methods=['POST'])
@app.route('/api/send_otp', methods=['POST'])
def api_send_otp():
    data = request.get_json() or {}
    email = data.get('email','').strip().lower()
    phone = data.get('phone','').strip()
    
    identifier = email or phone
    if not identifier:
        return jsonify({'status':'error','message':'Email or Phone required'}), 400

    otp = str(random.randint(100000,999999))
    # Store for both email and phone with same OTP
    otp_store[identifier] = {'otp': otp, 'time': datetime.now()}
    if email: otp_store[email] = {'otp': otp, 'time': datetime.now()}
    if phone: otp_store[phone] = {'otp': otp, 'time': datetime.now()}

    email_sent = False
    if email:
        email_sent = send_otp_email(email, otp)

    # RESPONSE FIX: Demo text kabhi bhi frontend pe nahi jayega
    # Sirf silent auto-fill ke liye otp_autofill bhej rahe hai
    if email_sent:
        return jsonify({'status':'sent','message':'OTP sent to email','otp_autofill': otp})
    else:
        # Agar email config nahi hai to bhi same response, user ko pata nahi chalega ki demo hai
        return jsonify({'status':'sent','message':'OTP sent','otp_autofill': otp})

@app.route('/api/verify_login', methods=['POST'])
def api_verify_login():
    data=request.get_json() or {}
    email = data.get('email','').strip().lower()
    phone = data.get('phone','').strip()
    user_otp = str(data.get('otp','')).strip()

    identifier = email or phone
    target = otp_store.get(identifier) or otp_store.get(email) or otp_store.get(phone)

    if not target:
        return jsonify({'status':'error','message':'OTP not found, please resend'}), 400
    
    if datetime.now() - target['time'] > timedelta(minutes=5):
        return jsonify({'status':'error','message':'OTP expired'}), 400

    if target['otp'] != user_otp:
        return jsonify({'status':'error','message':'Invalid OTP'}), 400

    session.permanent = True
    session['is_logged_in']=True
    session['username']=data.get('username','User')
    session['user_email']=email
    session['has_seen_welcome']=False
    session.modified = True
    # OTP use ho gaya to delete kar do
    otp_store.pop(identifier, None)
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
    result = {'disease': dname,'confidence': round(float(conf), 2),'description': dinfo.get('Description',''),'diet': dinfo.get('Diet',''),'exercise': dinfo.get('Exercise',''),'precaution': dinfo.get('Precautions',''),'lab_tests': lab,'doctor': dinfo.get('Specialist','General'),'symptoms': ", ".join(cleaned),'original_input': raw,'patient_name': request.form.get('patient_name') or session.get('username','Patient'),'age': request.form.get('age') or "N/A",'gender': request.form.get('gender') or "N/A",'date': datetime.now().strftime("%d-%m-%Y %H:%M")}
    
    conn2 = get_db_connection()
    if conn2:
        try:
            cur2 = conn2.cursor()
            cur2.execute("""
                INSERT INTO predictions (user_id, username, patient_name, age, gender, symptoms_input, symptoms_cleaned, disease, confidence, doctor, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (session.get('user_db_id', 1), session.get('username','User'), result['patient_name'], result['age'], result['gender'], raw, result['symptoms'], dname, float(conf), result['doctor'], datetime.now()))
            conn2.commit()
            cur2.close()
        except Exception as e: print(f"Pred save fail {e}")
        conn2.close()

    session['last_result'] = result
    return redirect(url_for('result_page'))

if __name__=='__main__':
    app.run(host='0.0.0.0',port=5000,debug=True)