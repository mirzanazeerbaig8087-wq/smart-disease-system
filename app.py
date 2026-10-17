from flask import Flask, render_template, request, jsonify, session, redirect, url_for, flash, render_template_string, send_file
import json, pickle, gzip, os, re, difflib, random, smtplib, math, requests, io
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta
import mysql.connector
from mysql.connector import Error

app = Flask(__name__)
app.secret_key = 'smart_disease_2026_secret_key_123_final_700'

MAIL_USER = os.getenv('MAIL_USER', 'tumhara_email@gmail.com')
MAIL_PASS = os.getenv('MAIL_PASS', 'tumhara_16_digit_app_password')

def send_email_otp(to_email, otp):
    print(f"TRYING TO SEND OTP {otp} TO {to_email} FROM {MAIL_USER}")
    if not MAIL_USER or not MAIL_PASS or '@' not in MAIL_USER or 'tumhara_email' in MAIL_USER:
        print(f"[DEMO MODE] MAIL_USER/PASS not set. OTP is {otp}")
        return False
    try:
        msg = MIMEMultipart()
        msg['From'] = MAIL_USER
        msg['To'] = to_email
        msg['Subject'] = f"Predict AI - Your OTP is {otp}"
        body = f"""
        <div style='font-family:Poppins;padding:20px;background:#f8f9fb;border-radius:12px'>
        <h2 style='color:#2f80ff'>Predict AI - Smart Disease System</h2>
        <h1 style='letter-spacing:5px;color:#121a2b'>{otp}</h1>
        <p>Valid for 5 mins. Don't share with anyone.</p>
        <p style='font-size:11px;color:#8a9bb5'>Nagpur, Maharashtra</p>
        </div>
        """
        msg.attach(MIMEText(body, 'html'))
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(MAIL_USER, MAIL_PASS.replace(" ", ""))
        server.send_message(msg)
        server.quit()
        print(f"SUCCESS: Email OTP sent to {to_email}")
        return True
    except Exception as e:
        print(f"Email FAILED Error: {e}")
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
    except Exception as e: print(f"init_db error {e}")
    finally:
        try: cur.close(); conn.close()
        except: pass

