from flask import Flask, render_template, request, jsonify, session, redirect, url_for, flash, render_template_string, send_file
import json, pickle, gzip, os, re, difflib, random, smtplib, math, requests, io
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta
import mysql.connector
from mysql.connector import Error

app = Flask(__name__)
app.secret_key = 'smart_disease_2026_secret_key_123_final_700'
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'

MAIL_USER = os.getenv('MAIL_USER', 'tumhara_email@gmail.com')
MAIL_PASS = os.getenv('MAIL_PASS', 'tumhara_16_digit_app_password')

def send_email_otp(to_email, otp):
    print(f"TRYING TO SEND OTP {otp} TO {to_email}")
    if not MAIL_USER or 'tumhara_email' in MAIL_USER:
        print(f"[DEMO] OTP {otp}")
        return False
    try:
        msg = MIMEMultipart()
        msg['From'] = MAIL_USER
        msg['To'] = to_email
        msg['Subject'] = f"Predict AI - Your OTP is {otp}"
        body = f"<div style='font-family:Poppins;padding:20px'><h2>Predict AI</h2><h1>{otp}</h1><p>Valid 5 mins</p></div>"
        msg.attach(MIMEText(body, 'html'))
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(MAIL_USER, MAIL_PASS.replace(" ",""))
        server.send_message(msg)
        server.quit()
        return True
    except Exception as e:
        print(f"Email fail {e}")
        return False

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
        if os.path.exists('ca.pem'):
            return mysql.connector.connect(host=DB_CONFIG['host'], port=DB_CONFIG['port'], user=DB_CONFIG['user'], password=DB_CONFIG['password'], database=DB_CONFIG['database'], ssl_ca='ca.pem', ssl_verify_cert=True)
        else:
            return mysql.connector.connect(host=DB_CONFIG['host'], port=DB_CONFIG['port'], user=DB_CONFIG['user'], password=DB_CONFIG['password'], database=DB_CONFIG['database'], ssl_disabled=False)
    except Error as e:
        print(f"DB Error {e}")
        return None

def init_db():
    conn = get_db_connection()
    if not conn: return
    try:
        cur = conn.cursor()
        cur.execute("CREATE TABLE IF NOT EXISTS users (id INT AUTO_INCREMENT PRIMARY KEY, username VARCHAR(100) UNIQUE, email VARCHAR(100) UNIQUE, password VARCHAR(100), phone VARCHAR(20), created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)")
        cur.execute("CREATE TABLE IF NOT EXISTS predictions (id INT AUTO_INCREMENT PRIMARY KEY, user_id INT, symptoms TEXT, predicted_disease VARCHAR(200), confidence FLOAT, original_input TEXT, patient_name VARCHAR(100), age VARCHAR(10), gender VARCHAR(10), duration VARCHAR(50), created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)")
        conn.commit()
    except Exception as e: print(f"init error {e}")
    finally:
        try: cur.close(); conn.close()
        except: pass

# ============ TRANSLATION MAP (TERA WALA SAME) ============
TRANSLATION_MAP = {
"bukhar":"fever","khansi":"cough","sir dard":"headache","wazan kam":"weight loss","wazan ki kami":"weight loss","thakan":"fatigue","pet dard":"abdominal pain","chakkar":"dizziness"
# Baki 700+ wala tera same rehne de, yaha short kiya hai
}

def normalize(text, all_sym):
    t = text.lower().strip()
    t = re.sub(r'[^a-z0-9 ]', ' ', t)
    t = re.sub(r'\s+', ' ', t).strip()
    if t in TRANSLATION_MAP: return TRANSLATION_MAP[t]
    for hi,en in TRANSLATION_MAP.items():
        if hi in t or t in hi: return en
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

model=vectorizer=label_encoder=None; diseases_data={}; all_symptoms=[]
try:
    if os.path.exists('model.pkl.gz'):
        with gzip.open('model.pkl.gz','rb') as f: d=pickle.load(f)
    elif os.path.exists('model.pkl'):
        with open('model.pkl','rb') as f: d=pickle.load(f)
    else: d=None
    if d and isinstance(d, dict):
        model=d.get('model'); vectorizer=d.get('vectorizer'); label_encoder=d.get('label_encoder')
        diseases_data=d.get('diseases_data') or d.get('disease_data') or {}
    if os.path.exists('symptoms.pkl'):
        with open('symptoms.pkl','rb') as f: all_symptoms=pickle.load(f)
    if not diseases_data and os.path.exists('diseases.json'):
        with open('diseases.json','r',encoding='utf-8') as f: diseases_data=json.load(f)
    print(f"Loaded {len(diseases_data)} diseases")
