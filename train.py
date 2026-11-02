# train.py - Diseases.json -> Model + Symptoms pkl + qz + gz
import json
import pickle
import gzip
import os
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.preprocessing import LabelEncoder

def load_diseases(path="diseases.json"):
    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    print(f"Loaded {len(data)} diseases from {path}")
    return data

def build_corpus(diseases_data):
    X_texts = []
    y_labels = []
    symptoms_list = []
    
    for disease_name, info in diseases_data.items():
        # Combine all text fields for best matching
        desc = info.get("Description","")
        symp = info.get("Symptoms","")
        key_symp = info.get("Key_Symptoms","")
        
        full_text = f"{disease_name} {desc} {symp} {key_symp}"
        # Clean commas -> space for TF-IDF
        full_text = full_text.replace(",", " ").lower()
        
        X_texts.append(full_text)
        y_labels.append(disease_name)
        
        symptoms_list.append({
            "disease": disease_name,
            "symptoms": symp,
            "key_symptoms": key_symp,
            "description": desc
        })
    
    return X_texts, y_labels, symptoms_list

def quantize_matrix(matrix):
    # qz form = float16 quantized to save memory
    if hasattr(matrix, "toarray"):
        dense = matrix.toarray()
    else:
        dense = matrix
    qz = dense.astype(np.float16)
    return qz

def save_pkl(obj, path):
    with open(path, 'wb') as f:
        pickle.dump(obj, f, protocol=pickle.HIGHEST_PROTOCOL)
    size = os.path.getsize(path) / 1024
    print(f"Saved {path} - {size:.2f} KB")

def save_gz(obj, path):
    with gzip.open(path, 'wb') as f:
        pickle.dump(obj, f, protocol=pickle.HIGHEST_PROTOCOL)
    size = os.path.getsize(path) / 1024
    print(f"Saved {path} - {size:.2f} KB")

def save_qz_gz(qz_array, path_qz, path_gz):
    # qz = raw quantized pkl
    save_pkl(qz_array, path_qz)
    # gz = gzip of quantized
    save_gz(qz_array, path_gz)

if __name__ == "__main__":
    INPUT = "diseases.json"
    
    diseases_data = load_diseases(INPUT)
    X_texts, y_labels, symptoms_list = build_corpus(diseases_data)

    # 1. TF-IDF Vectorizer = Symptoms Model
    print("\nTraining TF-IDF Vectorizer...")
    vectorizer = TfidfVectorizer(
        ngram_range=(1,2),
        max_features=5000,
        stop_words='english',
        min_df=1
    )
    X_vectors = vectorizer.fit_transform(X_texts)
    
    # 2. Label Encoder
    le = LabelEncoder()
    y_encoded = le.fit_transform(y_labels)

    # 3. Prepare model.pkl content
    model_data = {
        "vectorizer": vectorizer,
        "label_encoder": le,
        "vectors": X_vectors,
        "labels": y_labels,
        "diseases_data": diseases_data  # full json for lookup
    }
    
    symptoms_data = {
        "symptoms_list": symptoms_list,
        "vectorizer_vocab": vectorizer.vocabulary_,
        "label_classes": le.classes_.tolist()
    }

    # 4. Save Normal PKL
    print("\n--- Saving PKL ---")
    save_pkl(model_data, "model.pkl")
    save_pkl(symptoms_data, "symptoms.pkl")
    save_pkl(symptoms_list, "symptoms_list.pkl") # extra simple list

    # 5. Save GZ (compressed)
    print("\n--- Saving GZ (gzip compressed) ---")
    save_gz(model_data, "model.gz")
    save_gz(symptoms_data, "symptoms.gz")

    # 6. Save QZ (quantized float16)
    print("\n--- Saving QZ (quantized float16) ---")
    X_qz = quantize_matrix(X_vectors)
    save_pkl(X_qz, "model.qz")
    save_pkl(X_qz, "symptoms.qz")
    
    save_gz(X_qz, "model.qz.gz")
    save_gz(X_qz, "symptoms.qz.gz")

    # Also save combined quantized model for direct use
    model_qz_data = {
        "vectorizer": vectorizer,
        "label_encoder": le,
        "vectors_qz": X_qz,  # float16
        "labels": y_labels
    }
    save_pkl(model_qz_data, "model_qz.pkl")
    save_gz(model_qz_data, "model_qz.gz")

    print("\n✅ All Done! Generated files:")
    for f in ["model.pkl", "symptoms.pkl", "model.gz", "symptoms.gz", "model.qz", "symptoms.qz", "model.qz.gz", "symptoms.qz.gz", "model_qz.pkl", "model_qz.gz"]:
        if os.path.exists(f):
            print(f" - {f}")