# ===================== 700+ TRANSLATION MAP =====================
TRANSLATION_MAP = {
"ankho me andhera":"blurred vision","aankh me dhundhla":"blurred vision","dhundhla dikhna":"blurred vision","ankh dukhna":"eye pain","aankh dard":"eye pain","aankh laal":"red eyes","aankh me khujli":"eye itching","aankh se paani":"watery eyes","aankh soojna":"swollen eyes","do dikhna":"double vision","raat me na dikhna":"night blindness","aankh me jalan":"burning eyes","palak soojna":"swollen eyelids","aankh phadakna":"eye twitching","aankh peeli":"yellow eyes","aankh me sujan":"eye swelling","aankh se keechad":"eye discharge","roshni se dard":"photophobia","aankh bhari":"heavy eyes","aankh thakan":"eye strain","chashme ka number badhna":"increased eye power","kala motiya":"glaucoma","safed motiya":"cataract","aankh me dard tez":"severe eye pain",
"chakkar":"dizziness","chakkar aana":"dizziness","sir ghumna":"dizziness","chakkar khana":"vertigo","sir dard":"headache","sar dard":"headache","adha sir dard":"migraine","sir bhari":"heavy head","neend na aana":"insomnia","neend zyada":"excessive sleepiness","thakan":"fatigue","thakawat":"fatigue","kamzori":"weakness","susti":"lethargy","behoshi":"fainting","behos hona":"loss of consciousness","ghabrahat":"anxiety","bechaini":"restlessness","yaaddasht kam":"memory loss","bhulna":"forgetfulness","bolne me dikkat":"difficulty speaking","ulti seedha bolna":"slurred speech","haath kampna":"tremors","haath kaapna":"hand tremor","pair kaapna":"leg tremor","sir kampna":"head tremor","haath pair kampna":"tremor in limbs","neend me chaunkna":"sleep disturbance","sapne zyada":"vivid dreams","bolna band":"loss of speech","samajh na aana":"confusion","cheez bhulna":"forgetting things","rasta bhulna":"disorientation","chidchidapan":"irritability","gussa zyada":"anger issues","udaasi":"depression","rona aana":"crying spells","dar lagna":"fearfulness","tension":"stress","dimag sunn":"brain fog","sir sunn":"numbness in head","haath sunn":"numbness in hands","pair sunn":"numbness in legs","jhanjhanahat":"tingling","sunnapan":"numbness","mirgi jaisa daura":"seizure","jhatka aana":"convulsions","hath pair mudna":"muscle spasms","gardhan akadna":"neck stiffness","peeth akadna":"back stiffness","haath pair me jalan":"burning in limbs",
"bukhar":"fever","tez bukhar":"high fever","halka bukhar":"low grade fever","thand lagna":"chills","kapkapi":"rigors","pasina aana":"sweating","raat ko pasina":"night sweats","din me bukhar":"daytime fever","shaam ko bukhar":"evening fever","roz bukhar":"daily fever","ruk ruk ke bukhar":"intermittent fever","lagatar bukhar":"continuous fever","bukhar utarna chadna":"fluctuating fever","andaruni bukhar":"internal fever","viral bukhar":"viral fever","bukhar ke sath thand":"fever with chills","bukhar ke sath khansi":"fever with cough","bukhar ke sath sir dard":"fever with headache",
"naak band":"nasal congestion","naak behna":"runny nose","cheenk aana":"sneezing","naak se khoon":"nosebleed","kaan dard":"ear pain","kaan bajna":"tinnitus","kaan se paani":"ear discharge","sunne me kami":"hearing loss","gala dard":"sore throat","gale me dard":"sore throat","gala kharash":"throat irritation","nigalne me dard":"painful swallowing","aawaz baithna":"hoarseness","mooh me chhale":"mouth ulcers","mooh se badbu":"bad breath","naak me khujli":"nasal itching","gale me khujli":"throat itching","kaan me khujli":"ear itching","naak me jalan":"nasal burning","gale me jalan":"throat burning","gale me kuch atka":"foreign body in throat","thook me khoon":"blood in saliva","mooh ka sukhna":"dry mouth","jeebh safed":"white tongue","jeebh laal":"red tongue","jeebh me chhale":"tongue ulcers","honth sukhna":"dry lips","honth phatna":"cracked lips","daat dard":"toothache","masudo me khoon":"bleeding gums","gardan me dard":"neck pain in throat","gardan me gath":"neck lump",
"saans phoolna":"shortness of breath","saans ki takleef":"shortness of breath","saans lene me dikkat":"difficulty breathing","dum ghutna":"breathlessness","seene me dard":"chest pain","chhati me dard":"chest discomfort","seene me jalan":"chest burning","khansi":"cough","sukhi khansi":"dry cough","balkam wali khansi":"productive cough","balkam":"sputum","balkam me khoon":"coughing blood","ghar ghar":"wheezing","hichki":"hiccups","khansi me dard":"painful cough","raat me khansi":"night cough","subah khansi":"morning cough","lambi khansi":"chronic cough","kaali khansi":"whooping cough","seene me ghutan":"chest tightness","seene me bhari":"chest heaviness","saans tez":"rapid breathing","saans dheere":"slow breathing","chal ne par saans phoolna":"breathlessness on walking","seedhi chadhne par saans phoolna":"breathlessness on climbing","letne par saans phoolna":"breathlessness on lying","thand me saans phoolna":"breathlessness in cold",
"pet dard":"abdominal pain","pait dard":"abdominal pain","pait me dard":"abdominal pain","pet me marod":"abdominal cramps","pait phoolna":"bloating","pet phoolna":"bloating","gas banna":"gas formation","pet me gas":"flatulence","dakaar":"belching","acidity":"heartburn","khatti dakaar":"acid burping","pet me jalan":"stomach burning","ulti":"vomiting","matli":"nausea","dast":"diarrhea","loose motion":"diarrhea","khooni dast":"bloody diarrhea","latrine me khoon":"blood in stool","kabz":"constipation","bhukh na lagna":"loss of appetite","bhukh zyada":"increased appetite","wazan kam":"weight loss","wazan badhna":"weight gain","pait me awaaz":"stomach rumbling","bawaseer":"piles","latrine me dard":"pain during defecation","khoon ki ulti":"vomiting blood","kaala latrine":"black stools","pet me tez dard":"severe abdominal pain","naabhi me dard":"pain around navel","daayi taraf pet dard":"right side abdominal pain","baayi taraf pet dard":"left side abdominal pain","upar pet dard":"upper abdominal pain","neeche pet dard":"lower abdominal pain","khaane ke baad pet dard":"pain after eating","bhukh ke samay pet dard":"pain when hungry","pet me sujan":"abdominal swelling","pet sakht":"hard abdomen","pet me paani":"ascites","ulti aur dast":"vomiting and diarrhea","subah ulti":"morning vomiting","khaane ke baad ulti":"vomiting after meals","kaale rang ki ulti":"black vomit","peele rang ki ulti":"yellow vomit","dast me aaw":"mucus in stool","badbudar dast":"foul smelling stool","paani jaisa dast":"watery diarrhea","subah dast":"morning diarrhea","khoon ke saath dast":"bloody diarrhea","kabz aur dast":"alternating constipation diarrhea","latrine rokna mushkil":"difficulty controlling stool","gas na nikalna":"inability to pass gas","bhukh nahi lag rahi":"loss of appetite","khatta paani aana":"acid reflux","pet me keede":"worms in stool","guda me khujli":"anal itching","guda me dard":"anal pain","peela latrine":"yellow stool","safed latrine":"pale stool","pet me jalan aur dard":"abdominal pain with burning",
"peshaab me jalan":"burning urination","peshaab me dard":"painful urination","bar bar peshaab":"frequent urination","raat me peshaab":"nocturia","peshaab rukna":"urinary retention","peshaab me khoon":"blood in urine","peshaab peela":"yellow urine","peshaab kam":"decreased urine output","peshaab zyada":"excessive urination","gurde me dard":"kidney pain","peshaab me jhaag":"foamy urine","peshaab me badbu":"foul smelling urine","peshaab me jalan tez":"severe burning urination","peshaab rok na paana":"urinary incontinence","peshaab karne me zor":"straining to urinate","peshaab ke baad dard":"pain after urination","pet ke neeche dard peshaab me":"lower abdominal pain with urination","kamar dard peshaab me":"back pain with urination","peshaab me dard aur jalan":"pain and burning urination","peshaab ka rang gehra":"dark urine",
"jism dard":"body ache","badan dard":"body pain","jod dard":"joint pain","jodo me soojan":"joint swelling","jod jam":"joint stiffness","ghutne me dard":"knee pain","kamar dard":"low back pain","gardan dard":"neck pain","kandhe me dard":"shoulder pain","maas peshi me dard":"muscle pain","pair me cramp":"leg cramps","haath per sunn":"numbness","soojan":"swelling","paer me soojan":"leg swelling","chehre pe soojan":"facial swelling","chalna mushkil":"difficulty walking","haddi me dard":"bone pain","kamar me sujan":"back swelling","ghutne me sujan":"knee swelling","kohni me dard":"elbow pain","kalaai me dard":"wrist pain","ungli me dard":"finger pain","erhi me dard":"heel pain","talve me dard":"sole pain","kamar akadna":"back stiffness","subah jod akadna":"morning joint stiffness","thand me jod dard":"joint pain in cold","baith ne par kamar dard":"back pain on sitting","khade hone par dard":"pain on standing","chal ne par dard":"pain on walking","raat me jod dard":"joint pain at night","poore jism me soojan":"generalized swelling","haath me soojan":"hand swelling","pair me jalan":"burning in feet","haath me jalan":"burning in hands","maas peshi me kamzori":"muscle weakness","haath me kamzori":"weakness in hands","pair me kamzori":"weakness in legs","haddi tootna aasani se":"frequent fractures","kamar jhukna":"stooped posture","kad kam hona":"loss of height","jod se awaaz":"joint cracking","jod me garmi":"joint warmth","maas peshi akadna":"muscle stiffness",
"khujli":"itching","kharish":"itching","daane":"rash","laal daane":"red rash","chakatte":"hives","paani wale daane":"blisters","kaale daag":"black spots","safed daag":"white patches","sookhi chamdi":"dry skin","chamdi ukhadna":"skin peeling","neel padna":"bruising","baal girna":"hair fall","baal jhadna":"hair loss","ganjapan":"baldness","chehre pe daane":"facial acne","peeth pe daane":"back acne","laal chakatte":"red hives","khujli wale daane":"itchy rash","peep wale daane":"pus filled pimples","paani wale chhale":"watery blisters","khoon wale chhale":"blood blisters","chamdi laal":"red skin","chamdi kaali":"dark skin","chamdi peeli":"yellow skin","twacha pe laal nishan":"red spots on skin","haath pe chhale":"blisters on hands","pair pe chhale":"blisters on feet","nakhun kharab":"nail damage","nakhun peele":"yellow nails","nakhun me dard":"nail pain","baal safed":"white hair","bhawon me khujli":"eyebrow itching","daadi me khujli":"beard itching","sir me khujli":"scalp itching","sir me dani":"dandruff","chamdi me jalan":"burning skin","thand me laal daane":"cold induced rash","garmi me daane":"heat rash","pasine me daane":"sweat rash","dhoop me jalan":"sunburn","chamdi me dard":"skin pain","chamdi moti":"thick skin","chamdi patli":"thin skin","chehre pe sujan":"facial puffiness",
"period me dard":"dysmenorrhea","mahwari me dard":"painful periods","safed pani":"white vaginal discharge","mahwari band":"amenorrhea","sthan me dard":"breast pain","sthan me gath":"breast lump","ling me dard":"penile pain","andkosh me dard":"testicular pain","period zyada":"heavy periods","period kam":"light periods","period baar baar":"frequent periods","period late":"delayed periods","safed paani aana":"white discharge","peela paani":"yellow discharge","badbudar paani":"foul discharge","khujli neeche":"vaginal itching","jalan neeche":"vaginal burning","pet ke neeche dard period me":"lower abdominal pain during periods","kamar dard period me":"back pain during periods","sthan se paani":"nipple discharge","sthan me khujli":"breast itching","sthan ka aakar badhna":"breast enlargement","sthan laal":"red breast","bacha na hona":"infertility","garbhpat":"miscarriage","pet me gath mahila":"abdominal lump female","period me chakkar":"dizziness during periods","period me ulti":"vomiting during periods","safed paani me khujli":"white discharge with itching","peshab me jalan mahila":"burning urination female","pet ke neeche gath":"pelvic lump",
"dil tez dhadakna":"palpitations","bp high":"hypertension","bp low":"low blood pressure","sugar high":"high blood sugar","sugar low":"low blood sugar","khoon ki kami":"anemia","paani ki kami":"dehydration","mooh sukhna":"dry mouth","gala sukhna":"dry throat","jukaam":"common cold","sardi khansi":"cold and cough","gardan me gath":"neck lump","bhukh nahi lag rahi":"loss of appetite","neend nahi aa rahi":"insomnia","vajan kam hona":"weight loss","vajan badhna":"weight gain","wazan ki kami":"weight loss","wazan ki kmai":"weight loss","wazan kam":"weight loss","motapa":"obesity","patla hona":"thinness","kamjori mehsoos":"feeling weak","thakan mehsoos":"feeling tired","dil ghabrana":"palpitations with anxiety","seene me dhadkan":"heart pounding","bp badhna":"high bp","bp kam hona":"low bp","sugar badhna":"high blood sugar","khoon patla":"thin blood","khoon gadha":"thick blood","haath pair thande":"cold extremities","haath pair garam":"hot extremities","pasina zyada":"excessive sweating","pasina kam":"less sweating","pyaas zyada":"excessive thirst","pyaas kam":"less thirst","bhook zyada":"excessive hunger","thand zyada lagna":"feeling cold","garmi zyada lagna":"feeling hot","vajan tezi se kam":"rapid weight loss","vajan tezi se badhna":"rapid weight gain",
# EXTRA 200+ TO REACH 700+
"aankh me dard halka":"mild eye pain","aankh me jalan halki":"mild burning eyes","aankh dukhna tez":"severe eye pain","naak se paani behna":"watery nasal discharge","naak band subah":"morning nasal congestion","gala sukhna subah":"morning dry throat","khansi ke sath bukhar":"cough with fever","khansi ke sath balgam":"cough with sputum","khansi me khoon aana":"blood in cough","saans lene me si":"wheezing sound","saans rukna":"apnea","saans tez chalna":"tachypnea","dil ki dhadkan tez":"tachycardia","dil ki dhadkan dheere":"bradycardia","dil me dard":"heart pain","seene me jalan tez":"severe chest burning","pet me jalan tez":"severe stomach burning","pet me gas tez":"severe gas","pet me dard tez":"severe stomach ache","pet phoolna tez":"severe bloating","ulti aana baar baar":"frequent vomiting","matli aana":"feeling nauseous","dast lagna":"diarrhea","kabz hona":"constipation","bhukh kam lagna":"decreased appetite","bhukh bilkul na lagna":"no appetite","wazan tezi se girna":"rapid weight loss","thand lagna bukhar me":"chills in fever","kapkapana bukhar me":"rigors in fever","pasina aana bukhar me":"sweating in fever","sir me bhari pan":"heaviness in head","sir me dard tez":"severe headache","adhe sir me dard":"half headache","poore sir me dard":"whole headache","chakkar aana khade hone par":"dizziness on standing","chakkar aana subah":"morning dizziness","neend na aana raat me":"night insomnia","neend zyada aana din me":"daytime sleepiness","thakan rehti hai":"persistent fatigue","kamzori lagti hai":"feeling weakness","bechaini rehti hai":"persistent restlessness","ghabrahat rehti hai":"persistent anxiety","yaaddasht kamzor":"weak memory","bolne me atakna":"stammering","haath kampna likhte samay":"tremor while writing","haath kampna kaam karte":"tremor during work","pair me jalan raat me":"burning feet at night","haath me jalan raat me":"burning hands at night","jod me dard subah":"morning joint pain","jod me sujan shaam ko":"evening joint swelling","ghutne me dard chalne par":"knee pain on walking","kamar me dard jhukne par":"back pain on bending","gardan me dard peeche":"posterior neck pain","kandhe me dard uthane par":"shoulder pain on lifting","maas peshi me dard raat me":"night muscle pain","soojan subah zyada":"more swelling in morning","pair me soojan shaam ko":"evening leg swelling","chehre pe soojan subah":"morning facial swelling","khujli raat me zyada":"more itching at night","daane garmi me":"rash in heat","daane sardi me":"rash in cold","chamdi laal hona":"redness of skin","chamdi kaali padna":"blackening of skin","chamdi pe safed daag":"white spots on skin","baal girna tez":"rapid hair fall","baal patle hona":"thinning hair","nakhun tootna":"brittle nails","nakhun me safed daag":"white spots on nails","mooh me chhale baar baar":"recurrent mouth ulcers","mooh se badbu subah":"morning bad breath","daat me thand garam lagna":"tooth sensitivity","masudo me sujan":"gum swelling","kaan se peep aana":"pus in ear","kaan band lagna":"blocked ear","sunai kam dena":"decreased hearing","aankh se paani aana subah":"morning watery eyes","aankh laal hona subah":"morning red eyes","aankh me khujli subah":"morning eye itching","naak se khoon aana subah":"morning nosebleed","gala dard subah":"morning sore throat","gala kharab hona":"bad throat","aawaz baithna gala me":"hoarse voice","peshaab me jalan subah":"morning burning urination","peshaab peela gehra":"dark yellow urine","peshaab me khoon aana":"blood in urine","peshaab baar baar aana":"frequent urge to urinate","peshaab rok na paana raat me":"night urinary incontinence","kamar dard peshaab ke sath":"back pain with urination","pet ke neeche dard peshaab ke baad":"lower abdominal pain after urination","period me dard tez":"severe period pain","period me khoon zyada":"excessive bleeding during period","period me khoon kam":"scanty periods","safed pani me badbu":"foul smelling white discharge","sthan me dard mahwari se pehle":"premenstrual breast pain","sthan me gath dard ke sath":"painful breast lump","thakan period me":"fatigue during periods","dil tez dhadakna ghabrahat me":"palpitations in anxiety","bp high hona":"hypertension","bp low hona":"hypotension","sugar high hona":"hyperglycemia","sugar low hona":"hypoglycemia","khoon ki kami mehsoos":"feeling anemic","paani ki kami mehsoos":"feeling dehydrated","vajan kam hona tezi se":"rapid weight loss","vajan badhna tezi se":"rapid weight gain","bhook nahi lagna bilkul":"complete loss of appetite","pyaas bahut lagna":"excessive thirst","pasina bahut aana":"excessive sweating","thand bahut lagna":"excessive cold feeling","garmi bahut lagna":"excessive heat feeling","dil ghabrana tez":"severe palpitations","seene me dabav":"chest pressure","seene me jalan khana khane ke baad":"heartburn after eating","pet me jalan khana khane ke baad":"stomach burning after eating","khatti dakaar aana":"acid belching","dakaar zyada aana":"excessive belching","gas banna zyada":"excessive gas","pet me awaaz aana":"rumbling in stomach","latrine me jalan":"burning during defecation","latrine me dard tez":"severe pain during defecation","latrine me khoon aana tez":"severe bloody stool","kabz rehti hai":"persistent constipation","dast rehte hain":"persistent diarrhea","ulti aana khana khane ke baad":"vomiting after eating","matli aana subah":"morning nausea","bhukh kam hona subah":"morning loss of appetite","wazan kam hona bina wajah":"unexplained weight loss","wazan badhna bina wajah":"unexplained weight gain","haath pair me sujan":"swelling in hands and feet","poore sharir me dard":"whole body pain","poore sharir me khujli":"whole body itching","poore sharir me jalan":"whole body burning","thakan aur kamzori":"fatigue and weakness","bukhar aur khansi":"fever and cough","bukhar aur sir dard":"fever and headache","bukhar aur jism dard":"fever and body ache","sardi jukaam bukhar":"cold fever","sardi khansi jukaam":"cold cough","gala dard bukhar":"sore throat fever"
}

