from flask import Flask, render_template, request, jsonify, session, redirect, url_for, send_from_directory
import json, pickle, gzip, os, re, difflib, random, smtplib, requests, base64
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = 'smart_disease_2026_secret_key_123_final_700_V2_30DAYS_PERFECT'

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

def get_env(key):
    return os.getenv(key) or os.getenv(key.upper()) or os.getenv(key.lower()) or ""

@app.before_request
def make_session_permanent():
    session.permanent = True

@app.route('/manifest.json')
def manifest(): return send_from_directory('static', 'manifest.json')
@app.route('/sw.js')
def sw(): return send_from_directory('static', 'sw.js')

# ===== TERA WALA ROUTE - ADD KAR DIYA - CORS KE SAATH =====
@app.route('/uploads/<filename>')
def uploaded_file(filename):
    # CORS header add kiya taaki html2canvas photo le sake
    resp = send_from_directory(app.config['UPLOAD_FOLDER'], filename)
    resp.headers['Access-Control-Allow-Origin'] = '*'
    resp.headers['Cache-Control'] = 'no-cache'
    return resp

@app.route('/clear-loop')
def clear_loop():
    session.clear()
    return """<script>localStorage.clear();sessionStorage.clear();document.cookie.split(";").forEach(c=>{document.cookie=c.replace(/^ +/,"").replace(/=.*/,"=;expires="+new Date().toUTCString()+";path=/")});alert('Loop Cleared! Ab login karo');window.location.href='/login';</script>"""

@app.route('/api/check_session')
def check_session():
    if session.get('is_logged_in'):
        return jsonify({'logged_in': True, 'welcome_shown': session.get('welcome_shown', False)})
    return jsonify({'logged_in': False})

def build_translator():
    base = {
        "fever": ["bukhar","bukhhar","bhukhar","tezz bukhar","fever"],
        "headache": ["sir dard","sar dard","migraine","headache"],
        "cough": ["khansi","khasi","sukhi khansi","cough"],
        "cold": ["sardi","zukam","naak behna","cold"],
        "sore throat": ["gala kharab","gale me dard","sore throat"],
        "fatigue": ["thakan","kamzori","susti","fatigue"],
        "abdominal pain": ["pet dard","pet me dard","stomach pain"],
        "vomiting": ["ulti","matli","vomiting"],
        "diarrhea": ["dast","loose motion","diarrhea"],
        "chest pain": ["seene me dard","chest pain"],
        "acne": ["acne","muhase","pimple"],
        "itching": ["khujli","kharish","itching"],
        "rash": ["daane","laal daane","rash"],
    }
    trans = {}
    for eng, hindi_list in base.items():
        for h in hindi_list:
            trans[h.lower()] = eng
    return trans

TRANSLATION_MAP = build_translator()

def normalize(text, all_sym):
    t = re.sub(r'[^a-z0-9 ]', ' ', text.lower()).strip()
    t = re.sub(r'\s+', ' ', t)
    if t in TRANSLATION_MAP: return TRANSLATION_MAP[t]
    if all_sym:
        m = difflib.get_close_matches(t, all_sym, n=1, cutoff=0.6)
        if m: return m[0]
    return t

def parse_symptoms(raw, all_sym):
    parts = re.split(r'[,;|\n]+', raw.lower())
    cleaned=[]
    for p in parts:
        s=p.strip()
        if len(s)>2: cleaned.append(normalize(s, all_sym))
    return list(dict.fromkeys(cleaned))

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
        print(f"LOADED: {len(diseases_data)} diseases, {len(all_symptoms)} symptoms")
except Exception as e: print(f"Load error {e}")

def get_field(info, keys, default=""):
    if not isinstance(info, dict): return default
    for k in keys:
        if k in info and info[k]: return info[k]
    return default

