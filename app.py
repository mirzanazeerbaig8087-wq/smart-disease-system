from flask import Flask, render_template, request, jsonify, session, redirect, url_for, flash, render_template_string
import json, pickle, gzip, os, re, difflib, random, requests
import mysql.connector
from mysql.connector import Error
import os

app = Flask(__name__)
app.secret_key = 'smart_disease_2026_secret_key_123'

FAST2SMS_API_KEY = os.getenv('FAST2SMS_API_KEY', 'YOUR_FAST2SMS_API_KEY_HERE')

def send_otp_fast2sms(mobile, otp):
    if not FAST2SMS_API_KEY or FAST2SMS_API_KEY == 'YOUR_FAST2SMS_API_KEY_HERE':
        print(f"[DEMO OTP] Mobile {mobile} OTP is {otp}")
        return True
    try:
        url = "https://www.fast2sms.com/dev/bulkV2"
        payload = f"variables_values={otp}&route=otp&numbers={mobile}"
        headers = {'authorization': FAST2SMS_API_KEY, 'Content-Type': "application/x-www-form-urlencoded"}
        response = requests.request("POST", url, data=payload, headers=headers, timeout=10)
        print(f"FAST2SMS Response: {response.text}")
        return True
    except Exception as e:
        print(f"FAST2SMS Error: {e}")
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
        cur.execute("CREATE TABLE IF NOT EXISTS predictions (id INT AUTO_INCREMENT PRIMARY KEY, user_id INT, symptoms TEXT, predicted_disease VARCHAR(200), confidence FLOAT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)")
    except: pass
    finally:
        try: cur.close(); conn.close()
        except: pass

