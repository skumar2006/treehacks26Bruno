# Bruno 🎵

**AI-powered audio generation for your videos**

Bruno is an intelligent video processing pipeline that takes audioless videos and automatically generates context-aware background music using cutting-edge AI services.

![Next.js](https://img.shields.io/badge/Next.js-16.1-black?style=flat-square&logo=next.js)
![FastAPI](https://img.shields.io/badge/FastAPI-0.109-009688?style=flat-square&logo=fastapi)
![Python](https://img.shields.io/badge/Python-3.10+-3776AB?style=flat-square&logo=python)
![TypeScript](https://img.shields.io/badge/TypeScript-5-3178C6?style=flat-square&logo=typescript)

## ✨ Features

- 🎬 **Automatic Video Analysis** - Uses Google Cloud Video Intelligence to understand your video content
- 🎼 **Context-Aware Music** - Generates music that matches your video's mood, pacing, and scenes
- ⚡ **Real-time Progress** - Live updates via Server-Sent Events as your video processes
- 🎨 **Beautiful UI** - Modern, animated interface with smooth transitions
- 🛡️ **Rate Limited** - Smart rate limiting prevents abuse (3 videos/hour per IP)
- ⏱️ **Duration Control** - Automatically matches audio length to video duration
- 📥 **Easy Download** - Download your video with AI-generated audio in one click

## 🏗️ Architecture

```
User uploads video
    ↓
1. Google Cloud Video Intelligence → Analyzes scenes, objects, labels
    ↓
2. OpenAI GPT-4o → Generates genre-authentic music prompt with precise timing
    ↓
3. Suno AI → Creates professional-quality audio/music
    ↓
4. FFmpeg (via moviepy) → Combines video + audio
    ↓
Final video with AI-generated audio!
```

## 🚀 Tech Stack

### Frontend
- **Next.js 16** - React framework with App Router
- **TypeScript** - Type-safe development
- **Tailwind CSS 4** - Utility-first styling
- **shadcn/ui** - Beautiful, accessible components
- **Server-Sent Events** - Real-time progress updates

### Backend
- **FastAPI** - Modern Python web framework
- **Google Cloud Video Intelligence API** - Video analysis
- **OpenAI GPT-4o** - Intelligent prompt generation
- **Suno AI** - Music generation (TreeHacks API)
- **moviepy** - Video/audio processing
- **slowapi** - Rate limiting

## 📋 Prerequisites

- **Python 3.10+**
- **Node.js 18+** and npm
- **Google Cloud Account** with Video Intelligence API enabled
- **OpenAI API Key**
- **Suno API Key** (TreeHacks)
- **FFmpeg** installed on your system

### Installing FFmpeg

**macOS:**
```bash
brew install ffmpeg
```

**Ubuntu/Debian:**
```bash
sudo apt update
sudo apt install ffmpeg
```

**Windows:**
Download from [ffmpeg.org](https://ffmpeg.org/download.html)

## 🔧 Installation

### 1. Clone the repository
```bash
git clone <your-repo-url>
cd calHacksProject
```

### 2. Backend Setup

```bash
cd backend

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Frontend Setup

```bash
cd frontend

# Install dependencies
npm install
```

## 🔑 Environment Variables

### Backend (`backend/.env`)

Create a `.env` file in the `backend/` directory:

```env
# Google Cloud
GOOGLE_APPLICATION_CREDENTIALS=/path/to/your/gcp-service-account.json

# OpenAI
OPENAI_API_KEY=sk-...

# Suno AI
SUNO_API_KEY=your-suno-api-key
```

### Google Cloud Setup

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select existing
3. Enable **Video Intelligence API**
4. Create a **Service Account** and download the JSON key
5. Set the path in `GOOGLE_APPLICATION_CREDENTIALS`
6. Create a **Cloud Storage bucket** named `soundscape-ai-uploads-shivam` (or update the bucket name in `backend/api/gcp_video_analysis.py`)

### Frontend (Optional)

Create `frontend/.env.local`:

```env
NEXT_PUBLIC_API_URL=http://localhost:8000
```

## 🏃 Running the Application

### Start Backend

```bash
cd backend
source venv/bin/activate  # If not already activated
python main.py
```

Backend will run on `http://localhost:8000`

### Start Frontend

```bash
cd frontend
npm run dev
```

Frontend will run on `http://localhost:3000` (or 3001, 3005, etc.)

### Open in Browser

Navigate to `http://localhost:3000` (or whichever port Next.js started on)

## 🎯 Usage

1. **Upload Video** - Click or drag-drop a video file (max 60 seconds)
2. **Click "Generate Audio"** - Watch real-time progress through each AI stage:
   - 📹 Analyzing video with Google Cloud AI
   - ✨ Crafting music prompt with OpenAI
   - 🎵 Generating audio with Suno AI
   - 🎬 Combining video and audio
3. **Preview** - Your video with AI-generated audio plays automatically
4. **Download** - Click "Download Video" to save the result

## ⚙️ Rate Limits

To prevent abuse and manage API costs:

- **Main endpoints:** 3 videos per hour per IP address
- **Debug endpoints:** 5 requests per hour per IP address
- **Video duration:** Maximum 60 seconds
- Rate limits reset after 1 hour

## 🛠️ API Endpoints

### Main Endpoints

- `POST /api/generate-stream` - Process video with real-time SSE updates
- `POST /api/generate` - Process video (legacy, returns full video)
- `GET /api/outputs/{filename}` - Retrieve processed video file

### Debug Endpoints

- `GET /` - Health check
- `POST /api/analyze-only` - Test GCP video analysis only
- `POST /api/prompt-only` - Test GCP + OpenAI prompt generation

### API Documentation

Once the backend is running, visit:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

## 📁 Project Structure

```
calHacksProject/
├── backend/
│   ├── api/
│   │   ├── gcp_video_analysis.py  # Google Cloud Video Intelligence
│   │   ├── openai_prompt.py       # GPT-4o prompt generation
│   │   ├── suno_generate.py       # Suno AI audio generation
│   │   └── combine_media.py       # Video + audio merging
│   ├── main.py                    # FastAPI server
│   ├── requirements.txt           # Python dependencies
│   ├── .env                       # Environment variables (not in repo)
│   ├── uploads/                   # Temporary upload directory
│   └── outputs/                   # Final output videos
├── frontend/
│   ├── src/
│   │   ├── app/
│   │   │   ├── page.tsx           # Main UI
│   │   │   ├── layout.tsx         # Root layout
│   │   │   └── globals.css        # Global styles + animations
│   │   └── components/ui/         # shadcn/ui components
│   ├── package.json               # npm dependencies
│   └── next.config.ts             # Next.js configuration
├── CLAUDE.md                      # Development guide for Claude Code
└── README.md                      # This file
```

## 🎨 Key Features Explained

### Real-time Progress Updates

Bruno uses **Server-Sent Events (SSE)** to stream progress updates from the backend to the frontend in real-time. You'll see exactly what stage your video is in:

- Uploading video
- Analyzing with Google Cloud
- Generating music prompt
- Creating audio with Suno
- Combining video and audio

### Genre-Authentic Music

The OpenAI prompt engineering is designed to generate **realistic, genre-appropriate music**:

- Analyzes video content for mood and pacing
- Generates scene-grounded lyrics (describes visible actions, not emotions)
- Matches structure to video duration with precise timestamps
- Uses positive and negative tags to guide Suno's generation

### Smart Duration Control

- Duration is emphasized **4+ times** in the prompt text
- Suno API doesn't have a duration parameter, so we use aggressive prompt engineering
- Audio is automatically trimmed to match video length if needed

## 🐛 Troubleshooting

### Backend won't start

**Problem:** `ModuleNotFoundError` or import errors

**Solution:**
```bash
pip install -r requirements.txt --upgrade
```

### CORS errors in browser

**Problem:** `Access-Control-Allow-Origin` error

**Solution:** Make sure your frontend port is in the CORS allowed origins in `backend/main.py`:
```python
allow_origins=["http://localhost:3000", "http://localhost:3001", "http://localhost:3005", ...]
```

### Video doesn't display

**Problem:** Video processing completes but doesn't show in frontend

**Solution:**
1. Check browser console for errors
2. Verify backend has CORS configured for your frontend port
3. Check if output file exists in `backend/outputs/`
4. Test direct URL: `http://localhost:8000/api/outputs/output_filename.mp4`

### GCP timeout

**Problem:** Video analysis times out

**Solution:**
- Ensure you're using REST transport (already configured)
- Check your GCP quotas
- Use shorter videos
- Verify service account has proper permissions

### Rate limit during testing

**Problem:** Hit rate limit while developing

**Solution:** Adjust rate limits in `backend/main.py`:
```python
@limiter.limit("10/hour")  # Increase for testing
```

## 📝 Development

### Running Tests

```bash
# Backend
cd backend
pytest  # (if tests are added)

# Frontend
cd frontend
npm run lint
```

### Debug Endpoints

Use the debug endpoints to test individual pipeline stages:

```bash
# Test video analysis only
curl -X POST http://localhost:8000/api/analyze-only \
  -F "video=@test.mp4"

# Test analysis + prompt generation
curl -X POST http://localhost:8000/api/prompt-only \
  -F "video=@test.mp4"
```

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## 📄 License

This project is for educational purposes. Please ensure you comply with all API provider terms of service (Google Cloud, OpenAI, Suno).

## 🙏 Acknowledgments

- **Google Cloud** - Video Intelligence API
- **OpenAI** - GPT-4o API
- **Suno AI** - Music generation (TreeHacks API)
- **shadcn/ui** - Beautiful component library
- **FastAPI** - Excellent Python web framework

## 📧 Support

For issues and questions, please open an issue on GitHub.

---

**Built with ❤️ for CalHacks**
