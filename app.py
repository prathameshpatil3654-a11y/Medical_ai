import os
import re
import secrets
import sqlite3
import warnings
from contextlib import contextmanager
from datetime import date
from pathlib import Path

import requests
from dotenv import load_dotenv
from flask import (
    Flask,
    abort,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)


BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

app = Flask(__name__)
app.config.update(
    SECRET_KEY=os.getenv("FLASK_SECRET_KEY") or secrets.token_hex(32),
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=os.getenv("COOKIE_SECURE", "false").lower() == "true",
    MAX_CONTENT_LENGTH=32 * 1024,
)
if not os.getenv("FLASK_SECRET_KEY"):
    warnings.warn(
        "FLASK_SECRET_KEY is not configured; sessions will reset when the app restarts.",
        RuntimeWarning,
    )

DATABASE = BASE_DIR / "database.db"
GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-safeguard-20b")
SYSTEM_PROMPT = (
    "You are MediCare AI, a friendly source of general health education. "
    "Use plain language and explain medical terms simply. You cannot diagnose, "
    "prescribe, recommend personalized dosages, or replace a qualified clinician. "
    "Encourage users to contact a healthcare professional for personal concerns. "
    "If a user describes severe, sudden, or potentially life-threatening symptoms, "
    "tell them to seek emergency care now and contact their local emergency number. "
    "Do not claim that this prototype is clinically validated."
)
EMERGENCY_TERMS = (
    "can't breathe",
    "cannot breathe",
    "difficulty breathing",
    "shortness of breath",
    "chest pain",
    "severe bleeding",
    "unconscious",
    "not waking",
    "stroke",
    "suicidal",
    "suicide",
    "overdose",
    "seizure",
)

MEDICINES = [
    {
        "name": "Paracetamol (acetaminophen)",
        "generic": "Paracetamol",
        "uses": "Commonly used for temporary relief of mild pain and fever.",
        "warning": "Taking too much can seriously harm the liver. Check labels to avoid combining products that contain it.",
        "category": "Pain relief",
    },
    {
        "name": "Ibuprofen",
        "generic": "Ibuprofen",
        "uses": "A non-prescription anti-inflammatory medicine used for temporary pain, swelling, and fever relief.",
        "warning": "May not be suitable for some people, including those with stomach ulcers, kidney problems, or certain medicines. Ask a pharmacist or clinician.",
        "category": "Anti-inflammatory",
    },
    {
        "name": "Cetirizine",
        "generic": "Cetirizine hydrochloride",
        "uses": "An antihistamine commonly used to relieve allergy symptoms.",
        "warning": "Can cause sleepiness in some people. Check the package information and ask a pharmacist if unsure.",
        "category": "Allergy",
    },
    {
        "name": "Oral rehydration salts",
        "generic": "Glucose-electrolyte solution",
        "uses": "Used to replace water and salts lost through dehydration, when appropriate.",
        "warning": "Follow the product label for preparation. Seek medical care for severe dehydration or persistent symptoms.",
        "category": "Rehydration",
    },
    {
        "name": "Amoxicillin",
        "generic": "Amoxicillin",
        "uses": "A prescription antibiotic used for certain bacterial infections when prescribed by a clinician.",
        "warning": "Prescription medicine. Do not take leftover antibiotics or use them without a prescription; they do not treat viral infections.",
        "category": "Prescription information",
    },
]

