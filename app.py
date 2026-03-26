from flask import Flask, request, jsonify
from flask_cors import CORS
from firebase_config import db
import jwt
from functools import wraps
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
import io
from flask import send_file
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.platypus import Table, TableStyle
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib.styles import getSampleStyleSheet
from io import BytesIO
from datetime import datetime
from datetime import date
import yagmail
import threading
import time
from datetime import timedelta
import os

def today():
    return date.today().isoformat()
# ================================
# CONFIG
# ================================
SECRET_KEY = "mysecretkey"

EMAIL_USER = "medqueuesup@gmail.com"
EMAIL_PASS = "gjjmsnfhzicweyad"

yag = yagmail.SMTP(EMAIL_USER, EMAIL_PASS)


app = Flask(__name__)
CORS(app, supports_credentials=True)

# ================================
# AUTH DECORATOR
# ================================
def token_required(allowed_roles=None):
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            auth_header = request.headers.get("Authorization")

            if not auth_header:
                return jsonify({"error": "Token missing"}), 401

            try:
                token = auth_header.split(" ")[1]
                decoded = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
                user_role = decoded.get("role")

                if allowed_roles and user_role not in allowed_roles:
                    return jsonify({"error": "Access denied"}), 403

                request.user = decoded

            except:
                return jsonify({"error": "Invalid token"}), 401

            return f(*args, **kwargs)
        return wrapper
    return decorator


# ================================
# HELPER FUNCTIONS
# ================================
def get_now_serving(date):
    qs = db.collection("queue_status").where("date", "==", date).stream()
    for d in qs:
        return d.to_dict().get("now_serving_token", 0)
    return 0


def calculate_queue(date):
    now_serving = get_now_serving(date)

    appts = db.collection("appointments").where("date", "==", date).stream()
    queue = []

    for a in appts:
        data = a.to_dict()

        token_no = data.get("token_no", 0)
        doctor_id = data.get("doctor_id", "d001")  # default doctor

        # 🔥 Fetch doctor's avg consult time
        avg_time = 10
        doctor_doc = db.collection("doctors").document(doctor_id).get()
        if doctor_doc.exists:
            avg_time = doctor_doc.to_dict().get("avg_consult_time", 10)

        # 🔥 Calculate waiting time
        if token_no > now_serving:
            patients_ahead = token_no - now_serving - 1
            estimated_wait = max(patients_ahead * avg_time, 0)
        else:
            estimated_wait = 0

        queue.append({
            "id": a.id,
            "token_no": token_no,
            "patient_id":data.get("patient_id"),
            "status": data.get("status", "waiting"),
            "priority": data.get("priority", "normal"),
            "department": data.get("department"),
            "source":data.get("source","online"),
            "estimated_waiting_time_min": estimated_wait
        })

    queue.sort(key=lambda x: x["token_no"])

    return {
        "date": date,
        "now_serving_token": now_serving,
        "queue": queue
    }



# ================================
# ROUTES
# ================================

@app.route("/")
def home():
    return "Smart Hospital Queue System Running"


# ---------------- LOGIN ----------------
@app.route("/login", methods=["POST"])
def login():
    data = request.get_json()

    email = data.get("email")
    password = data.get("password")
    role = data.get("role")

    if not email or not password or not role:
        return jsonify({"error": "Email, password and role required"}), 400

    # ========================
    # PATIENT LOGIN (OPEN)
    # ========================
    if role.strip().lower() == "patient":
        token = jwt.encode(
            {"email": email, "role": "patient"},
            SECRET_KEY,
            algorithm="HS256"
        )
        return jsonify({"token": token, "role": "patient"})

    # ========================
    # DOCTOR / RECEPTIONIST
    # ========================
    users = db.collection("users").where("email", "==", email).stream()

    user_doc = None
    for u in users:
        user_doc = u.to_dict()
        break

    if not user_doc:
        return jsonify({"error": "User not found"}), 401

    # Password check
    if user_doc.get("password") != password:
        return jsonify({"error": "Invalid password"}), 401

    #  CLEAN ROLE CHECK
    db_role = str(user_doc.get("role", "")).strip().lower()
    req_role = str(role).strip().lower()

    if db_role != req_role:
        return jsonify({
            "error": f"Role mismatch (DB: {db_role}, Request: {req_role})"
        }), 401

    # Generate token
    token = jwt.encode(
        {"email": email, "role": db_role},
        SECRET_KEY,
        algorithm="HS256"
    )

    return jsonify({
        "token": token,
        "role": db_role
    }), 200


