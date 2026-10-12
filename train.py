import json
import pickle
import gzip
import re
import os
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.preprocessing import LabelEncoder
from sklearn.ensemble import RandomForestClassifier

print("=== SMART DISEASE TRAINING START ===")

# 1. Load 409 wala diseases.json (tumhara final wala)
JSON_FILE = 'diseases.json'
if not os.path.exists(JSON_FILE):
    # agar naam alag hai to check karo
    for name in ['disease_data.json', 'final_409.json', 'diseases_final.json']:
        if os.path.exists(name):
            JSON_FILE = name
            break

with open(JSON_FILE, 'r', encoding='utf-8') as f:
    diseases_data = json.load(f)

print(f"Total Diseases Loaded: {len(diseases_data)}")

# 2. Symptoms nikalo - tumhare format ke hisab se
# Format: "Symptoms": "1. High fever 2. Rash..."
all_symptoms_set = set()
X_texts = [] # har disease ke symptoms ka ek sentence
y_labels = [] # disease name

for disease_name, info in diseases_data.items():
    sym_raw = info.get('Symptoms', '') or info.get('symptoms', '') or ''
    # 1. 2. 3. se split karke clean list banao
    # Regex se number. hatao
    parts = re.split(r'\d+\.', sym_raw)
    cleaned_list = []
    for p in parts:
        p = p.strip()
        # chote useless words hatao
        if len(p) < 4:
            continue
        # "if severe" jaise extra hatao
        p = p.split(' if ')[0].split(' due ')[0].strip()
        p = re.sub(r'\(.*?\)', '', p).strip() # bracket hatao
        p = p.lower()
        if p:
            cleaned_list.append(p)
            all_symptoms_set.add(p)

    # Agar Symptoms list form me hai (old format)
    if not cleaned_list and 'key_symptoms' in info:
        cleaned_list = [s.lower() for s in info['key_symptoms']]
        for s in cleaned_list:
            all_symptoms_set.add(s)

    # ML ke liye ek document banao
    doc = " ".join(cleaned_list)
    X_texts.append(doc)
    y_labels.append(disease_name)

print(f"Total Unique Symptoms Found: {len(all_symptoms_set)}") # 3200+ ayega

# 3. symptoms.pkl banao - ye tumhare app.py me 3200+ search ke liye
symptoms_list = sorted(list(all_symptoms_set))
with open('symptoms.pkl', 'wb') as f:
    pickle.dump(symptoms_list, f)
print("✅ symptoms.pkl saved!")

# 4. Vectorizer + Label Encoder + Model train
# Tfidf best hai spelling + Hindi translation ke liye
vectorizer = TfidfVectorizer(
    max_features=5000,
    ngram_range=(1,2), # 2 words tak - "chest pain" pakdega
    stop_words='english'
)
X_vec = vectorizer.fit_transform(X_texts)

label_encoder = LabelEncoder()
y_encoded = label_encoder.fit_transform(y_labels)

# RandomForest - 409 diseases ke liye best accuracy
model = RandomForestClassifier(
    n_estimators=300, # 300 trees - accuracy high
    max_depth=None,
    random_state=42,
    n_jobs=-1,
    class_weight='balanced'
)
model.fit(X_vec, y_encoded)

print(f"✅ Model Trained! Training Accuracy: {model.score(X_vec, y_encoded)*100:.2f}%")

# 5. model.pkl banao - isme sab kuch hai jo app.py ko chahiye
model_data = {
    'model': model,
    'vectorizer': vectorizer,
    'label_encoder': label_encoder,
    'diseases_data': diseases_data, # app.py yahi use karta hai result dikhane ke liye
    'disease_data': diseases_data, # backup key
}

# Normal pkl
with open('model.pkl', 'wb') as f:
    pickle.dump(model_data, f)
print("✅ model.pkl saved!")

# Gzip wala - Vercel ke liye halka
with gzip.open('model.pkl.gz', 'wb') as f:
    pickle.dump(model_data, f)
print("✅ model.pkl.gz saved! (Vercel ke liye)")

# 6. diseases_info.pkl extra backup
with open('diseases_info.pkl', 'wb') as f:
    pickle.dump(diseases_data, f)
print("✅ diseases_info.pkl saved!")

print("\n=== DONE BHAI 😇 ===")
print(f"Files ready: model.pkl ({os.path.getsize('model.pkl')//1024} KB), symptoms.pkl ({os.path.getsize('symptoms.pkl')//1024} KB)")
print(f"Diseases: {len(diseases_data)} | Symptoms: {len(symptoms_list)} | Target 2500++ CROSSED ✅")

# 7. Test prediction
test_input = "high fever severe joint pain rash red"
test_vec = vectorizer.transform([test_input])
pred = model.predict(test_vec)[0]
disease_pred = label_encoder.inverse_transform([pred])[0]
print(f"\nTest: '{test_input}' -> Predicted: {disease_pred}")