SYMPTOMS = [
    {
        "name": "Headache",
        "description": "Headaches can have many causes, such as tension, dehydration, illness, or other conditions. Patterns and accompanying symptoms matter.",
        "common_causes": "Common contributors include stress or muscle tension, missed meals, not getting enough sleep, dehydration, eye strain, and common illnesses. These are possibilities, not a diagnosis.",
        "self_care": "For a mild headache, consider resting somewhere quiet, taking a screen break, and drinking water if you can. Notice possible triggers and how long it lasts. Ask a healthcare professional if it is new, keeps returning, or concerns you.",
        "guidance": "Rest and fluids may help some mild headaches. Seek urgent care for a sudden, unusually severe headache, confusion, weakness, fever with a stiff neck, or after a head injury.",
    },
    {
        "name": "Cough",
        "description": "A cough is a reflex that helps clear the airways. It can occur with infections, allergies, asthma, and other causes.",
        "common_causes": "Common causes include colds and other respiratory infections, allergies, asthma, and exposure to smoke or other irritants. A cough can have other causes too.",
        "self_care": "For a mild cough, consider resting, drinking fluids if you can, and avoiding smoke or other irritants. A clinician or pharmacist can advise you if it persists, worsens, or you are unsure what is safe for you.",
        "guidance": "Consider professional advice if it persists or worsens. Seek urgent help for difficulty breathing, blue lips, severe chest pain, or coughing up significant blood.",
    },
    {
        "name": "Fever",
        "description": "A fever is a higher-than-usual body temperature and can happen with many infections and other conditions.",
        "common_causes": "Infections are a common cause of fever. Some medicines and other conditions can also affect body temperature; the cause cannot be determined from a temperature alone.",
        "self_care": "If you feel unwell, rest, drink fluids if you can, and monitor your temperature using the thermometer instructions. Ask a healthcare professional what care is appropriate, especially for an infant, an older adult, or someone with other health conditions.",
        "guidance": "Rest and drink fluids if you can. Seek professional advice for a very high or persistent fever, or if you are worried. For infants or severe symptoms, seek urgent care.",
    },
    {
        "name": "Sore throat",
        "description": "A sore throat may be related to a viral illness, irritation, or another cause; this page cannot determine the cause.",
        "common_causes": "Common causes include colds and other viral infections, dry air, smoke or other irritation, and some bacterial infections. Similar symptoms can have different causes.",
        "self_care": "For mild discomfort, consider resting, drinking fluids, and avoiding smoke or other irritants. A healthcare professional can advise whether you need an assessment, particularly if symptoms are severe or do not improve.",
        "guidance": "Seek medical advice if symptoms are severe or persistent. Get urgent help if you cannot swallow or breathe, or are drooling because you cannot swallow.",
    },
    {
        "name": "Fatigue",
        "description": "Fatigue means feeling unusually tired or lacking energy. It may relate to sleep, stress, illness, medicines, or many other factors.",
        "common_causes": "Possible contributors include disrupted sleep, stress, a recent illness, changes in routine, and medicine effects. Fatigue can also have other health-related causes.",
        "self_care": "Consider a regular sleep routine, regular meals, and gentle activity if it feels comfortable. Keep track of how long the fatigue lasts and any other changes. Discuss persistent, unexplained, or disruptive fatigue with a healthcare professional.",
        "guidance": "If fatigue is unexplained, persistent, or affecting daily life, discuss it with a healthcare professional. Seek urgent care for sudden severe symptoms.",
    },
    {
        "name": "Nausea",
        "description": "Nausea is an unsettled feeling in the stomach and can have many possible causes.",
        "common_causes": "Nausea may occur with infections, motion, stress, pregnancy, or as a side effect of some medicines. These are examples only and do not identify the cause for any one person.",
        "self_care": "If symptoms are mild, try resting and taking small sips of fluid if you can keep them down. Eat only if you feel able. Ask a healthcare professional if nausea persists, you are concerned, or you may be pregnant and need advice.",
        "guidance": "Seek medical advice if it persists or you cannot keep fluids down. Get urgent care for severe pain, blood in vomit, fainting, or signs of serious dehydration.",
    },
]

SYMPTOM_MEDICINES = {
    "headache": ("Paracetamol (acetaminophen)", "Ibuprofen"),
    "fever": ("Paracetamol (acetaminophen)", "Ibuprofen"),
}

HOSPITALS = [
    {
        "name": "Northside Community Health Centre",
        "city": "Sample City",
        "postal_code": "DEMO-000001",
        "type": "Community clinic",
        "note": "Illustrative demo listing only. Location, services, and contact details are not verified.",
    },
    {
        "name": "Riverside General Hospital",
        "city": "Sample City",
        "postal_code": "DEMO-000002",
        "type": "General hospital",
        "note": "Illustrative demo listing only. Location, services, and contact details are not verified.",
    },
    {
        "name": "Greenfield Family Clinic",
        "city": "Demo Town",
        "postal_code": "DEMO-000003",
        "type": "Family clinic",
        "note": "Illustrative demo listing only. Location, services, and contact details are not verified.",
    },
    {
        "name": "Central Urgent Care Centre",
        "city": "Demo Town",
        "postal_code": "DEMO-000004",
        "type": "Urgent care",
        "note": "Illustrative demo listing only. Location, services, and contact details are not verified.",
    },
]