# ---------------- ADD APPOINTMENT ----------------
@app.route("/add_appointment", methods=["POST"])
@token_required()
def add_appointment():
    # Check OPD status
    opd_doc = db.collection("system_settings").document("opd_status").get()
    if opd_doc.exists and opd_doc.to_dict().get("status") == "closed":
     return jsonify({"error": "OPD is closed today"}), 403

    data = request.get_json()

    date = data.get("date")
    department = data.get("department")

    if not date or not department:
        return jsonify({"error": "Date and department required"}), 400

    # Generate token number
    appts = db.collection("appointments").where("date", "==", date).stream()
    token_no = len(list(appts)) + 1

    decoded = request.user
    patient_email = decoded.get("email")

    current_time = datetime.now()
    appointment_time=(current_time + timedelta(minutes=30)).strftime("%H:%M")

    db.collection("appointments").add({
    "date": date,
    "patient_id": patient_email,   # 🔥 IMPORTANT
    "department": department,
    "token_no": token_no,
    "status": "waiting",
    "priority": "normal",
    "appointment_time": appointment_time
})

    return jsonify({
        "message": "Appointment added",
        "token_no": token_no
    }), 201

# ---------------- ADD OFFLINE PATIENT ----------------
@app.route("/add_offline_patient", methods=["POST"])
@token_required(allowed_roles=["receptionist"])
def add_offline_patient():

    data = request.get_json()

    name = data.get("name")
    department = data.get("department")
    date = data.get("date")

    if not name or not department or not date:
        return jsonify({"error": "Missing fields"}), 400

    appts = db.collection("appointments").where("date", "==", date).stream()
    token_no = len(list(appts)) + 1

    db.collection("appointments").add({
        "patient_name": name,
        "department": department,
        "date": date,
        "token_no": token_no,
        "status": "waiting",
        "priority": "normal",
        "source": "offline"
    })

    return jsonify({
        "message": "Offline patient added",
        "token_no": token_no
    })


# ---------------- SET NOW SERVING ----------------
@app.route("/set_now_serving", methods=["POST"])
@token_required(allowed_roles=["receptionist"])
def set_now_serving():
    data = request.get_json()

    date = data.get("date")
    now_serving = data.get("now_serving_token")

    if not date or now_serving is None:
        return jsonify({"error": "date and now_serving_token required"}), 400

    qs_ref = db.collection("queue_status")
    existing = qs_ref.where("date", "==", date).stream()
    doc_found = None

    for d in existing:
        doc_found = d
        break
    
    if doc_found:
       qs_ref.document(doc_found.id).update({
        "now_serving_token": now_serving
    })
    else:
       qs_ref.add({
        "date": date,
        "now_serving_token": now_serving
    })


    # Auto update statuses
    appts = db.collection("appointments").where("date", "==", date).stream()

    for a in appts:
        token_no = a.to_dict().get("token_no")

        if token_no < now_serving:
            status = "completed"
        elif token_no == now_serving:
            status = "in_service"
        else:
            status = "waiting"

        db.collection("appointments").document(a.id).update({
            "status": status
        })

    return jsonify({"message": "Now serving updated"})


# ---------------- GET LIVE QUEUE ----------------
@app.route("/get_live_queue", methods=["GET"])
def get_live_queue():
    date = request.args.get("date")

    if not date:
        return jsonify({"error": "date required"}), 400

    return jsonify(calculate_queue(date))