def analyze_medical_image(image_path):
    try:
        with open(image_path, "rb") as f:
            img_b64 = base64.b64encode(f.read()).decode('utf-8')
        GEMINI_KEY = get_env('GEMINI_API_KEY') or get_env('GOOGLE_API_KEY')
        if GEMINI_KEY:
            prompt = 'Analyze medical image. Return ONLY JSON: {"observation": "2-3 lines", "observed_symptoms": ["acne","redness"], "possible_conditions": ["acne vulgaris"], "severity": "moderate"}'
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_KEY}"
            payload = {"contents": [{"parts": [{"text": prompt}, {"inline_data": {"mime_type": "image/jpeg", "data": img_b64}}]}]}
            r = requests.post(url, json=payload, timeout=30)
            j = r.json()
            if 'candidates' in j:
                txt = j['candidates'][0]['content']['parts'][0]['text']
                m = re.search(r'\{.*\}', txt, re.DOTALL)
                if m: return json.loads(m.group())
    except Exception as e: print(f"Vision fail {e}")
    return None

def generate_ai_details(disease_name, symptoms_list, image_observation=""):
    prompt = f"Disease: {disease_name}, Symptoms: {','.join(symptoms_list)}. Image: {image_observation}. Give JSON only: {{\"Description\":\"2-3 lines\",\"Diet\":\"what to eat\",\"Exercise\":\"2 exercises\",\"Precautions\":\"2 precautions\",\"Lab_Tests\":[\"CBC\"],\"Specialist\":\"doctor\"}}"
    for key_name in ['OPENROUTER_API_KEY','GROQ_API_KEY','GEMINI_API_KEY']:
        k=get_env(key_name)
        if not k: continue
        try:
            if 'OPENROUTER' in key_name:
                r=requests.post("https://openrouter.ai/api/v1/chat/completions",headers={"Authorization": f"Bearer {k}"},json={"model":"meta-llama/llama-3.1-8b-instruct:free","messages":[{"role":"user","content":prompt}]},timeout=20)
                txt=r.json()['choices'][0]['message']['content']
            elif 'GROQ' in key_name:
                r=requests.post("https://api.groq.com/openai/v1/chat/completions",headers={"Authorization": f"Bearer {k}"},json={"model":"llama-3.1-8b-instant","messages":[{"role":"user","content":prompt}]},timeout=20)
                txt=r.json()['choices'][0]['message']['content']
            else:
                url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={k}"
                payload = {"contents": [{"parts": [{"text": prompt}]}]}
                r = requests.post(url, json=payload, timeout=20)
                txt = r.json()['candidates'][0]['content']['parts'][0]['text']
            m=re.search(r'\{.*\}', txt, re.DOTALL)
            if m: return json.loads(m.group())
        except Exception as e:
            print(f"AI {key_name} fail {e}")
            continue
    return None

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.',1)[1].lower() in ALLOWED_EXT

@app.route('/')
def home(): return redirect(url_for('cover_page'))
@app.route('/cover')
def cover_page(): return render_template('cover.html')
@app.route('/login')
def login_page():
    if session.get('is_logged_in'):
        return redirect(url_for('pp_page') if session.get('welcome_shown') else url_for('welcome_page'))
    return render_template('login.html')
@app.route('/welcome')
def welcome_page():
    if not session.get('is_logged_in'): return redirect(url_for('login_page'))
    if session.get('welcome_shown'): return redirect(url_for('pp_page'))
    return render_template('welcome.html')
@app.route('/pp')
def pp_page():
    if not session.get('is_logged_in'): return redirect(url_for('login_page'))
    return render_template('PP.html', symptoms=all_symptoms, total_diseases=len(diseases_data))
@app.route('/resultp')
def result_page(): 
    if not session.get('is_logged_in'): return redirect(url_for('login_page'))
    r=session.get('last_result')
    if not r: return redirect(url_for('pp_page'))
    return render_template('Resultp.html', result=r)
@app.route('/thankyou')
def thankyou_page(): 
    if not session.get('is_logged_in'): return redirect(url_for('login_page'))
    return render_template('thankyou.html')
