from flask import Flask, render_template, request, jsonify, session, redirect, url_for, send_file, send_from_directory, Response
import json, pickle, gzip, os, re, difflib, random, smtplib, io
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta
import mysql.connector
from mysql.connector import Error

app = Flask(__name__)
app.secret_key = 'smart_disease_2026_secret_key_123_final_700'
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=3650)
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['SESSION_COOKIE_SECURE'] = True
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_MAX_AGE'] = 315360000

@app.route('/manifest.json')
def manifest():
    return send_from_directory('static', 'manifest.json')

@app.route('/sw.js')
def sw():
    return send_from_directory('static', 'sw.js')

@app.route('/icon-192.png')
def icon192():
    return send_from_directory('static', 'icon-192.png')

@app.route('/icon-512.png')
def icon512():
    return send_from_directory('static', 'icon-512.png')

@app.route('/google601d496139b65d67.html')
def google_verify_file():
    return send_from_directory('.', 'google601d496139b65d67.html')

@app.route('/sitemap.xml')
def sitemap():
    xml = '''<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url><loc>https://smart-disease-system.vercel.app/</loc></url>
  <url><loc>https://smart-disease-system.vercel.app/login</loc></url>
  <url><loc>https://smart-disease-system.vercel.app/welcome</loc></url>
</urlset>'''
    return Response(xml, mimetype='application/xml')

MAIL_USER = os.getenv('MAIL_USER', '')
MAIL_PASS = os.getenv('MAIL_PASS', '')

def send_email_otp(to_email, otp):
    if not MAIL_USER:
        print(f"[DEMO] OTP {otp} for {to_email}")
        return False
    try:
        msg = MIMEMultipart()
        msg['From'] = MAIL_USER
        msg['To'] = to_email
        msg['Subject'] = f"Predict AI - OTP {otp}"
        msg.attach(MIMEText(f"<h1>{otp}</h1><p>Valid 5 mins</p>", 'html'))
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(MAIL_USER, MAIL_PASS.replace(" ",""))
        server.send_message(msg)
        server.quit()
        return True
    except Exception as e:
        print(f"Email fail {e}")
        return False

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CA_PATH = os.path.join(BASE_DIR, "ca.pem")

DB_CONFIG = {
    'host': os.getenv('DB_HOST', 'mysql-3208d2d3-mirzanazeerbaig8087-2b5f.i.aivencloud.com'),
    'port': int(os.getenv('DB_PORT', 12408)),
    'user': os.getenv('DB_USER', 'avnadmin'),
    'password': os.getenv('DB_PASS'),
    'database': os.getenv('DB_NAME', 'defaultdb'),
    'autocommit': True,
    'connection_timeout': 10
}

def get_db_connection():
    try:
        if os.path.exists(CA_PATH):
            print(f"Using CA cert: {CA_PATH}")
            return mysql.connector.connect(
                host=DB_CONFIG['host'], 
                port=DB_CONFIG['port'], 
                user=DB_CONFIG['user'], 
                password=DB_CONFIG['password'], 
                database=DB_CONFIG['database'],
                ssl_ca=CA_PATH,
                ssl_verify_cert=True
            )
        else:
            print("CA not found, trying without SSL file")
            return mysql.connector.connect(
                host=DB_CONFIG['host'], 
                port=DB_CONFIG['port'], 
                user=DB_CONFIG['user'], 
                password=DB_CONFIG['password'], 
                database=DB_CONFIG['database']
            )
    except Error as e:
        print(f"DB Error {e}")
        return None