def normalize(text, all_sym):
    t = text.lower().strip()
    t = re.sub(r'[^a-z0-9 ]', ' ', t)
    t = re.sub(r'\s+', ' ', t).strip()
    if t in TRANSLATION_MAP: return TRANSLATION_MAP[t]
    for hi, en in TRANSLATION_MAP.items():
        if hi in t or t in hi:
            if abs(len(hi)-len(t)) < 12: return en
    if all_sym:
        m = difflib.get_close_matches(t, all_sym, n=1, cutoff=0.6)
        if m: return m[0]
    return t

def parse_symptoms(raw, all_sym):
    parts = re.split(r'[,;|\n]+', raw.lower())
    cleaned = []
    for p in parts:
        if not p.strip(): continue
        sub = re.split(r'\s+and\s+|\s+aur\s+|\s+ke sath\s+|\s+with\s+', p)
        for s in sub:
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
    print(f"Loaded {len(diseases_data)} diseases, {len(all_symptoms)} symptoms, {len(TRANSLATION_MAP)} translations")
except Exception as e: print(f"Load error {e}")

otp_store = {}
temp_users = {}

# ===================== ROUTING FINAL =====================
# cover.html -> login.html -> welcome.html (ONCE) -> pp.html -> resultp.html -> thankyou.html
# After login, cover -> direct pp.html