DOCTORS = [
    {
        "name": "Dr. Asha Mehta",
        "image": "doctor-asha.svg",
        "specialty": "Family medicine",
        "qualification": "MBBS · MD (Family Medicine)",
        "clinic": "Northside Community Health Centre",
        "about": "Demo profile for a primary-care physician focused on general wellness and preventive care.",
    },
    {
        "name": "Dr. Kabir Rao",
        "image": "doctor-kabir.svg",
        "specialty": "Cardiology",
        "qualification": "MBBS · MD (General Medicine) · DM (Cardiology)",
        "clinic": "Riverside General Hospital",
        "about": "Demo profile for a heart-health specialist. This is not a real provider listing.",
    },
    {
        "name": "Dr. Nila Sen",
        "image": "doctor-nila.svg",
        "specialty": "Pediatrics",
        "qualification": "MBBS · MD (Pediatrics)",
        "clinic": "Greenfield Family Clinic",
        "about": "Demo profile for a children's health specialist. This is not a real provider listing.",
    },
    {
        "name": "Dr. Omar Das",
        "image": "doctor-omar.svg",
        "specialty": "Dermatology",
        "qualification": "MBBS · MD (Dermatology)",
        "clinic": "Central Urgent Care Centre",
        "about": "Demo profile for a skin-health specialist. This is not a real provider listing.",
    },
]

HEALTH_TIPS = [
    {
        "slug": "hydration",
        "icon": "fa-droplet",
        "category": "Everyday wellness",
        "title": "Make hydration a gentle habit",
        "summary": "Keep water within reach and drink regularly. Needs vary with activity, climate, and health.",
        "body": "Water supports many normal body functions. Carrying a refillable bottle and having a drink with meals can help make hydration part of your routine. Fluid needs differ between people; some health conditions require individualized advice, so ask a clinician if you have been told to limit fluids.",
    },
    {
        "slug": "sleep",
        "icon": "fa-moon",
        "category": "Rest & recovery",
        "title": "Build a calming sleep routine",
        "summary": "A consistent wind-down routine and regular sleep schedule may support better rest.",
        "body": "Try keeping a regular bedtime, making your room comfortable, and setting aside a quiet wind-down period. Reduce bright screens before bed if they keep you alert. Ongoing sleep difficulties or daytime sleepiness are worth discussing with a healthcare professional.",
    },
    {
        "slug": "nutrition",
        "icon": "fa-apple-whole",
        "category": "Food & nutrition",
        "title": "Aim for variety on your plate",
        "summary": "A mix of fruits, vegetables, grains, and protein sources can support balanced eating.",
        "body": "When available, include a variety of vegetables and fruits, whole grains, and protein sources that work for your preferences and needs. There is no single eating pattern that suits everyone. A registered dietitian or clinician can help with individual health requirements.",
    },
    {
        "slug": "movement",
        "icon": "fa-person-walking",
        "category": "Movement",
        "title": "Find movement that feels manageable",
        "summary": "Short walks, stretching, or other comfortable activities can be a useful starting point.",
        "body": "Movement can be adapted to different abilities and schedules. A few minutes at a time can be a start; choose activities that feel safe and enjoyable. If you have a health condition, pain, or concerns about exercise, get guidance from a healthcare professional.",
    },
    {
        "slug": "prevention",
        "icon": "fa-shield-heart",
        "category": "Prevention",
        "title": "Keep preventive care on your calendar",
        "summary": "Routine checkups and recommended screenings are opportunities to discuss your health.",
        "body": "Preventive care can include routine checkups, vaccinations, and screenings based on your age, health history, and local guidance. Keep a list of questions for your clinician, and use a trusted local health service to learn what is recommended for you.",
    },
]


