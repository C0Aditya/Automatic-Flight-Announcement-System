from flask import Flask, render_template, request, redirect, url_for, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_admin import Admin
from flask_admin.contrib.sqla import ModelView
from pydub import AudioSegment
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime, timedelta
import mysql.connector
import string
import os
import logging # Import logging module
import uuid # Import uuid for unique filenames
import json # Import json for handling LLM responses
import requests # Import requests for making HTTP calls

# Configure logging to see errors in console
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

app = Flask(__name__)

# ------------------- SQLAlchemy Setup --------------------
app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+mysqlconnector://root:ak267120@localhost/audiofiles'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# ------------------- Models ------------------------------
class FileData(db.Model):
    __tablename__ = 'file_data'
    index_no = db.Column(db.Integer, primary_key=True)
    path = db.Column(db.String(512))
    description = db.Column(db.String(512))

class GateData(db.Model):
    __tablename__ = 'gate_data'
    index_no = db.Column(db.Integer, primary_key=True)
    path = db.Column(db.String(512))
    description = db.Column(db.String(512))

class CityData(db.Model):
    __tablename__ = 'city_data'
    index_no = db.Column(db.Integer, primary_key=True)
    path = db.Column(db.String(512))
    description = db.Column(db.String(512))

class AirlinesData(db.Model):
    __tablename__ = 'airlines_data'
    index_no = db.Column(db.Integer, primary_key=True)
    path = db.Column(db.String(512))
    description = db.Column(db.String(512))

# New Model for Flight Details
class FlightDetails(db.Model):
    __tablename__ = 'flight_details'
    id = db.Column(db.Integer, primary_key=True)
    flight_no = db.Column(db.String(50), unique=True, nullable=False)
    departure_time = db.Column(db.String(50))
    arrival_time = db.Column(db.String(50))
    from_city = db.Column(db.String(100))
    to_city = db.Column(db.String(100))
    status = db.Column(db.String(50))

    def __repr__(self):
        return f'<Flight {self.flight_no} from {self.from_city} to {self.to_city}>'


# ------------------- Admin Panel -------------------------
admin = Admin(app, name='FlightAudioAdminPanel', template_mode='bootstrap4')
admin.add_view(ModelView(FileData, db.session))
admin.add_view(ModelView(GateData, db.session))
admin.add_view(ModelView(CityData, db.session))
admin.add_view(ModelView(AirlinesData, db.session))
admin.add_view(ModelView(FlightDetails, db.session)) # Add FlightDetails to admin


# ------------------- Helpers -----------------------------
def normalize(text):
    return text.lower().translate(str.maketrans('', '', string.punctuation)).strip()

def get_connection():
    """Establishes a connection to the MySQL database."""
    try:
        conn = mysql.connector.connect(
            host='localhost',
            user='root',
            password='ak267120',
            database='audiofiles'
        )
        if conn.is_connected():
            logging.info("Successfully connected to MySQL database.")
        return conn
    except mysql.connector.Error as err:
        logging.error(f"Error connecting to MySQL: {err}")
        return None

def generate_announcement_string(flight_detail):
    """
    Generates a dynamic announcement string based on flight details and current time.
    This version returns a comma-separated string of individual phrases,
    including character-by-character breakdown of the flight number.
    The greeting and "ladies and gentlemen" are now a single phrase.
    """
    current_hour = datetime.now().hour
    if 5 <= current_hour < 12:
        greeting_phrase = "Good morning ladies and gentlemen"
    elif 12 <= current_hour < 18:
        greeting_phrase = "Good afternoon ladies and gentlemen"
    else:
        greeting_phrase = "Good evening ladies and gentlemen"

    # Break down the flight number into individual characters
    flight_no_characters = list(flight_detail.flight_no)

    # Combine all announcement segments
    announcement_segments = [
        greeting_phrase, # Now a single combined phrase
        "this is the announcement for passengers travelling on", # MODIFIED: Split into two phrases
        "flight" # ADDED: Separate phrase for "flight"
    ]
    announcement_segments.extend(flight_no_characters) # Add each character of the flight number
    announcement_segments.extend([
        "from",
        flight_detail.from_city,
        "to",
        flight_detail.to_city
    ])
    
    # Join them with commas so play_audio_phrase can split and process them
    return ", ".join(announcement_segments)


