from flask import Flask, render_template, request, jsonify, session
import json
import os
from datetime import datetime
from deep_translator import GoogleTranslator
from concurrent.futures import ThreadPoolExecutor
import threading

app = Flask(__name__)
app.secret_key = 'your-secret-key-here'

# Department configuration
DEPARTMENTS = {
    'gastrointestinal': 'Gastrointestinal Issues',
    'dermatology': 'Skin & Dermatology',
    'first_aid': 'First Aid & Emergency',
    'general_medicine': 'General Medicine',
    'mental_health': 'Mental Health',
    'musculoskeletal': 'Musculoskeletal & Pain'
}

# Treatment types with enhanced descriptions
TREATMENT_TYPES = {
    'allopathy': '🏥 Modern Medicine (Allopathy)',
    'homeopathy': '🌿 Homeopathic Medicine', 
    'ayurveda': '🌱 Ayurvedic Medicine',
    'home_remedy': '🏠 Home Remedies & Lifestyle'
}

# Language configuration
LANGUAGES = {
    'en': 'English',
    'es': 'Español',
    'fr': 'Français',
    'de': 'Deutsch',
    'hi': 'हिन्दी',
    'ta': 'தமிழ்',
    'te': 'తెలుగు',
    'kn': 'ಕನ್ನಡ',
    'ml': 'മലയാളം',
    'bn': 'বাংলা',
    'gu': 'ગુજરાતી',
    'mr': 'मराठी',
    'pa': 'ਪੰਜਾਬੀ'
}

# ----------------------------
# Translation helpers (global)
# ----------------------------
translation_cache = {}
translator_pool = ThreadPoolExecutor(max_workers=4)
translation_lock = threading.Lock()

def translate_text(text: str) -> str:
    """Threaded, cached translation for speed."""
    if not text:
        return text
    lang = session.get("language", "en")
    if lang == "en":
        return text

    key = (text, lang)
    if key in translation_cache:
        return translation_cache[key]

    def do_translate():
        try:
            return GoogleTranslator(source="auto", target=lang).translate(text)
        except Exception as e:
            print(f"[⚠️ Translation error: {e}] for text: {text[:50]}")
            return text

    future = translator_pool.submit(do_translate)
    try:
        translated = future.result(timeout=3)
        translation_cache[key] = translated
        return translated
    except Exception:
        return text

def translate_question(question: dict) -> dict:
    """Translate a question + options efficiently."""
    if not question:
        return None

    q_copy = json.loads(json.dumps(question))
    q_copy["question"] = translate_text(q_copy.get("question", ""))

    lang = session.get("language", "en")
    if lang == "en":
        return q_copy

    if "options" in q_copy:
        try:
            texts = [opt["text"] for opt in q_copy["options"] if "text" in opt]
            translated = GoogleTranslator(source="auto", target=lang).translate_batch(texts)
            for i, opt in enumerate(q_copy["options"]):
                opt["text"] = translated[i]
        except Exception as e:
            print(f"[⚠️ Batch translation failed: {e}]")
            for opt in q_copy["options"]:
                opt["text"] = translate_text(opt["text"])
    return q_copy

def translate_treatments(treatments: dict) -> dict:
    """Translate treatment recommendations."""
    if not treatments:
        return treatments
    
    lang = session.get("language", "en")
    if lang == "en":
        return treatments
    
    translated_treatments = {}
    for treatment_type, treatment_list in treatments.items():
        if isinstance(treatment_list, list):
            translated_treatments[treatment_type] = [translate_text(item) for item in treatment_list]
        else:
            translated_treatments[treatment_type] = translate_text(treatment_list)
    
    return translated_treatments

@app.before_request
def clear_old_cache():
    """Light cache limiter — keeps last 500 translations"""
    if len(translation_cache) > 500:
        for _ in range(100):
            if translation_cache:
                translation_cache.pop(next(iter(translation_cache)))