@contextmanager
def get_db():
    connection = sqlite3.connect(DATABASE)
    connection.row_factory = sqlite3.Row
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def init_db():
    with get_db() as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS appointments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                name TEXT NOT NULL,
                contact TEXT NOT NULL,
                specialty TEXT NOT NULL,
                requested_date TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS saved_articles (
                user_id TEXT NOT NULL,
                slug TEXT NOT NULL,
                saved_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (user_id, slug)
            );
            CREATE TABLE IF NOT EXISTS contact_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT NOT NULL,
                message TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS chat_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                role TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
                content TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            DELETE FROM chat_messages
            WHERE created_at < datetime('now', '-1 day');
            """
        )


init_db()


@app.before_request
def protect_forms():
    if request.method not in ("POST", "PUT", "PATCH", "DELETE"):
        return None
    supplied_token = request.headers.get("X-CSRF-Token") or request.form.get("csrf_token")
    expected_token = session.get("csrf_token")
    if not expected_token or not supplied_token or not secrets.compare_digest(
        supplied_token, expected_token
    ):
        if request.endpoint == "chat_api":
            return jsonify(error="Your session expired. Refresh the page and try again."), 400
        abort(400, description="Form security check failed. Please go back and try again.")
    return None


@app.context_processor
def inject_template_values():
    token = session.setdefault("csrf_token", secrets.token_urlsafe(32))
    return {"csrf_token": token, "today": date.today().isoformat()}


@app.after_request
def add_security_headers(response):
    response.headers.setdefault(
        "Content-Security-Policy",
        "default-src 'self'; script-src 'self'; "
        "style-src 'self' https://cdnjs.cloudflare.com https://fonts.googleapis.com; "
        "font-src 'self' https://cdnjs.cloudflare.com https://fonts.gstatic.com; img-src 'self' data:; "
        "connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'",
    )
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    return response


def filtered(items, query, *fields):
    needle = query.strip().casefold()
    if not needle:
        return items
    return [
        item
        for item in items
        if any(needle in item[field].casefold() for field in fields)
    ]


def medicines_for_symptoms(symptoms):
    names = {
        name
        for symptom in symptoms
        for name in SYMPTOM_MEDICINES.get(symptom["name"].casefold(), ())
    }
    return [medicine for medicine in MEDICINES if medicine["name"] in names]


def valid_text(value, maximum):
    value = (value or "").strip()
    if not value or len(value) > maximum:
        return None
    return value


def valid_contact(value):
    contact = valid_text(value, 120)
    if not contact:
        return None
    if re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", contact):
        return contact
    digits = re.sub(r"\D", "", contact)
    if re.fullmatch(r"[\d+\-().\s]+", contact) and 7 <= len(digits) <= 15:
        return contact
    return None


def current_user_id():
    return "demo-user"


def current_chat_history():
    chat_id = session.get("chat_session_id")
    if not chat_id:
        return []
    with get_db() as connection:
        rows = connection.execute(
            """SELECT role, content FROM chat_messages
               WHERE session_id = ? ORDER BY id DESC LIMIT 12""",
            (chat_id,),
        ).fetchall()
    return [dict(row) for row in reversed(rows)]


@app.get("/")
def home():
    query = request.args.get("q", "").strip()[:80]
    searchable = [
        {"title": item["title"], "description": item["summary"], "url": url_for("health_tips")}
        for item in HEALTH_TIPS
    ] + [
        {"title": item["name"], "description": item["uses"], "url": url_for("medicines")}
        for item in MEDICINES
    ] + [
        {
            "title": item["name"],
            "description": f'{item["specialty"]} · {item["clinic"]}',
            "url": url_for("doctors"),
        }
        for item in DOCTORS
    ]
    results = [
        item
        for item in searchable
        if query and query.casefold() in (item["title"] + " " + item["description"]).casefold()
    ]
    return render_template("index.html", query=query, search_results=results)


@app.get("/ai-assistant")
def ai_assistant():
    return render_template("ai_assistant.html", history=current_chat_history())


@app.post("/api/chat")
def chat_api():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify(error="Send a valid message to continue."), 400
    message = valid_text(data.get("message"), 1200)
    if not message:
        return jsonify(error="Enter a message of up to 1,200 characters."), 400

    history = current_chat_history()

    if any(term in message.casefold() for term in EMERGENCY_TERMS):
        reply = (
            "Your message may describe an emergency. Please seek emergency medical care now "
            "and contact your local emergency number. If possible, ask someone nearby to help. "
            "This chat cannot assess or treat an emergency."
        )
    else:
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            return jsonify(
                error="The AI service is not configured yet. Add GROQ_API_KEY to your .env file."
            ), 503
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        for item in history[-10:]:
            if (
                isinstance(item, dict)
                and item.get("role") in ("user", "assistant")
                and isinstance(item.get("content"), str)
            ):
                messages.append({"role": item["role"], "content": item["content"][:1200]})
        messages.append({"role": "user", "content": message})
        try:
            response = requests.post(
                GROQ_API_URL,
                headers={"Authorization": f"Bearer {api_key}"},
                json={
                    "model": GROQ_MODEL,
                    "messages": messages,
                    "temperature": 0.4,
                    "max_tokens": 600,
                },
                timeout=(5, 30),
            )
            response.raise_for_status()
            payload = response.json()
            reply = payload["choices"][0]["message"]["content"].strip()
            if not reply:
                raise ValueError("The AI service returned an empty response.")
        except requests.Timeout:
            return jsonify(error="The AI service took too long to respond. Please try again."), 504
        except (requests.RequestException, ValueError, KeyError, IndexError, TypeError):
            app.logger.exception("Groq chat request failed")
            return jsonify(
                error="The AI service is temporarily unavailable. Please try again later."
            ), 502

    chat_id = session.setdefault("chat_session_id", secrets.token_urlsafe(32))
    with get_db() as connection:
        connection.executemany(
            "INSERT INTO chat_messages (session_id, role, content) VALUES (?, ?, ?)",
            ((chat_id, "user", message), (chat_id, "assistant", reply)),
        )
        connection.execute(
            """DELETE FROM chat_messages WHERE session_id = ?
               AND id NOT IN (
                   SELECT id FROM chat_messages WHERE session_id = ? ORDER BY id DESC LIMIT 12
               )""",
            (chat_id, chat_id),
        )
    return jsonify(reply=reply, history=current_chat_history())


@app.post("/api/chat/clear")
def clear_chat():
    chat_id = session.pop("chat_session_id", None)
    if chat_id:
        with get_db() as connection:
            connection.execute(
                "DELETE FROM chat_messages WHERE session_id = ?", (chat_id,)
            )
    return jsonify(ok=True)


@app.get("/symptoms")
def symptoms():
    query = request.args.get("q", "").strip()[:80]
    matching = filtered(SYMPTOMS, query, "name", "description")
    return render_template(
        "symptoms.html",
        query=query,
        symptoms=matching,
        entered_symptom="",
        related_medicines=medicines_for_symptoms(matching) if query else [],
        medicine_search_done=bool(query),
    )


@app.post("/symptoms")
def symptom_lookup():
    entered = valid_text(request.form.get("symptom"), 80)
    if not entered:
        flash("Enter a symptom or choose one from the list.", "error")
        return redirect(url_for("symptoms"))
    matching = filtered(SYMPTOMS, entered, "name", "description")
    return render_template(
        "symptoms.html",
        query="",
        symptoms=matching,
        entered_symptom=entered,
        no_symptom_match=not matching,
        related_medicines=medicines_for_symptoms(matching),
        medicine_search_done=bool(matching),
    )


@app.get("/medicines")
def medicines():
    query = request.args.get("q", "").strip()[:80]
    return render_template(
        "medicines.html",
        query=query,
        medicines=filtered(MEDICINES, query, "name", "generic", "uses", "category"),
    )


@app.get("/hospitals")
def hospitals():
    query = request.args.get("q", "").strip()[:80]
    return render_template(
        "hospitals.html",
        query=query,
        hospitals=filtered(HOSPITALS, query, "name", "city", "postal_code", "type"),
    )


@app.get("/doctors")
def doctors():
    query = request.args.get("q", "").strip()[:80]
    return render_template(
        "doctors.html",
        query=query,
        doctors=filtered(DOCTORS, query, "name", "specialty", "clinic"),
    )


@app.route("/appointments", methods=["GET", "POST"])
def appointments():
    if request.method == "GET":
        specialty = request.args.get("specialty", "")
        allowed = {doctor["specialty"] for doctor in DOCTORS}
        return render_template(
            "appointments.html", specialties=sorted(allowed), selected_specialty=specialty
        )

    name = valid_text(request.form.get("name"), 100)
    contact = valid_contact(request.form.get("contact"))
    specialty = valid_text(request.form.get("specialty"), 60)
    requested_date = valid_text(request.form.get("requested_date"), 10)
    allowed = {doctor["specialty"] for doctor in DOCTORS}
    try:
        parsed_date = date.fromisoformat(requested_date or "")
    except ValueError:
        parsed_date = None
    if (
        not name
        or not contact
        or not specialty
        or specialty not in allowed
        or not parsed_date
        or parsed_date < date.today()
    ):
        flash("Check each field and choose a valid date today or later.", "error")
        return redirect(url_for("appointments"))

    with get_db() as connection:
        connection.execute(
            """INSERT INTO appointments
               (user_id, name, contact, specialty, requested_date)
               VALUES (?, ?, ?, ?, ?)""",
            (current_user_id(), name, contact, specialty, parsed_date.isoformat()),
        )
    flash("Your demo appointment enquiry has been saved.", "success")
    return redirect(url_for("dashboard"))


@app.get("/health-tips")
def health_tips():
    return render_template("health_tips.html", articles=HEALTH_TIPS)


@app.post("/articles/<slug>/save")
def save_article(slug):
    if not any(article["slug"] == slug for article in HEALTH_TIPS):
        abort(404)
    with get_db() as connection:
        connection.execute(
            "INSERT OR IGNORE INTO saved_articles (user_id, slug) VALUES (?, ?)",
            (current_user_id(), slug),
        )
    flash("Article saved to your demo dashboard.", "success")
    return redirect(url_for("dashboard"))


@app.post("/articles/<slug>/remove")
def remove_article(slug):
    with get_db() as connection:
        connection.execute(
            "DELETE FROM saved_articles WHERE user_id = ? AND slug = ?",
            (current_user_id(), slug),
        )
    flash("Article removed from your saved list.", "success")
    return redirect(url_for("dashboard"))


@app.get("/dashboard")
def dashboard():
    with get_db() as connection:
        appointments_list = connection.execute(
            """SELECT name, specialty, requested_date, created_at
               FROM appointments WHERE user_id = ? ORDER BY id DESC""",
            (current_user_id(),),
        ).fetchall()
        saved_slugs = {
            row["slug"]
            for row in connection.execute(
                "SELECT slug FROM saved_articles WHERE user_id = ?",
                (current_user_id(),),
            ).fetchall()
        }
    saved_articles = [article for article in HEALTH_TIPS if article["slug"] in saved_slugs]
    return render_template(
        "dashboard.html", appointments=appointments_list, articles=saved_articles
    )


@app.route("/about", methods=["GET", "POST"])
def about():
    if request.method == "POST":
        name = valid_text(request.form.get("name"), 100)
        email = valid_text(request.form.get("email"), 254)
        message = valid_text(request.form.get("message"), 2000)
        if not name or not email or not re.fullmatch(
            r"[^@\s]+@[^@\s]+\.[^@\s]+", email
        ) or not message:
            flash("Enter your name, a valid email address, and a message.", "error")
            return redirect(url_for("about"))
        with get_db() as connection:
            connection.execute(
                "INSERT INTO contact_messages (name, email, message) VALUES (?, ?, ?)",
                (name, email, message),
            )
        flash("Thanks. Your demo message has been recorded locally.", "success")
        return redirect(url_for("about"))
    return render_template("about.html")


@app.cli.command("init-db")
def init_db_command():
    init_db()
    print(f"Database initialized at {DATABASE}")


if __name__ == "__main__":
    app.run(debug=os.getenv("FLASK_DEBUG", "false").lower() == "true")