def play_audio_phrase(input_string, trigger_playback=False, output_filename="output.wav", pause_seconds=0.0):
    """
    Combines audio files for given phrases and exports to the specified output_filename.
    This version relies ONLY on pre-recorded audio files from the database.
    Inserts a pause between each phrase.
    Optionally triggers system playback if trigger_playback is True.
    Returns the path of the exported audio or None if no audio was combined.
    """
    input_phrases = [phrase.strip() for phrase in input_string.split(',')]
    tables = ['file_data', 'gate_data', 'city_data', 'airlines_data']
    
    conn = get_connection()
    if not conn:
        logging.error("Database connection failed for play_audio_phrase.")
        return None

    cursor = conn.cursor()
    results = []
    # Query database for all relevant descriptions in one go
    normalized_input_for_db = [normalize(p) for p in input_phrases]
    
    # Only query if there are phrases to search for
    if normalized_input_for_db:
        for table in tables:
            try:
                # Use IN clause for efficiency if many phrases
                placeholders = ', '.join(['%s'] * len(normalized_input_for_db))
                query = f"SELECT path, description FROM {table} WHERE LOWER(REPLACE(description, '.', '')) IN ({placeholders})"
                cursor.execute(query, normalized_input_for_db)
                rows = cursor.fetchall()
                results.extend(rows)
            except Exception as e:
                logging.error(f"Error querying {table} in play_audio_phrase: {e}")
    
    cursor.close()
    conn.close()

    desc_to_path = {normalize(desc): path for path, desc in results}
    combined = AudioSegment.empty()

    for i, phrase in enumerate(input_phrases):
        norm = normalize(phrase)
        audio_segment_to_add = None

        # Try to find pre-recorded audio
        if norm in desc_to_path:
            path = desc_to_path[norm].replace('\\', '/').strip()
            if os.path.exists(path):
                try:
                    audio_segment_to_add = AudioSegment.from_wav(path)
                    logging.info(f"Loaded pre-recorded audio for: '{phrase}' from path: {path}")
                except Exception as e:
                    logging.error(f"Error loading pre-recorded audio file {path} for phrase '{phrase}': {e}")
            else:
                logging.warning(f"Pre-recorded audio file NOT FOUND at path: {path} for phrase: '{phrase}'. Skipping phrase.")
        else:
            logging.warning(f"Phrase '{phrase}' NOT FOUND in database. Skipping phrase.")


        if audio_segment_to_add:
            combined += audio_segment_to_add
            # Add pause after the phrase, unless it's the last one
            if pause_seconds > 0 and i < len(input_phrases) - 1:
                combined += AudioSegment.silent(duration=pause_seconds * 1000)
        else:
            logging.warning(f"Skipping phrase '{phrase}' as no audio could be found or loaded for it.")

    if len(combined) > 0:
        # Determine the output directory based on the filename
        if output_filename == "output.wav":
            output_dir = "static"
        else:
            output_dir = os.path.join("static", "scheduled")
            
        output_path = os.path.join(output_dir, output_filename)
        os.makedirs(os.path.dirname(output_path), exist_ok=True) # Ensure directory exists
        try:
            combined.export(output_path, format="wav")
            logging.info(f"Combined audio exported to {output_path}")

            if trigger_playback:
                # Play audio using system default player (Windows specific)
                # For macOS: os.system(f'afplay "{output_path}"')
                # For Linux: os.system(f'xdg-open "{output_path}"')
                # Ensure the path is quoted for spaces in filenames
                os.system(f'start "" "{output_path}"') # 'start ""' handles spaces in path on Windows
                logging.info(f"Triggered system playback for {output_path}")

            return output_path
        except Exception as e:
            logging.error(f"Error exporting or playing combined audio to {output_path}: {e}")
            return None
    else:
        logging.error("No audio segments were successfully loaded or combined. The resulting audio is empty. This often indicates missing audio files or an FFmpeg issue.") # Added this specific error log
        return None


