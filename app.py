import os
import re
from flask import Flask, request, jsonify, session, send_from_directory
from flask_cors import CORS
from dotenv import load_dotenv
from pydantic import BaseModel
from langchain_core.messages import HumanMessage, AIMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import PydanticOutputParser
from langchain_classic.agents import create_tool_calling_agent, AgentExecutor
from tools import search_tool, save_tool, search_products
from graph_agent import run_until_approval, run_synthesis
from llm import get_llm
from rag_service import (
    list_context_files,
    save_and_index_file,
    delete_file,
    reindex_all,
    query_context,
)

load_dotenv()

class ResearchResponse(BaseModel):
    topic: str
    summary: str
    sources: list[str]
    tools_used: list[str]

parser = PydanticOutputParser(pydantic_object=ResearchResponse)

prompt = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            """
            You are a research assistant that will help generate a research paper.
            Answer the user query and use neccessary tools.
            Wrap the output in this format and provide no other text\n{format_instructions}
            """,
        ),
        ("placeholder", "{chat_history}"),
        ("human", "{query}"),
        ("placeholder", "{agent_scratchpad}"),
    ]
).partial(format_instructions=parser.get_format_instructions())

tools = [search_tool, save_tool]


def get_agent():
    llm = get_llm(temperature=0.2)
    agent = create_tool_calling_agent(llm=llm, prompt=prompt, tools=tools)
    return AgentExecutor(agent=agent, tools=tools, verbose=True, handle_parsing_errors=True, handle_tool_error=True)


def _parse_output(output, original_query=""):
    if isinstance(output, list):
        text = "".join(
            item.get("text", "") if isinstance(item, dict) else str(item)
            for item in output
        )
    else:
        text = str(output)

    match = re.search(r'\{[\s\S]*\}', text)
    if match:
        try:
            return parser.parse(match.group(0)).model_dump()
        except Exception:
            pass

    # Graceful fallback for conversational responses or non-JSON greetings
    clean_text = text.strip()
    return {
        "topic": original_query or "Research Assistant",
        "summary": clean_text or "I am your AI research assistant ready to help you investigate any topic.",
        "sources": [],
        "tools_used": [],
    }


app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "ai-agent-persistent-session-secret-key-2026")
CORS(app, supports_credentials=True)

FRONTEND_DIST = os.path.join(os.path.dirname(os.path.abspath(__file__)), "frontend", "dist")


# ── Web Research Agent Endpoints ───────────────────────────────────────────

@app.route("/research", methods=["GET"])
def research():
    query = request.args.get("query", "").strip()
    if not query:
        return jsonify({"error": "Missing 'query' parameter"}), 400

    try:
        # Load recent session conversation history
        history = session.get("research_history", [])
        chat_messages = []
        for item in history[-4:]:
            if item.get("role") == "user":
                chat_messages.append(HumanMessage(content=item.get("content", "")))
            else:
                chat_messages.append(AIMessage(content=item.get("summary", "") or item.get("content", "")))

        raw_response = get_agent().invoke({"query": query, "chat_history": chat_messages})
        data = _parse_output(raw_response.get("output", ""), original_query=query)

        # Save to session history
        history.append({"role": "user", "content": query})
        history.append({
            "role": "assistant",
            "topic": data.get("topic", query),
            "summary": data.get("summary", ""),
            "sources": data.get("sources", []),
            "tools_used": data.get("tools_used", []),
        })
        session["research_history"] = history[-8:]
        session.modified = True
    except Exception as e:
        return jsonify({"error": f"Research failed: {str(e)}"}), 500

    return jsonify({**data, "history": session["research_history"]})


@app.route("/research-clear-history", methods=["POST"])
def research_clear_history():
    session.pop("research_history", None)
    return jsonify({"success": True, "message": "Research conversation reset"})


# ── Retail Product Search Endpoints ────────────────────────────────────────

@app.route("/product-search", methods=["GET"])
def product_search():
    query = request.args.get("query", "").strip()
    if not query:
        return jsonify({"error": "Missing 'query' parameter"}), 400

    try:
        listings = search_products(query)
    except Exception as e:
        return jsonify({"error": f"Product search failed: {str(e)}"}), 500

    return jsonify({"query": query, "listings": listings})


# ── Multi-Step Agent (LangGraph) ────────────────────────────────────────────

