import json
import pickle
import gzip
import re
import os
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.preprocessing import LabelEncoder
from sklearn.ensemble import RandomForestClassifier

print("=== SMART DISEASE TRAINING V2 - NEW 221 JSON ===")

JSON_FILE = 'diseases.json'
if not os.path.exists(JSON_FILE):
    for name in ['disease_data.json', 'final_409.json', 'diseases_final.json', 'diseases_221.json']:
        if os.path.exists(name):
            JSON_FILE = name
            break

with open(JSON_FILE, 'r', encoding='utf-8') as f:
    diseases_data = json.load(f)

print(f"Total Diseases Loaded: {len(diseases_data)}")

all_symptoms_set = set()
X_texts = []
y_labels = []
qz_list = []

for disease_name, info in diseases_data.items():
    sym_raw = info.get('Symptoms', '') or info.get('symptoms', '') or ''
    key_raw = info.get('Key_Symptoms', '') or info.get('key_symptoms', '') or ''

    # NEW RULE: Jaanleva me Stage1...Stage4 hai -> poora parse karna
    # Normal me Stage nahi hai -> direct
    cleaned_list = []

    # 1) Key_Symptoms se (tune comma se diya hai)
    if key_raw:
        for part in key_raw.split(','):
            p = part.strip().lower()
            p = re.sub(r'\(.*?\)', '', p).strip()
            if len(p) >= 3:
                cleaned_list.append(p)
                all_symptoms_set.add(p)

    # 2) Symptoms se - Stage1: ... Stage2: ... ya 1. 2. format dono handle
    if sym_raw:
        # Stage wise split
        stage_parts = re.split(r'Stage\d+[:\-]?', sym_raw, flags=re.IGNORECASE)
        for sp in stage_parts:
            # ab 1. 2. se split
            sub_parts = re.split(r'\d+\.', sp)
            for p in sub_parts:
                p = p.strip()
                if len(p) < 4:
                    continue
                p = p.split(' if ')[0].split(' due ')[0].strip()
                p = re.sub(r'\(.*?\)', '', p).strip()
                p = p.lower()
                # extra long sentence ko short symptom me todo
                # 5-6 words tak rakho
                if p:
                    cleaned_list.append(p)
                    all_symptoms_set.add(p)

    # Fallback agar list empty
    if not cleaned_list:
        cleaned_list = [sym_raw.lower()[:200]]

    doc = " ".join(cleaned_list)
    X_texts.append(doc)
    y_labels.append(disease_name)

    # QZ file ke liye
    is_jaanleva = "Stage1" in str(info) or "Stage" in sym_raw
    if is_jaanleva:
        qz_list.append({"question": f"What are stages of {disease_name}?", "answer": sym_raw, "disease": disease_name, "type": "staged"})
        qz_list.append({"question": f"{disease_name} ke stages kya hain?", "answer": sym_raw, "disease": disease_name, "type": "staged_hindi"})
    else:
        qz_list.append({"question": f"What are symptoms of {disease_name}?", "answer": sym_raw, "disease": disease_name, "type": "normal"})

    qz_list.append({"question": f"What is {disease_name}?", "answer": info.get('Description',''), "disease": disease_name, "type": "description"})

print(f"Total Unique Symptoms Found: {len(all_symptoms_set)}")

# 1. symptoms.pkl - 3200+ search ke liye (tere app.py wala)
symptoms_list = sorted(list(all_symptoms_set))
with open('symptoms.pkl', 'wb') as f:
    pickle.dump(symptoms_list, f)
print("✅ symptoms.pkl saved!")

# 2. info.pkl - naya manga tha
with open('info.pkl', 'wb') as f:
    pickle.dump(diseases_data, f)
print("✅ info.pkl saved!")

# 3. qz file - qz.pkl + qz.json dono
with open('qz.pkl', 'wb') as f:
    pickle.dump(qz_list, f)
with open('qz.json', 'w', encoding='utf-8') as f:
    json.dump(qz_list, f, indent=2, ensure_ascii=False)
print(f"✅ qz.pkl + qz.json saved! Total Q: {len(qz_list)}")

# 4. Vectorizer + Model
vectorizer = TfidfVectorizer(
    max_features=5000,
    ngram_range=(1,2),
    stop_words='english'
)
X_vec = vectorizer.fit_transform(X_texts)

label_encoder = LabelEncoder()
y_encoded = label_encoder.fit_transform(y_labels)

model = RandomForestClassifier(
    n_estimators=300,
    max_depth=None,
    random_state=42,
    n_jobs=-1,
    class_weight='balanced'
)
model.fit(X_vec, y_encoded)

print(f"✅ Model Trained! Accuracy: {model.score(X_vec, y_encoded)*100:.2f}%")

# 5. model.pkl + model.pkl.gz
model_data = {
    'model': model,
    'vectorizer': vectorizer,
    'label_encoder': label_encoder,
    'diseases_data': diseases_data,
    'disease_data': diseases_data,
}

with open('model.pkl', 'wb') as f:
    pickle.dump(model_data, f)
print("✅ model.pkl saved!")

with gzip.open('model.pkl.gz', 'wb') as f:
    pickle.dump(model_data, f)
print("✅ model.pkl.gz saved! (Vercel ke liye)")

with open('diseases_info.pkl', 'wb') as f:
    pickle.dump(diseases_data, f)
print("✅ diseases_info.pkl saved!")

print("\n=== DONE BHAI 😇 ===")
print(f"Files: model.pkl ({os.path.getsize('model.pkl')//1024} KB), symptoms.pkl ({os.path.getsize('symptoms.pkl')//1024} KB), info.pkl, qz.pkl")
print(f"Diseases: {len(diseases_data)} | Symptoms: {len(symptoms_list)}")

# Test
test_input = "high fever severe joint pain rash red lymph nodes"
test_vec = vectorizer.transform([test_input])
pred = model.predict(test_vec)[0]
disease_pred = label_encoder.inverse_transform([pred])[0]
print(f"\nTest: '{test_input}' -> Predicted: {disease_pred}")