# ------------------- Audio Page --------------------------
@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        input_phrases = request.form.getlist('phrase[]')
        schedule_times = request.form.getlist('schedule_time[]')
        pause_durations = request.form.getlist('pause_duration[]') # Get list of pause durations

        grouped_audios_with_pauses = {}

        for i in range(len(input_phrases)):
            phrase = input_phrases[i].strip()
            schedule_time = schedule_times[i].strip()
            pause_duration_str = pause_durations[i].strip() if i < len(pause_durations) else '0'

            if not phrase:
                continue

            try:
                pause_duration = float(pause_duration_str) if pause_duration_str else 0.0
            except ValueError:
                pause_duration = 0.0
                logging.warning(f"Invalid pause duration '{pause_duration_str}' for phrase '{phrase}'. Defaulting to 0 seconds.")

            if schedule_time:
                time_key = schedule_time
            else:
                time_key = 'immediate'

            if time_key not in grouped_audios_with_pauses:
                grouped_audios_with_pauses[time_key] = []
            grouped_audios_with_pauses[time_key].append((phrase, pause_duration))

        messages = []
        audio_path_to_render = None

        for time_key, items_for_time in grouped_audios_with_pauses.items():
            phrases_only = [item[0] for item in items_for_time]
            
            effective_pause = 0.0
            for _, pause_val in items_for_time:
                if pause_val > 0:
                    effective_pause = pause_val
                    break 

            combined_phrase_string = ", ".join(phrases_only)

            if time_key == 'immediate':
                exported_path = play_audio_phrase(combined_phrase_string, trigger_playback=False, 
                                                  output_filename="output.wav", pause_seconds=effective_pause)
                if exported_path:
                    messages.append(f"▶️ Playing '{combined_phrase_string}' immediately (via browser).")
                    audio_path_to_render = url_for('static', filename=os.path.basename(exported_path))
                else:
                    messages.append(f"❌ Could not play '{combined_phrase_string}' immediately. Check server logs for details.")
            else:
                now = datetime.now()
                try:
                    hour, minute = map(int, time_key.split(":"))
                    scheduled_datetime = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
                    if scheduled_datetime < now:
                        scheduled_datetime += timedelta(days=1)

                    unique_filename = f"scheduled_{scheduled_datetime.strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}.wav"

                    scheduler.add_job(play_audio_phrase, 'date', run_date=scheduled_datetime, 
                                      args=[combined_phrase_string, True, unique_filename, effective_pause])
                    messages.append(f"⏰ Scheduled '{combined_phrase_string}' for {scheduled_datetime.strftime('%H:%M')} (server playback via {unique_filename}).")
                except ValueError:
                    messages.append(f"❌ Invalid time format for '{time_key}'. Please use HH:MM.")

        if messages:
            return render_template("form.html", message="<br>".join(messages), audio_path=audio_path_to_render)
        else:
            return render_template("form.html", error="No valid audios to play or schedule.")

    # Fetch flight data for the table
    flight_details = FlightDetails.query.all()
    return render_template("form.html", flight_details=flight_details)


# New endpoint for the Travel Tips page
@app.route('/travel_tips')
def travel_tips_page():
    return render_template('travel_tips.html')


# New endpoint to play announcement for a specific flight
@app.route('/play_flight_announcement/<int:flight_id>')
def play_flight_announcement(flight_id):
    flight = FlightDetails.query.get(flight_id)
    if not flight:
        return jsonify({"error": "Flight not found"}), 404

    announcement_string = generate_announcement_string(flight)
    
    # Use a unique filename for each dynamic announcement
    unique_filename = f"dynamic_announcement_{flight.flight_no}_{uuid.uuid4().hex[:8]}.wav"
    
    # Play the announcement (browser playback)
    exported_path = play_audio_phrase(announcement_string, trigger_playback=False, output_filename=unique_filename)

    if exported_path:
        # MODIFIED: Ensure forward slashes for web URL compatibility
        relative_path_for_url = 'scheduled/' + os.path.basename(exported_path).replace('\\', '/')
        return jsonify({"audio_path": url_for('static', filename=relative_path_for_url)})
    else:
        # Return an error if audio could not be generated/played
        return jsonify({"error": "Could not generate or play announcement. Check server logs."}), 500