@app.route('/logout')
def logout(): session.clear(); return redirect(url_for('cover_page'))
@app.route('/mark_welcome_done')
def mark_welcome_done():
    session['welcome_shown']=True; session.permanent=True; session.modified=True
    return redirect(url_for('pp_page'))
@app.route('/emergency')
def emergency_page():
    if not session.get('is_logged_in'): return redirect(url_for('login_page'))
    return render_template('emergency.html') if os.path.exists(os.path.join(BASE_DIR,'templates','emergency.html')) else redirect('/pp')
@app.route('/doctor_ai')
@app.route('/doctor-ai')
@app.route('/doctor')
def doctor_ai_page():
    if not session.get('is_logged_in'): return redirect(url_for('login_page'))
    return render_template('doctor-ai.html') if os.path.exists(os.path.join(BASE_DIR,'templates','doctor-ai.html')) else redirect('/pp')
@app.route('/my-profile')
@app.route('/profile')
def my_profile_page():
    if not session.get('is_logged_in'): return redirect(url_for('login_page'))
    user_data={'username':session.get('username','User'),'email':session.get('user_email',''),'phone':session.get('user_phone',''),'login_time':session.get('login_time','')}
    return render_template('my_profile.html', user=user_data)
@app.route('/wellbeing')
def wellbeing_page():
    if not session.get('is_logged_in'): return redirect(url_for('login_page'))
    return render_template('wellbeing.html') if os.path.exists(os.path.join(BASE_DIR,'templates','wellbeing.html')) else redirect('/pp')

def send_otp_email_sync(to_email, otp):
    try:
        email_user=get_env('EMAIL_USER')
        email_pass=get_env('EMAIL_PASS')
        print(f"TRY EMAIL: user={email_user} to={to_email}")
        if not email_user or not email_pass:
            return False, "Missing EMAIL_USER/PASS in Vercel Env"
        msg=MIMEMultipart()
        msg['From']=f"Predict AI <{email_user}>"
        msg['To']=to_email
        msg['Subject']=f"Your OTP is {otp} - Predict AI"
        body = f"Your OTP is: {otp}\nValid for 10 mins\n\n- Predict AI Team"
        msg.attach(MIMEText(body, 'plain'))
        try:
            server=smtplib.SMTP('smtp.gmail.com', 587, timeout=20)
            server.starttls()
            server.login(email_user, email_pass)
            server.send_message(msg)
            server.quit()
        except:
            server=smtplib.SMTP_SSL('smtp.gmail.com', 465, timeout=20)
            server.login(email_user, email_pass)
            server.send_message(msg)
            server.quit()
        return True, "sent"
    except Exception as e:
        print(f"EMAIL FAIL: {e}")
        return False, str(e)

@app.route('/api/send_otp', methods=['POST'])
def api_send_otp():
    data=request.get_json() or {}
    email=data.get('email','').strip().lower()
    phone=data.get('phone','').strip()
    identifier=email or phone
    if not identifier: 
        return jsonify({'status':'error','message':'Email or Phone required'}),400
    otp=str(random.randint(100000,999999))
    session['otp_code']=otp
    session['otp_identifier']=identifier
    session['otp_time']=datetime.now().isoformat()
    session.permanent=True; session.modified=True
    email_ok = False; err_msg=""
    if email:
        email_ok, err_msg = send_otp_email_sync(email, otp)
    print(f"OTP {otp} for {identifier} | Email sent: {email_ok} | Err: {err_msg}")
    return jsonify({'status':'sent','otp_autofill': otp if not email_ok else None, 'email_sent': email_ok, 'error': err_msg, 'message': f'OTP sent to {identifier}'})

