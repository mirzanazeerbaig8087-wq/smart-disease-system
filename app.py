from flask import Flask, render_template, request, jsonify, session, redirect, url_for, send_from_directory, Response
import json, pickle, gzip, os, re, difflib, random, smtplib, requests
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta
from werkzeug.utils import secure_filename
import mysql.connector
from mysql.connector import Error

otp_store = {}

app = Flask(__name__)
app.secret_key = 'smart_disease_2026_secret_key_123_final_700'

# ===== 30 DAYS LOGIN + UPLOAD FOLDER =====
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=30)
app.config['SESSION_COOKIE_NAME'] = 'smart_session'
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['SESSION_COOKIE_SECURE'] = False
app.config['SESSION_COOKIE_HTTPONLY'] = True
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'static', 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
ALLOWED_EXT = {'png','jpg','jpeg','pdf'}

@app.before_request
def make_session_permanent():
    if session.get('is_logged_in'):
        session.permanent = True

@app.route('/manifest.json')
def manifest(): return send_from_directory('static', 'manifest.json')
@app.route('/sw.js')
def sw(): return send_from_directory('static', 'sw.js')
@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

# ===== 700+ TRANSLATOR MAP - FINAL =====
def build_translator():
    # 100+ English symptoms x 7-8 Hindi variants = 700+
    base = {
        "fever": ["bukhar","bukhhar","bhukhar","tezz bukhar","tez bukhar","halka bukhar","bukhar thand","thand ke sath bukhar","kapkapahat","fever","high fever","bukhar hai"],
        "headache": ["sir dard","sar dard","sir me dard","adha sir dard","sir bhari","migraine","headache","sir dard hai"],
        "cough": ["khansi","khasi","sukhi khansi","gili khansi","khoon wali khansi","cough","dry cough","khansi hai"],
        "cold": ["sardi","zukam","jukaam","naak behna","naak band","cheek","cold","sardi hai"],
        "sore throat": ["gala kharab","gale me dard","gala dard","gala kharash","sore throat"],
        "fatigue": ["thakan","thakawat","kamzori","susti","fatigue","weakness","thakan hai"],
        "abdominal pain": ["pet dard","pet me dard","pet kharab","pet me jalan","gas","abdominal pain","stomach pain","pet dard hai"],
        "vomiting": ["ulti","ultiyan","matli","jeee ghabrana","vomiting","nausea","ulti hai"],
        "diarrhea": ["dast","patla dast","loose motion","diarrhea","dast hai"],
        "constipation": ["kabz","kabj","pet saaf nahi","constipation","kabz hai"],
        "chest pain": ["seene me dard","seena dard","chati me dard","chest pain","seene me dard hai"],
        "dizziness": ["chakkar","chakkar aana","sir ghumna","dizziness","chakkar hai"],
        "joint pain": ["jodo me dard","ghutno me dard","gathiya","joint pain","knee pain"],
        "back pain": ["kamar dard","peeth dard","back pain","kamar dard hai"],
        "muscle pain": ["badan dard","body pain","muscle pain","badan dard hai"],
        "shortness of breath": ["saans phoolna","saans lene me dikkat","dum ghutna","shortness of breath","saans phool rahi"],
        "weight loss": ["wazan kam","patla hona","weight loss","wazan kam ho raha"],
        "weight gain": ["wazan badhna","mota hona","weight gain"],
        "loss of appetite": ["bhukh kam","bhukh nahi","loss of appetite","bhukh nahi lag rahi"],
        "itching": ["khujli","kharish","khujali","itching","khujli hai"],
        "rash": ["daane","laal daane","rash","daane hai"],
        "swelling": ["soojan","sujan","pair me soojan","swelling","soojan hai"],
        "numbness": ["sunn hona","haath sunn","pair sunn","numbness"],
        "tingling": ["jhanjhanahat","tingling","haath me jhanjhan"],
        "palpitations": ["dil ki dhadkan tez","palpitations","dil tez dhadakna"],
        "rapid heartbeat": ["dil tez","rapid heartbeat","heartbeat fast"],
        "wheezing": ["seeti wali saans","wheezing","saans me seeti"],
        "night sweats": ["raat me pasina","night sweats","raat ko pasina"],
        "shivering": ["kapkapi","thand se kaapna","shivering","kaap raha"],
        "tremor": ["kampan","haath kaapna","tremor"],
        "seizure": ["daura","mirgi ka daura","seizure","jhatka"],
        "fainting": ["behosh","chakkar kha ke girna","fainting"],
        "memory loss": ["yaad bhoolna","memory loss","bhoolne ki bimari"],
        "confusion": ["ghabrahat","confusion","samajh nahi aana"],
        "depression": ["udaasi","depression","man udaas","tension"],
        "anxiety": ["ghabrahat","bechaini","anxiety","dar lagna"],
        "insomnia": ["neend nahi","neend kam","insomnia","neend nahi aati"],
        "blurred vision": ["dhundla dikhna","blurred vision","aankh dhundli"],
        "red eyes": ["laal aankh","aankh laal","red eyes"],
        "eye pain": ["aankh me dard","eye pain","aankh dukhna"],
        "ear pain": ["kaan me dard","ear pain","kaan dukhna"],
        "hearing loss": ["sunai kam","sunna band","hearing loss"],
        "nosebleed": ["naak se khoon","nosebleed","naak se khoon aana"],
        "loss of smell": ["sunghna band","smell nahi aana","loss of smell"],
        "toothache": ["daant dard","daat me dard","toothache"],
        "neck stiffness": ["gardan akadna","neck stiffness","gardan me dard"],
        "hair loss": ["baal jhadna","baal girna","hair loss"],
        "swollen glands": ["giltyan","gale me gilty","swollen glands"],
        "blood in stool": ["potty me khoon","khoon ki potty","blood in stool"],
        "yellow skin": ["peela padna","peeli chamdi","yellow skin","piliya"],
        "pale skin": ["peela padna","pale skin","khoon ki kami"],
        "acidity": ["khatta paani","jalan","acidity","pet me jalan"],
        "indigestion": ["hazam nahi","bad-hazmi","indigestion"],
        "burning urination": ["peshaab me jalan","jalan ke sath peshaab","burning urination"],
        "frequent urination": ["baar baar peshaab","frequent urination","peshaab baar baar"],
        "excessive thirst": ["bahut pyaas","pyaas zyada","excessive thirst"],
        "dark urine": ["kaala peshaab","gehra peshaab","dark urine"],
        "blood in urine": ["peshaab me khoon","blood in urine","peshaab me khoon aana"],
        "hiccups": ["hichki","hichki lagna","hiccups"],
        "snoring": ["kharrate","kharate lena","snoring"],
        "yellow eyes": ["aankh peeli","yellow eyes","piliya aankh"],
        "liver lump": ["liver me gath","pet me gath","liver lump"],
        "brittle nails": ["nakhun tootna","brittle nails","nakhun kharab"],
        "double vision": ["do do dikhna","double vision"],
        "loss of taste": ["swaad nahi","taste nahi","loss of taste"],
        "dry mouth": ["munh sukhna","dry mouth","munh sukha"],
        "mouth ulcer": ["munh me chhale","chhale","mouth ulcer"],
        "bleeding gums": ["masudo se khoon","bleeding gums","masudo me khoon"],
    }
    trans = {}
    prefixes = ["", "mujhe ", "mere ko ", "mujhko ", "muje "]
    suffixes = ["", " hai", " ho raha hai", " ho rahi hai", " bahut hai"]
    for eng, hindi_list in base.items():
        for h in hindi_list:
            h = h.lower().strip()
            trans[h] = eng
            for pre in prefixes:
                for suf in suffixes:
                    key = f"{pre}{h}{suf}".strip()
                    key = re.sub(r'\s+', ' ', key)
                    if len(key)>1: trans[key]=eng
    # Extra english variations
    extra = ["fever","high fever","low fever","cough","dry cough","wet cough","cold","runny nose","sore throat","headache","migraine","dizziness","fatigue","weakness","body pain","muscle pain","joint pain","knee pain","back pain","chest pain","abdominal pain","stomach pain","nausea","vomiting","diarrhea","constipation","loss of appetite","weight loss","weight gain","burning urination","frequent urination","blood in urine","itching","rash","swelling","numbness","tingling","shortness of breath","wheezing","palpitations","anxiety","depression","insomnia","blurred vision","red eyes","ear pain","nosebleed","toothache","hair loss","yellow skin","acidity","hiccups","snoring"]
    for s in extra:
        trans[s]=s
        trans[f"i have {s}"]=s
        trans[f"mujhe {s} hai"]=s
    print(f"Translator built {len(trans)} entries")  # ~800+
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
                if 'all_symptoms' in d: all_symptoms = d['all_symptoms']
    if not diseases_data and os.path.exists('diseases.json'):
        with open('diseases.json','r',encoding='utf-8') as f:
            diseases_data=json.load(f)
    if not all_symptoms and os.path.exists('symptoms.pkl'):
        with open('symptoms.pkl','rb') as f: all_symptoms=pickle.load(f)
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

