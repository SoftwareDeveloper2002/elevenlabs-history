ElevenLabs History Sync Dashboard

This project downloads and stores your ElevenLabs text-to-speech history locally and provides a simple web dashboard to browse it.

FEATURES

Downloads ElevenLabs TTS history

Saves both text metadata and audio files

Resume-safe syncing using cursor pagination

Web dashboard for browsing conversations

Works with large histories

REQUIREMENTS

Python 3.9 or newer

An ElevenLabs API key

PYTHON DEPENDENCIES
Install with:

pip install -r requirements.txt

ENVIRONMENT SETUP
Create a file named .env in the project root:

ELEVENLABS_API_KEY=your_api_key_here

Do not commit this file to version control.

RUNNING THE APP
Start the server with:

uvicorn main:app --reload

Then open your browser at:

http://127.0.0.1:8000

USING THE APP

Click Sync to download your ElevenLabs history

Files are saved in the logs folder

Audio is stored as .mp3 files

Sync can be safely stopped and resumed

FOLDER STRUCTURE

project/
├── main.py
├── requirements.txt
├── .env
├── logs/
│ └── YYYY-MM-DD/
│ ├── chat/
│ │ └── timestamp.json
│ └── voice/
│ └── timestamp.mp3
└── templates/
└── admin.html

TROUBLESHOOTING

If you get a 401 error:

Check your API key

Restart the server after editing .env

If audio is missing:

Confirm your ElevenLabs plan allows TTS

Verify voice_id exists in responses

NOTES

Uses cursor-based pagination (no duplicates)

Safe for large histories

Designed for long-running background syncs