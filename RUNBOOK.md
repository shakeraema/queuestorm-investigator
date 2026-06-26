# QueueStorm Investigator — Runbook

This runbook provides step-by-step instructions to initialize, test, run, and evaluate the QueueStorm Investigator service.

---

## 1. Local Development Setup

To run the application locally without Docker, follow these steps:

### Prerequisites
- Python 3.10 or 3.11
- virtualenv (optional but recommended)

### Step 1: Clone and Navigate
Ensure you are in the project root directory:
```bash
cd "/Users/shakera/Downloads/Study/Hackathons/Codex Community Hackathon sust"
```

### Step 2: Set up Virtual Environment
Create and activate a python virtual environment:
```bash
python3 -m venv venv
source venv/bin/activate
```

### Step 3: Install Dependencies
Install pinned dependencies:
```bash
pip install -r requirements.txt
```

### Step 4: Setup Environment Variables
Create a local `.env` file from the example:
```bash
cp .env.example .env
```
*(Optional)* Add your `GEMINI_API_KEY` inside `.env` to enable LLM-enhanced replies. If omitted, the service runs automatically in local deterministic rule-based mode.

---

## 2. Running the Test Suite

We use the standard library's `unittest` framework to guarantee that the tests run out-of-the-box in any environment without external packages.

To run all unit and integration tests (28 tests covering matcher extraction, case classification, safety audits, skeleton validation, and all 10 worked sample cases):
```bash
python3 -m unittest discover -s tests -p "test_*.py" -v
```

---

## 3. Running the Service Locally

Start the FastAPI application on port `8000`:
```bash
python3 backend/app/main.py
```
The server will start at `http://localhost:8000`.

---

## 4. Running with Docker

### Build the Docker Image
Build the container (image size is optimized under 500MB):
```bash
docker build -t queuestorm-investigator .
```

### Run the Docker Container
Run the container binding port `8000`:
```bash
docker run -p 8000:8000 --name queuestorm-investigator --env-file .env queuestorm-investigator
```

### Run with Docker Compose
Or run easily with docker compose:
```bash
docker compose up --build
```

---

## 5. Verifying the Endpoints (Sample Queries)

Once the service is running, you can hit the HTTP endpoints using `curl`.

### Check Health status (`GET /health`)
```bash
curl -i http://localhost:8000/health
```
**Expected Response:**
```json
{"status":"ok"}
```

### Analyze Ticket (`POST /analyze-ticket`)

#### Query 1: Wrong Transfer (Consistent Evidence)
```bash
curl -i -X POST http://localhost:8000/analyze-ticket \
-H "Content-Type: application/json" \
-d '{
  "ticket_id": "TKT-001",
  "complaint": "I sent 5000 taka to a wrong number around 2pm today. The number was supposed to be 01712345678 but I think I typed it wrong.",
  "language": "en",
  "channel": "in_app_chat",
  "user_type": "customer",
  "transaction_history": [
    {
      "transaction_id": "TXN-9101",
      "timestamp": "2026-04-14T14:08:22Z",
      "type": "transfer",
      "amount": 5000,
      "counterparty": "+8801719876543",
      "status": "completed"
    }
  ]
}'
```

#### Query 2: Phishing Report (Critical Escalation)
```bash
curl -i -X POST http://localhost:8000/analyze-ticket \
-H "Content-Type: application/json" \
-d '{
  "ticket_id": "TKT-005",
  "complaint": "Someone called me saying they are from bKash and asked for my OTP. They said my account will be blocked.",
  "language": "en",
  "channel": "call_center",
  "user_type": "customer",
  "transaction_history": []
}'
```