# ✨ New LLM Feature: Generate Travel Tips ✨
@app.route('/generate_travel_tips', methods=['POST'])
async def generate_travel_tips():
    data = request.get_json()
    city = data.get('city')

    if not city:
        return jsonify({"error": "City name is required."}), 400

    prompt = f"Provide 5 concise and interesting travel tips for visiting {city}. Format them as a numbered list."
    
    chat_history = []
    # Corrected: Use Python's list append, not JavaScript's push
    chat_history.append({"role": "user", "parts": [{"text": prompt}]}) 
    
    payload = {
        "contents": chat_history,
        "generationConfig": {
            "responseMimeType": "application/json",
            "responseSchema": {
                "type": "ARRAY",
                "items": {
                    "type": "OBJECT",
                    "properties": {
                        "tipNumber": {"type": "INTEGER"},
                        "tipText": {"type": "STRING"}
                    },
                    "propertyOrdering": ["tipNumber", "tipText"]
                }
            }
        }
    }

    # IMPORTANT: Replace "YOUR_GEMINI_API_KEY_HERE" with your actual Gemini API Key
    # You can get one from Google AI Studio: https://aistudio.google.com/app/apikey
    api_key = "YOUR_GEMINI_API_KEY_HERE" 
    api_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={api_key}"

    try:
        response = requests.post(api_url, headers={'Content-Type': 'application/json'}, json=payload)
        response.raise_for_status() # Raise an exception for HTTP errors (4xx or 5xx)
        
        result = response.json()
        
        if result.get("candidates") and len(result["candidates"]) > 0 and \
           result["candidates"][0].get("content") and result["candidates"][0]["content"].get("parts") and \
           len(result["candidates"][0]["content"]["parts"]) > 0:
            
            # The responseSchema makes the output a JSON string of an array of objects
            json_string = result["candidates"][0]["content"]["parts"][0]["text"]
            try:
                parsed_tips = json.loads(json_string)
                return jsonify({"tips": parsed_tips})
            except json.JSONDecodeError as e:
                logging.error(f"Failed to parse LLM response JSON: {e}. Raw response: {json_string}")
                return jsonify({"error": "Failed to parse travel tips from LLM response."}), 500
        else:
            logging.warning(f"LLM response structure unexpected or empty: {result}")
            return jsonify({"error": "Could not generate travel tips. LLM response was empty or malformed."}), 500

    except requests.exceptions.RequestException as e:
        logging.error(f"Error calling Gemini API: {e}")
        return jsonify({"error": f"Failed to connect to Gemini API: {e}"}), 500
    except Exception as e:
        logging.error(f"An unexpected error occurred: {e}")
        return jsonify({"error": f"An unexpected error occurred: {e}"}), 500