@app.route('/')
def cover():
    # Cover image static folder se leni hai - cover.html me /static/cover.jpg use karo
    if not session.get('is_logged_in'):
        return render_template('cover.html') if os.path.exists('templates/cover.html') else redirect(url_for('login_page'))
    if not session.get('has_seen_welcome'):
        return redirect(url_for('welcome_page'))
    return redirect(url_for('pp_page'))

@app.route('/cover')
def cover2():
    return render_template('cover.html') if os.path.exists('templates/cover.html') else redirect(url_for('cover'))

@app.route('/welcome')
def welcome_page():
    if not session.get('is_logged_in'): return redirect(url_for('login_page'))
    if session.get('has_seen_welcome'): return redirect(url_for('pp_page'))
    session['has_seen_welcome']=True
    try: return render_template('welcome.html', username=session.get('username','User'))
    except: return render_template_string("<h1 style='font-family:Poppins;text-align:center;margin-top:100px'>Welcome {{u}}!<br><small>One time welcome</small><br><br><a href='/pp' style='background:#2f80ff;color:white;padding:10px 20px;border-radius:10px;text-decoration:none'>Continue</a></h1>", u=session.get('username','User'))

@app.route('/login', methods=['GET','POST'])
def login_page():
    if session.get('is_logged_in'):
        if not session.get('has_seen_welcome'): return redirect(url_for('welcome_page'))
        else: return redirect(url_for('pp_page'))
    try: return render_template('login.html')
    except: return render_template_string('<h2>Login template missing</h2>')

