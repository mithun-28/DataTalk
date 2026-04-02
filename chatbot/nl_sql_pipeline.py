import sqlite3
import subprocess
from openai import OpenAI
import google.generativeai as genai
import re

# ==============================
# CONFIG
# ==============================
import os

hf_token = os.getenv("HF_TOKEN")
GEMINI_API_KEY = "AIzaSyA6k2mdpOK05rzx5Lel9qaaFStw4zSEWks"

DB_PATH = r"C:\Users\slpmi\OneDrive\Desktop\Capstone\project\chinook.db"

client = OpenAI(
    base_url="https://router.huggingface.co/v1",
    api_key=HF_TOKEN
)

genai.configure(api_key=GEMINI_API_KEY)

# ==============================
# CASA
# ==============================
def run_casa_algorithm(user_query):
    try:
        casa_path = "c:/Users/slpmi/OneDrive/Desktop/Capstone/CASA.py"
        process = subprocess.Popen(
            ['python', casa_path],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
        )
        stdout, _ = process.communicate(input=user_query)
        return stdout
    except Exception as e:
        return f"CASA Error: {str(e)}"

def extract_schema_context(casa_output):
    return "\n".join([
        line.split(':')[-1].strip()
        for line in casa_output.split('\n')
        if ':' in line and '0.' in line
    ])

# ==============================
# SCHEMA
# ==============================
def extract_db_schema(db_path):
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        tables = cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table';"
        ).fetchall()

        schema = []
        for tbl in tables:
            tbl_name = tbl[0]
            cols = cursor.execute(f"PRAGMA table_info({tbl_name})").fetchall()
            col_names = [c[1] for c in cols]
            schema.append(f"{tbl_name}({', '.join(col_names)})")

        conn.close()
        return "\n".join(schema)

    except Exception as e:
        return f"Schema Extraction Error: {str(e)}"

# ==============================
# CLEAN SQL
# ==============================
def clean_sql_output(sql):
    return sql.replace("```sql", "").replace("```", "").strip()

# ==============================
# FIX TABLE NAMES
# ==============================
def fix_table_names(sql_query, schema):
    tables = [line.split("(")[0] for line in schema.split("\n")]

    for tbl in tables:
        if tbl.endswith("s"):
            singular = tbl[:-1]
            pattern = r'\b' + singular + r'\b'
            sql_query = re.sub(pattern, tbl, sql_query, flags=re.IGNORECASE)

    return sql_query

# ==============================
# SQL ENHANCE
# ==============================
def enhance_sql(sql_query, schema):
    sql_query = fix_table_names(sql_query, schema)

    if "transactions" in sql_query.lower():
        sql_query = sql_query.replace("transactions", "invoice")

    if "amount" in sql_query.lower():
        sql_query = sql_query.replace("amount", "Total")

    return sql_query

# ==============================
# EXECUTE SQL
# ==============================
def execute_sql_query(db_path, sql_query):
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute(sql_query)

        rows = cursor.fetchall()
        columns = [desc[0] for desc in cursor.description]

        conn.close()
        return columns, rows, None

    except Exception as e:
        return None, None, str(e)

# ==============================
# RETRY SQL (SELF-CORRECT)
# ==============================
def retry_sql_generation(query, schema, error_msg):
    completion = client.chat.completions.create(
        model="Qwen/Qwen2.5-Coder-7B-Instruct",
        temperature=0.1,
        messages=[
            {
                "role": "system",
                "content": """
You are an expert SQLite debugger.

Fix SQL using:
- Correct table/column names
- Proper joins
- Given schema only

Return ONLY SQL.
"""
            },
            {
                "role": "user",
                "content": f"""
Schema:
{schema}

Query:
{query}

Error:
{error_msg}
"""
            }
        ]
    )

    return clean_sql_output(completion.choices[0].message.content)

# ==============================
# GEMINI (SHORT CHATBOT STYLE)
# ==============================
def generate_nl_summary(query, columns, results):
    try:
        model = genai.GenerativeModel("models/gemini-2.5-flash")

        if not results:
            return f"No results found for '{query}'."

        sample = results[:5]

        data_text = "\n".join(
            [", ".join(f"{col}: {val}" for col, val in zip(columns, row)) for row in sample]
        )
        prompt = f"""
        User Query: {query}
        Data: {data_text}
        Return output EXACTLY in this format:
        Summary:
        - point 1
        - point 2
        - point 3
        
        Insights:
        - point 1
        - point 2
        - point 3
        IMPORTANT:
        - Put EACH point on a NEW LINE
        - Add a BLANK LINE between Summary and Insights
        - Do NOT combine into paragraph
        - Do NOT use markdown or *
        """

        response = model.generate_content(prompt)
        return response.text.strip()

    except Exception as e:
        return f"Insight Error: {str(e)}"

# ==============================
# VISUALIZATION RECOMMENDATION
# ==============================
def recommend_visualization(query, columns, results):
    try:
        model = genai.GenerativeModel("models/gemini-2.5-flash")

        sample = results[:5]

        data_text = "\n".join(
            [", ".join(f"{c}:{v}" for c, v in zip(columns, row)) for row in sample]
        )

        prompt = f"""
Query: {query}
Columns: {columns}
Data:
{data_text}

Return ONLY one:
bar, line, pie, table
"""

        response = model.generate_content(prompt)
        return response.text.strip().lower()

    except:
        return "table"




# ==============================
# MAIN PIPELINE (Django SAFE)
# ==============================
def run_pipeline(user_query):

    db_schema = extract_db_schema(DB_PATH)

    # CASA
    casa_out = run_casa_algorithm(user_query)
    schema_context = extract_schema_context(casa_out)

    # SQL GENERATION
    completion = client.chat.completions.create(
        model="Qwen/Qwen2.5-Coder-7B-Instruct",
        temperature=0.1,
        messages=[
            {
                "role": "system",
                "content": """
You are an expert SQLite generator.

RULES:
- Use exact schema
- No hallucination
- Correct joins

Return ONLY SQL.
"""
            },
            {
                "role": "user",
                "content": f"""
Schema:
{db_schema}

Context:
{schema_context}

Question:
{user_query}
"""
            }
        ]
    )

    sql_query = clean_sql_output(completion.choices[0].message.content)
    sql_query = enhance_sql(sql_query, db_schema)

    # EXECUTION
    columns, results, error = execute_sql_query(DB_PATH, sql_query)

    # AUTO RETRY
    if error:
        sql_query = retry_sql_generation(user_query, db_schema, error)
        columns, results, error = execute_sql_query(DB_PATH, sql_query)

    # SAFETY CHECK
    if error:
        return {
            "sql": sql_query,
            "columns": [],
            "results": [],
            "summary": f"SQL Error: {error}",
            "viz": "table"
        }

    # INSIGHTS + VIS
    summary = generate_nl_summary(user_query, columns, results)
    viz_type = recommend_visualization(user_query, columns, results)

    return {
        "sql": sql_query,
        "columns": columns,
        "results": results,
        "summary": summary,
        "viz": viz_type
    }