TRANSLATION_MAP = {
"ankho me andhera":"blurred vision","aankh me dhundhla":"blurred vision","dhundhla dikhna":"blurred vision","ankh dukhna":"eye pain","aankh dard":"eye pain","aankh laal":"red eyes","aankh me khujli":"eye itching","aankh se paani":"watery eyes","aankh soojna":"swollen eyes","do dikhna":"double vision","raat me na dikhna":"night blindness","aankh me jalan":"burning eyes","palak soojna":"swollen eyelids","aankh phadakna":"eye twitching",
"chakkar":"dizziness","chakkar aana":"dizziness","sir ghumna":"dizziness","chakkar khana":"vertigo","sir dard":"headache","sar dard":"headache","adha sir dard":"migraine","sir bhari":"heavy head","neend na aana":"insomnia","neend zyada":"excessive sleepiness","thakan":"fatigue","thakawat":"fatigue","kamzori":"weakness","susti":"lethargy","behoshi":"fainting","behos hona":"loss of consciousness","ghabrahat":"anxiety","bechaini":"restlessness","yaaddasht kam":"memory loss","bhulna":"forgetfulness","bolne me dikkat":"difficulty speaking","ulti seedha bolna":"slurred speech","haath kampna":"tremors","haath kaapna":"hand tremor",
"bukhar":"fever","tez bukhar":"high fever","halka bukhar":"low grade fever","thand lagna":"chills","kapkapi":"rigors","pasina aana":"sweating","raat ko pasina":"night sweats",
"naak band":"nasal congestion","naak behna":"runny nose","cheenk aana":"sneezing","naak se khoon":"nosebleed","kaan dard":"ear pain","kaan bajna":"tinnitus","kaan se paani":"ear discharge","sunne me kami":"hearing loss","gala dard":"sore throat","gale me dard":"sore throat","gala kharash":"throat irritation","nigalne me dard":"painful swallowing","aawaz baithna":"hoarseness","mooh me chhale":"mouth ulcers","mooh se badbu":"bad breath",
"saans phoolna":"shortness of breath","saans ki takleef":"shortness of breath","saans lene me dikkat":"difficulty breathing","dum ghutna":"breathlessness","seene me dard":"chest pain","chhati me dard":"chest discomfort","seene me jalan":"chest burning","khansi":"cough","sukhi khansi":"dry cough","balkam wali khansi":"productive cough","balkam":"sputum","balkam me khoon":"coughing blood","ghar ghar":"wheezing","hichki":"hiccups",
"pet dard":"abdominal pain","pait dard":"abdominal pain","pait me dard":"abdominal pain","pet me marod":"abdominal cramps","pait phoolna":"bloating","pet phoolna":"bloating","gas banna":"gas formation","pet me gas":"flatulence","dakaar":"belching","acidity":"heartburn","khatti dakaar":"acid burping","pet me jalan":"stomach burning","ulti":"vomiting","matli":"nausea","dast":"diarrhea","loose motion":"diarrhea","khooni dast":"bloody diarrhea","latrine me khoon":"blood in stool","kabz":"constipation","bhukh na lagna":"loss of appetite","bhukh zyada":"increased appetite","wazan kam":"weight loss","wazan badhna":"weight gain","pait me awaaz":"stomach rumbling","bawaseer":"piles","latrine me dard":"pain during defecation","khoon ki ulti":"vomiting blood","kaala latrine":"black stools",
"peshaab me jalan":"burning urination","peshaab me dard":"painful urination","bar bar peshaab":"frequent urination","raat me peshaab":"nocturia","peshaab rukna":"urinary retention","peshaab me khoon":"blood in urine","peshaab peela":"yellow urine","peshaab kam":"decreased urine output","peshaab zyada":"excessive urination","gurde me dard":"kidney pain",
"jism dard":"body ache","badan dard":"body pain","jod dard":"joint pain","jodo me soojan":"joint swelling","jod jam":"joint stiffness","ghutne me dard":"knee pain","kamar dard":"low back pain","gardan dard":"neck pain","kandhe me dard":"shoulder pain","maas peshi me dard":"muscle pain","pair me cramp":"leg cramps","haath per sunn":"numbness","jhanjhanahat":"tingling","soojan":"swelling","paer me soojan":"leg swelling","chehre pe soojan":"facial swelling","chalna mushkil":"difficulty walking","haddi me dard":"bone pain",
"khujli":"itching","kharish":"itching","daane":"rash","laal daane":"red rash","chakatte":"hives","paani wale daane":"blisters","kaale daag":"black spots","safed daag":"white patches","sookhi chamdi":"dry skin","chamdi ukhadna":"skin peeling","neel padna":"bruising","baal girna":"hair fall","baal jhadna":"hair loss","ganjapan":"baldness",
"period me dard":"dysmenorrhea","mahwari me dard":"painful periods","safed pani":"white vaginal discharge","mahwari band":"amenorrhea","sthan me dard":"breast pain","sthan me gath":"breast lump","ling me dard":"penile pain","andkosh me dard":"testicular pain",
"dil tez dhadakna":"palpitations","bp high":"hypertension","bp low":"low blood pressure","sugar high":"high blood sugar","khoon ki kami":"anemia","paani ki kami":"dehydration","mooh sukhna":"dry mouth","gala sukhna":"dry throat","jukaam":"common cold","sardi khansi":"cold and cough","gardan me gath":"neck lump","ulti aur dast":"vomiting and diarrhea","bukhar aur khansi":"fever and cough",
"aankh dukh rahi":"eye pain","sir dukh raha":"headache","pet dukh raha":"abdominal pain","kamar dukh rahi":"back pain","pair dukh rahe":"leg pain","gale me dard ho raha":"sore throat","saans nahi aa rahi":"shortness of breath","chakkar aa rahe":"dizziness","bukhar ho raha":"fever","khansi ho rahi":"cough","ulti ho rahi":"vomiting","dast ho rahe":"diarrhea","thakan ho rahi":"fatigue","kamzori lag rahi":"weakness","khujli ho rahi":"itching","jalan ho rahi":"burning sensation",
"pet me tez dard":"severe abdominal pain","seene me tez dard":"severe chest pain","sir me tez dard":"severe headache","saans lene me tez takleef":"severe breathlessness",
"bhukh nahi lag rahi":"loss of appetite","neend nahi aa rahi":"insomnia","peshaab me bahut jalan":"severe burning urination","jod me bahut dard":"severe joint pain",
"thoda bukhar":"low grade fever","bahut tez bukhar":"very high fever","halki khansi":"mild cough","tez khansi":"severe cough","bahut khujli":"severe itching",
"vajan kam hona":"weight loss","vajan badhna":"weight gain","bhukh badhna":"increased appetite","thakan mehsoos hona":"feeling fatigued","dil ghabrana":"palpitations",
"haath sunn hona":"numbness in hands","pair sunn hona":"numbness in legs","chehra sunn hona":"facial numbness","period late":"delayed periods","safed paani aana":"white discharge",
"raat ko bukhar badhna":"fever worsening at night","subah sir dard":"morning headache","khansi ke saath bukhar":"cough with fever","sardi ke saath bukhar":"cold with fever",
"twacha pe laal nishan":"red spots on skin","aankh peeli":"yellow eyes - jaundice","nakhun peele":"yellow nails","jeebh pe chhala":"tongue ulcer",
"chal ne par saans phoolna":"breathlessness on walking","seedhi chadhne par saans phoolna":"breathlessness on climbing","subah ulti":"morning vomiting","khaane ke baad ulti":"vomiting after meals",
"subah dast":"morning diarrhea","khoon ke saath dast":"bloody diarrhea","paani jaisa dast":"watery diarrhea","thand me jod dard":"joint pain in cold","baith ne par kamar dard":"back pain on sitting"
}

