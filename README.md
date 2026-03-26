# Smart Notes Backend

Backend for smart notes and task planning system using FastAPI + PostgreSQL.

## Run locally

### 1. Create virtual environment
python -m venv .venv

### 2. Activate it
Windows:
.venv\Scripts\activate

Linux/macOS:
source .venv/bin/activate

### 3. Install dependencies
pip install -r requirements.txt

### 4. Start PostgreSQL
docker compose up -d

### 5. Run server
uvicorn app.main:app --reload