# ---------------- MARK EMERGENCY ----------------
@app.route("/mark_emergency", methods=["POST"])
@token_required(allowed_roles=["receptionist"])
def mark_emergency():
    data = request.get_json()

    token_no = data.get("token_no")
    date = data.get("date")

    appts = db.collection("appointments") \
        .where("date", "==", date) \
        .where("token_no", "==", token_no) \
        .stream()

    appointment = None
    for a in appts:
        appointment = a
        break

    if not appointment:
        return jsonify({"error": "Appointment not found"}), 404

    db.collection("appointments").document(appointment.id).update({
        "priority": "emergency",
        "status": "in_service"
    })

    return jsonify({"message": "Marked as emergency"})


# ---------------- MARK ADMITTED ----------------
@app.route("/mark_admitted", methods=["POST"])
@token_required(allowed_roles=["doctor"])
def mark_admitted():
    data = request.get_json()

    token_no = data.get("token_no")
    date = data.get("date")

    appts = db.collection("appointments") \
        .where("date", "==", date) \
        .where("token_no", "==", token_no) \
        .stream()

    appointment = None
    for a in appts:
        appointment = a
        break

    if not appointment:
        return jsonify({"error": "Appointment not found"}), 404

    db.collection("appointments").document(appointment.id).update({
        "status": "admitted"
    })

    return jsonify({"message": "Patient admitted"})


# ---------------- DOCTOR SUMMARY ----------------
@app.route("/doctor_summary", methods=["GET"])
@token_required(allowed_roles=["doctor"])
def doctor_summary():

    date = request.args.get("date")

    if not date:
        return jsonify({"error": "date is required"}), 400

    # =========================
    # 1️⃣ Appointment Summary
    # =========================
    appts = db.collection("appointments") \
        .where("date", "==", date) \
        .stream()

    total = 0
    emergency = 0
    admitted = 0

    for a in appts:
        data = a.to_dict()
        total += 1

        if data.get("priority") == "emergency":
            emergency += 1

        if data.get("status") == "admitted":
            admitted += 1

    # =========================
    # 2️⃣ Doctor Status (Single Doctor System)
    # =========================
    status_doc = db.collection("system_settings") \
        .document("doctor_status") \
        .get()

    doctor_status = "available"  # default

    if status_doc.exists:
        doctor_status = status_doc.to_dict().get("status", "available")

    # =========================
    # 3️⃣ Final Response
    # =========================
    return jsonify({
        "total_opd": total,
        "emergency": emergency,
        "admitted": admitted,
        "doctor_status": doctor_status
    }), 200

@app.route("/get_opd_status", methods=["GET"])
def get_opd_status():
    doc = db.collection("system_settings").document("opd_status").get()

    if doc.exists:
        return jsonify(doc.to_dict()), 200
    else:
        return jsonify({"status": "open"}), 200


@app.route("/set_opd_status", methods=["POST"])
@token_required(allowed_roles=["doctor"])
def set_opd_status():
    data = request.get_json()
    status = data.get("status")

    if status not in ["open", "closed"]:
        return jsonify({"error": "Invalid status"}), 400

    db.collection("system_settings").document("opd_status").set({
        "status": status
    })

    return jsonify({"message": f"OPD {status} successfully"}), 200

@app.route("/admission_history", methods=["GET"])
@token_required(allowed_roles=["doctor"])
def admission_history():

    date = request.args.get("date")

    if not date:
        return jsonify({"error": "date required"}), 400

    appts = db.collection("appointments") \
        .where("date", "==", date) \
        .where("status", "==", "admitted") \
        .stream()

    admitted_list = []

    for a in appts:
        data = a.to_dict()

        admitted_list.append({
            "token_no": data.get("token_no"),
            "department": data.get("department"),
            "priority": data.get("priority")
        })

    return jsonify({
        "date": date,
        "admitted_patients": admitted_list
    })
# ---------------- UPDATE DOCTOR STATUS ----------------

@app.route("/set_doctor_status", methods=["POST"])
@token_required(allowed_roles=["doctor"])
def set_doctor_status():

    data = request.get_json()
    status = data.get("status")

    if status not in ["available", "busy", "emergency"]:
        return jsonify({"error": "Invalid status"}), 400

    # 🔄 Store inside system_settings (Single Doctor System)
    db.collection("system_settings").document("doctor_status").set({
        "status": status
    })

    return jsonify({
        "message": "Doctor status updated successfully",
        "status": status
    }), 200