# --- OTP APIs - BOTH PAGES FIXED ---
@app.route('/api/send_email_otp', methods=['POST'])
def api_send_email_otp():
    data = request.get_json() or {}
    email = data.get('email','').strip()
    username = data.get('username','').strip()
    password = data.get('password','').strip()
    if not email or '@' not in email: return jsonify({'status':'error','message':'Invalid email'}),400
    otp = str(random.randint(100000,999999))
    otp_store[email] = {'otp':otp, 'time':datetime.now()}
    temp_users[email] = {'username':username,'email':email,'password':password}
    ok = send_email_otp(email, otp)
    if ok: return jsonify({'status':'sent','message':'OTP sent to Gmail'})
    else: return jsonify({'status':'sent','demo_otp': otp, 'message':'Demo mode - Check Render MAIL_USER/PASS'})

@app.route('/api/verify_login', methods=['POST'])
def api_verify_login():
    data = request.get_json() or {}
    login_type = data.get('type')
    if login_type == 'email':
        email = data.get('email','').strip(); otp = str(data.get('otp','')).strip()
        stored = otp_store.get(email)
        # Allow demo 123456 or real OTP within 10 mins
        valid = False
        if stored and stored['otp']==otp and datetime.now()-stored['time'] < timedelta(minutes=10): valid=True
        if otp=="123456": valid=True
        if not valid: return jsonify({'status':'error','message':'Invalid OTP'}),400
        user_info = temp_users.get(email, {'username':data.get('username','User'),'email':email,'password':data.get('password','')})
        conn = get_db_connection(); uid=None; uname=user_info['username']
        if conn:
            try:
                cur = conn.cursor(dictionary=True)
                cur.execute("SELECT * FROM users WHERE email=%s", (email,))
                ex = cur.fetchone()
                if ex: uid=ex['id']; uname=ex['username']
                else:
                    cur2=conn.cursor()
                    cur2.execute("INSERT INTO users (username,email,password,phone) VALUES (%s,%s,%s,%s)", (uname, email, user_info.get('password',''), ''))
                    conn.commit(); uid=cur2.lastrowid; cur2.close()
                cur.close(); conn.close()
            except Exception as e: print(f"DB email login error {e}")
        if not uid: uid=random.randint(1000,9999)
        session['is_logged_in']=True; session['user_id']=uid; session['username']=uname; session['has_seen_welcome']=False
        otp_store.pop(email,None); temp_users.pop(email,None)
        return jsonify({'status':'success'})
    elif login_type == 'phone':
        phone = data.get('phone','').strip(); username = data.get('username','User'); otp = str(data.get('otp','')).strip()
        # PHONE - ACCEPT ANY 6 DIGIT OTP (random har bar alag)
        if not otp or len(otp)!=6 or not otp.isdigit():
            return jsonify({'status':'error','message':'Enter 6 digit OTP'}),400
        conn = get_db_connection(); uid=None
        if conn:
            try:
                cur = conn.cursor(dictionary=True)
                cur.execute("SELECT * FROM users WHERE phone=%s", (phone,))
                ex = cur.fetchone()
                if ex: uid=ex['id']; username=ex['username']
                else:
                    cur2=conn.cursor()
                    cur2.execute("INSERT INTO users (username,email,password,phone) VALUES (%s,%s,%s,%s)", (username, f"{phone}@phone.local", 'phone_auth', phone))
                    conn.commit(); uid=cur2.lastrowid; cur2.close()
                cur.close(); conn.close()
            except Exception as e: print(f"DB phone login error {e}")
        if not uid: uid=random.randint(1000,9999)
        session['is_logged_in']=True; session['user_id']=uid; session['username']=username; session['has_seen_welcome']=False
        return jsonify({'status':'success'})
    return jsonify({'status':'error','message':'Invalid type'}),400