@app.route("/multi-step", methods=["GET"])
def multi_step():
    query = request.args.get("query", "").strip()
    if not query:
        return jsonify({"error": "Missing 'query' parameter"}), 400

    try:
        # Run breakdown → research (stops before synthesize, waiting for approval)
        state = run_until_approval(query)
        # Store in session for the approval step
        session["ms_state"] = {
            "query": state["query"],
            "sub_questions": state["sub_questions"],
            "raw_search": state["raw_search"],
        }
    except Exception as e:
        return jsonify({"error": f"Multi-step agent failed: {str(e)}"}), 500

    return jsonify(state)


@app.route("/multi-step-approve", methods=["POST"])
def multi_step_approve():
    state_data = session.get("ms_state")
    if not state_data:
        return jsonify({"error": "No session state"}), 400

    try:
        answer = run_synthesis(state_data)
        session.pop("ms_state", None)
    except Exception as e:
        return jsonify({"error": f"Synthesis failed: {str(e)}"}), 500

    return jsonify({
        "query": state_data["query"],
        "sub_questions": state_data["sub_questions"],
        "answer": answer,
    })


# ── Context / Policy RAG Endpoints ─────────────────────────────────────────

@app.route("/rag-files", methods=["GET"])
def rag_files():
    files = list_context_files()
    return jsonify({"files": files})


@app.route("/rag-upload", methods=["POST"])
def rag_upload():
    uploaded_file = request.files.get("file")
    if not uploaded_file or not uploaded_file.filename:
        return jsonify({"error": "No file uploaded", "files": list_context_files()}), 400

    try:
        success, filename, chunks = save_and_index_file(uploaded_file)
        files = list_context_files()
        msg = f"Successfully uploaded and indexed '{filename}' ({chunks} chunks generated)."
    except Exception as e:
        files = list_context_files()
        msg = f"Error processing file '{uploaded_file.filename}': {str(e)}"
        success, filename, chunks = False, uploaded_file.filename, 0

    return jsonify({"success": success, "filename": filename, "chunks": chunks, "message": msg, "files": files})


@app.route("/rag-delete/<filename>", methods=["POST", "DELETE"])
def rag_delete(filename):
    delete_file(filename)
    files = list_context_files()
    msg = f"Deleted '{filename}' from /context and removed its vector index."
    return jsonify({"success": True, "message": msg, "files": files})


@app.route("/rag-reindex", methods=["POST"])
def rag_reindex():
    total_chunks = reindex_all()
    files = list_context_files()
    msg = f"Re-indexed all {len(files)} files in /context ({total_chunks} chunks indexed)."
    return jsonify({"success": True, "total_chunks": total_chunks, "files": files, "message": msg})


@app.route("/rag-query", methods=["GET", "POST"])
def rag_query():
    query = request.args.get("query", "").strip() or request.form.get("query", "").strip()
    if not query:
        return jsonify({"error": "Missing query"}), 400

    try:
        # Load previous conversation history from current session
        chat_history = session.get("rag_history", [])
        result = query_context(query, chat_history=chat_history)

        # Append latest turn to session history
        chat_history.append({"role": "user", "content": query})
        chat_history.append({
            "role": "assistant",
            "content": result.get("answer", ""),
            "sources": result.get("sources", []),
        })
        # Maintain recent dialogue turns in session
        session["rag_history"] = chat_history[-10:]
        session.modified = True
    except Exception as e:
        return jsonify({"error": f"RAG query failed: {str(e)}"}), 500

    return jsonify({
        "question": query,
        "answer": result.get("answer", ""),
        "sources": result.get("sources", []),
        "history": session["rag_history"],
    })


@app.route("/rag-clear-history", methods=["POST"])
def rag_clear_history():
    session.pop("rag_history", None)
    return jsonify({"success": True, "message": "Conversation history cleared"})


# ── Frontend (React SPA) ───────────────────────────────────────────────────

@app.route("/assets/<path:path>")
def serve_react_assets(path):
    assets_dir = os.path.join(FRONTEND_DIST, "assets")
    if os.path.exists(assets_dir):
        return send_from_directory(assets_dir, path)
    return ("Asset not found", 404)


@app.route("/", defaults={"path": ""})
@app.route("/<path:path>")
def serve_react(path):
    # Static files directly under frontend/dist (e.g. favicon.svg, icons.svg)
    file_path = os.path.join(FRONTEND_DIST, path)
    if path != "" and os.path.exists(file_path) and os.path.isfile(file_path):
        return send_from_directory(FRONTEND_DIST, path)

    # React index.html
    index_file = os.path.join(FRONTEND_DIST, "index.html")
    if os.path.exists(index_file):
        return send_from_directory(FRONTEND_DIST, "index.html")

    return jsonify({
        "status": "Flask API running",
        "message": "React frontend build not found in frontend/dist. Run 'npm run build' inside frontend/"
    }), 404


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