except Exception as e: print(f"Load error {e}")

otp_store={}; temp_users={}

# ===================== FINAL ROUTING FIX =====================
# ===================== FINAL ROUTING FIX =====================
@app.route('/')
@app.route('/cover')
def cover():
    # Cover hamesha dikhega - koi redirect nahi
    return render_template('cover.html')

@app.route('/login')
@app.route('/login.html')
def login_page():
    # Agar already login hai to
    if session.get('is_logged_in'):
        if not session.get('has_seen_welcome'):
            return redirect(url_for('welcome_page')) # welcome nahi dekha to welcome
        else:
            return redirect(url_for('pp_page')) # welcome dekh liya to direct pp
    return render_template('login.html')

@app.route('/welcome')
@app.route('/welcome.html')
def welcome_page():
    if not session.get('is_logged_in'): 
        return redirect(url_for('login_page'))
    # Agar welcome pehle dekh liya hai to direct pp
    if session.get('has_seen_welcome'):
        return redirect(url_for('pp_page'))
    # Pehli baar welcome dekhega
    session['has_seen_welcome'] = True
    return render_template('welcome.html', username=session.get('username','User'))

@app.route('/pp')
@app.route('/patient')
@app.route('/pp.html')
def pp_page():
    if not session.get('is_logged_in'): 
        return redirect(url_for('login_page'))
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
    if not session.get('is_logged_in'): 
        return redirect(url_for('login_page'))
    r=session.get('last_result',{})
    return render_template('thankyou.html', result=r, username=session.get('username','User'))

@app.route('/logout')
def logout(): 
    session.clear()
    return redirect(url_for('cover'))

# --- APIs FIXED - NO FIREBASE ---

otp_store = {}  # email/phone -> {otp, time}
temp_users = {}

@app.route('/api/send_email_otp', methods=['POST'])
def api_send_email_otp():
    data = request.get_json() or {}
    email = data.get('email','').strip()
    if not email or '@' not in email:
        return jsonify({'status':'error','message':'Invalid email'}),400
    
    otp = str(random.randint(100000, 999999)) # Har baar naya
    otp_store[email] = {'otp': otp, 'time': datetime.now()}
    temp_users[email] = {'username': data.get('username','User'), 'email': email, 'password': data.get('password','')}
    
    ok = send_email_otp(email, otp)
    if ok:
        return jsonify({'status':'sent','message':'OTP sent to Gmail'})
    else:
        # Demo mode - OTP frontend pe dikhega
        return jsonify({'status':'sent','demo_otp': otp, 'message': f'Demo OTP: {otp}'})

@app.route('/api/send_phone_otp', methods=['POST'])
def api_send_phone_otp():
    data = request.get_json() or {}
    phone = data.get('phone','').strip()
    if not phone or len(phone) < 10:
        return jsonify({'status':'error','message':'Invalid phone'}),400
    
    otp = str(random.randint(100000, 999999)) # Har baar naya random
    otp_store[phone] = {'otp': otp, 'time': datetime.now()}
    temp_users[phone] = {'username': data.get('username','User'), 'phone': phone}
    
    # Phone ke liye hamesha demo_otp return karo - SMS nahi bhejna
    return jsonify({'status':'sent','demo_otp': otp, 'message': f'Phone OTP: {otp}'})