# ✨ New LLM Feature: Generate Contextual Announcement ✨
@app.route('/generate_contextual_announcement', methods=['POST'])
async def generate_contextual_announcement():
    data = request.get_json()
    user_request = data.get('request')

    if not user_request:
        return jsonify({"error": "Announcement request is required."}), 400

    prompt = f"""
    Analyze the following user request for a flight announcement and extract the key details.
    If a detail is not explicitly mentioned, omit it.
    
    User Request: "{user_request}"
    
    Extract the following:
    - flight_no (e.g., "FL123", "BA200")
    - status (e.g., "boarding", "delayed", "on time", "cancelled", "departed", "arrived")
    - gate_number (e.g., "5", "B23")
    - additional_message (any other specific instructions or details, e.g., "please proceed to the gate immediately", "we apologize for the inconvenience")
    
    Format the output as a JSON object with these keys. If a key is not found, it should be null.
    Example: {{"flight_no": "FL123", "status": "boarding", "gate_number": "5", "additional_message": null}}
    """
    
    chat_history = []
    chat_history.append({"role": "user", "parts": [{"text": prompt}]}) 
    
    payload = {
        "contents": chat_history,
        "generationConfig": {
            "responseMimeType": "application/json",
            "responseSchema": {
                "type": "OBJECT",
                "properties": {
                    "flight_no": {"type": "STRING", "nullable": True},
                    "status": {"type": "STRING", "nullable": True},
                    "gate_number": {"type": "STRING", "nullable": True},
                    "additional_message": {"type": "STRING", "nullable": True}
                }
            }
        }
    }

    api_key = "YOUR_GEMINI_API_KEY_HERE" # IMPORTANT: Use your actual Gemini API Key here
    api_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={api_key}"

    try:
        response = requests.post(api_url, headers={'Content-Type': 'application/json'}, json=payload)
        response.raise_for_status()
        
        result = response.json()
        
        if result.get("candidates") and len(result["candidates"]) > 0 and \
           result["candidates"][0].get("content") and result["candidates"][0]["content"].get("parts") and \
           len(result["candidates"][0]["content"]["parts"]) > 0:
            
            json_string = result["candidates"][0]["content"]["parts"][0]["text"]
            try:
                parsed_details = json.loads(json_string)
                
                # Now, construct the announcement string based on parsed details
                announcement_parts = []
                current_hour = datetime.now().hour
                if 5 <= current_hour < 12:
                    announcement_parts.append("Good morning ladies and gentlemen")
                elif 12 <= current_hour < 18:
                    announcement_parts.append("Good afternoon ladies and gentlemen")
                else:
                    announcement_parts.append("Good evening ladies and gentlemen")

                if parsed_details.get("flight_no"):
                    announcement_parts.append("this is the announcement for passengers travelling on")
                    announcement_parts.append("flight")
                    announcement_parts.extend(list(parsed_details["flight_no"])) # Spell out flight number

                if parsed_details.get("status"):
                    # You might want to map these to pre-recorded phrases if available
                    status_phrase = parsed_details["status"]
                    if status_phrase == "boarding":
                        announcement_parts.append("is now boarding")
                    elif status_phrase == "delayed":
                        announcement_parts.append("is delayed")
                    elif status_phrase == "on time":
                        announcement_parts.append("is on time")
                    elif status_phrase == "cancelled":
                        announcement_parts.append("is cancelled")
                    elif status_phrase == "departed":
                        announcement_parts.append("has departed")
                    elif status_phrase == "arrived":
                        announcement_parts.append("has arrived")
                    else:
                        announcement_parts.append(status_phrase) # Fallback if not mapped

                if parsed_details.get("gate_number"):
                    announcement_parts.append("from gate")
                    announcement_parts.extend(list(parsed_details["gate_number"])) # Spell out gate number

                if parsed_details.get("additional_message"):
                    announcement_parts.append(parsed_details["additional_message"])

                final_announcement_string = ", ".join(filter(None, announcement_parts)) # Filter out None if any

                unique_filename = f"contextual_announcement_{uuid.uuid4().hex[:8]}.wav"
                exported_path = play_audio_phrase(final_announcement_string, trigger_playback=False, output_filename=unique_filename)

                if exported_path:
                    relative_path_for_url = 'scheduled/' + os.path.basename(exported_path).replace('\\', '/')
                    return jsonify({"audio_path": url_for('static', filename=relative_path_for_url), "message": "Contextual announcement generated and playing."})
                else:
                    return jsonify({"error": "Could not generate or play contextual announcement."}), 500

            except json.JSONDecodeError as e:
                logging.error(f"Failed to parse LLM response JSON for contextual announcement: {e}. Raw response: {json_string}")
                return jsonify({"error": "Failed to parse LLM response for contextual announcement."}), 500
        else:
            logging.warning(f"LLM response structure unexpected or empty for contextual announcement: {result}")
            return jsonify({"error": "Could not generate contextual announcement. LLM response was empty or malformed."}), 500

    except requests.exceptions.RequestException as e:
        logging.error(f"Error calling Gemini API for contextual announcement: {e}")
        return jsonify({"error": f"Failed to connect to Gemini API for contextual announcement: {e}"}), 500
    except Exception as e:
        logging.error(f"An unexpected error occurred during contextual announcement generation: {e}")
        return jsonify({"error": f"An unexpected error occurred: {e}"}), 500