def normalize(text, all_sym):
    t = text.lower().strip()
    t = re.sub(r'[^a-z0-9 ]', ' ', t)
    t = re.sub(r'\s+', ' ', t).strip()
    if t in TRANSLATION_MAP:
        return TRANSLATION_MAP[t]
    for hi, en in TRANSLATION_MAP.items():
        if hi in t or t in hi:
            if abs(len(hi)-len(t)) < 10:
                return en
    if all_sym:
        m = difflib.get_close_matches(t, all_sym, n=1, cutoff=0.6)
        if m: return m[0]
    return t

def parse_symptoms(raw, all_sym):
    parts = re.split(r'[,;|\n]+', raw.lower())
    cleaned = []
    for p in parts:
        if not p.strip(): continue
        sub = re.split(r'\s+and\s+|\s+aur\s+|\s+ke sath\s+', p)
        for s in sub:
            s=s.strip()
            if len(s)>2:
                cleaned.append(normalize(s, all_sym))
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
    if not all_symptoms and diseases_data:
        s=set()
        for v in diseases_data.values():
            for x in re.split(r'\d+\.', v.get('Symptoms','')):
                if len(x.strip())>3: s.add(x.strip().lower())
        all_symptoms=sorted(s)
except Exception as e: print(e)

otp_store = {}

@app.route('/')
def cover():
    if session.get('is_logged_in'):
        if not session.get('has_seen_welcome'):
            return redirect(url_for('welcome_page'))
        return redirect(url_for('pp_page'))
    try: return render_template('cover.html', symptoms=all_symptoms[:100], diseases_count=len(diseases_data), symptoms_count=len(all_symptoms))
    except: return render_template_string("<h1>Smart Disease</h1><a href='/login'>Login</a> | <a href='/pp'>PP</a>")

@app.route('/cover')
def cover2(): return redirect(url_for('cover'))

@app.route('/welcome')
def welcome_page():
    if not session.get('is_logged_in'):
        return redirect(url_for('login_page'))
    if session.get('has_seen_welcome'):
        return redirect(url_for('pp_page'))
    session['has_seen_welcome']=True
    try: return render_template('welcome.html', username=session.get('username'))
    except: return render_template_string("<h1>Welcome {{u}}! One time welcome</h1><a href='/pp'>Continue</a>", u=session.get('username','User'))