@app.route('/api/nearby_hospitals')
def nearby_hospitals():
    lat = request.args.get('lat'); lon = request.args.get('lon')
    disease = request.args.get('disease',''); doctor = request.args.get('doctor','General Physician')
    if not lat or not lon: return jsonify({"status":"error","message":"lat lon required"}),400
    try:
        lat_f=float(lat); lon_f=float(lon)
        overpass_q = f"""[out:json][timeout:25];(node["amenity"="hospital"](around:5000,{lat_f},{lon_f});way["amenity"="hospital"](around:5000,{lat_f},{lon_f});node["amenity"="clinic"](around:5000,{lat_f},{lon_f});node["amenity"="doctors"](around:5000,{lat_f},{lon_f}););out center 15;"""
        r = requests.get("https://overpass-api.de/api/interpreter", params={"data":overpass_q}, timeout=15)
        data = r.json()
        def calc_dist(la1, lo1, la2, lo2):
            R=6371; dLat=math.radians(la2-la1); dLon=math.radians(lo2-lo1)
            a=math.sin(dLat/2)**2+math.cos(math.radians(la1))*math.cos(math.radians(la2))*math.sin(dLon/2)**2
            return R*2*math.atan2(math.sqrt(a), math.sqrt(1-a))
        hospitals=[]
        for el in data.get('elements',[])[:12]:
            hLat=el.get('lat') or el.get('center',{}).get('lat')
            hLon=el.get('lon') or el.get('center',{}).get('lon')
            if not hLat: continue
            tags=el.get('tags',{})
            hospitals.append({
                "name": tags.get('name') or f"{doctor} Care Center",
                "address": tags.get('addr:street') or tags.get('addr:city') or tags.get('addr:full') or "Near your location",
                "lat": hLat, "lon": hLon,
                "distance_km": round(calc_dist(lat_f, lon_f, hLat, hLon),1),
                "speciality": doctor,
                "for_disease": disease,
                "gmaps_dir": f"https://www.google.com/maps/dir/?api=1&origin={lat_f},{lon_f}&destination={hLat},{hLon}",
                "gmaps_search": f"https://www.google.com/maps/search/{doctor}+hospital/@{hLat},{hLon},15z"
            })
        hospitals = sorted(hospitals, key=lambda x:x['distance_km'])[:6]
        # Agar real me 0 mile toh empty return karo, frontend handle karega - NO FAKE EXAMPLE
        return jsonify({"status":"success", "user_location":{"lat":lat_f,"lon":lon_f}, "count":len(hospitals), "hospitals":hospitals, "google_maps_user": f"https://www.google.com/maps?q={lat_f},{lon_f}&z=15&output=embed"})
    except Exception as e:
        print(f"Nearby hospital error: {e}")
        return jsonify({"status":"error","message":str(e),"hospitals":[]}),500

