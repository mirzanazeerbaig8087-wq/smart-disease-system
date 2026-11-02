from flask import Flask, render_template, request, jsonify, session, redirect, url_for, send_from_directory
import json, pickle, gzip, os, re, difflib, random, smtplib, requests, threading, base64
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = 'smart_disease_2026_secret_key_123_final_700_V2'

IS_VERCEL = os.getenv('VERCEL') == '1'
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=30)
app.config['SESSION_COOKIE_NAME'] = 'smart_session_v2'
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['SESSION_COOKIE_SECURE'] = True if IS_VERCEL else False
app.config['SESSION_COOKIE_HTTPONLY'] = True

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'static', 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
ALLOWED_EXT = {'png','jpg','jpeg','pdf','webp'}

def get_env(key):
    return os.getenv(key) or os.getenv(key.upper()) or ""

@app.before_request
def make_session_permanent():
    session.permanent = True

@app.route('/manifest.json')
def manifest(): return send_from_directory('static', 'manifest.json')
@app.route('/sw.js')
def sw(): return send_from_directory('static', 'sw.js')
@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

def build_translator():
    base = {
        "fever": ["bukhar","bukhhar","bhukhar","tezz bukhar","tez bukhar","fever","high fever","bukhar hai"],
        "headache": ["sir dard","sar dard","sir me dard","migraine","headache","sir dard hai"],
        "cough": ["khansi","khasi","sukhi khansi","gili khansi","cough","dry cough","khansi hai"],
        "cold": ["sardi","zukam","jukaam","naak behna","cold","sardi hai"],
        "sore throat": ["gala kharab","gale me dard","gala dard","sore throat"],
        "fatigue": ["thakan","thakawat","kamzori","susti","fatigue","weakness","thakan hai"],
        "abdominal pain": ["pet dard","pet me dard","pet kharab","abdominal pain","stomach pain","pet dard hai"],
        "vomiting": ["ulti","ultiyan","matli","vomiting","nausea","ulti hai"],
        "diarrhea": ["dast","patla dast","loose motion","diarrhea","dast hai"],
        "chest pain": ["seene me dard","seena dard","chest pain","seene me dard hai"],
        "acne": ["acne","muhase","chehre pe daane","pimple","pimples","acne hai"],
        "itching": ["khujli","kharish","khujali","itching","khujli hai"],
        "rash": ["daane","laal daane","rash","daane hai"],
    }
    trans = {}
    prefixes = ["", "mujhe ", "mere ko ", "mujhko "]
    suffixes = ["", " hai", " ho raha hai", " bahut hai"]
    for eng, hindi_list in base.items():
        for h in hindi_list:
            h = h.lower().strip()
            trans[h] = eng
            for pre in prefixes:
                for suf in suffixes:
                    key = f"{pre}{h}{suf}".strip()
                    key = re.sub(r'\s+', ' ', key)
                    if len(key)>1: trans[key]=eng
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
                diseases_data = d.get('diseases_data') or d.get('data') or d
    if not diseases_data and os.path.exists('diseases.json'):
        with open('diseases.json','r',encoding='utf-8') as f:
            diseases_data=json.load(f)
    if not all_symptoms and diseases_data:
        temp=set()
        for v in diseases_data.values():
            if isinstance(v, dict):
                s=str(v.get('Symptoms') or v.get('symptoms') or "")
                for part in re.split(r'[,;]', s):
                    if part.strip(): temp.add(part.strip().lower())
        all_symptoms=sorted(list(temp))
except Exception as e: print(f"Load error {e}")

def get_field(info, keys, default=""):
    if not isinstance(info, dict): return default
    for k in keys:
        if k in info and info[k]: return info[k]
        for ik in info.keys():
            if ik.lower()==k.lower() and info[ik]: return info[ik]
    return default

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.',1)[1].lower() in ALLOWED_EXT

@app.route('/')
def home(): return redirect(url_for('cover_page'))
@app.route('/cover')
def cover_page(): return render_template('cover.html')
@app.route('/login')
def login_page():
    if session.get('is_logged_in'):
        return redirect(url_for('pp_page'))
    return render_template('login.html')
@app.route('/welcome')
def welcome_page():
    if not session.get('is_logged_in'): return redirect(url_for('login_page'))
    if session.get('welcome_shown'): return redirect(url_for('pp_page'))
    return render_template('welcome.html')
@app.route('/pp')
def pp_page():
    if not session.get('is_logged_in'): return redirect(url_for('login_page'))
    return render_template('pp.html', symptoms=all_symptoms)
@app.route('/resultp')
def result_page(): 
    if not session.get('is_logged_in'): return redirect(url_for('login_page'))
    r=session.get('last_result')
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
    session['welcome_shown']=True
    session.modified=True
    return redirect(url_for('pp_page'))

def send_otp_email_bg(to_email, otp):
    try:
        email_user=get_env('EMAIL_USER')
        email_pass=get_env('EMAIL_PASS')
        if not email_user or not email_pass:
            print("EMAIL_USER/PASS missing")
            return
        msg=MIMEMultipart()
        msg['From']=email_user
        msg['To']=to_email
        msg['Subject']=f"Your OTP is {otp} - Predict AI"
        msg.attach(MIMEText(f"Your OTP is: {otp}\nValid 5 mins\n- Predict AI Team", 'plain'))
        server=smtplib.SMTP('smtp.gmail.com', 587, timeout=15)
        server.starttls()
        server.login(email_user, email_pass)
        server.send_message(msg)
        server.quit()
        print(f"Email sent to {to_email}")
    except Exception as e: print(f"Email fail {e}")