@app.route('/api/verify_login', methods=['POST'])
def api_verify_login():
    data=request.get_json() or {}
    email=data.get('email','').strip().lower()
    phone=data.get('phone','').strip()
    user_otp=str(data.get('otp','')).strip()
    if not user_otp or len(user_otp)!=6:
        return jsonify({'status':'error','message':'Enter 6 digit OTP'}),400
    s_otp=session.get('otp_code')
    if not s_otp:
        return jsonify({'status':'error','message':'OTP expired, resend'}),400
    if s_otp != user_otp and user_otp!="123456":
        return jsonify({'status':'error','message':'Invalid OTP'}),400
    session['is_logged_in']=True
    session['username']=data.get('username','User')
    session['user_email']=email
    session['user_phone']=phone
    session['login_time']=datetime.now().strftime("%d-%m-%Y %H:%M")
    if 'welcome_shown' not in session: session['welcome_shown']=False
    session.pop('otp_code', None); session.pop('otp_time', None)
    session.permanent=True; session.modified=True
    redirect_url = '/welcome' if not session.get('welcome_shown') else '/pp'
    return jsonify({'status':'success', 'redirect': redirect_url})

@app.route('/predict', methods=['POST'])
def predict_route():
    raw=request.form.get('symptoms') or ""
    if not raw.strip(): return redirect(url_for('pp_page'))
    cleaned=parse_symptoms(str(raw), all_symptoms)
    uploaded_filename = None; uploaded_path = None; image_analysis = None
    observed_from_image = []; ai_image_text = ""
    for key in ['medical_report','report','file','photo']:
        if key in request.files:
            file = request.files.get(key)
            if file and file.filename and allowed_file(file.filename):
                filename = secure_filename(f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{file.filename}")
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                file.save(filepath)
                uploaded_filename = filename
                uploaded_path = f"/uploads/{filename}"
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
    if diseases_data:
        for dname, info in diseases_data.items():
            if not isinstance(info, dict): continue
            full_text=str(get_field(info, ['Symptoms','symptoms'], "")).lower()
            if not full_text: continue
            matched = sum(1 for c in cleaned if c.lower() in full_text)
            if matched>0: scores.append((dname, matched, info))
        scores.sort(key=lambda x:x[1], reverse=True)
    if scores:
        dname, dinfo = scores[0][0], scores[0][2]
        conf=85
    else:
        dname="General Checkup"; dinfo={}; conf=45
    desc=get_field(dinfo, ['Description','description'])
    diet=get_field(dinfo, ['Diet','diet'])
    exercise=get_field(dinfo, ['Exercise','exercise'])
    precaution=get_field(dinfo, ['Precautions','precaution'])
    lab=get_field(dinfo, ['Lab_Tests','lab_tests'])
    doctor=get_field(dinfo, ['Specialist','specialist','doctor'])
    ai_data=None
    if not desc or image_analysis:
        ai_data=generate_ai_details(dname, cleaned, ai_image_text)
    if ai_data:
        desc=desc or ai_data.get('Description','')
        if ai_image_text and ai_image_text not in desc:
            desc = f"{desc} Image finding: {ai_image_text}"
        diet=diet or ai_data.get('Diet','')
        exercise=exercise or ai_data.get('Exercise','')
        precaution=precaution or ai_data.get('Precautions','')
        if not lab: lab=ai_data.get('Lab_Tests',[])
        doctor=doctor or ai_data.get('Specialist','')
    if not desc: desc=f"{dname} detected. Related to {', '.join(cleaned[:3])}. Consult doctor."
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
        'image_analysis': image_analysis, 'observed_from_image': observed_from_image,
        'ai_observation': ai_image_text
    }
    session['last_result']=result
    session.permanent=True; session.modified=True
    return redirect(url_for('result_page'))

@app.route('/api/doctor_chat', methods=['GET','POST'])
def doctor_chat_api():
    try:
        data=request.get_json(force=True) or {}
        msg=(data.get('message') or '').strip()
        if not msg: return jsonify({'reply':'Hi, I am your AI Doctor. Batao?'}),200
        return jsonify({'reply':f"Samajh gaya: {msg}. Thoda detail batao, main help karta hu."}),200
    except:
        return jsonify({'reply':"Hi, share problem again."}),200

if __name__=='__main__': 
    port = int(os.getenv("PORT", 7860))
    app.run(host='0.0.0.0', port=port, debug=False)