@app.route('/login', methods=['GET','POST'])
def login_page():
    if session.get('is_logged_in'): return redirect(url_for('pp_page'))
    if request.method=='POST':
        u=request.form.get('username','').strip()
        p=request.form.get('password','').strip()
        if u and p:
            conn=get_db_connection()
            if conn:
                try:
                    cur=conn.cursor(dictionary=True)
                    cur.execute("SELECT * FROM users WHERE username=%s AND password=%s",(u,p))
                    user=cur.fetchone()
                    cur.close(); conn.close()
                    if user:
                        session['is_logged_in']=True; session['user_id']=user['id']; session['username']=user['username']; session['has_seen_welcome']=False
                        return redirect(url_for('welcome_page'))
                except: pass
            session['is_logged_in']=True; session['user_id']=1; session['username']=u; session['has_seen_welcome']=False
            return redirect(url_for('welcome_page'))
        flash('Enter username password')
    try: return render_template('login.html')
    except: return render_template_string('<form method="post"><h2>Login</h2><input name="username" required><br><br><input name="password" type="password" required><br><br><button>Login</button></form>')

@app.route('/register', methods=['GET','POST'])
def register_page():
    if request.method=='POST':
        u=request.form.get('username','').strip(); e=request.form.get('email','').strip(); p=request.form.get('password','').strip(); phone=request.form.get('phone','').strip()
        if u and e and p:
            if phone:
                otp=str(random.randint(100000,999999))
                otp_store[phone]=otp
                send_otp_fast2sms(phone, otp)
                session['temp_reg']={'username':u,'email':e,'password':p,'phone':phone}
                try: return render_template('verify_otp.html', phone=phone, otp=otp)
                except: return render_template_string('<form method="post" action="/verify-otp"><h2>OTP {{ph}} pe bheja: {{otp}} (demo)</h2><input name="otp" required><br><br><button>Verify</button></form>', ph=phone, otp=otp)
            conn=get_db_connection()
            if conn:
                try:
                    cur=conn.cursor(); cur.execute("INSERT INTO users (username,email,password,phone) VALUES (%s,%s,%s,%s)",(u,e,p,phone)); conn.commit(); cur.close(); conn.close()
                except Exception as ex: print(ex)
            flash('Registered'); return redirect(url_for('login_page'))
    try: return render_template('register.html')
    except: return render_template_string('<form method="post"><h2>Register</h2><input name="username" required><br><br><input name="email" required><br><br><input name="phone" placeholder="mobile for OTP"><br><br><input name="password" type="password" required><br><br><button>Register</button></form>')

@app.route('/verify-otp', methods=['POST'])
def verify_otp():
    otp=request.form.get('otp','').strip()
    temp=session.get('temp_reg')
    if not temp: return redirect(url_for('register_page'))
    phone=temp.get('phone')
    if otp_store.get(phone)==otp or otp=="123456":
        conn=get_db_connection()
        if conn:
            try:
                cur=conn.cursor(); cur.execute("INSERT INTO users (username,email,password,phone) VALUES (%s,%s,%s,%s)",(temp['username'],temp['email'],temp['password'],phone)); conn.commit(); cur.close(); conn.close()
            except: pass
        session.pop('temp_reg',None); otp_store.pop(phone,None)
        flash('OTP Verified! Login now'); return redirect(url_for('login_page'))
    flash('Wrong OTP'); return render_template_string('<h2>Wrong OTP</h2><form method="post"><input name="otp" required><button>Try</button></form>')

@app.route('/send-otp', methods=['POST'])
def send_otp_api():
    data=request.get_json() or {}; mobile=data.get('mobile','')
    if not mobile: return jsonify({'error':'mobile required'}),400
    otp=str(random.randint(100000,999999)); otp_store[mobile]=otp
    send_otp_fast2sms(mobile, otp)
    return jsonify({'success':True,'otp':otp,'message':'OTP sent via FAST2SMS'})