class MedicalChatbot:
    def __init__(self):
        self.departments_data = {}
        self.load_all_departments()
        self.conversation_flows = self.create_conversation_flows()
    
    def load_all_departments(self):
        """Load all department JSON files"""
        for dept in DEPARTMENTS.keys():
            try:
                file_path = f'data/{dept}.json'
                if os.path.exists(file_path):
                    with open(file_path, 'r', encoding='utf-8') as f:
                        self.departments_data[dept] = json.load(f)
                else:
                    print(f"Warning: {file_path} not found")
                    self.departments_data[dept] = {}
            except Exception as e:
                print(f"Error loading {dept}: {e}")
                self.departments_data[dept] = {}
    
    def create_conversation_flows(self):
        """Define the question flow for each department"""
        return {
            'gastrointestinal': [
                {
                    'id': 'symptom_location',
                    'question': 'Where is your abdominal discomfort primarily located?',
                    'type': 'single_choice',
                    'options': [
                        {'value': 'upper_abdomen', 'text': 'Upper Abdomen (below chest)'},
                        {'value': 'lower_abdomen', 'text': 'Lower Abdomen (below belly button)'},
                        {'value': 'whole_abdomen', 'text': 'Whole Abdomen'},
                        {'value': 'right_side', 'text': 'Right Side'},
                        {'value': 'left_side', 'text': 'Left Side'},
                        {'value': 'none', 'text': 'No specific location'}
                    ]
                },
                {
                    'id': 'upper_abdomen_timing',
                    'question': 'When does your upper abdominal pain occur?',
                    'type': 'single_choice',
                    'depends_on': {'symptom_location': 'upper_abdomen'},
                    'options': [
                        {'value': 'after_meals', 'text': 'After Eating'},
                        {'value': 'empty_stomach', 'text': 'On Empty Stomach'},
                        {'value': 'constant', 'text': 'Constant Pain'},
                        {'value': 'night_time', 'text': 'At Night'},
                        {'value': 'none', 'text': 'No specific timing'}
                    ]
                },
                {
                    'id': 'pain_character',
                    'question': 'What best describes the character of your pain?',
                    'type': 'single_choice',
                    'options': [
                        {'value': 'burning', 'text': 'Burning Sensation'},
                        {'value': 'cramping', 'text': 'Cramping Pain'},
                        {'value': 'sharp', 'text': 'Sharp/Stabbing Pain'},
                        {'value': 'dull', 'text': 'Dull Ache'},
                        {'value': 'none', 'text': 'No specific character'}
                    ]
                },
                {
                    'id': 'digestive_symptoms',
                    'question': 'Do you experience any of these digestive symptoms?',
                    'type': 'multiple_choice',
                    'options': [
                        {'value': 'heartburn', 'text': 'Heartburn/Acidity'},
                        {'value': 'bloating', 'text': 'Bloating'},
                        {'value': 'belching', 'text': 'Excessive Belching'},
                        {'value': 'nausea', 'text': 'Nausea'},
                        {'value': 'vomiting', 'text': 'Vomiting'},
                        {'value': 'loss_of_appetite', 'text': 'Loss of Appetite'},
                        {'value': 'none', 'text': 'None of these'}
                    ]
                },
                {
                    'id': 'bowel_changes',
                    'question': 'Any changes in your bowel movements?',
                    'type': 'multiple_choice',
                    'options': [
                        {'value': 'constipation', 'text': 'Constipation'},
                        {'value': 'diarrhea', 'text': 'Diarrhea'},
                        {'value': 'alternating', 'text': 'Alternating Constipation/Diarrhea'},
                        {'value': 'bloody_stools', 'text': 'Blood in Stool'},
                        {'value': 'mucus_stools', 'text': 'Mucus in Stool'},
                        {'value': 'straining', 'text': 'Straining during Bowel Movement'},
                        {'value': 'urgency', 'text': 'Urgent Need for Bowel Movement'},
                        {'value': 'none', 'text': 'No bowel changes'}
                    ]
                },
                {
                    'id': 'systemic_symptoms',
                    'question': 'Are you experiencing any of these general symptoms?',
                    'type': 'multiple_choice',
                    'options': [
                        {'value': 'fever', 'text': 'Fever'},
                        {'value': 'jaundice', 'text': 'Yellowing of Skin/Eyes (Jaundice)'},
                        {'value': 'painful_bowel_movement', 'text': 'Painful Bowel Movements'},
                        {'value': 'none', 'text': 'None of these'}
                    ]
                }
            ],
            'dermatology': [
                {
                    'id': 'skin_condition_type',
                    'question': 'What type of skin condition are you experiencing?',
                    'type': 'single_choice',
                    'options': [
                        {'value': 'rash_bumps', 'text': 'Rash or Bumps'},
                        {'value': 'dry_patches', 'text': 'Dry/Scaly Patches'},
                        {'value': 'oily_skin', 'text': 'Oily Skin with Pimples'},
                        {'value': 'color_changes', 'text': 'Skin Color Changes'},
                        {'value': 'blisters', 'text': 'Blisters or Sores'},
                        {'value': 'none', 'text': 'Not Sure'}
                    ]
                },
                {
                    'id': 'skin_location',
                    'question': 'Where is the skin condition located?',
                    'type': 'multiple_choice',
                    'options': [
                        {'value': 'face', 'text': 'Face'},
                        {'value': 'scalp', 'text': 'Scalp'},
                        {'value': 'arms', 'text': 'Arms'},
                        {'value': 'legs', 'text': 'Legs'},
                        {'value': 'chest_back', 'text': 'Chest or Back'},
                        {'value': 'all_over_body', 'text': 'All Over Body'},
                        {'value': 'none', 'text': 'No Specific Location'}
                    ]
                },
                {
                    'id': 'sensation',
                    'question': 'What sensation do you feel on the affected skin?',
                    'type': 'multiple_choice',
                    'options': [
                        {'value': 'itchy', 'text': 'Itchy'},
                        {'value': 'burning', 'text': 'Burning'},
                        {'value': 'painful', 'text': 'Painful'},
                        {'value': 'tender', 'text': 'Tender to Touch'},
                        {'value': 'no_sensation', 'text': 'No Sensation'},
                        {'value': 'none', 'text': 'None of These'}
                    ]
                },
                {
                    'id': 'severity',
                    'question': 'How severe is the itching or discomfort?',
                    'type': 'single_choice',
                    'options': [
                        {'value': 'mild', 'text': 'Mild (barely noticeable)'},
                        {'value': 'moderate', 'text': 'Moderate (annoying but manageable)'},
                        {'value': 'severe', 'text': 'Severe (interferes with daily activities)'},
                        {'value': 'none', 'text': 'No Itching/Discomfort'}
                    ]
                },
                {
                    'id': 'duration',
                    'question': 'How long have you had this skin condition?',
                    'type': 'single_choice',
                    'options': [
                        {'value': 'recent', 'text': 'Recent (less than 1 week)'},
                        {'value': 'chronic', 'text': 'Chronic (more than 1 month)'},
                        {'value': 'recurring', 'text': 'Comes and Goes'},
                        {'value': 'none', 'text': 'Not Sure'}
                    ]
                },
                {
                    'id': 'triggers',
                    'question': 'Do you notice any triggers that make it worse?',
                    'type': 'multiple_choice',
                    'options': [
                        {'value': 'food', 'text': 'Certain Foods'},
                        {'value': 'weather', 'text': 'Weather Changes'},
                        {'value': 'cosmetics', 'text': 'Cosmetics or Soaps'},
                        {'value': 'stress', 'text': 'Stress'},
                        {'value': 'medications', 'text': 'Medications'},
                        {'value': 'none', 'text': 'No Known Triggers'}
                    ]
                },
                {
                    'id': 'other_symptoms',
                    'question': 'Are you experiencing any other symptoms?',
                    'type': 'multiple_choice',
                    'options': [
                        {'value': 'swelling', 'text': 'Swelling'},
                        {'value': 'pus', 'text': 'Pus or Discharge'},
                        {'value': 'hair_loss', 'text': 'Hair Loss'},
                        {'value': 'nail_changes', 'text': 'Nail Changes'},
                        {'value': 'fever', 'text': 'Fever'},
                        {'value': 'none', 'text': 'None of These'}
                    ]
                }
            ],
            'musculoskeletal': [
                {
                    'id': 'pain_location',
                    'question': 'Where is your pain primarily located?',
                    'type': 'multiple_choice',
                    'options': [
                        {'value': 'neck', 'text': 'Neck'},
                        {'value': 'shoulder', 'text': 'Shoulder'},
                        {'value': 'upper_back', 'text': 'Upper Back'},
                        {'value': 'lower_back', 'text': 'Lower Back'},
                        {'value': 'hip', 'text': 'Hip'},
                        {'value': 'knee', 'text': 'Knee'},
                        {'value': 'elbow', 'text': 'Elbow'},
                        {'value': 'wrist', 'text': 'Wrist'},
                        {'value': 'ankle', 'text': 'Ankle'},
                        {'value': 'multiple_joints', 'text': 'Multiple Joints'},
                        {'value': 'none', 'text': 'No Specific Location'}
                    ]
                },
                {
                    'id': 'pain_type',
                    'question': 'What type of pain are you experiencing?',
                    'type': 'single_choice',
                    'options': [
                        {'value': 'sharp_shooting', 'text': 'Sharp/Shooting Pain'},
                        {'value': 'dull_ache', 'text': 'Dull Ache'},
                        {'value': 'burning', 'text': 'Burning Sensation'},
                        {'value': 'throbbing', 'text': 'Throbbing Pain'},
                        {'value': 'stabbing', 'text': 'Stabbing Pain'},
                        {'value': 'none', 'text': 'No Specific Type'}
                    ]
                },
                {
                    'id': 'pain_timing',
                    'question': 'When does the pain occur or worsen?',
                    'type': 'multiple_choice',
                    'options': [
                        {'value': 'morning', 'text': 'Morning Stiffness'},
                        {'value': 'activity', 'text': 'During Activity'},
                        {'value': 'rest', 'text': 'During Rest'},
                        {'value': 'night', 'text': 'At Night'},
                        {'value': 'constant', 'text': 'Constant Pain'},
                        {'value': 'none', 'text': 'No Specific Timing'}
                    ]
                },
                {
                    'id': 'mobility_issues',
                    'question': 'What mobility issues are you experiencing?',
                    'type': 'multiple_choice',
                    'options': [
                        {'value': 'difficulty_moving', 'text': 'Difficulty Moving'},
                        {'value': 'stiffness', 'text': 'Stiffness'},
                        {'value': 'limited_range', 'text': 'Limited Range of Motion'},
                        {'value': 'weakness', 'text': 'Weakness'},
                        {'value': 'giving_way', 'text': 'Joint Giving Way'},
                        {'value': 'none', 'text': 'No Mobility Issues'}
                    ]
                },
                {
                    'id': 'swelling_inflammation',
                    'question': 'Do you have any signs of inflammation?',
                    'type': 'multiple_choice',
                    'options': [
                        {'value': 'swelling', 'text': 'Swelling'},
                        {'value': 'redness', 'text': 'Redness'},
                        {'value': 'warmth', 'text': 'Warmth to Touch'},
                        {'value': 'tenderness', 'text': 'Tenderness'},
                        {'value': 'none', 'text': 'No Inflammation Signs'}
                    ]
                },
                {
                    'id': 'injury_cause',
                    'question': 'Was this caused by an injury or specific activity?',
                    'type': 'single_choice',
                    'options': [
                        {'value': 'recent_injury', 'text': 'Recent Injury'},
                        {'value': 'overuse', 'text': 'Overuse/Repetitive Motion'},
                        {'value': 'sports', 'text': 'Sports Injury'},
                        {'value': 'fall', 'text': 'Fall or Accident'},
                        {'value': 'none', 'text': 'No Specific Cause'}
                    ]
                },
                {
                    'id': 'duration',
                    'question': 'How long have you had these symptoms?',
                    'type': 'single_choice',
                    'options': [
                        {'value': 'acute', 'text': 'Recent (less than 1 week)'},
                        {'value': 'subacute', 'text': 'Few Weeks (1-4 weeks)'},
                        {'value': 'chronic', 'text': 'Chronic (more than 3 months)'},
                        {'value': 'recurring', 'text': 'Comes and Goes'},
                        {'value': 'none', 'text': 'Not Sure'}
                    ]
                },
                {
                    'id': 'other_symptoms',
                    'question': 'Are you experiencing any other symptoms?',
                    'type': 'multiple_choice',
                    'options': [
                        {'value': 'numbness', 'text': 'Numbness'},
                        {'value': 'tingling', 'text': 'Tingling Sensation'},
                        {'value': 'muscle_spasms', 'text': 'Muscle Spasms'},
                        {'value': 'fatigue', 'text': 'Fatigue'},
                        {'value': 'fever', 'text': 'Fever'},
                        {'value': 'none', 'text': 'None of These'}
                    ]
                }
            ],
            'mental_health': [
                {
                    'id': 'mood_symptoms',
                    'question': 'What mood-related symptoms are you experiencing?',
                    'type': 'multiple_choice',
                    'options': [
                        {'value': 'sadness', 'text': 'Sadness or Hopelessness'},
                        {'value': 'anxiety', 'text': 'Anxiety or Worry'},
                        {'value': 'irritability', 'text': 'Irritability or Anger'},
                        {'value': 'mood_swings', 'text': 'Mood Swings'},
                        {'value': 'emotional_numbness', 'text': 'Emotional Numbness'},
                        {'value': 'none', 'text': 'None of These'}
                    ]
                },
                {
                    'id': 'physical_symptoms',
                    'question': 'What physical symptoms are you experiencing?',
                    'type': 'multiple_choice',
                    'options': [
                        {'value': 'sleep_problems', 'text': 'Sleep Problems'},
                        {'value': 'appetite_changes', 'text': 'Appetite Changes'},
                        {'value': 'fatigue', 'text': 'Fatigue or Low Energy'},
                        {'value': 'body_aches', 'text': 'Body Aches or Pains'},
                        {'value': 'digestive_issues', 'text': 'Digestive Issues'},
                        {'value': 'none', 'text': 'None of These'}
                    ]
                },
                {
                    'id': 'cognitive_symptoms',
                    'question': 'What thinking-related symptoms are you experiencing?',
                    'type': 'multiple_choice',
                    'options': [
                        {'value': 'concentration', 'text': 'Concentration Problems'},
                        {'value': 'memory', 'text': 'Memory Issues'},
                        {'value': 'indecisiveness', 'text': 'Indecisiveness'},
                        {'value': 'racing_thoughts', 'text': 'Racing Thoughts'},
                        {'value': 'negative_thoughts', 'text': 'Negative Thoughts'},
                        {'value': 'none', 'text': 'None of These'}
                    ]
                },
                {
                    'id': 'behavioral_symptoms',
                    'question': 'What behavior changes have you noticed?',
                    'type': 'multiple_choice',
                    'options': [
                        {'value': 'social_withdrawal', 'text': 'Social Withdrawal'},
                        {'value': 'loss_interest', 'text': 'Loss of Interest in Activities'},
                        {'value': 'agitation', 'text': 'Agitation or Restlessness'},
                        {'value': 'procrastination', 'text': 'Procrastination'},
                        {'value': 'routine_changes', 'text': 'Changes in Routine'},
                        {'value': 'none', 'text': 'None of These'}
                    ]
                },
                {
                    'id': 'duration',
                    'question': 'How long have you been experiencing these symptoms?',
                    'type': 'single_choice',
                    'options': [
                        {'value': 'recent', 'text': 'Recent (less than 2 weeks)'},
                        {'value': 'chronic', 'text': 'Chronic (more than 2 months)'},
                        {'value': 'daily', 'text': 'Daily'},
                        {'value': 'episodic', 'text': 'Comes and Goes'},
                        {'value': 'constant', 'text': 'Constant'},
                        {'value': 'none', 'text': 'Not Sure'}
                    ]
                },
                {
                    'id': 'impact_life',
                    'question': 'How is this affecting your daily life?',
                    'type': 'multiple_choice',
                    'options': [
                        {'value': 'work_school', 'text': 'Work or School Problems'},
                        {'value': 'relationships', 'text': 'Relationship Issues'},
                        {'value': 'self_care', 'text': 'Difficulty with Self-Care'},
                        {'value': 'daily_tasks', 'text': 'Daily Tasks Challenging'},
                        {'value': 'none', 'text': 'No Significant Impact'}
                    ]
                },
                {
                    'id': 'stress_triggers',
                    'question': 'Are there any specific stressors or triggers?',
                    'type': 'multiple_choice',
                    'options': [
                        {'value': 'work_stress', 'text': 'Work Stress'},
                        {'value': 'relationship_stress', 'text': 'Relationship Stress'},
                        {'value': 'financial_stress', 'text': 'Financial Stress'},
                        {'value': 'health_concerns', 'text': 'Health Concerns'},
                        {'value': 'life_changes', 'text': 'Major Life Changes'},
                        {'value': 'none', 'text': 'No Specific Triggers'}
                    ]
                },
                {
                    'id': 'severe_symptoms',
                    'question': 'Are you experiencing any of these severe symptoms?',
                    'type': 'multiple_choice',
                    'options': [
                        {'value': 'panic_attacks', 'text': 'Panic Attacks'},
                        {'value': 'suicidal_thoughts', 'text': 'Suicidal Thoughts'},
                        {'value': 'self_harm', 'text': 'Self-Harm Thoughts'},
                        {'value': 'detachment', 'text': 'Feeling Detached from Reality'},
                        {'value': 'extreme_fear', 'text': 'Extreme Fear'},
                        {'value': 'none', 'text': 'None of These'}
                    ]
                }
            ],
            'first_aid': [
                {
                    'id': 'injury_type',
                    'question': 'What type of injury or emergency are you dealing with?',
                    'type': 'single_choice',
                    'options': [
                        {'value': 'cuts', 'text': 'Cuts or Scrapes'},
                        {'value': 'burns', 'text': 'Burns'},
                        {'value': 'sprains', 'text': 'Sprains or Strains'},
                        {'value': 'fractures', 'text': 'Possible Fractures'},
                        {'value': 'bleeding', 'text': 'Bleeding'},
                        {'value': 'bites', 'text': 'Animal or Insect Bites'},
                        {'value': 'other', 'text': 'Other Emergency'},
                        {'value': 'none', 'text': 'Not Sure'}
                    ]
                },
                {
                    'id': 'bleeding_level',
                    'question': 'Is there bleeding?',
                    'type': 'single_choice',
                    'options': [
                        {'value': 'minor_bleeding', 'text': 'Minor Bleeding'},
                        {'value': 'heavy_bleeding', 'text': 'Heavy Bleeding'},
                        {'value': 'no_bleeding', 'text': 'No Bleeding'},
                        {'value': 'none', 'text': 'Not Sure'}
                    ]
                },
                {
                    'id': 'pain_level',
                    'question': 'How severe is the pain?',
                    'type': 'single_choice',
                    'options': [
                        {'value': 'mild_pain', 'text': 'Mild Pain'},
                        {'value': 'moderate_pain', 'text': 'Moderate Pain'},
                        {'value': 'severe_pain', 'text': 'Severe Pain'},
                        {'value': 'none', 'text': 'No Pain'}
                    ]
                },
                {
                    'id': 'emergency_signs',
                    'question': 'Are there any emergency warning signs?',
                    'type': 'multiple_choice',
                    'options': [
                        {'value': 'breathing', 'text': 'Difficulty Breathing'},
                        {'value': 'unconscious', 'text': 'Unconsciousness'},
                        {'value': 'allergy', 'text': 'Severe Allergic Reaction'},
                        {'value': 'chest_pain', 'text': 'Chest Pain'},
                        {'value': 'head_injury', 'text': 'Head Injury'},
                        {'value': 'none', 'text': 'None of These'}
                    ]
                },
                {
                    'id': 'mobility',
                    'question': 'Can the injured area move normally?',
                    'type': 'single_choice',
                    'options': [
                        {'value': 'full_movement', 'text': 'Full Movement'},
                        {'value': 'limited_movement', 'text': 'Limited Movement'},
                        {'value': 'no_movement', 'text': 'Cannot Move'},
                        {'value': 'none', 'text': 'Not Applicable'}
                    ]
                }
            ],
            'general_medicine': [
                {
                    'id': 'main_symptoms',
                    'question': 'What are your main symptoms?',
                    'type': 'multiple_choice',
                    'options': [
                        {'value': 'fever', 'text': 'Fever'},
                        {'value': 'cough', 'text': 'Cough'},
                        {'value': 'sore_throat', 'text': 'Sore Throat'},
                        {'value': 'runny_nose', 'text': 'Runny Nose'},
                        {'value': 'headache', 'text': 'Headache'},
                        {'value': 'body_aches', 'text': 'Body Aches'},
                        {'value': 'nausea', 'text': 'Nausea'},
                        {'value': 'diarrhea', 'text': 'Diarrhea'},
                        {'value': 'none', 'text': 'None of These'}
                    ]
                },
                {
                    'id': 'fever_level',
                    'question': 'Do you have fever?',
                    'type': 'single_choice',
                    'options': [
                        {'value': 'mild_fever', 'text': 'Mild Fever (below 101°F)'},
                        {'value': 'high_fever', 'text': 'High Fever (above 101°F)'},
                        {'value': 'chills', 'text': 'Chills without Fever'},
                        {'value': 'no_fever', 'text': 'No Fever'},
                        {'value': 'none', 'text': 'Not Sure'}
                    ]
                },
                {
                    'id': 'respiratory_symptoms',
                    'question': 'Any breathing or chest symptoms?',
                    'type': 'multiple_choice',
                    'options': [
                        {'value': 'congestion', 'text': 'Nasal Congestion'},
                        {'value': 'shortness', 'text': 'Shortness of Breath'},
                        {'value': 'chest_pain', 'text': 'Chest Pain'},
                        {'value': 'sinus', 'text': 'Sinus Pressure'},
                        {'value': 'none', 'text': 'None of These'}
                    ]
                },
                {
                    'id': 'digestive_symptoms',
                    'question': 'Any digestive symptoms?',
                    'type': 'multiple_choice',
                    'options': [
                        {'value': 'nausea', 'text': 'Nausea'},
                        {'value': 'vomiting', 'text': 'Vomiting'},
                        {'value': 'diarrhea', 'text': 'Diarrhea'},
                        {'value': 'abdominal_pain', 'text': 'Abdominal Pain'},
                        {'value': 'loss_appetite', 'text': 'Loss of Appetite'},
                        {'value': 'none', 'text': 'None of These'}
                    ]
                },
                {
                    'id': 'duration',
                    'question': 'How long have you had these symptoms?',
                    'type': 'single_choice',
                    'options': [
                        {'value': 'recent', 'text': 'Recent (1-3 days)'},
                        {'value': 'lasting', 'text': 'Lasting (4-7 days)'},
                        {'value': 'chronic', 'text': 'Chronic (over 1 week)'},
                        {'value': 'recurring', 'text': 'Comes and Goes'},
                        {'value': 'none', 'text': 'Not Sure'}
                    ]
                },
                {
                    'id': 'severity',
                    'question': 'How severe are your symptoms?',
                    'type': 'single_choice',
                    'options': [
                        {'value': 'mild', 'text': 'Mild (can do daily activities)'},
                        {'value': 'moderate', 'text': 'Moderate (affects daily activities)'},
                        {'value': 'severe', 'text': 'Severe (cannot do daily activities)'},
                        {'value': 'none', 'text': 'Not Sure'}
                    ]
                }
            ]
        }

    
    def get_next_question(self, department, current_answers):
        """Determine the next question based on current answers"""
        if department not in self.conversation_flows:
            return None
        
        flow = self.conversation_flows[department]
        
        for question in flow:
            # Check if this question was already answered
            if question['id'] in current_answers:
                continue
            
            # Check dependencies
            if 'depends_on' in question:
                dependency_met = True
                for dep_key, dep_value in question['depends_on'].items():
                    if current_answers.get(dep_key) != dep_value:
                        dependency_met = False
                        break
                if not dependency_met:
                    continue
            
            return question
        
        return None
    
    def map_answers_to_symptoms(self, department, answers):
        """Map user answers to symptom IDs in the JSON database"""
        symptom_mapping = {
            'gastrointestinal': {
                'upper_abdomen': 'SYP_001',
                'lower_abdomen': 'SYP_007',
                'right_side': 'SYP_008',
                'left_side': 'SYP_009',
                'whole_abdomen': 'SYP_010',
                'after_meals': 'SYP_001',
                'empty_stomach': 'SYP_004',
                'constant': 'SYP_005',
                'night_time': 'SYP_006',
                'burning': 'SYP_011',
                'cramping': 'SYP_007',
                'sharp': 'SYP_008',
                'dull': 'SYP_005',
                'nausea': 'SYP_014',
                'vomiting': 'SYP_014',
                'bloating': 'SYP_025',
                'heartburn': 'SYP_011',
                'belching': 'SYP_026',
                'loss_of_appetite': 'SYP_027',
                'constipation': 'SYP_018',
                'diarrhea': 'SYP_019',
                'alternating': 'SYP_020',
                'bloody_stools': 'SYP_021',
                'mucus_stools': 'SYP_022',
                'straining': 'SYP_023',
                'urgency': 'SYP_024',
                'fever': 'SYP_028',
                'jaundice': 'SYP_029',
                'painful_bowel_movement': 'SYP_030'
            },
            'dermatology': {
                'rash_bumps': 'DER_001',
                'dry_patches': 'DER_004',
                'oily_skin': 'DER_005',
                'color_changes': 'DER_006',
                'blisters': 'DER_003',
                'face': 'DER_014',
                'scalp': 'DER_015',
                'arms': 'DER_016',
                'legs': 'DER_017',
                'chest_back': 'DER_018',
                'all_over_body': 'DER_019',
                'itchy': 'DER_002',
                'burning': 'DER_010',
                'painful': 'DER_011',
                'tender': 'DER_012',
                'no_sensation': 'DER_013',
                'mild': 'DER_020',
                'moderate': 'DER_021',
                'severe': 'DER_022',
                'recent': 'DER_024',
                'chronic': 'DER_025',
                'recurring': 'DER_026',
                'food': 'DER_027',
                'weather': 'DER_028',
                'cosmetics': 'DER_029',
                'stress': 'DER_030',
                'medications': 'DER_031',
                'swelling': 'DER_032',
                'pus': 'DER_033',
                'hair_loss': 'DER_034',
                'nail_changes': 'DER_035',
                'fever': 'DER_036'
            },
            'musculoskeletal': {
                'neck': 'MSK_001',
                'shoulder': 'MSK_002',
                'upper_back': 'MSK_003',
                'lower_back': 'MSK_004',
                'hip': 'MSK_005',
                'knee': 'MSK_006',
                'elbow': 'MSK_007',
                'wrist': 'MSK_008',
                'ankle': 'MSK_009',
                'multiple_joints': 'MSK_010',
                'sharp_shooting': 'MSK_011',
                'dull_ache': 'MSK_012',
                'burning': 'MSK_013',
                'throbbing': 'MSK_014',
                'stabbing': 'MSK_015',
                'morning': 'MSK_016',
                'activity': 'MSK_017',
                'rest': 'MSK_018',
                'night': 'MSK_019',
                'constant': 'MSK_020',
                'difficulty_moving': 'MSK_021',
                'stiffness': 'MSK_022',
                'limited_range': 'MSK_023',
                'weakness': 'MSK_024',
                'giving_way': 'MSK_025',
                'swelling': 'MSK_026',
                'redness': 'MSK_027',
                'warmth': 'MSK_028',
                'tenderness': 'MSK_029',
                'recent_injury': 'MSK_030',
                'overuse': 'MSK_031',
                'sports': 'MSK_032',
                'fall': 'MSK_033',
                'acute': 'MSK_034',
                'subacute': 'MSK_035',
                'chronic': 'MSK_036',
                'recurring': 'MSK_037',
                'numbness': 'MSK_038',
                'tingling': 'MSK_039',
                'muscle_spasms': 'MSK_040',
                'fatigue': 'MSK_041',
                'fever': 'MSK_042'
            },
            'mental_health': {
                'sadness': 'MH_001',
                'anxiety': 'MH_002',
                'irritability': 'MH_003',
                'mood_swings': 'MH_004',
                'emotional_numbness': 'MH_005',
                'sleep_problems': 'MH_006',
                'appetite_changes': 'MH_007',
                'fatigue': 'MH_008',
                'body_aches': 'MH_009',
                'digestive_issues': 'MH_010',
                'concentration': 'MH_011',
                'memory': 'MH_012',
                'indecisiveness': 'MH_013',
                'racing_thoughts': 'MH_014',
                'negative_thoughts': 'MH_015',
                'social_withdrawal': 'MH_016',
                'loss_interest': 'MH_017',
                'agitation': 'MH_018',
                'procrastination': 'MH_019',
                'routine_changes': 'MH_020',
                'recent': 'MH_021',
                'chronic': 'MH_022',
                'daily': 'MH_023',
                'episodic': 'MH_024',
                'constant': 'MH_025',
                'work_school': 'MH_026',
                'relationships': 'MH_027',
                'self_care': 'MH_028',
                'daily_tasks': 'MH_029',
                'work_stress': 'MH_030',
                'relationship_stress': 'MH_031',
                'financial_stress': 'MH_032',
                'health_concerns': 'MH_033',
                'life_changes': 'MH_034',
                'panic_attacks': 'MH_035',
                'suicidal_thoughts': 'MH_036',
                'self_harm': 'MH_037',
                'detachment': 'MH_038',
                'extreme_fear': 'MH_039'
            },
            'first_aid': {
                'cuts': 'FA_001',
                'burns': 'FA_002',
                'sprains': 'FA_004',
                'fractures': 'FA_005',
                'bleeding': 'FA_009',
                'bites': 'FA_007',
                'minor_bleeding': 'FA_009',
                'heavy_bleeding': 'FA_010',
                'no_bleeding': 'FA_011',
                'mild_pain': 'FA_012',
                'moderate_pain': 'FA_013',
                'severe_pain': 'FA_014',
                'breathing': 'FA_024',
                'unconscious': 'FA_025',
                'allergy': 'FA_026',
                'chest_pain': 'FA_027',
                'head_injury': 'FA_028',
                'full_movement': 'FA_018',
                'limited_movement': 'FA_019',
                'no_movement': 'FA_020'
            },
            'general_medicine': {
                'fever': 'GM_001',
                'cough': 'GM_005',
                'sore_throat': 'GM_006',
                'runny_nose': 'GM_007',
                'headache': 'GM_010',
                'body_aches': 'GM_019',
                'nausea': 'GM_014',
                'diarrhea': 'GM_016',
                'mild_fever': 'GM_001',
                'high_fever': 'GM_002',
                'chills': 'GM_003',
                'no_fever': 'GM_001',
                'congestion': 'GM_008',
                'shortness': 'GM_009',
                'chest_pain': 'GM_031',
                'sinus': 'GM_012',
                'vomiting': 'GM_015',
                'abdominal_pain': 'GM_017',
                'loss_appetite': 'GM_018',
                'recent': 'GM_023',
                'lasting': 'GM_024',
                'chronic': 'GM_025',
                'recurring': 'GM_026',
                'mild': 'GM_027',
                'moderate': 'GM_028',
                'severe': 'GM_029'
            }
        }

        symptoms = []
        if department in symptom_mapping:
            for answer_key, answer_value in answers.items():
                # multiple choice answers stored as lists
                if isinstance(answer_value, (list, tuple)):
                    for item in answer_value:
                        if item and item != 'none' and item in symptom_mapping[department]:
                            symptom_id = symptom_mapping[department][item]
                            if symptom_id not in symptoms:
                                symptoms.append(symptom_id)
                else:
                    if answer_value and answer_value != 'none' and answer_value in symptom_mapping[department]:
                        symptom_id = symptom_mapping[department][answer_value]
                        if symptom_id not in symptoms:
                            symptoms.append(symptom_id)

        return symptoms

    
    def find_condition_by_symptoms(self, department, symptoms):
        """Find conditions matching the symptoms with improved matching algorithm"""
        if department not in self.departments_data:
            return None
        
        dept_data = self.departments_data[department]
        matched_conditions = []
        
        if 'diseases' in dept_data and 'treatments' in dept_data:
            for disease in dept_data['diseases']:
                disease_symptoms = disease.get('symptoms', [])
                
                # Calculate match score based on symptom overlap
                matching_symptoms = set(symptoms) & set(disease_symptoms)
                match_count = len(matching_symptoms)
                
                # Calculate match percentage
                total_possible = len(disease_symptoms)
                match_percentage = (match_count / total_possible) * 100 if total_possible > 0 else 0
                
                # Enhanced matching thresholds - require at least 2 symptoms or 30% match
                # This prevents false positives with single symptom matches
                if match_count >= 2 or (match_count >= 1 and match_percentage >= 30):
                    condition_info = {
                        'disease_id': disease['id'],
                        'disease_name': disease['name'],
                        'match_score': match_count,
                        'match_percentage': match_percentage,
                        'matching_symptoms': list(matching_symptoms),
                        'total_disease_symptoms': total_possible,
                        'symptoms': disease_symptoms,
                        'treatments': dept_data['treatments'].get(disease['id'], {})
                    }
                    matched_conditions.append(condition_info)
        
        # Sort by match score and percentage
        matched_conditions.sort(key=lambda x: (x['match_score'], x['match_percentage']), reverse=True)
        return matched_conditions