def generate_ai_details(disease_name, symptoms_list):
    GEMINI_KEY = os.getenv('GEMINI_API_KEY') or os.getenv('GOOGLE_API_KEY')
    GROQ_KEY = os.getenv('GROQ_API_KEY')
    prompt = f"Disease: {disease_name}, Symptoms: {','.join(symptoms_list)}. Give JSON only: {{\"Description\":\"2 lines\",\"Diet\":\"what to eat\",\"Exercise\":\"2 exercises\",\"Precautions\":\"2 precautions\",\"Lab_Tests\":[\"CBC\",\"X-Ray\"],\"Specialist\":\"doctor type\"}}"
    if GROQ_KEY:
        try:
            r=requests.post("https://api.groq.com/openai/v1/chat/completions", headers={"Authorization": f"Bearer {GROQ_KEY}","Content-Type":"application/json"}, json={"model":"llama-3.1-8b-instant","messages":[{"role":"user","content":prompt}],"temperature":0.5,"max_tokens":500}, timeout=15)
            txt=r.json()['choices'][0]['message']['content']
            m=re.search(r'\{.*\}', txt, re.DOTALL)
            if m: return json.loads(m.group())
        except: pass
    if GEMINI_KEY:
        try:
            url=f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_KEY}"
            r=requests.post(url, json={"contents":[{"parts":[{"text":prompt}]}],"generationConfig":{"temperature":0.5,"maxOutputTokens":500}}, timeout=15)
            txt=r.json()['candidates'][0]['content']['parts'][0]['text']
            m=re.search(r'\{.*\}', txt, re.DOTALL)
            if m: return json.loads(m.group())
        except: pass
    return None

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.',1)[1].lower() in ALLOWED_EXT

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
    session['is_logged_in']=True
    session.permanent=True
    return redirect(url_for('pp_page'))
