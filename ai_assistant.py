import sqlite3
import os
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

conn = sqlite3.connect("amazon.db")

history = []

def ask_ai(question):
    schema = """
    Table: products

    Columns:
    product_name
    category
    discounted_price
    actual_price
    discount_percentage
    rating
    rating_count
    about_product
    """

    prompt = f"""
    You are a SQL assistant.

    Rules:
    - Only generate valid SQLite SELECT queries
    - Use only the columns in the schema
    - Do not invent columns
    - Always include LIMIT 10
    - Return SQL only

    Schema:
    {schema}

    Question: {question}
    """

    messages = history + [{"role": "user", "content": prompt}]

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=messages
    )

    sql_query = response.choices[0].message.content.strip()
    sql_query = sql_query.replace("```sql", "").replace("```", "").strip()

    print("\nGenerated SQL:\n", sql_query)

    for word in ["DROP","DELETE","UPDATE","INSERT","ALTER"]:
        if word in sql_query.upper():
            raise Exception("Unsafe query detected")

    try:
        cursor = conn.execute(sql_query)
        columns = [desc[0] for desc in cursor.description]
        rows = cursor.fetchall()
        result = [dict(zip(columns,row)) for row in rows]

    except Exception as e:
        print("SQL Error:", e)

        fix_prompt = f"""
        The following SQL caused an error: {e}
        SQL: {sql_query}
        Please provide a corrected SELECT query using only the schema and columns above.
        """
        response_fix = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": fix_prompt}]
        )
        sql_query = response_fix.choices[0].message.content.strip()
        sql_query = sql_query.replace("```sql", "").replace("```", "").strip()
        print("\nCorrected SQL:\n", sql_query)

        try:
            cursor = conn.execute(sql_query)
            columns = [desc[0] for desc in cursor.description]
            rows = cursor.fetchall()
            result = [dict(zip(columns,row)) for row in rows]
        except Exception as e2:
            print("Still failed:", e2)
            result = []

    summary_prompt = f"""
    User question: {question}

    SQL Result: {result}

    Explain the result in plain English as a concise answer.
    """
    summary_response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": summary_prompt}]
    )
    explanation = summary_response.choices[0].message.content.strip()

    history.append({"role": "user", "content": prompt})
    history.append({"role": "assistant", "content": sql_query})

    return result, explanation

print("Amazon AI Assistant (type 'exit' to quit)")

while True:
    q = input("\nAsk: ")
    if q.lower() == "exit":
        break

    result, explanation = ask_ai(q)
    print("\nResult:\n", result)
    print("\nExplanation:\n", explanation)