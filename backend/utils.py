

import os
import sqlite3
from contextlib import closing
from pathlib import Path
from typing import Any, Dict, List

from langchain_community.agent_toolkits import SQLDatabaseToolkit
from langchain_community.utilities import SQLDatabase
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import START, MessagesState, StateGraph
from langgraph.prebuilt import ToolNode, tools_condition

BASE_DIR = Path(__file__).resolve().parent
DEFAULT_DB = BASE_DIR / "ProductsSuppliers.db"


def _resolve_db_path() -> Path:
    """DB_PATH from the environment (absolute, or relative to backend/), else the sample DB."""
    configured = os.getenv("DB_PATH")
    if not configured:
        return DEFAULT_DB
    path = Path(configured).expanduser()
    return path if path.is_absolute() else (BASE_DIR / path).resolve()


# api.py calls load_dotenv() before importing this module, so DB_PATH is already set here.
DB_PATH = _resolve_db_path()

SYSTEM_PROMPT_TEMPLATE = """You are a helpful assistant that answers questions about the \
data in a SQLite database.

Tables and columns:
{schema}

Rules:
- Use the SQL tools to look up the data. Never guess values.
- Only write read-only SELECT queries. Never modify data.
- Text comparisons may be case-sensitive; use LOWER(column) = LOWER('value') or LIKE.
- Limit results to 20 rows unless the user asks for more.
- When you have the data, answer in short, clear plain English (no SQL, no markdown tables).
- If the question is not about this data, say you can only help with questions about it.
"""


def _q(name: str) -> str:
    """Quote an identifier for use in SQL (names come from sqlite_master, never from users)."""
    return '"' + name.replace('"', '""') + '"'

def _create_sample_database() -> None:
    with closing(sqlite3.connect(DB_PATH)) as con:
        cur = con.cursor()
        cur.execute(
            """CREATE TABLE IF NOT EXISTS suppliers (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                contactinfo TEXT,
                productcategories TEXT
            );"""
        )
        cur.execute(
            """CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                brand TEXT,
                price REAL,
                category TEXT,
                description TEXT,
                supplierid INTEGER,
                FOREIGN KEY (supplierid) REFERENCES suppliers(id)
            );"""
        )
        cur.executemany(
            "INSERT INTO suppliers (id, name, contactinfo, productcategories) VALUES (?, ?, ?, ?)",
            [
                (1, "a", "contactA@example.com", "electronics, home appliances"),
                (2, "b", "contactB@example.com", "furniture, decor"),
                (3, "c", "contactC@example.com", "groceries, beverages"),
            ],
        )
        cur.executemany(
            "INSERT INTO products (id, name, brand, price, category, description, supplierid) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            [
                (1, "smartphone", "x", 699.99, "electronics", "latest model with AI camera", 1),
                (2, "refrigerator", "y", 1199.99, "home appliances", "energy-efficient cooling", 1),
                (3, "sofa set", "z", 499.99, "furniture", "comfortable 3-seater", 2),
                (4, "dining table", "z", 899.99, "furniture", "solid wood with six chairs", 2),
                (5, "organic juice", "w", 5.99, "groceries", "freshly squeezed organic fruit juice", 3),
            ],
        )
        con.commit()


def setup_database() -> None:
    """Make sure the database exists and has tables.

    - DB_PATH set: the file must already exist (we never create or modify your data).
    - DB_PATH not set: create the sample products/suppliers DB if it is missing.
    """
    if not DB_PATH.exists():
        if os.getenv("DB_PATH"):
            raise FileNotFoundError(f"DB_PATH points to a file that does not exist: {DB_PATH}")
        _create_sample_database()

    try:
        tables = get_all_tables()
    except sqlite3.DatabaseError as e:
        raise RuntimeError(f"{DB_PATH} is not a valid SQLite database ({e}).") from e
    if not tables:
        raise RuntimeError(f"{DB_PATH} has no tables.")


def _connect_readonly() -> sqlite3.Connection:
    """Open the database in read-only mode."""
    return sqlite3.connect(f"{DB_PATH.as_uri()}?mode=ro", uri=True)