@app.route('/wellbeing')
@app.route('/well-being')
@app.route('/well_being')
def wellbeing_page():
    if not session.get('is_logged_in'): return redirect(url_for('login_page'))
    if os.path.exists('templates/wellbeing.html'): return render_template('wellbeing.html')
    elif os.path.exists('templates/well_being.html'): return render_template('well_being.html')
    else: return render_template('pp.html', symptoms=all_symptoms)
@app.route('/my-profile')
@app.route('/my_profile')
@app.route('/profile')
def my_profile_page():
    if not session.get('is_logged_in'): return redirect(url_for('login_page'))
    user_data={'username':session.get('username','User'),'email':session.get('user_email',''),'phone':session.get('user_phone',''),'login_time':session.get('login_time','')}
    if os.path.exists('templates/my_profile.html'): return render_template('my_profile.html', user=user_data)
    else:
        return f"""
        <html><head><meta name='viewport' content='width=device-width, initial-scale=1'>
        <style>body{{font-family:Arial;padding:20px;max-width:500px;margin:auto}} .card{{border:1px solid #ddd;padding:20px;border-radius:10px}} button{{background:#4CAF50;color:white;padding:10px 20px;border:none;border-radius:5px;width:100%;margin:5px 0}}</style>
        </head><body>
        <h2>👤 My Profile</h2>
        <div class='card'><p><b>Name:</b> {user_data['username']}</p><p><b>Email:</b> {user_data['email']}</p><p><b>Phone:</b> {user_data['phone']}</p><p><b>Login: 30 Days</b></p></div>
        <button onclick="window.location.href='/logout'">🔄 Change ID - Logout & Login with New ID</button>
        <button onclick="window.location.href='/pp'">Back</button></body></html>
        """

def send_otp_email(to_email, otp):
    try:
        email_user=os.getenv('EMAIL_USER') or os.getenv('MAIL_USER')
        email_pass=os.getenv('EMAIL_PASS') or os.getenv('MAIL_PASS')
        if not email_user or not email_pass: return False
        body=f"Your OTP is: {otp}\nValid for 5 minutes."
        msg=MIMEMultipart()
        msg['From']=email_user
        msg['To']=to_email
        msg['Subject']="Your OTP Code"
        msg.attach(MIMEText(body, 'plain'))
        server=smtplib.SMTP('smtp.gmail.com', 587, timeout=15)
        server.starttls()
        server.login(email_user, email_pass)
        server.send_message(msg)
        server.quit()
        return True
    except Exception as e:
        print(f"Email fail {e}")
        return False

@app.route('/api/send_otp', methods=['POST'])
def api_send_otp():
    data=request.get_json() or {}
    email=data.get('email','').strip().lower()
    phone=data.get('phone','').strip()
    identifier=email or phone
    if not identifier: return jsonify({'status':'error','message':'Email required'}),400
    otp=str(random.randint(100000,999999))
    session['otp_code']=otp
    session['otp_email']=email
    session['otp_phone']=phone
    session['otp_time']=datetime.now().isoformat()
    session.permanent=True
    otp_store[identifier]={'otp':otp,'time':datetime.now()}
    print(f"OTP {otp} for {identifier}")
    email_sent=True
    if email: email_sent=send_otp_email(email, otp)
    return jsonify({'status':'sent','otp_autofill':otp, 'email_sent':email_sent})