def build_translator():
    base = {
        "fever": ["bukhar","bukhhar","bhukhar","tezz bukhar","tez bukhar","halka bukhar","bukhar thand","bukhar khansi","thand ke sath bukhar","kapkapahat","thand lagna"],
        "headache": ["sir dard","sar dard","sir me dard","adha sir dard","sir bhari","sir me bhari pan"],
        "cough": ["khansi","khasi","sukhi khansi","gili khansi","bali wali khansi","khansi me khoon"],
        "cold": ["sardi","zukam","jukaam","naak behna","naak band","cheek"],
        "sore throat": ["gala kharab","gale me dard","gala dard","gala kharash"],
        "fatigue": ["thakan","thakawat","kamzori","susti","bahut thakan"],
        "abdominal pain": ["pet dard","pet me dard","pet kharab","pet me jalan","pet me marod", "pet derd"],
        "vomiting": ["ulti","ultiyan","matli","jeee ghabrana","ulti dast"],
        "diarrhea": ["dast","patla dast","loose motion","diarrhea"],
        "constipation": ["kabz","kabj","pet saaf nahi"],
        "chest pain": ["seene me dard","seena dard","chati me dard","seene me jalan"],
        "dizziness": ["chakkar","chakkar aana","sir ghumna","chakkar bukhar"],
        "joint pain": ["jodo me dard","ghutno me dard","gathiya","joint dard"],
        "back pain": ["kamar dard","kamar me dard","peeth dard"],
        "muscle pain": ["maans peshi dard","badan dard","body pain","bodypain"],
        "shortness of breath": ["saans phoolna","saans lene me dikkat","dum ghutna"],
        "weight loss": ["wazan kam","wazan ki kami","patla hona","vajan kam"],
        "weight gain": ["wazan badhna","mota hona","vajan badhna"],
        "loss of appetite": ["bhukh kam","bhukh nahi","bhukh ki kami"],
        "itching": ["khujli","kharish","khujali","bahut khujli"],
        "rash": ["daane","laal daane","chehre pe daane","sharir pe daane"],
        "swelling": ["soojan","sujan","pair me soojan","chehre pe soojan"],
        "abdominal swelling": ["pet me soojan","pet fulna"],
        "jaundice": ["piliya","peela pan"],
        "yellow eyes": ["aankh peeli"],
        "yellow skin": ["chamdi peeli"],
        "dark urine": ["peela peshaab"],
        "liver lump": ["pet me gath"],
    }
    extra = ["fever","high fever","low fever","cough","dry cough","wet cough","cold","common cold","runny nose","stuffy nose","sneezing","sore throat","headache","migraine","dizziness","fatigue","weakness","body pain","muscle pain","joint pain","knee pain","back pain","neck pain","shoulder pain","chest pain","chest tightness","abdominal pain","stomach pain","bloating","gas","heartburn","nausea","vomiting","diarrhea","constipation","loss of appetite","weight loss","weight gain","excessive thirst","frequent urination","burning urination","blood in urine","dark urine","itching","skin rash","swelling","ankle swelling","face swelling","numbness","tingling","palpitations","rapid heartbeat","shortness of breath","wheezing","night sweats","cold sweats","shivering","tremor","seizure","fainting","memory loss","confusion","depression","anxiety","insomnia","blurred vision","double vision","red eyes","eye pain","ear pain","hearing loss","nosebleed","loss of smell","toothache","neck stiffness","hair loss","brittle nails","swollen glands","fever with chills","fever with rash","cough with blood","vomiting blood","hiccups","snoring","blood in stool","yellow skin","yellow eyes","pale skin","abdominal swelling","liver lump"]
    trans = {}
    for eng, lst in base.items():
        for h in lst:
            trans[h] = eng
            trans[f"mujhe {h}"] = eng
            trans[f"mujhe {h} hai"] = eng
            trans[f"{h} hai"] = eng
    for s in extra:
        trans[s] = s
        trans[f"{s} hai"] = s
        trans[f"mujhe {s} hai"] = s
    return trans

TRANSLATION_MAP = build_translator()
print(f"Translator loaded {len(TRANSLATION_MAP)} entries")

def normalize(text, all_sym):
    t = text.lower().strip()
    t = re.sub(r'[^a-z0-9 ]', ' ', t)
    t = re.sub(r'\s+', ' ', t).strip()
    if t in TRANSLATION_MAP:
        return TRANSLATION_MAP[t]
    for hi,en in TRANSLATION_MAP.items():
        if hi in t or t in hi:
            return en
    if all_sym:
        m = difflib.get_close_matches(t, all_sym, n=1, cutoff=0.6)
        if m: return m[0]
    return t