@app.route('/logout')
def logout(): session.clear(); return redirect(url_for('cover'))

@app.route('/pp')
def pp_page():
    if not session.get('is_logged_in'): return redirect(url_for('login_page'))
    try: return render_template('pp.html', symptoms=all_symptoms, diseases_count=len(diseases_data), symptoms_count=len(all_symptoms), username=session.get('username','User'), translation_count=len(TRANSLATION_MAP))
    except Exception as e: return render_template_string("<h1>PP Error {{e}}</h1><a href='/'>Home</a>", e=str(e))

@app.route('/predict', methods=['GET','POST'])
def predict_route():
    try:
        raw=""; patient_name="Patient"; age="N/A"; gender="N/A"; duration="N/A"
        if request.is_json:
            j=request.get_json(silent=True) or {}
            raw=j.get('symptoms') or j.get('symptoms_text') or ""
        else:
            raw=request.form.get('symptoms_text') or request.form.get('symptoms') or request.form.get('symptomsInput') or ""
            patient_name=request.form.get('patient_name') or request.form.get('name') or session.get('username','Patient')
            age=request.form.get('age') or "N/A"
            gender=request.form.get('gender') or "N/A"
            duration=request.form.get('duration') or "N/A"
        if not raw.strip():
            flash('Please enter symptoms'); return redirect(url_for('pp_page'))
        all_lower=[s.lower() for s in all_symptoms] if all_symptoms else []
        cleaned=parse_symptoms(str(raw), all_lower)
        if not cleaned: cleaned=[normalize(str(raw).lower(), all_lower)]

        scores=[]
        for dname, info in diseases_data.items():
            key_syms=[k.lower() for k in info.get('key_symptoms',[]) if k]
            full_text=info.get('Symptoms','').lower()
            full=[s.lower().strip() for s in re.split(r'\d+\.|,|;', full_text) if s.strip() and len(s.strip())>2]
            if not key_syms: key_syms=full[:8]
            km=len(set(cleaned)&set(key_syms))
            fm=len(set(cleaned)&set(full))
            sc=(km*5)+fm
            for c in cleaned:
                for f in full:
                    if c in f or f in c: sc+=0.5
            if sc>0: scores.append((dname,sc,info))
        scores.sort(key=lambda x:x[1], reverse=True)

        if scores and scores[0][1]>=1:
            dname=scores[0][0]; dinfo=scores[0][2]
            max_possible = len(cleaned)*5 + 3
            conf = min(96, max(40, (scores[0][1]/max_possible)*100 + 45))
        else:
            # Agar match nahi toh bhi first disease lo, General Checkup nahi
            if diseases_data:
                # Sabse close wala try karo difflib se
                disease_names = list(diseases_data.keys())
                close = difflib.get_close_matches(" ".join(cleaned), [d.lower() for d in disease_names], n=1, cutoff=0.1)
                if close:
                    idx = [d.lower() for d in disease_names].index(close[0])
                    dname=disease_names[idx]; dinfo=diseases_data[dname]
                else:
                    dname=disease_names[0]; dinfo=diseases_data[dname]
                conf=35
            else:
                dname="Analysis Needed"; dinfo={"Description":"Symptoms noted. Please add more symptoms for better prediction.","Diet":"Balanced diet","Exercise":"Light walk","Precautions":"Consult doctor","Lab_Tests":["CBC"],"Specialist":"General Physician"}; conf=30

        # Normalize Lab_Tests to list
        lab = dinfo.get('Lab_Tests') or dinfo.get('Lab Tests') or dinfo.get('lab_tests') or ["CBC"]
        if isinstance(lab, str): lab = [s.strip() for s in re.split(r',|;', lab) if s.strip()]

        result={
            'disease':dname,'confidence':round(float(conf),2),
            'description':dinfo.get('Description') or dinfo.get('description') or '',
            'diet':dinfo.get('Diet') or dinfo.get('diet') or 'Balanced diet',
            'exercise':dinfo.get('Exercise') or dinfo.get('exercise') or 'Light walk 30 min',
            'precaution':dinfo.get('Precautions') or dinfo.get('precaution') or 'Consult doctor',
            'lab_tests':lab,
            'doctor':dinfo.get('Specialist') or dinfo.get('specialist') or 'General Physician',
            'is_emergency':dinfo.get('is_emergency',False),
            'symptoms':", ".join(cleaned),
            'original_input':raw,
            'patient_name':patient_name,'age':age,'gender':gender,'duration':duration,
            'date':datetime.now().strftime("%d-%m-%Y %H:%M")
        }
        # Save to DB + session
        session['last_result']=result
        conn=get_db_connection()
        if conn:
            try:
                cur=conn.cursor()
                cur.execute("INSERT INTO predictions (user_id,symptoms,predicted_disease,confidence,original_input,patient_name,age,gender,duration) VALUES (%s,%s,%s,%s,%s)",
                            (session.get('user_id',0), result['symptoms'], result['disease'], result['confidence'], result['original_input'], result['patient_name'], str(result['age']), str(result['gender']), str(result['duration'])))
                conn.commit(); cur.close(); conn.close()
            except Exception as e: print(f"Prediction save error {e}")
        return redirect(url_for('result_page'))
    except Exception as e:
        import traceback; traceback.print_exc(); flash(f'Error {e}'); return redirect(url_for('pp_page'))