# -------------------Patient History---------------------
@app.route("/patient_history", methods=["GET"])
@token_required(allowed_roles=["patient"])
def patient_history():

    # 🔐 Get patient email from token
    decoded = request.user
    patient_email = decoded.get("email")

    appts = db.collection("appointments") \
        .where("patient_id", "==", patient_email) \
        .stream()

    history = []

    for a in appts:
        data = a.to_dict()

        history.append({
            "date": data.get("date"),
            "token_no": data.get("token_no"),
            "department": data.get("department"),
            "status": data.get("status"),
            "priority": data.get("priority")
        })

    # sort latest first
    history.sort(key=lambda x: x["date"], reverse=True)

    return jsonify({
        "history": history
    }), 200

# -----------Download Report---------------

@app.route("/download_report", methods=["GET"])
@token_required()
def download_report():

    date = request.args.get("date")

    if not date:
        return jsonify({"error": "date required"}), 400

    # 🔐 Get patient email from token
    decoded = request.user
    patient_email = decoded.get("email")

    # 🔎 Get patient appointment for that date
    appts = db.collection("appointments") \
        .where("date", "==", date) \
        .stream()

    patient_visit = None
    total = 0
    emergency = 0
    admitted = 0

    for a in appts:
        data = a.to_dict()
        total += 1

        if data.get("priority") == "emergency":
            emergency += 1

        if data.get("status") == "admitted":
            admitted += 1

        # match patient
        if data.get("patient_id") == patient_email:
            patient_visit = data

    if not patient_visit:
        return jsonify({"error": "Visit not found"}), 404

    # 🔥 Load Doctor Status
    status_doc = db.collection("system_settings").document("doctor_status").get()
    doctor_status = "available"
    if status_doc.exists:
        doctor_status = status_doc.to_dict().get("status", "available")

    # 🔥 Performance Classification
    load_ratio = total / 20  # assume 20 patients = heavy day baseline

    if load_ratio < 0.4:
        load_level = "Low"
    elif load_ratio < 0.7:
        load_level = "Moderate"
    else:
        load_level = "High"

    if patient_visit.get("estimated_waiting_time_min", 0) <= 10:
        wait_experience = "Good"
    elif patient_visit.get("estimated_waiting_time_min", 0) <= 25:
        wait_experience = "Moderate"
    else:
        wait_experience = "Busy"

    # ================= PDF GENERATION =================

    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer)
    elements = []
    styles = getSampleStyleSheet()

    elements.append(Paragraph("<b>MEDQUEUE HOSPITAL</b>", styles["Title"]))
    elements.append(Spacer(1, 0.3 * inch))

    elements.append(Paragraph("<b>Patient Visit Report</b>", styles["Heading2"]))
    elements.append(Spacer(1, 0.2 * inch))

    report_data = [
        ["Patient Email:", patient_email],
        ["Visit Date:", date],
        ["Department:", patient_visit.get("department")],
        ["Token Number:", str(patient_visit.get("token_no"))],
        ["Priority:", patient_visit.get("priority")],
        ["Final Status:", patient_visit.get("status")]
    ]

    table = Table(report_data, colWidths=[2.5 * inch, 3 * inch])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
    ]))

    elements.append(table)
    elements.append(Spacer(1, 0.4 * inch))

    elements.append(Paragraph("<b>Queue Analysis</b>", styles["Heading2"]))
    elements.append(Spacer(1, 0.2 * inch))

    analysis_data = [
        ["Total Patients Today:", str(total)],
        ["Emergency Cases:", str(emergency)],
        ["Admission Cases:", str(admitted)],
        ["Doctor Status:", doctor_status],
        ["Queue Load Level:", load_level],
        ["Your Waiting Experience:", wait_experience]
    ]

    analysis_table = Table(analysis_data, colWidths=[2.5 * inch, 3 * inch])
    analysis_table.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
    ]))

    elements.append(analysis_table)
    elements.append(Spacer(1, 0.4 * inch))

    elements.append(Paragraph("<b>System Generated Summary</b>", styles["Heading2"]))
    elements.append(Spacer(1, 0.2 * inch))

    summary_text = f"""
    This visit occurred during a {load_level.lower()} load period.
    The system classified your waiting experience as {wait_experience.lower()}.
    Doctor status during your visit was {doctor_status}.
    """

    elements.append(Paragraph(summary_text, styles["Normal"]))
    elements.append(Spacer(1, 0.4 * inch))

    elements.append(Paragraph(
        f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        styles["Normal"]
    ))

    doc.build(elements)

    buffer.seek(0)

    return send_file(
        buffer,
        as_attachment=True,
        download_name="patient_report.pdf",
        mimetype="application/pdf"
    )