@app.route('/api/verify_login', methods=['POST'])
def api_verify_login():
    data = request.get_json() or {}
    login_type = data.get('type')

    if login_type == 'email':
        email = data.get('email','').strip()
        otp = str(data.get('otp','')).strip()
        stored = otp_store.get(email)
        
        valid = False
        if stored and stored['otp'] == otp and datetime.now() - stored['time'] < timedelta(minutes=10):
            valid = True
        if otp == "123456": # Master OTP testing ke liye
            valid = True
            
        if not valid:
            return jsonify({'status':'error','message':'Invalid or Expired OTP'}),400
        
        user_info = temp_users.get(email, {'username': data.get('username','User'), 'email': email})
        session['is_logged_in'] = True
        session['user_id'] = random.randint(1000,9999)
        session['username'] = user_info['username']
        session['has_seen_welcome'] = False
        otp_store.pop(email, None)
        return jsonify({'status':'success'})

    elif login_type == 'phone':
        phone = data.get('phone','').strip()
        otp = str(data.get('otp','')).strip()
        username = data.get('username','User')
        stored = otp_store.get(phone)
        
        # PHONE: Har baar alag OTP, par testing me koi bhi 6 digit accept
        valid = False
        if stored and stored['otp'] == otp and datetime.now() - stored['time'] < timedelta(minutes=10):
            valid = True
        if len(otp) == 6 and otp.isdigit(): # Pehle jaisa - har baar different, koi bhi 6 digit chalega
            valid = True
        
        if not valid:
            return jsonify({'status':'error','message':'Enter 6 digit OTP'}),400
        
        session['is_logged_in'] = True
        session['user_id'] = random.randint(1000,9999)
        session['username'] = username
        session['has_seen_welcome'] = False
        otp_store.pop(phone, None)
        return jsonify({'status':'success'})

    return jsonify({'status':'error','message':'Invalid type'}),400

@app.route('/predict', methods=['POST'])
def predict_route():
    raw=request.form.get('symptoms') or request.form.get('symptoms_text') or ""
    patient_name=request.form.get('patient_name') or session.get('username','Patient')
    age=request.form.get('age') or "N/A"
    gender=request.form.get('gender') or "N/A"
    duration=request.form.get('duration') or "N/A"
    if not raw.strip(): return redirect(url_for('pp_page'))
    all_lower=[s.lower() for s in all_symptoms] if all_symptoms else []
    cleaned=parse_symptoms(str(raw), all_lower)
    scores=[]
    for dname, info in diseases_data.items():
        key_syms=[k.lower() for k in info.get('key_symptoms',[]) if k]
        full_text=info.get('Symptoms','').lower()
        full=[s.lower().strip() for s in re.split(r'\d+\.|,|;', full_text) if s.strip()]
        if not key_syms: key_syms=full[:8]
        km=len(set(cleaned)&set(key_syms)); fm=len(set(cleaned)&set(full))
        sc=(km*5)+fm
        if sc>0: scores.append((dname,sc,info))
    scores.sort(key=lambda x:x[1], reverse=True)
    if scores and scores[0][1]>=1:
        dname=scores[0][0]; dinfo=scores[0][2]; conf=min(96, max(40, scores[0][1]*10+45))
    else:
        dname=list(diseases_data.keys())[0] if diseases_data else "Analysis Needed"
        dinfo=diseases_data.get(dname,{}) if diseases_data else {}
        conf=35
    lab=dinfo.get('Lab_Tests') or ["CBC"]
    if isinstance(lab,str): lab=[s.strip() for s in re.split(r',|;', lab) if s.strip()]
    result={'disease':dname,'confidence':round(float(conf),2),'description':dinfo.get('Description',''),'diet':dinfo.get('Diet','Balanced diet'),'exercise':dinfo.get('Exercise','Light walk'),'precaution':dinfo.get('Precautions','Consult doctor'),'lab_tests':lab,'doctor':dinfo.get('Specialist','General Physician'),'is_emergency':dinfo.get('is_emergency',False),'symptoms':", ".join(cleaned),'original_input':raw,'patient_name':patient_name,'age':age,'gender':gender,'duration':duration,'date':datetime.now().strftime("%d-%m-%Y %H:%M")}
    session['last_result']=result
    # FIXED INSERT QUERY - 9 values
    conn=get_db_connection()
    if conn:
        try:
            cur=conn.cursor()
            cur.execute("INSERT INTO predictions (user_id,symptoms,predicted_disease,confidence,original_input,patient_name,age,gender,duration) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)", (session.get('user_id',0), result['symptoms'], result['disease'], result['confidence'], result['original_input'], result['patient_name'], str(result['age']), str(result['gender']), str(result['duration'])))
        except Exception as e: print(f"DB save error {e}")
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
    init_db()
    app.run(host='0.0.0.0',port=5000,debug=True)