@app.route('/api/verify_login', methods=['POST'])
def api_verify_login():
    data=request.get_json() or {}
    email=data.get('email','').strip().lower()
    phone=data.get('phone','').strip()
    user_otp=str(data.get('otp','')).strip()
    identifier=email or phone
    target=None
    s_otp=session.get('otp_code')
    s_time_str=session.get('otp_time')
    if s_otp and s_time_str:
        try:
            s_time=datetime.fromisoformat(s_time_str)
            if datetime.now()-s_time<timedelta(minutes=5) and s_otp==user_otp:
                target={'otp':s_otp,'time':s_time}
        except: pass
    if not target:
        target=otp_store.get(identifier) or otp_store.get(email) or otp_store.get(phone)
    if not target: return jsonify({'status':'error','message':'OTP not found'}),400
    if datetime.now()-target['time']>timedelta(minutes=5): return jsonify({'status':'error','message':'OTP expired'}),400
    if target['otp']!=user_otp: return jsonify({'status':'error','message':'Invalid OTP'}),400
    session.clear()
    session.permanent=True
    session['is_logged_in']=True
    session['username']=data.get('username','User')
    session['user_email']=email
    session['user_phone']=phone
    session['login_time']=datetime.now().strftime("%d-%m-%Y %H:%M")
    session['welcome_shown']=False
    return jsonify({'status':'success'})

# ===== PREDICT WITH FILE UPLOAD - REPORT PDF KE SAATH =====
@app.route('/predict', methods=['POST'])
def predict_route():
    raw=request.form.get('symptoms') or ""
    if not raw.strip(): return redirect(url_for('pp_page'))
    cleaned=parse_symptoms(str(raw), all_symptoms)
    
    # File upload handle
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
            print(f"File saved {filepath}")

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

    ai_data=None
    if not desc or not diet:
        ai_data=generate_ai_details(dname, cleaned)
    if ai_data:
        desc=desc or ai_data.get('Description','')
        diet=diet or ai_data.get('Diet','')
        exercise=exercise or ai_data.get('Exercise','')
        precaution=precaution or ai_data.get('Precautions','')
        if not lab: lab=ai_data.get('Lab_Tests',[])
        doctor=doctor or ai_data.get('Specialist','')

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
        'uploaded_file': uploaded_filename, 'uploaded_path': uploaded_path
    }
    
    session['last_result']=result
    session['is_logged_in']=True
    session.permanent=True
    return redirect(url_for('result_page'))

@app.route('/api/doctor_chat', methods=['GET','POST'])
def doctor_chat_api():
    if request.method=='GET':
        return jsonify({'gemini':bool(os.getenv('GEMINI_API_KEY')), 'groq':bool(os.getenv('GROQ_API_KEY')), 'diseases':len(diseases_data), 'translator':len(TRANSLATION_MAP), 'status':'ok'})
    try:
        data=request.get_json(force=True) or {}
        msg=(data.get('message') or '').strip()
        if not msg: return jsonify({'reply':'Hi, I am your AI Doctor. Batao?','source':'System'}),200
        GEMINI_KEY=os.getenv('GEMINI_API_KEY') or os.getenv('GOOGLE_API_KEY')
        GROQ_KEY=os.getenv('GROQ_API_KEY')
        if GEMINI_KEY:
            for model in ["gemini-1.5-flash","gemini-1.5-flash-latest"]:
                try:
                    url=f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={GEMINI_KEY}"
                    prompt=f"You are Predict AI, friendly Indian doctor. User: {msg}. 4-5 lines advice."
                    r=requests.post(url, json={"contents":[{"parts":[{"text":prompt}]}],"generationConfig":{"temperature":0.7,"maxOutputTokens":600}}, timeout=25)
                    j=r.json()
                    if 'candidates' in j:
                        return jsonify({'reply':j['candidates'][0]['content']['parts'][0]['text'],'source':'Gemini'}),200
                except: continue
        if GROQ_KEY:
            try:
                r=requests.post("https://api.groq.com/openai/v1/chat/completions", headers={"Authorization": f"Bearer {GROQ_KEY}","Content-Type":"application/json"}, json={"model":"llama-3.1-8b-instant","messages":[{"role":"system","content":"You are Predict AI"},{"role":"user","content":msg}],"temperature":0.7,"max_tokens":800}, timeout=20)
                j=r.json()
                if 'choices' in j: return jsonify({'reply':j['choices'][0]['message']['content'],'source':'Groq'}),200
            except: pass
        return jsonify({'reply':f"Samajh gaya: {msg}. Detail batao.",'source':'Fallback'}),200
    except: return jsonify({'reply':"Hi, share problem again.",'source':'Fallback'}),200

if __name__=='__main__': 
    app.run(host='0.0.0.0',port=5000,debug=True)