# Initialize chatbot
chatbot = MedicalChatbot()

@app.route('/')
def index():
    # send available languages for front-end dropdown
    return render_template('index.html', departments=DEPARTMENTS, treatment_types=TREATMENT_TYPES, languages=LANGUAGES)

@app.route('/api/set_language', methods=['POST'])
def set_language():
    """Set user's preferred language"""
    language = request.json.get('language', 'en')
    if language in LANGUAGES:
        session['language'] = language
        # Clear cache when language changes
        translation_cache.clear()
        return jsonify({'success': True, 'message': f'Language set to {LANGUAGES[language]}'})
    return jsonify({'error': 'Invalid language'}), 400

@app.route('/api/start_chat', methods=['POST'])
def start_chat():
    """Start a new chat session with a department"""
    department = request.json.get('department')
    
    if department not in DEPARTMENTS:
        return jsonify({'error': 'Invalid department'}), 400
    
    # Initialize session
    session.clear()
    session['department'] = department
    session['answers'] = {}
    session['current_step'] = 0
    session['treatment_type'] = None
    session['language'] = request.json.get('language', 'en')
    
    # Get first question
    first_question = chatbot.get_next_question(department, {})
    translated_question = translate_question(first_question)
    
    welcome_message = translate_text(f"Great! Let's start with the {DEPARTMENTS[department]} assessment.")
    
    return jsonify({
        'success': True,
        'department': department,
        'question': translated_question,
        'message': welcome_message
    })