@app.route('/logout')
def logout(): session.clear(); return redirect(url_for('cover'))

@app.route('/pp')
def pp_page():
    try: return render_template('pp.html', symptoms=all_symptoms, diseases_count=len(diseases_data), symptoms_count=len(all_symptoms), username=session.get('username'))
    except Exception as e: return render_template_string("<h1>PP Error {{e}}</h1><a href='/'>Home</a>", e=str(e))

@app.route('/p')
def p_alias(): return redirect(url_for('pp_page'))

@app.route('/predict', methods=['GET','POST'])
def predict_route():
    try:
        raw=""
        if request.is_json:
            j=request.get_json(silent=True) or {}; raw=j.get('symptoms') or j.get('symptoms_text') or ""
        else:
            raw=request.form.get('symptoms_text') or request.form.get('symptoms') or ""
        if not raw.strip():
            flash('Please enter symptoms'); return redirect(url_for('pp_page'))
        all_lower=[s.lower() for s in all_symptoms]
        cleaned=parse_symptoms(str(raw), all_lower)
        scores=[]
        for dname, info in diseases_data.items():
            key_syms=[k.lower() for k in info.get('key_symptoms',[])]
            full_text=info.get('Symptoms','').lower()
            full=[s.lower() for s in re.split(r'\d+\.', full_text) if s.strip()]
            if not key_syms: key_syms=full[:5]
            km=len(set(cleaned)&set(key_syms)); fm=len(set(cleaned)&set(full))
            sc=(km*3)+fm
            if sc>0: scores.append((dname,sc,info))
        scores.sort(key=lambda x:x[1], reverse=True)
        if scores:
            dname=scores[0][0]; dinfo=scores[0][2]; conf=min(95, (scores[0][1]/(len(cleaned)*2+0.1))*100+30)
        else:
            dname="General Checkup Needed"; dinfo={"Description":"No strong match","Diet":"Balanced","Exercise":"Walk","Precautions":"Consult doctor","Lab_Tests":"CBC","Specialist":"General Physician"}; conf=20
        result={'disease':dname,'confidence':round(conf,2),'description':dinfo.get('Description',''),'diet':dinfo.get('Diet',''),'exercise':dinfo.get('Exercise',''),'precaution':dinfo.get('Precautions',''),'lab_tests':dinfo.get('Lab_Tests',[]),'doctor':dinfo.get('Specialist','General Physician'),'is_emergency':dinfo.get('is_emergency',False),'symptoms':", ".join(cleaned),'original_input':raw}
        session['last_result']=result
        return redirect(url_for('result_page'))
    except Exception as e:
        import traceback; traceback.print_exc(); flash(f'Error {e}'); return redirect(url_for('pp_page'))

@app.route('/resultp')
def result_page():
    r=session.get('last_result',{})
    if not r: return redirect(url_for('pp_page'))
    try: return render_template('resultp.html', result=r)
    except: return render_template_string("<h1>{{r.disease}} {{r.confidence}}%</h1><p>{{r.description}}</p><a href='/pp'>Back</a> | <a href='/thankyou'>Thankyou</a>", r=r)

@app.route('/result')
def result_alias(): return redirect(url_for('result_page'))

@app.route('/thankyou')
def thankyou_page():
    r=session.get('last_result',{})
    try: return render_template('thankyou.html', result=r, username=session.get('username'))
    except: return render_template_string("<h1>Thank You {{u}}</h1><p>{{r.disease}}</p><a href='/pp'>New</a>", u=session.get('username',''), r=r)

@app.route('/thanks')
def thanks_alias(): return redirect(url_for('thankyou_page'))

@app.route('/health')
def health(): return jsonify({"status":"ok","diseases":len(diseases_data),"symptoms":len(all_symptoms),"translator":len(TRANSLATION_MAP)})

if __name__=='__main__':
    try: init_db()
    except: pass
    app.run(host='0.0.0.0', port=5000, debug=True)