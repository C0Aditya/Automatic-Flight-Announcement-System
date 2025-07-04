# Automatic-Flight-Announcement-System

A Flask-based web application designed to manage flight information, play pre-recorded and dynamically generated audio announcements, and provide AI-powered travel tips.

Features
Flight Information Management:

Display a list of flights with details like flight number, departure/arrival times, origin, destination, and status.

Admin panel for inserting and managing flight data.

Audio Announcement System:

Play pre-recorded audio phrases immediately or schedule them for a specific time.

Combine multiple audio phrases with customizable pauses.

"Announce" button on each flight row to generate and play a standard announcement for that flight.

LLM-Assisted Contextual Announcements:

Generate dynamic flight announcements based on natural language input using the Gemini API.

Extracts details like flight number, status, gate number, and additional messages from user requests.

Combines pre-recorded audio segments with LLM-generated phrases for a comprehensive announcement.

Travel Tip Generator (Powered by Gemini LLM):

Dedicated page to generate concise travel tips for any city using the Gemini API.

Provides structured, numbered lists of tips.

User-Friendly Interface:

Clean and responsive design using Tailwind CSS.

Loading indicators for long-running operations (audio generation, LLM calls).

Technologies Used
Backend:

Python 3

Flask (web framework)

Flask-SQLAlchemy (ORM for database interaction)

Flask-Admin (for administrative interface)

MySQL (database)

Pydub (for audio manipulation)

APScheduler (for scheduling announcements)

Requests (for making HTTP requests to external APIs)

Frontend:

HTML5

CSS3 (Tailwind CSS framework)

JavaScript (for dynamic UI and API calls)

AI/LLM:

Google Gemini API (gemini-2.0-flash model)

Setup and Installation
Follow these steps to get the project up and running on your local machine.

1. Prerequisites
Python 3.8+

pip (Python package installer)

MySQL Server running locally

FFmpeg (required by Pydub for audio processing). Download from ffmpeg.org and ensure it's in your system's PATH.

A Google Gemini API Key. Get one from Google AI Studio.

2. Clone the Repository
git clone https://github.com/C0Aditya/Flight-Announcement-System.git
cd Flight-Announcement-System


3. Set up a Virtual Environment (Recommended)
python -m venv venv
# On Windows:
.\venv\Scripts\activate
# On macOS/Linux:
source venv/bin/activate

4. Install Dependencies
pip install -r requirements.txt
# If you don't have requirements.txt, you can install them manually:
pip install Flask Flask-SQLAlchemy Flask-Admin pydub mysql-connector-python APScheduler requests
# IMPORTANT: Install Flask with async support for LLM features
pip install Flask[async]

5. Database Setup
Ensure your MySQL server is running.

Log in to your MySQL server (e.g., via MySQL Workbench, command line).

Create a database named audiofiles:

CREATE DATABASE audiofiles;

Update the database connection string in app.py:

app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+mysqlconnector://root:YOUR_MYSQL_PASSWORD@localhost/audiofiles'



6. Configure Gemini API Key
Open app.py and locate the api_key variables within the generate_travel_tips and generate_contextual_announcement functions. Replace "YOUR_GEMINI_API_KEY_HERE" with your actual Gemini API key:

# In generate_travel_tips and generate_contextual_announcement functions:
api_key = "YOUR_GEMINI_API_KEY_HERE"

7. Run the Application
python app.py

The application should now be running on http://127.0.0.1:5000/.

8. Initial Data (Optional)
The app.py includes logic to populate some dummy flight data if the flight_details table is empty. You can also use the /admin panel to manually insert data for FileData, GateData, CityData, AirlinesData, and FlightDetails.

Admin Panel: Access http://127.0.0.1:5000/admin to manage database entries.

Insert Data: Access http://127.0.0.1:5000/insert for a simplified data insertion form.

9. Uploading Audio Files
For the audio announcement features to work, you need to upload .wav files corresponding to the phrases you want to play. Use the /insert page or the /admin panel to upload audio files and associate them with descriptions in the file_data, gate_data, city_data, and airlines_data tables.

Ensure the uploads/ directory exists in your project root.

When uploading, the description should match the exact phrase (case-insensitive, punctuation-insensitive) you expect the system to look up (e.g., "Good morning ladies and gentlemen", "flight", "FL123", "Delhi", "gate 5").

10. Database Setup
Create the MySQL Database:
Ensure your MySQL server is running. Log in to your MySQL server (e.g., via MySQL Workbench, command line) and create a database named audiofiles before running the Flask application:

CREATE DATABASE audiofiles;

Configure Database Connection:
Update the database connection string in app.py:

app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+mysqlconnector://root:YOUR_MYSQL_PASSWORD@localhost/audiofiles'

Replace YOUR_MYSQL_PASSWORD with your MySQL root password.

Database Tables:
The Flask application will automatically create the necessary tables (file_data, gate_data, city_data, airlines_data, flight_details) within the audiofiles database when you run app.py for the first time.


Usage
Flight Announcements (Home Page):

Enter custom phrases and schedule times.

Click "Announce" next to a flight to hear a pre-defined announcement for it.

Travel Tips (New Page):

Navigate to the "Travel Tips" link in the header.

Enter a city name and click "Generate Travel Tips" to get AI-powered recommendations.

Admin Panel: Manage all your database records.

Insert Data: Quickly add new audio file paths and descriptions, or flight details.