@app.route('/api/answer_question', methods=['POST'])
def answer_question():
    """Process answer and get next question"""
    answer_data = request.json
    question_id = answer_data.get('question_id')
    answer = answer_data.get('answer')
    department = session.get('department')
    
    if not department or not question_id:
        return jsonify({'error': 'Invalid request'}), 400
    
    # Store answer
    if 'answers' not in session:
        session['answers'] = {}
    
    session['answers'][question_id] = answer
    session.modified = True
    
    # Get next question
    next_question = chatbot.get_next_question(department, session['answers'])
    translated_question = translate_question(next_question)
    
    if translated_question:
        return jsonify({
            'next_question': translated_question,
            'completed': False
        })
    else:
        # No more questions, ask for treatment preference
        treatment_question = {
            'id': 'treatment_preference',
            'question': translate_text('Which treatment type would you prefer?'),
            'type': 'treatment_selection',
            'options': [{'value': k, 'text': translate_text(v)} for k, v in TREATMENT_TYPES.items()]
        }
        return jsonify({
            'next_question': treatment_question,
            'completed': False
        })

@app.route('/api/select_treatment', methods=['POST'])
def select_treatment():
    """Process treatment type selection and provide recommendations"""
    treatment_type = request.json.get('treatment_type')
    department = session.get('department')
    answers = session.get('answers', {})
    
    if not department or not treatment_type:
        return jsonify({'error': 'Invalid request'}), 400
    
    # Store treatment preference
    session['treatment_type'] = treatment_type
    
    # Map answers to symptoms
    symptoms = chatbot.map_answers_to_symptoms(department, answers)
    
    # Find matching conditions
    matched_conditions = chatbot.find_condition_by_symptoms(department, symptoms)
    
    if matched_conditions:
        top_condition = matched_conditions[0]
        treatments = top_condition['treatments']
        
        # Translate treatments
        translated_treatments = translate_treatments(treatments)
        
        # Get the selected treatment type
        selected_treatment = translated_treatments.get(treatment_type, [])
        
        # Format the response message
        condition_name = translate_text(top_condition['disease_name'])
        treatment_type_name = translate_text(TREATMENT_TYPES[treatment_type])
        
        if treatment_type == 'home_remedy' and selected_treatment == translate_text('please consult doctor'):
            message = f"🚨 **{translate_text('Condition Identified:')}** {condition_name}\n\n"
            message += f"**{translate_text('Urgent Medical Attention Required')}**\n\n"
            message += translate_text("This condition requires professional medical diagnosis and treatment. ")
            message += translate_text("Please consult a healthcare provider immediately.")
        else:
            message = f"**{translate_text('Condition Identified:')}** {condition_name}\n\n"
            message += f"**{translate_text('Recommended')} {treatment_type_name}:**\n\n"
            
            if isinstance(selected_treatment, list):
                for i, item in enumerate(selected_treatment, 1):
                    message += f"**{i}.** {item}\n"
            else:
                message += f"• {selected_treatment}\n"
            
            # Add usage instructions based on treatment type
            message += f"\n**{translate_text('Usage Instructions:')}**\n"
            if treatment_type == 'allopathy':
                message += translate_text("Take as directed above. Complete the full course if antibiotics are prescribed.\n")
            elif treatment_type == 'homeopathy':
                message += translate_text("Take pills 15-20 minutes before or after meals. Avoid strong smells during treatment.\n")
            elif treatment_type == 'ayurveda':
                message += translate_text("Take with warm water unless specified. Best taken before meals.\n")
            elif treatment_type == 'home_remedy':
                message += translate_text("Follow the remedies consistently for best results.\n")
            
            # Add matched symptoms for transparency
            message += f"\n**{translate_text('Matched Symptoms:')}** {len(symptoms)} {translate_text('symptoms identified')}\n"
            
            # Add severity warning for serious conditions
            serious_conditions = {
                'gastrointestinal': ['DIS_07', 'DIS_12', 'DIS_13', 'DIS_15'],
                'dermatology': ['DER_DIS_11', 'DER_DIS_12', 'DER_DIS_14'],
                'musculoskeletal': ['MSK_DIS_09', 'MSK_DIS_10', 'MSK_DIS_14'],
                'mental_health': ['MH_DIS_03', 'MH_DIS_06', 'MH_DIS_07'],
                'first_aid': ['FA_DIS_08', 'FA_DIS_09', 'FA_DIS_10', 'FA_DIS_11', 'FA_DIS_12', 'FA_DIS_13'],
                'general_medicine': ['GM_DIS_09', 'GM_DIS_10']
            }
            
            department_serious = serious_conditions.get(department, [])
            if top_condition['disease_id'] in department_serious:
                message += f"\n⚠️ **{translate_text('Medical Attention Recommended:')}** {translate_text('This condition may require professional supervision.')}\n"
        
        message += "\n---\n"
        message += f"**{translate_text('Disclaimer:')}** {translate_text('This information is for educational purposes only. Always consult qualified healthcare providers for medical advice and proper diagnosis.')}"
        
        response_data = {
            'condition': condition_name,
            'treatment_type': treatment_type_name,
            'recommendations': selected_treatment,
            'matched_symptoms_count': len(symptoms),
            'formatted_message': message,
            'requires_doctor': top_condition['disease_id'] in department_serious
        }
        
    else:
        response_data = {
            'condition': None,
            'message': translate_text("No specific conditions matched your symptoms pattern. Please consult a healthcare professional for proper diagnosis and treatment."),
            'requires_doctor': True
        }
    
    return jsonify(response_data)

@app.route('/api/restart_chat', methods=['POST'])
def restart_chat():
    """Restart the chat session"""
    session.clear()
    return jsonify({'success': True})

@app.route('/api/get_chat_status', methods=['GET'])
def get_chat_status():
    """Get current chat status"""
    return jsonify({
        'department': session.get('department'),
        'answers': session.get('answers', {}),
        'treatment_type': session.get('treatment_type'),
        'language': session.get('language', 'en')
    })

@app.route('/api/get_current_language', methods=['GET'])
def get_current_language():
    """Get current language setting"""
    return jsonify({
        'language': session.get('language', 'en'),
        'language_name': LANGUAGES.get(session.get('language', 'en'), 'English')
    })

if __name__ == '__main__':
    app.run(debug=True)