@app.route("/peak_hour_analysis", methods=["GET"])
@token_required(allowed_roles=["doctor"])
def peak_hour_analysis():

    date = request.args.get("date")

    if not date:
        return jsonify({"error": "date required"}), 400

    appts = db.collection("appointments") \
        .where("date", "==", date) \
        .stream()

    hourly_count = {}

    for a in appts:
        data = a.to_dict()
        time = data.get("appointment_time")

        if not time:
            continue

        hour = time.split(":")[0]

        if hour not in hourly_count:
            hourly_count[hour] = 0

        hourly_count[hour] += 1

    if not hourly_count:
        return jsonify({
            "message": "No appointment time data"
        }), 200

    peak_hour = max(hourly_count, key=hourly_count.get)

    return jsonify({
        "hourly_distribution": hourly_count,
        "peak_hour": peak_hour,
        "peak_count": hourly_count[peak_hour]
    }), 200

# ================================
# APPOINTMENT REMINDER SYSTEM
# ================================
def send_reminders():

    now = datetime.now()

    appts = db.collection("appointments").stream()

    for a in appts:

        data = a.to_dict()

        email = data.get("patient_id")
        date_val = data.get("date")
        time_val = data.get("appointment_time")

        if not email or not time_val:
            continue

        try:

            appt_time = datetime.strptime(
                date_val + " " + time_val,
                "%Y-%m-%d %H:%M"
            )

            diff = (appt_time - now).total_seconds() / 60

            if 29 <= diff <= 30:

                yag.send(
    to=email,
    subject="MedQueue Hospital Appointment Reminder",

    contents=f"""
Dear Patient,

This is an automated reminder for your upcoming hospital appointment.

Date: {date_val}
Time: {time_val}
Department: {data.get("department")}
Token Number: {data.get("token_no")}

Kindly arrive at the hospital reception before your appointment time.

Regards,
MedQueue Hospital
"""
)

        except:
            continue

@token_required()
def is_hindi(message):
    hindi_words = ["kya", "kaise", "kyu", "mera", "mujhe", "hai"]
    return any(word in message for word in hindi_words)