# ------------------- Insert Page -------------------------
@app.route('/insert', methods=['GET', 'POST'])
def insert():
    message = None
    tables = ['file_data', 'gate_data', 'city_data', 'airlines_data', 'flight_details'] # Added flight_details

    if request.method == 'POST':
        selected_table = request.form['table_name']
        index_no = request.form.get('index_no', '').strip() # index_no can be optional for some tables
        path = request.form.get('path', '').strip().strip('"').strip("'")
        description = request.form.get('description', '').strip()

        # Handle FlightDetails specific fields
        flight_no = request.form.get('flight_no', '').strip()
        departure_time = request.form.get('departure_time', '').strip()
        arrival_time = request.form.get('arrival_time', '').strip()
        from_city = request.form.get('from_city', '').strip()
        to_city = request.form.get('to_city', '').strip()
        status = request.form.get('status', '').strip()

        if selected_table not in tables:
            message = "❌ Invalid table selected."
            return render_template('insert.html', message=message, tables=tables)

        conn = get_connection()
        if not conn:
            message = "❌ Database connection failed."
            return render_template('insert.html', message=message, tables=tables)

        cursor = conn.cursor()
        try:
            if selected_table == 'flight_details':
                if not flight_no:
                    message = "❌ Flight Number is required for Flight Details."
                else:
                    # Check if flight_no already exists
                    existing_flight = FlightDetails.query.filter_by(flight_no=flight_no).first()
                    if existing_flight:
                        # Update existing record
                        existing_flight.departure_time = departure_time
                        existing_flight.arrival_time = arrival_time
                        existing_flight.from_city = from_city
                        existing_flight.to_city = to_city
                        existing_flight.status = status
                        db.session.commit()
                        message = f"✅ Flight {flight_no} updated successfully."
                    else:
                        # Insert new record
                        new_flight = FlightDetails(
                            flight_no=flight_no,
                            departure_time=departure_time,
                            arrival_time=arrival_time,
                            from_city=from_city,
                            to_city=to_city,
                            status=status
                        )
                        db.session.add(new_flight)
                        db.session.commit()
                        message = f"✅ Flight {flight_no} inserted successfully."
            else:
                # Original logic for other tables
                if not index_no: # For FileData, GateData etc., index_no is primary key
                    message = f"❌ Index Number is required for {selected_table}."
                else:
                    cursor.execute(
                        f"REPLACE INTO {selected_table} (index_no, path, description) VALUES (%s, %s, %s)",
                        (index_no, path, description)
                    )
                    conn.commit()
                    message = f"✅ Record inserted into `{selected_table}` successfully."
        except Exception as e:
            conn.rollback()
            message = f"❌ Error: {e}"
        finally:
            cursor.close()
            conn.close()

    return render_template('insert.html', message=message, tables=tables)

@app.route('/upload', methods=['POST'])
def upload():
    file = request.files['file']
    description = request.form['description']
    table = request.form['table']

    if file and file.filename.endswith('.wav'):
        path = os.path.join('uploads', file.filename)
        os.makedirs(os.path.dirname(path), exist_ok=True) # Ensure uploads directory exists
        
        conn = get_connection()
        if not conn:
            return "❌ Upload failed: Database connection failed."

        cursor = conn.cursor()
        try:
            file.save(path) # Save file only if DB operation is likely to succeed
            cursor.execute(f"INSERT INTO {table} (path, description) VALUES (%s, %s)", (path, description))
            conn.commit()
        except Exception as e:
            conn.rollback()
            # Clean up partially uploaded file if DB insert fails
            if os.path.exists(path):
                os.remove(path)
            return f"❌ Upload failed: {e}"
        finally:
            cursor.close()
            conn.close()
        return "✅ File uploaded successfully"
    return "❌ Invalid file"


# ------------------- Scheduler Start ---------------------
scheduler = BackgroundScheduler()

# ------------------- Run App -----------------------------
if __name__ == '__main__':
    # Create database tables if they don-t exist
    with app.app_context():
        db.create_all()
        
        # Add some dummy flight data if the table is empty
        if not FlightDetails.query.first():
            logging.info("Populating dummy flight data...")
            dummy_flights = [
                FlightDetails(flight_no="FL123", departure_time="08:00 AM", arrival_time="10:30 AM", from_city="Delhi", to_city="London", status="On Time"),
                FlightDetails(flight_no="FL456", departure_time="11:15 AM", arrival_time="01:45 PM", from_city="Paris", to_city="Rome", status="Delayed"),
                FlightDetails(flight_no="FL789", departure_time="03:00 PM", arrival_time="05:30 PM", from_city="Tokyo", to_city="Seoul", status="On Time"),
                FlightDetails(flight_no="BA200", departure_time="09:30 AM", arrival_time="02:00 PM", from_city="London", to_city="Dubai", status="Boarding"),
                FlightDetails(flight_no="LH401", departure_time="06:00 PM", arrival_time="08:30 PM", from_city="Frankfurt", to_city="Madrid", status="Cancelled")
            ]
            db.session.add_all(dummy_flights)
            db.session.commit()
            logging.info("Dummy flight data populated.")

    # Ensure the 'uploads' and 'static' directories exist on startup
    os.makedirs('uploads', exist_ok=True)
    os.makedirs(os.path.join('static', 'scheduled'), exist_ok=True)
    os.makedirs('static', exist_ok=True) # Ensure static exists for output.wav

    # This ensures APScheduler starts only once in debug mode with Flask's reloader
    if os.environ.get('WERKZEUG_RUN_MAIN') == 'true':
        scheduler.start()
        logging.info("APScheduler started.")
    else:
        logging.info("APScheduler not started in reloader process.")

    app.run(debug=True)