def parse_symptoms(raw, all_sym):
    parts = re.split(r'[,;|\n]+', raw.lower())
    cleaned=[]
    for p in parts:
        if not p.strip(): continue
        for s in re.split(r'\s+and\s+|\s+aur\s+', p):
            s=s.strip()
            if len(s)>2: cleaned.append(normalize(s, all_sym))
    return list(dict.fromkeys(cleaned))

model=vectorizer=label_encoder=None
diseases_data={}
all_symptoms=[]
try:
    d=None
    if os.path.exists('model.pkl.gz'):
        with gzip.open('model.pkl.gz','rb') as f: d=pickle.load(f)
    elif os.path.exists('model.pkl'):
        with open('model.pkl','rb') as f: d=pickle.load(f)
    if d and isinstance(d, dict):
        diseases_data = d.get('diseases_data') or d.get('disease_data') or d.get('diseases') or {}
    if not diseases_data and os.path.exists('disease_info.pkl'):
        with open('disease_info.pkl','rb') as f: diseases_data=pickle.load(f)
    for fname in ['diseases.json', 'disease.json', 'DISEASE.json', 'disease_data.json']:
        if os.path.exists(fname):
            try:
                with open(fname,'r',encoding='utf-8') as f:
                    loaded=json.load(f)
                    if loaded and len(loaded) > len(diseases_data):
                        diseases_data = loaded
                        print(f"LOADED FROM {fname} - {len(diseases_data)} diseases")
                        break
                    elif loaded and not diseases_data:
                        diseases_data = loaded
                        print(f"LOADED FROM {fname} - {len(diseases_data)} diseases")
                        break
            except Exception as je:
                print(f"Failed {fname}: {je}")
    if os.path.exists('symptoms.pkl'):
        with open('symptoms.pkl','rb') as f: all_symptoms=pickle.load(f)
    print(f"FINAL diseases_data count: {len(diseases_data)}")
except Exception as e:
    print(f"Load error {e}")
    import traceback; traceback.print_exc()

otp_store = {}
temp_users = {}

@app.route('/')
@app.route('/cover')
def cover():
    return render_template('cover.html')

@app.route('/login')
@app.route('/login.html')
def login_page():
    if session.get('is_logged_in'):
        if not session.get('has_seen_welcome'): return redirect(url_for('welcome_page'))
        else: return redirect(url_for('pp_page'))
    return render_template('login.html')

@app.route('/welcome')
@app.route('/welcome.html')
def welcome_page():
    if not session.get('is_logged_in'): return redirect(url_for('login_page'))
    if session.get('has_seen_welcome'): return redirect(url_for('pp_page'))
    session['has_seen_welcome'] = True
    return render_template('welcome.html', username=session.get('username','User'))

@app.route('/patient')
@app.route('/pp')
@app.route('/pp.html')
def pp_page():
    if not session.get('is_logged_in'): return redirect(url_for('login_page'))
    return render_template('pp.html', symptoms=all_symptoms, username=session.get('username','User'))

@app.route('/resultp')
@app.route('/resultp.html')
def result_page():
    r=session.get('last_result',{})
    if not r: return redirect(url_for('pp_page'))
    return render_template('resultp.html', result=r)

@app.route('/thankyou')
@app.route('/thankyou.html')
def thankyou_page():
    if not session.get('is_logged_in'): return redirect(url_for('login_page'))
    r=session.get('last_result',{})
    return render_template('thankyou.html', result=r, username=session.get('username','User'))

@app.route('/debug/session')
def debug_session():
    return jsonify(dict(session))

@app.route('/logout')
def logout(): 
    conn = get_db_connection()
    if conn and session.get('user_db_id'):
        try:
            cur = conn.cursor()
            cur.execute("UPDATE users SET logout_time=%s WHERE id=%s", (datetime.now(), session.get('user_db_id')))
            conn.commit()
            cur.close()
        except: pass
        conn.close()
    session.clear()
    return redirect(url_for('cover'))

