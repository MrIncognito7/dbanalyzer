# DB Chatbot: Chat with Your SQLite Database

Ask questions about a database in plain English. A **LangGraph** agent powered by
**Google Gemini** writes the SQL, runs it **read-only** against SQLite, and explains the result.
The backend is **FastAPI**, the frontend is **React + Vite**.

It works with **any SQLite file**: point it at your own database, or run it as-is with the
built-in sample product and supplier data.

![chatbot-screen](resource/screen.gif)

## Features

- **Natural-language querying**: ask about products, suppliers, prices, categories, or whatever is in your own database.
- **Bring your own database**: set `DB_PATH` to any SQLite file. Table names, columns and foreign keys are detected automatically and given to the model, so no code changes are needed.
- **Agentic SQL workflow**: LangGraph loops between the LLM and SQL tools (list tables, read schema, run query) until it has an answer.
- **Conversation memory**: follow-up questions work ("which supplier sells it?"); each browser session has its own history.
- **Safe by design**: the database is opened in read-only mode (your data is never modified), only tables that exist in the database are exposed by the REST API, and there is no raw-SQL endpoint.
- **Polished UI**: typing indicator, suggested questions, clear-chat button, error messages, mobile friendly.
- **Free to run**: uses Gemini's free API tier.

## Architecture

```
React (Vite)  --POST /chat_query-->  FastAPI  -->  LangGraph agent  <-->  Gemini
                                                        |
                                                  SQL tools (read-only)
                                                        |
                                           SQLite database (sample or your own)
```

## Tech stack

| Layer    | Tech                                                           |
| -------- | -------------------------------------------------------------- |
| Backend  | Python 3.10+, FastAPI, LangGraph, LangChain, Gemini            |
| Frontend | React 19, Vite                                                 |
| Database | SQLite (your own file, or sample data created automatically)   |

### Sample data

If you do not set `DB_PATH`, a small sample database is created on first start:

`products`: id, name, brand, price, category, description, supplierid
`suppliers`: id, name, contactinfo, productcategories

## Setup

### 1. Get a free Gemini API key
Create one at <https://aistudio.google.com/apikey>.

### 2. Backend

```bash
cd DBChatbot/backend

python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env            # then paste your key into GOOGLE_API_KEY (see "Configuration" below)
python api.py                   # http://localhost:8000  (docs at /docs)
```

Without `DB_PATH`, the file `ProductsSuppliers.db` is created with sample data on first start.

### 3. Frontend

```bash
cd ../frontend
npm install
npm run dev                     # http://localhost:5173
```

To point the UI at a different backend, copy `frontend/.env.example` to `frontend/.env` and edit `VITE_API_URL`.

## Use your own database

1. Put your SQLite file (`.db`, `.sqlite` or `.sqlite3`) anywhere, for example inside `backend/`.
2. In `backend/.env`, set its path:
   ```
   DB_PATH=my_database.db                 # relative paths are resolved from backend/
   # DB_PATH=C:\data\my_database.db       # or an absolute path
   ```
3. Restart the backend (`python api.py`).

That's it. On startup the app reads your tables, columns and foreign keys and gives them to the model,
so it can write correct queries and joins for your schema.

Things to know:
- Your database is opened **read-only**. The app never creates, changes or deletes anything in it.
- If `DB_PATH` points to a missing file, or to a file that is not SQLite or has no tables, the server stops with a clear error message.
- Views are supported as well as tables.
- `GET /tables/data/{table}` returns at most 500 rows per table.
- Optional: edit the `SUGGESTIONS` list at the top of `frontend/src/App.jsx` so the suggested questions match your data.
- Your `.env` and your database file are git-ignored, so they are not pushed to GitHub.

## API

| Method | Path                       | Description                                   |
| ------ | -------------------------- | --------------------------------------------- |
| POST   | `/chat_query`              | `{ "input_message": "...", "session_id": "..." }` returns `{ "answer", "session_id" }` |
| GET    | `/tables`                  | List the tables (and views) in the database   |
| GET    | `/tables/data/{table}`     | Up to 500 rows of an existing table           |
| GET    | `/health`                  | Server status and whether the API key is set  |

## Try these questions

With the sample data:

- Show me all the products.
- Name all products under brand X.
- Which suppliers provide furniture?
- Give me details of products 2, 3 and 4.
- What is the average price of all products?
- Which supplier should I contact for electronics? Give me their contact details.
- Which supplier sells the most products? List them.
- Which is the least priced product?

With your own database, ask about whatever your tables contain, for example "How many rows are in each table?" or "Show the 5 most recent records".

## Configuration (`backend/.env`)

Your private settings (API key, database path) live in a file called `.env` inside the `backend/` folder, next to `api.py`. It is **not** included in the repository, so you create it yourself.

### Create the file

Copy the example file:

```bash
cd backend
cp .env.example .env            # Windows CMD: copy .env.example .env
                                # PowerShell:  Copy-Item .env.example .env
```

Or create a new text file named exactly `.env` (no `.txt` at the end), then open it in any editor.

### What to put in it

```env
# Required: free key from https://aistudio.google.com/apikey
GOOGLE_API_KEY=paste-your-key-here

# Optional: only if the default model name stops working
GEMINI_MODEL=gemini-3.8-flash

# Optional: use your own SQLite database instead of the sample data
DB_PATH=my_database.db
```

For a normal first run, `GOOGLE_API_KEY` alone is enough.

Rules:
- Write `NAME=value` with **no spaces** around `=` and **no quotes** around the value.
- One setting per line. Lines starting with `#` are comments.
- Restart the backend (`python api.py`) after changing the file; it is only read at startup.

### Check that it works

Open <http://localhost:8000/health>. You should see `"llm_configured": true`. If it says `false`, the key is not being read. Check that the file is at `backend/.env` (not `.env.txt`, not in another folder) and that the line starts with `GOOGLE_API_KEY=`.

The frontend has its own optional `frontend/.env`. You only need it if your backend is not at `http://localhost:8000` (set `VITE_API_URL=` to its address).

### All variables

| Variable         | Default                 | Purpose                                              |
| ---------------- | ----------------------- | ---------------------------------------------------- |
| `GOOGLE_API_KEY` | (required)              | Gemini API key                                       |
| `DB_PATH`        | sample database         | Path to your SQLite file (absolute, or relative to `backend/`) |
| `GEMINI_MODEL`   | `gemini-3.8-flash`      | Any Gemini model with tool calling. Google retires models often; if you get a "model not found" error, set a current one here |
| `CORS_ORIGINS`   | `http://localhost:5173` | Allowed browser origins                              |
| `HOST` / `PORT`  | `127.0.0.1` / `8000`    | Where the backend listens                            |

> **Never commit `.env`.** It is listed in `.gitignore`, and only `.env.example` is pushed.

## Notes

- The free Gemini tier is rate limited. If you see a "rate limit" message, wait a minute and retry.
- Conversation memory is kept in server memory and resets when the backend restarts.
- Very large databases (hundreds of tables) make the prompt longer; the model works best with a focused schema.