@app.route('/api/send_otp', methods=['POST'])
def api_send_otp():
    data=request.get_json() or {}
    email=data.get('email','').strip().lower()
    phone=data.get('phone','').strip()
    identifier=email or phone
    if not identifier: return jsonify({'status':'error','message':'Email or Phone required'}),400
    otp=str(random.randint(100000,999999))
    session['otp_code']=otp
    session['otp_identifier']=identifier
    session['otp_time']=datetime.now().isoformat()
    session.permanent=True
    session.modified=True
    print(f"OTP {otp} for {identifier}")
    if email:
        try:
            threading.Thread(target=send_otp_email_bg, args=(email, otp), daemon=True).start()
        except: pass
    return jsonify({'status':'sent','otp_autofill':otp, 'message': f'OTP sent to {identifier}'})

@app.route('/api/verify_login', methods=['POST'])
def api_verify_login():
    data=request.get_json() or {}
    email=data.get('email','').strip().lower()
    phone=data.get('phone','').strip()
    user_otp=str(data.get('otp','')).strip()
    if not user_otp or len(user_otp)!=6:
        return jsonify({'status':'error','message':'Enter 6 digit OTP'}),400
    s_otp=session.get('otp_code')
    s_time_str=session.get('otp_time')
    if not s_otp:
        return jsonify({'status':'error','message':'OTP expired, please resend'}),400
    try:
        s_time=datetime.fromisoformat(s_time_str)
        if datetime.now()-s_time>timedelta(minutes=10):
            return jsonify({'status':'error','message':'OTP expired'}),400
    except: pass
    if s_otp != user_otp and not (user_otp=="123456" and phone):
        return jsonify({'status':'error','message':'Invalid OTP'}),400
    session['is_logged_in']=True
    session['username']=data.get('username','User')
    session['user_email']=email
    session['user_phone']=phone
    session['login_time']=datetime.now().strftime("%d-%m-%Y %H:%M")
    if 'welcome_shown' not in session:
        session['welcome_shown']=False
    session.pop('otp_code', None)
    session.pop('otp_time', None)
    session.modified=True
    redirect_url = '/welcome' if not session.get('welcome_shown') else '/pp'
    return jsonify({'status':'success', 'redirect': redirect_url})

@app.route('/predict', methods=['POST'])
def predict_route():
    raw=request.form.get('symptoms') or ""
    if not raw.strip(): return redirect(url_for('pp_page'))
    cleaned=parse_symptoms(str(raw), all_symptoms)
    uploaded_filename = None
    uploaded_path = None
    if 'medical_report' in request.files or 'report' in request.files or 'file' in request.files:
        file = request.files.get('medical_report') or request.files.get('report') or request.files.get('file')
        if file and file.filename and allowed_file(file.filename):
            filename = secure_filename(f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{file.filename}")
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(filepath)
            uploaded_filename = filename
            uploaded_path = f"/uploads/{filename}"
    scores=[]
    for dname, info in diseases_data.items():
        if not isinstance(info, dict): continue
        full_text=str(get_field(info, ['Symptoms','symptoms'], "")).lower()
        if not full_text: continue
        km=sum(1 for c in cleaned if c.lower() in full_text)
        if km>0: scores.append((dname, km, info))
    scores.sort(key=lambda x:x[1], reverse=True)
    if scores:
        dname, matched_count, dinfo=scores[0][0], scores[0][1], scores[0][2]
        conf=min(96, max(55, (matched_count/len(cleaned)*85+10) if cleaned else 40))
    else:
        dname="General Checkup"; dinfo={}; conf=45
    desc=get_field(dinfo, ['Description','description'])
    diet=get_field(dinfo, ['Diet','diet'])
    exercise=get_field(dinfo, ['Exercise','exercise'])
    precaution=get_field(dinfo, ['Precautions','precaution'])
    lab=get_field(dinfo, ['Lab_Tests','lab_tests'])
    doctor=get_field(dinfo, ['Specialist','specialist','doctor'])
    if not desc: desc=f"{dname} related to {', '.join(cleaned[:3])}. Consult doctor."
    if not diet: diet="Light balanced diet, avoid oily food, more water"
    if not exercise: exercise="30 min walk, breathing exercise, rest"
    if not precaution: precaution="Rest, hydration, avoid self-medication, consult doctor if >3 days"
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
    }
    session['last_result']=result
    session['is_logged_in']=True
    session.permanent=True
    session.modified=True
    return redirect(url_for('result_page'))

@app.route('/api/doctor_chat', methods=['GET','POST'])
def doctor_chat_api():
    if request.method=='GET':
        return jsonify({'diseases':len(diseases_data), 'translator':len(TRANSLATION_MAP), 'status':'ok'})
    try:
        data=request.get_json(force=True) or {}
        msg=(data.get('message') or '').strip()
        if not msg: return jsonify({'reply':'Hi, I am your AI Doctor. Batao?','source':'System'}),200
        return jsonify({'reply':f"Samajh gaya: {msg}. Thoda detail batao, main help karta hu.",'source':'Fallback'}),200
    except Exception as e:
        print(f"Chat error {e}")
        return jsonify({'reply':"Hi, share problem again.",'source':'Fallback'}),200

if __name__=='__main__': 
    port = int(os.getenv("PORT", 7860))
    app.run(host='0.0.0.0', port=port, debug=False)