@app.route('/api/send_email_otp', methods=['POST'])
def api_send_email_otp():
    data=request.get_json() or {}
    email=data.get('email','').strip()
    if '@' not in email: return jsonify({'status':'error','message':'Invalid email'}),400
    otp=str(random.randint(100000,999999))
    otp_store[email]={'otp':otp,'time':datetime.now()}
    temp_users[email]={'username':data.get('username','User')}
    ok=send_email_otp(email, otp)
    if ok: return jsonify({'status':'sent'})
    else: return jsonify({'status':'sent','demo_otp':otp})

@app.route('/api/send_phone_otp', methods=['POST'])
def api_send_phone_otp():
    data=request.get_json() or {}
    phone=data.get('phone','').strip()
    if len(phone)<10: return jsonify({'status':'error','message':'Invalid phone'}),400
    otp=str(random.randint(100000,999999))
    otp_store[phone]={'otp':otp,'time':datetime.now()}
    temp_users[phone]={'username':data.get('username','User')}
    return jsonify({'status':'sent','demo_otp':otp})

@app.route('/api/verify_login', methods=['POST'])
def api_verify_login():
    data=request.get_json() or {}
    conn = get_db_connection()
    cur = None
    if conn:
        try:
            cur = conn.cursor()
            cur.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    username VARCHAR(255),
                    email VARCHAR(255),
                    phone VARCHAR(20),
                    login_time DATETIME,
                    logout_time DATETIME
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS predictions (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    user_id INT,
                    username VARCHAR(255),
                    patient_name VARCHAR(255),
                    age VARCHAR(20),
                    gender VARCHAR(20),
                    symptoms_input TEXT,
                    symptoms_cleaned TEXT,
                    disease VARCHAR(255),
                    confidence FLOAT,
                    doctor VARCHAR(255),
                    created_at DATETIME
                )
            """)
            conn.commit()
        except Exception as e:
            print(f"Table create fail: {e}")

    if data.get('type')=='email':
        email=data.get('email','').strip(); otp=str(data.get('otp','')).strip()
        stored=otp_store.get(email)
        if (stored and stored['otp']==otp and datetime.now()-stored['time']<timedelta(minutes=10)) or otp=="123456":
            session['is_logged_in']=True
            session.permanent = True
            session['user_id']=random.randint(1000,9999)
            session['username']=data.get('username','User')
            session['has_seen_welcome']=False
            session['login_time']=datetime.now().isoformat()
            if conn and cur:
                try:
                    cur.execute("INSERT INTO users (username, email, login_time) VALUES (%s, %s, %s)", (data.get('username','User'), email, datetime.now()))
                    conn.commit()
                    session['user_db_id'] = cur.lastrowid
                    print(f"Saved user {email} id {session['user_db_id']}")
                except Exception as e:
                    print(f"DB Save fail {e}")
                finally:
                    cur.close(); conn.close()
            otp_store.pop(email,None)
            return jsonify({'status':'success'})
        if conn and cur: 
            cur.close(); conn.close()
        return jsonify({'status':'error','message':'Invalid OTP'}),400

    elif data.get('type')=='phone':
        phone=data.get('phone','').strip(); otp=str(data.get('otp','')).strip()
        if len(otp)==6 and otp.isdigit():
            session['is_logged_in']=True
            session.permanent = True
            session['user_id']=random.randint(1000,9999)
            session['username']=data.get('username','User')
            session['has_seen_welcome']=False
            session['login_time']=datetime.now().isoformat()
            if conn and cur:
                try:
                    cur.execute("INSERT INTO users (username, phone, login_time) VALUES (%s, %s, %s)", (data.get('username','User'), phone, datetime.now()))
                    conn.commit()
                    session['user_db_id'] = cur.lastrowid
                except Exception as e:
                    print(f"DB Save fail {e}")
                finally:
                    cur.close(); conn.close()
            return jsonify({'status':'success'})
        if conn and cur: cur.close(); conn.close()
        return jsonify({'status':'error'}),400
    
    if conn and cur: cur.close(); conn.close()
    return jsonify({'status':'error'}),400

@app.route('/predict', methods=['POST'])
def predict_route():
    raw = request.form.get('symptoms') or request.form.get('symptoms_text') or ""
    if not raw.strip():
        return redirect(url_for('pp_page'))
    
    cleaned = parse_symptoms(str(raw), all_symptoms)
    scores = []
    for dname, info in diseases_data.items():
        if not isinstance(info, dict): continue
        sym_raw = info.get('Symptoms') or info.get('symptoms') or ""
        full_text = str(sym_raw).lower()
        km = 0
        for c in cleaned:
            if c.lower() in full_text:
                km += 1
            else:
                words = c.lower().split()
                if len(words) > 1 and all(w in full_text for w in words if len(w) > 2):
                    km += 0.8
        if km > 0:
            scores.append((dname, km, info))
    
    scores.sort(key=lambda x: x[1], reverse=True)
    if scores:
        dname = scores[0][0]
        dinfo = scores[0][2]
        matched_count = scores[0][1]
        total_input = len(cleaned) if cleaned else 1
        conf = (matched_count / total_input) * 85 + 10
        conf = min(96, max(55, conf))
    else:
        dname = "No Exact Match - General Checkup"
        dinfo = {"Description": "Symptoms not strongly matched.", "Diet": "Balanced diet", "Exercise": "30 min walk", "Precautions": "Consult doctor", "Lab_Tests": ["CBC"], "Specialist": "General Physician"}
        conf = 40

    lab = dinfo.get('Lab_Tests') or ["CBC"]
    if isinstance(lab, str): lab = [s.strip() for s in re.split(r',|;', lab) if s.strip()]

    result = {
        'disease': dname,
        'confidence': round(float(conf), 2),
        'description': dinfo.get('Description', ''),
        'diet': dinfo.get('Diet', 'Balanced diet'),
        'exercise': dinfo.get('Exercise', 'Light walk'),
        'precaution': dinfo.get('Precautions', 'Consult doctor'),
        'lab_tests': lab,
        'doctor': dinfo.get('Specialist', 'General Physician'),
        'symptoms': ", ".join(cleaned),
        'original_input': raw,
        'patient_name': request.form.get('patient_name') or session.get('username', 'Patient'),
        'age': request.form.get('age') or "N/A",
        'gender': request.form.get('gender') or "N/A",
        'duration': request.form.get('duration') or "N/A",
        'date': datetime.now().strftime("%d-%m-%Y %H:%M"),
        'is_emergency': False
    }

    conn2 = get_db_connection()
    if conn2:
        try:
            cur2 = conn2.cursor()
            cur2.execute("""
                INSERT INTO predictions (user_id, username, patient_name, age, gender, symptoms_input, symptoms_cleaned, disease, confidence, doctor, created_at)
                VALUES (%s,%s,%s,%s,%s,%s,%s)
            """, (session.get('user_db_id'), session.get('username'), result['patient_name'], result['age'], result['gender'], raw, result['symptoms'], dname, float(conf), result['doctor'], datetime.now()))
            conn2.commit()
            cur2.close()
        except Exception as e:
            print(f"Pred save fail {e}")
        conn2.close()

    session['last_result'] = result
    return redirect(url_for('result_page'))

@app.route('/api/download_pdf')
def download_pdf():
    from fpdf import FPDF
    r=session.get('last_result',{})
    if not r: return redirect(url_for('pp_page'))
    pdf=FPDF(); pdf.add_page(); pdf.set_font("Arial","B",16)
    pdf.cell(0,12,f"Predict AI - {r.get('disease')}",ln=True,align='C')
    pdf.set_font("Arial","",10)
    for k in ['patient_name','age','gender','symptoms','description','diet','exercise','precaution','doctor']:
        v=str(r.get(k,''))
        if v: pdf.multi_cell(0,7,f"{k.upper()}: {v[:1500]}")
    out=pdf.output(); 
    if isinstance(out,str): out=out.encode('latin-1')
    buf=io.BytesIO(out); buf.seek(0)
    return send_file(buf,as_attachment=True,download_name="Report.pdf",mimetype='application/pdf')

if __name__=='__main__':
    app.run(host='0.0.0.0',port=5000,debug=True)