def get_all_tables() -> List[str]:
    with closing(_connect_readonly()) as con:
        rows = con.execute(
            "SELECT name FROM sqlite_master WHERE type IN ('table', 'view') "
            "AND name NOT LIKE 'sqlite_%' ORDER BY name"
        ).fetchall()
    return [r[0] for r in rows]


def fetch_table_data(table_name: str, limit: int = 500) -> List[Dict[str, Any]]:
    """Return up to `limit` rows of a table. Raises ValueError for unknown tables."""
    if table_name not in get_all_tables():  # allow-list read from the database itself
        raise ValueError(f"Unknown table '{table_name}'")
    with closing(_connect_readonly()) as con:
        con.row_factory = sqlite3.Row
        rows = con.execute(f"SELECT * FROM {_q(table_name)} LIMIT ?", (limit,)).fetchall()
    return [dict(r) for r in rows]


def get_schema_text() -> str:
    """Describe every table (columns and foreign keys) so the model knows the schema."""
    lines: List[str] = []
    with closing(_connect_readonly()) as con:
        for table in get_all_tables():
            columns = [r[1] for r in con.execute(f"PRAGMA table_info({_q(table)})")]
            lines.append(f"- {table}({', '.join(columns)})")
            for fk in con.execute(f"PRAGMA foreign_key_list({_q(table)})"):
                # fk columns: id, seq, referenced table, from column, to column, ...
                lines.append(f"    {table}.{fk[3]} references {fk[2]}.{fk[4]}")
    return "\n".join(lines)


def build_system_prompt() -> str:
    return SYSTEM_PROMPT_TEMPLATE.format(schema=get_schema_text())


# --------------------------------------------------------------------------- #
# LLM + agent
# --------------------------------------------------------------------------- #
def get_llm():
    """Create the Gemini chat model. Needs GOOGLE_API_KEY in the environment."""
    from langchain_google_genai import ChatGoogleGenerativeAI

    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise RuntimeError(
            "GOOGLE_API_KEY is not set. Get a free key at https://aistudio.google.com/apikey "
            "and put it in backend/.env (see .env.example)."
        )
    return ChatGoogleGenerativeAI(
        model=os.getenv("GEMINI_MODEL", "gemini-3.8-flash"),
        google_api_key=api_key,
        temperature=0,
    )


def get_db_tools(llm):
    """SQL tools bound to a READ-ONLY connection, so the agent cannot change data."""
    db = SQLDatabase.from_uri(f"sqlite:///{DB_PATH.as_uri()}?mode=ro&uri=true")
    return SQLDatabaseToolkit(db=db, llm=llm).get_tools()


def build_graph(llm):
    """Build the LangGraph agent: assistant <-> SQL tools loop, with per-session memory."""
    tools = get_db_tools(llm)
    llm_with_tools = llm.bind_tools(tools)
    system_prompt = build_system_prompt()  # schema is read from your database once, here

    def sql_assistant(state: MessagesState):
        messages = [SystemMessage(content=system_prompt)] + state["messages"]
        return {"messages": [llm_with_tools.invoke(messages)]}

    builder = StateGraph(MessagesState)
    builder.add_node("sql_assistant", sql_assistant)
    builder.add_node("tools", ToolNode(tools))
    builder.add_edge(START, "sql_assistant")
    builder.add_conditional_edges("sql_assistant", tools_condition)
    builder.add_edge("tools", "sql_assistant")
    # MemorySaver keeps each session's conversation (keyed by thread_id) in memory.
    return builder.compile(checkpointer=MemorySaver())


def _text_of(content: Any) -> str:
    """Gemini can return a plain string or a list of content parts; normalise to text."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for part in content:
            if isinstance(part, str):
                parts.append(part)
            elif isinstance(part, dict) and part.get("type") == "text":
                parts.append(part.get("text", ""))
        return "".join(parts)
    return str(content)


def process_chat_query(graph, message: str, session_id: str) -> str:
    """Run one user message through the agent and return the final answer text."""
    result = graph.invoke(
        {"messages": [HumanMessage(content=message)]},
        config={"configurable": {"thread_id": session_id}, "recursion_limit": 15},
    )
    return _text_of(result["messages"][-1].content).strip()