@app.route("/chatbot", methods=["POST"])
def chatbot():

    data = request.get_json()
    message = data.get("message", "").lower()

    user_email = "shrijayrokde101010@gmail.com"

    # =========================
    # 🔥 PATIENT HISTORY
    # =========================
    appts = db.collection("appointments") \
        .where("patient_id", "==", user_email).stream()

    visits = [a.to_dict() for a in appts]

    total_visits = len(visits)
    admitted_count = len([v for v in visits if v.get("status") == "admitted"])

    # =========================
    # 🔥 QUEUE DATA
    # =========================
    queue = calculate_queue(today())
    total_patients = len(queue["queue"])

    # =========================
    # 🔥 TOKEN FIND
    # =========================
    my_token = None
    estimated_wait = 0
    patients_ahead = 0

    for q in queue["queue"]:
        if q.get("patient_id") == user_email:
            my_token = q.get("token_no")
            estimated_wait = q.get("estimated_waiting_time_min", 0)
            break

    if my_token:
        patients_ahead = my_token - queue["now_serving_token"] - 1
        if patients_ahead < 0:
            patients_ahead = 0

    # =========================
    # 🔥 TIME CALCULATION
    # =========================
    current_time = datetime.now()

    if estimated_wait:
        expected_time = current_time + timedelta(minutes=estimated_wait)
        expected_time_str = expected_time.strftime("%I:%M %p")
    else:
        expected_time_str = "soon"

    # =========================
    # 🔥 MATCH FUNCTION
    # =========================
    def match(words):
        return any(w in message for w in words)

    # =========================
    # 🔥 RESPONSES
    # =========================

    # GREETING
    if match(["hi", "hello", "hey"]):
        if is_hindi(message):
            reply = "Hello 👋 Main aapka MedQueue assistant hoon. Aap mujhse kuch bhi pooch sakte hain."
        else:
            reply = "Hello 👋 I am your MedQueue assistant. Ask me anything."

    # WAITING TIME (UPGRADED)
    elif match(["wait", "waiting", "delay", "queue"]):

        if my_token:
            reply = f"""
⏳ Queue Status:

• Your Token: {my_token}
• Patients Ahead: {patients_ahead}
• Estimated Wait: {estimated_wait} minutes
• Expected Turn: {expected_time_str}

Stay ready near OPD 👍
"""
        else:
            reply = f"""
⏳ There are currently {total_patients} patients in queue.

Book appointment to get your token.
"""

    # WHEN TURN
    elif "when" in message and "turn" in message:
        reply = f"""
📢 Your expected turn is around {expected_time_str}

Please arrive 10-15 minutes early.
"""

    # HISTORY
    elif match(["history", "visit", "past"]):
        reply = f"""
📊 Your Medical Summary:

• Total Visits: {total_visits}
• Admissions: {admitted_count}
"""

    # REPORT
    elif match(["report", "analysis", "analyze"]):
        reply = f"""
📄 Health Report Analysis:

• Visits: {total_visits}
• Admissions: {admitted_count}

🧠 Insight:
Your condition seems {'stable' if admitted_count < 2 else 'needs attention'}

✔ Recommendation:
• Regular checkups
• Follow doctor advice
"""

    # OPD
    elif "opd" in message:
        doc = db.collection("system_settings").document("opd_status").get()
        status = doc.to_dict().get("status", "open") if doc.exists else "open"

        reply = f"""
🏥 OPD Status: {status.upper()}

{'Open for appointments' if status == 'open' else 'Currently closed'}
"""

    # SYMPTOMS
    elif match(["fever", "cold", "cough", "weakness"]):
        reply = """
🤒 Possible condition detected.

👉 Visit: General Medicine
"""

    elif match(["headache", "migraine"]):
        reply = """
🤕 Visit: General Medicine or Neurology
"""

    elif match(["bone", "fracture", "joint"]):
        reply = """
🦴 Visit: Orthopedics
"""

    elif match(["ear", "nose", "throat"]):
        reply = """
👂 Visit: ENT Department
"""

    # BOOKING
    elif match(["appointment", "book"]):
        reply = """
📅 Booking Steps:
1. Enter details
2. Select department
3. Book
"""

    # DOCTOR
    elif match(["doctor", "specialist"]):
        reply = """
👨‍⚕️ Fever → Medicine  
🦴 Bone → Ortho  
👂 ENT → ENT
"""

    # TIMING
    elif match(["timing", "open", "close"]):
        reply = "🕒 OPD timing: 9 AM to 5 PM"

    # FOLLOW UP
    elif "aur" in message or "what about" in message:
        reply = "Thoda aur detail me batao 😊"

    # DEFAULT
    else:
        reply = """
🤖 I can help with:
• Waiting time
• Reports
• Appointment booking
• Doctor suggestions

Try:
"waiting time"
"I have fever"
"""

    return jsonify({"reply": reply})

# @app.route("/test_email")
# def test_email():
#     yag.send(
#         to="shrijayrokde101010@gmail.com",
#         subject="MedQueue Test Email",
#         contents="If you see this email, email system is working."
#     )
#     return "Email sent"

# ================================
# RUN
# ================================
# ================================
# BACKGROUND REMINDER THREAD
# ================================
def reminder_loop():

    while True:

        send_reminders()

        time.sleep(60)

threading.Thread(target=reminder_loop, daemon=True).start()

if __name__ == "__main__":
    port = int(os.environ.get("PORT",5000))
    app.run(host="0.0.0.0",port=port)


