# MediCare AI – Smart Healthcare Assistant

A Flask, SQLite, HTML, CSS, and JavaScript student-project prototype for general health education. It includes an optional Groq-powered chat assistant, sample health and medicine information, fictional care-directory entries, appointment enquiries, saved articles, and a local demo dashboard.

> **Medical safety:** This project is not clinically validated and is not suitable for diagnosis, treatment, or real patient care. AI and page content provide general information only; they can be incomplete or inaccurate. They do not replace advice from a qualified healthcare professional. For severe or potentially life-threatening symptoms, contact your local emergency number or seek emergency care now.

## Requirements

- Windows 10/11
- Python 3.10 or newer
- Internet connection to install packages and, optionally, use the Groq API
- A Groq API key only if you want to use live AI responses

## Setup in VS Code (Windows PowerShell)

1. Open the `medicare_ai` folder in VS Code.
2. Open **Terminal → New Terminal** and run:

   ```powershell
   py -m venv .venv
   .\.venv\Scripts\Activate.ps1
   python -m pip install --upgrade pip
   pip install -r requirements.txt
   ```

   If PowerShell blocks activation, run `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass` in that terminal, then activate again. Alternatively, use Command Prompt:

   ```bat
   .venv\Scripts\activate.bat
   ```

3. Create your local environment file from the example:

   ```powershell
   Copy-Item .env.example .env
   ```

4. Open `.env` in VS Code. Set `FLASK_SECRET_KEY` to a long random value. To make one in PowerShell:

   ```powershell
   python -c "import secrets; print(secrets.token_hex(32))"
   ```

   Paste the generated value after `FLASK_SECRET_KEY=`. Add your own Groq API key after `GROQ_API_KEY=` to enable the chatbot. The key is read by Flask on the server and is never sent to the browser. You can leave it unset to use the rest of the site; the chat page will explain that AI is not configured.

5. Initialize the SQLite database:

   ```powershell
   flask --app app init-db
   ```

   The `database.db` file is created locally and excluded from Git.

6. Start the development server:

   ```powershell
   flask --app app run --debug
   ```

7. Open **http://127.0.0.1:5000/** in your browser.

`flask run --debug` enables Flask's development debugger. Use it only for local development, not for a public deployment. The application can also be started with `python app.py`; debug mode is off by default.

## Pages and features

- Home page with a fictional demo hospital illustration and MediCare AI logo, local demo search results, and direct searches on MedlinePlus, a service of the U.S. National Library of Medicine
- AI assistant with browser-session chat history stored locally in SQLite, loading state, clear-chat action, emergency-response guidance, and helpful configuration/service errors
- Common symptom and medicine information searches; symptom results include relevant general-use medicine guide entries where available, without personalized treatment or dose recommendations
- Clearly identified, fictional hospital/clinic entries and demo doctor profiles with illustrated portraits and sample qualifications
- Opt-in browser location permission on the hospital page, with an optional Google Maps handoff and city searches for Belagavi, Hubballi, Dharwad, and Bengaluru; fictional directory entries are not presented as nearby verified hospitals
- Appointment enquiry form saved in SQLite
- Health-tip articles saved to and removed from the demo dashboard
- About, local contact-message form, privacy explanation, and safety disclaimers
- Responsive navigation menu, accessible form labels, reduced-motion support, and security headers

All non-AI forms and chat endpoints use session-based CSRF checks. Appointment dates and allowed specialties are validated server-side, and SQLite queries are parameterized. Location is requested only after the visitor presses the hospital page's location button; it is not saved or sent to this app's server. Coordinates are shared with Google Maps only if the visitor separately chooses to open the map link.

The demo dashboard does not use real authentication: it displays entries associated with one fixed demo user. Use fictional details only. Recent chat messages are associated with a random browser-session identifier, can be cleared in the chat UI, and are automatically pruned after one day.

## Environment settings

| Variable | Purpose |
| --- | --- |
| `FLASK_SECRET_KEY` | Secret key for signed Flask sessions. Set a unique random value in `.env`. |
| `GROQ_API_KEY` | Optional Groq API key for live AI responses. Never put this in frontend code. |
| `GROQ_MODEL` | Optional Groq model identifier; defaults to `llama-3.3-70b-versatile`. |
| `COOKIE_SECURE` | Set to `true` only when serving over HTTPS. Keep `false` for localhost. |

`.env` and the SQLite database are ignored by Git. If `FLASK_SECRET_KEY` is missing, the app generates a temporary key and warns that sessions reset after restart.

## Troubleshooting

- **`py` is not recognized:** Install Python from [python.org](https://www.python.org/downloads/) and enable **Add python.exe to PATH**, then reopen VS Code.
- **Virtual environment activation is blocked:** Use the process-scoped PowerShell policy command above, or activate from Command Prompt.
- **`ModuleNotFoundError`:** Activate `.venv` and run `pip install -r requirements.txt` again.
- **AI says it is not configured:** Confirm `.env` exists beside `app.py`, contains `GROQ_API_KEY=...`, and restart Flask after editing it.
- **AI service unavailable:** Check the API key, Groq account/model availability, internet access, and terminal logs. The non-AI pages work without the Groq service.
- **Database/table errors:** Run `flask --app app init-db` from the `medicare_ai` directory.
- **Form security check failed:** Refresh the page and submit again so the browser has a current session token.
- **Port 5000 is busy:** Run `flask --app app run --debug --port 5001` and open `http://127.0.0.1:5001/`.

## Project layout

```text
medicare_ai/
├── app.py
├── requirements.txt
├── .env.example
├── .gitignore
├── database.db              # generated locally; ignored by Git
├── templates/
│   ├── base.html
│   ├── index.html
│   ├── ai_assistant.html
│   ├── symptoms.html
│   ├── medicines.html
│   ├── hospitals.html
│   ├── doctors.html
│   ├── appointments.html
│   ├── health_tips.html
│   ├── dashboard.html
│   └── about.html
├── static/
│   ├── css/style.css
│   └── js/main.js
└── images/                  # reserved for local project imagery
```

The prototype intentionally uses fictional directory entries and recommends trusted local sources for real provider details. It does not implement real authentication, bookings, clinical workflows, or emergency dispatch.