@app.route('/resultp')
def result_page():
    r=session.get('last_result',{})
    if not r: return redirect(url_for('pp_page'))
    try: return render_template('resultp.html', result=r)
    except Exception as e:
        print(f"resultp render error {e}")
        return render_template_string("<h1>{{r.disease}} {{r.confidence}}%</h1><p>{{r.description}}</p><a href='/pp'>Back</a> | <a href='/thankyou'>Thankyou</a> | <a href='/api/download_pdf'>Download PDF</a>", r=r)

@app.route('/thankyou')
def thankyou_page():
    r=session.get('last_result',{})
    if not session.get('is_logged_in'): return redirect(url_for('login_page'))
    try: return render_template('thankyou.html', result=r, username=session.get('username','User'))
    except: return render_template_string("<div style='font-family:Poppins;text-align:center;margin-top:80px'><h1>Thank You {{u}} ❤️</h1><p>Report: {{r.disease}} - {{r.confidence}}%</p><p>Take Care</p><br><a href='/pp' style='background:#2f80ff;color:white;padding:10px 20px;border-radius:10px;text-decoration:none'>Predict Again</a> <a href='/logout' style='background:#f0f0f0;color:#333;padding:10px 20px;border-radius:10px;text-decoration:none'>Logout</a></div>", u=session.get('username',''), r=r)

# --- PDF DOWNLOAD BACKEND - FINAL, ONLY FPDF2 ---
@app.route('/api/download_pdf')
def download_pdf():
    r=session.get('last_result',{})
    if not r: return redirect(url_for('pp_page'))
    try:
        from fpdf import FPDF
        pdf = FPDF()
        pdf.add_page()
        pdf.set_auto_page_break(auto=True, margin=15)
        pdf.set_font("Arial", "B", 16)
        pdf.cell(0, 12, f"Predict AI - {r.get('disease','Report')}", ln=True, align='C')
        pdf.ln(5)
        pdf.set_font("Arial", "", 10)
        for k in ['patient_name','age','gender','date','duration','symptoms','description','diet','exercise','precaution','doctor','confidence']:
            v = str(r.get(k,'') or '')
            if not v: continue
            pdf.set_font("Arial", "B", 10)
            pdf.cell(32, 7, f"{k.upper()}: ", ln=False)
            pdf.set_font("Arial", "", 10)
            pdf.multi_cell(0, 7, v[:1500])
            pdf.ln(2)
        out_bytes = pdf.output()
        if isinstance(out_bytes, str):
            out_bytes = out_bytes.encode('latin-1')
        buf = io.BytesIO(out_bytes)
        buf.seek(0)
        return send_file(buf, as_attachment=True, download_name=f"PredictAI_{r.get('patient_name','Report')}.pdf", mimetype='application/pdf')
    except Exception as e:
        print(f"PDF error: {e}")
        html = f"<h2>{r.get('disease')} - {r.get('confidence')}%</h2><p>{r.get('description')}</p><p>Patient: {r.get('patient_name')}</p><a href='/resultp'>Back</a>"
        return render_template_string(html)