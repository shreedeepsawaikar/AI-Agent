import os
import shutil
import pandas as pd
from datetime import datetime
from pypdf import PdfReader
import chromadb
from chromadb.utils import embedding_functions
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.prompts import ChatPromptTemplate
from llm import get_llm

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
CONTEXT_DIR = os.path.join(PROJECT_ROOT, "context")
CHROMA_DIR = os.path.join(PROJECT_ROOT, ".chroma_db")

# Ensure context directory exists
os.makedirs(CONTEXT_DIR, exist_ok=True)
os.makedirs(CHROMA_DIR, exist_ok=True)

COLLECTION_NAME = "policy_context"
text_splitter = RecursiveCharacterTextSplitter(chunk_size=700, chunk_overlap=120)


def _get_collection():
    client = chromadb.PersistentClient(path=CHROMA_DIR)
    # Uses default ONNX MiniLM-L6-v2 embeddings (cached locally)
    return client.get_or_create_collection(
        name=COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"}
    )


def list_context_files() -> list[dict]:
    """Return metadata about all files currently in the /context directory."""
    files_info = []
    if not os.path.exists(CONTEXT_DIR):
        return files_info

    for fname in os.listdir(CONTEXT_DIR):
        fpath = os.path.join(CONTEXT_DIR, fname)
        if os.path.isfile(fpath):
            stat = os.stat(fpath)
            size_kb = round(stat.st_size / 1024, 1)
            mtime = datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M")
            ext = os.path.splitext(fname)[1].lower().lstrip(".")
            files_info.append({
                "filename": fname,
                "size_kb": size_kb,
                "modified": mtime,
                "ext": ext,
            })
    return sorted(files_info, key=lambda x: x["filename"].lower())


def _extract_pdf_pages(filepath: str) -> list[tuple[int, str]]:
    """Robustly extract (page_num, text) from PDF using pypdfium2 with pypdf fallback."""
    pages = []
    # Primary: pypdfium2 (handles complex/print fonts without LimitReachedError)
    try:
        import pypdfium2 as pdfium
        pdf = pdfium.PdfDocument(filepath)
        for i in range(len(pdf)):
            page = pdf[i]
            textpage = page.get_textpage()
            text = (textpage.get_text_range() or "").strip()
            if text:
                pages.append((i + 1, text))
        if pages:
            return pages
    except Exception:
        pass

    # Fallback: pypdf
    try:
        reader = PdfReader(filepath, strict=False)
        for page_num, page in enumerate(reader.pages, start=1):
            try:
                text = (page.extract_text() or "").strip()
                if text:
                    pages.append((page_num, text))
            except Exception:
                continue
    except Exception:
        pass

    return pages


def extract_chunks_from_file(filepath: str, filename: str) -> list[dict]:
    """Parse PDF, Excel, CSV, or Text and split into chunks with metadata."""
    ext = os.path.splitext(filename)[1].lower()
    chunks = []

    # 1. PDF
    if ext == ".pdf":
        pages = _extract_pdf_pages(filepath)
        for page_num, text in pages:
            page_chunks = text_splitter.split_text(text)
            for chunk_idx, c in enumerate(page_chunks):
                enriched_text = f"[{filename} | Page {page_num}]\n{c}"
                chunks.append({
                    "id": f"{filename}_p{page_num}_{chunk_idx}",
                    "text": enriched_text,
                    "metadata": {
                        "source": filename,
                        "type": "pdf",
                        "page": page_num,
                        "is_first": 1 if (page_num == 1 and chunk_idx == 0) else 0,
                    }
                })

    # 2. Excel (.xlsx, .xls)
    elif ext in [".xlsx", ".xls"]:
        excel_data = pd.read_excel(filepath, sheet_name=None)
        sheet_idx = 0
        for sheet_name, df in excel_data.items():
            if df.empty:
                continue
            df = df.dropna(how="all")
            rows_text = []
            for idx, row in df.iterrows():
                row_items = [f"{col}: {val}" for col, val in row.items() if pd.notna(val)]
                if row_items:
                    rows_text.append(f"Row {idx+1}: " + " | ".join(row_items))

            sheet_content = f"Sheet: {sheet_name}\n" + "\n".join(rows_text)
            sheet_chunks = text_splitter.split_text(sheet_content)
            for chunk_idx, c in enumerate(sheet_chunks):
                enriched_text = f"[{filename} | Sheet: {sheet_name}]\n{c}"
                chunks.append({
                    "id": f"{filename}_{sheet_name}_{chunk_idx}",
                    "text": enriched_text,
                    "metadata": {
                        "source": filename,
                        "type": "excel",
                        "sheet": str(sheet_name),
                        "is_first": 1 if (sheet_idx == 0 and chunk_idx == 0) else 0,
                    }
                })
            sheet_idx += 1

    # 3. CSV
    elif ext == ".csv":
        df = pd.read_csv(filepath)
        df = df.dropna(how="all")
        rows_text = []
        for idx, row in df.iterrows():
            row_items = [f"{col}: {val}" for col, val in row.items() if pd.notna(val)]
            if row_items:
                rows_text.append(f"Row {idx+1}: " + " | ".join(row_items))

        csv_content = "\n".join(rows_text)
        csv_chunks = text_splitter.split_text(csv_content)
        for chunk_idx, c in enumerate(csv_chunks):
            enriched_text = f"[{filename} | CSV Table]\n{c}"
            chunks.append({
                "id": f"{filename}_{chunk_idx}",
                "text": enriched_text,
                "metadata": {
                    "source": filename,
                    "type": "csv",
                    "is_first": 1 if chunk_idx == 0 else 0,
                }
            })

    # 4. Text / Markdown
    elif ext in [".txt", ".md"]:
        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read().strip()
        if content:
            txt_chunks = text_splitter.split_text(content)
            for chunk_idx, c in enumerate(txt_chunks):
                enriched_text = f"[{filename} | Document]\n{c}"
                chunks.append({
                    "id": f"{filename}_{chunk_idx}",
                    "text": enriched_text,
                    "metadata": {
                        "source": filename,
                        "type": "text",
                        "is_first": 1 if chunk_idx == 0 else 0,
                    }
                })

    return chunks


def index_single_file(filename: str) -> int:
    """Index or re-index a single file from the /context directory."""
    filepath = os.path.join(CONTEXT_DIR, filename)
    if not os.path.exists(filepath):
        return 0

    chunks = extract_chunks_from_file(filepath, filename)
    if not chunks:
        return 0

    col = _get_collection()

    # Remove any existing chunks for this file first
    try:
        col.delete(where={"source": filename})
    except Exception:
        pass

    # Batch add chunks
    col.add(
        ids=[c["id"] for c in chunks],
        documents=[c["text"] for c in chunks],
        metadatas=[c["metadata"] for c in chunks],
    )
    return len(chunks)


def save_and_index_file(file_storage) -> tuple[bool, str, int]:
    """Save an uploaded file to /context and index it into ChromaDB."""
    filename = file_storage.filename
    if not filename:
        return False, "No file selected", 0

    # Ensure secure filename without directory traversal
    base_name = os.path.basename(filename)
    dest_path = os.path.join(CONTEXT_DIR, base_name)
    file_storage.save(dest_path)

    # Index into vector store
    chunk_count = index_single_file(base_name)
    return True, base_name, chunk_count


def delete_file(filename: str) -> bool:
    """Delete file from /context and remove its chunks from ChromaDB."""
    filepath = os.path.join(CONTEXT_DIR, filename)
    if os.path.exists(filepath):
        os.remove(filepath)

    try:
        col = _get_collection()
        col.delete(where={"source": filename})
    except Exception:
        pass

    return True


def reindex_all() -> int:
    """Wipe and rebuild the vector database from all files in /context."""
    client = chromadb.PersistentClient(path=CHROMA_DIR)
    try:
        client.delete_collection(COLLECTION_NAME)
    except Exception:
        pass

    total_chunks = 0
    if os.path.exists(CONTEXT_DIR):
        for fname in os.listdir(CONTEXT_DIR):
            fpath = os.path.join(CONTEXT_DIR, fname)
            if os.path.isfile(fpath):
                total_chunks += index_single_file(fname)

    return total_chunks


def _expand_query_dynamically(question: str, chat_history: list = None) -> list[str]:
    """Dynamically generate alternative search phrases using LLM, resolving conversational references if history exists."""
    queries = [question]
    try:
        llm = get_llm(temperature=0.2)
        if chat_history:
            history_lines = []
            for item in chat_history[-4:]:
                role = "User" if item.get("role") == "user" else "Assistant"
                text = item.get("content", "")
                if len(text) > 250:
                    text = text[:250] + "..."
                history_lines.append(f"{role}: {text}")
            history_str = "\n".join(history_lines)

            prompt = (
                "You are an expert search retrieval query optimizer for a document Q&A assistant.\n"
                "Given the recent conversation history and the user's latest follow-up question, "
                "generate 2-3 targeted, self-contained search phrases, table headings, or section titles where the answer would appear.\n"
                "Resolve any pronouns (e.g. 'he', 'she', 'they', 'it', 'this policy', 'their', 'the second one') to the actual entity or document from the conversation.\n"
                "Return ONLY the search phrases, one per line. No numbers, no bullets, no conversational text.\n\n"
                f"Conversation History:\n{history_str}\n\n"
                f"Follow-up Question: {question}"
            )
        else:
            prompt = (
                "You are a search retrieval query optimizer. Given a user question about uploaded documents, "
                "generate 2 alternative, highly specific search phrases, table headings, or section titles where the exact answer would appear.\n"
                "Return ONLY the search phrases, one per line. No numbers, no bullets, no conversational text.\n\n"
                f"Question: {question}"
            )

        resp = llm.invoke(prompt)
        lines = [line.strip().lstrip("-*0123456789. ") for line in resp.content.strip().split("\n") if line.strip()]
        queries.extend(lines[:3])
    except Exception:
        pass
    return list(dict.fromkeys(queries))


def query_context(question: str, top_k: int = 12, chat_history: list = None) -> dict:
    """Generalized multi-document RAG using dynamic query expansion, balanced RRF, and conversational session history."""
    col = _get_collection()
    count = col.count()

    if count == 0:
        return {
            "question": question,
            "answer": "No documents found in `/context`. Please upload your files (PDF, Excel, CSV, TXT) first.",
            "sources": [],
        }

    # 1. Discover all distinct document sources
    all_data = col.get(include=["metadatas", "documents"])
    all_metas = all_data.get("metadatas", [])
    all_docs = all_data.get("documents", [])
    unique_sources = list({m["source"] for m in all_metas if m and "source" in m})

    # 2. Dynamic query expansion (LLM-driven, resolving conversation context)
    queries = _expand_query_dynamically(question, chat_history=chat_history)

    # 3. Balanced multi-document retrieval with Reciprocal Rank Fusion (RRF)
    context_sections = []
    sources = []

    if unique_sources:
        for src in unique_sources:
            doc_chunks = {}
            for q_text in queries:
                try:
                    res = col.query(
                        query_texts=[q_text],
                        n_results=min(6, count),
                        where={"source": src},
                        include=["documents", "metadatas", "distances"],
                    )
                    docs = res.get("documents", [[]])[0]
                    metas = res.get("metadatas", [[]])[0]
                    for rank, (doc, meta) in enumerate(zip(docs, metas)):
                        cid = f"{meta.get('page', 0)}_{meta.get('sheet', '')}_{doc[:40]}"
                        rrf = 1.0 / (60.0 + rank)
                        if cid not in doc_chunks:
                            doc_chunks[cid] = {"text": doc, "meta": meta, "score": rrf}
                        else:
                            doc_chunks[cid]["score"] += rrf
                except Exception:
                    pass

            # Universal Overview Anchor: Include Page 1 / Title / Overview chunk for this document
            for doc, meta in zip(all_docs, all_metas):
                if meta.get("source") == src and (meta.get("is_first") == 1 or meta.get("page") == 1):
                    cid = f"first_{meta.get('page', 0)}_{doc[:40]}"
                    if cid not in doc_chunks:
                        doc_chunks[cid] = {"text": doc, "meta": meta, "score": 0.15}
                    else:
                        doc_chunks[cid]["score"] += 0.15

            top_doc_chunks = sorted(doc_chunks.values(), key=lambda x: x["score"], reverse=True)[:6]

            doc_text_block = f"=== DOCUMENT: {src} ===\n"
            for c in top_doc_chunks:
                loc = f"Page {c['meta']['page']}" if "page" in c["meta"] else c["meta"].get("sheet", "Doc")
                doc_text_block += f"[{loc}]:\n{c['text']}\n\n"
                sources.append({
                    "source": src,
                    "location": loc,
                    "snippet": c["text"][:280] + ("..." if len(c["text"]) > 280 else ""),
                })
            context_sections.append(doc_text_block)

        full_context = "\n\n--------------------\n\n".join(context_sections)
    else:
        # Fallback for single collection
        res = col.query(query_texts=[question], n_results=min(top_k, count), include=["documents", "metadatas"])
        docs = res.get("documents", [[]])[0]
        metas = res.get("metadatas", [[]])[0]
        full_context = "\n\n---\n\n".join([f"[{m.get('source')}]:\n{d}" for d, m in zip(docs, metas)])
        for d, m in zip(docs, metas):
            sources.append({"source": m.get("source"), "location": "Doc", "snippet": d[:280]})

    # 4. Invoke LLM with universal multi-document synthesis prompt (aware of chat history)
    llm = get_llm(temperature=0.1)

    history_str = ""
    if chat_history:
        recent_turns = []
        for item in chat_history[-6:]:
            role = "User" if item.get("role") == "user" else "Assistant"
            recent_turns.append(f"{role}: {item.get('content', '')}")
        history_str = "\n".join(recent_turns)

    if history_str:
        eval_prompt = ChatPromptTemplate.from_template(
            """You are an intelligent document analysis assistant engaging in an ongoing conversation with the user.
Analyze the provided document excerpts and answer the user question thoroughly, accurately, and clearly, maintaining continuity with the ongoing conversation.

Conversation History (Context so far):
{chat_history}

Document Excerpts:
{context}

User Follow-up Question: {question}

Guidelines:
1. Conversational Continuity: Maintain continuity with the prior conversation (e.g. resolve references to people, terms, or policies previously discussed).
2. Multi-Document Coverage: If the question applies across multiple documents, clearly break down your answer document by document.
3. Structure: Present information with clear headings, bullet points, or comparison tables when applicable.
4. Precision: Cite specific document names, page numbers, sheets, or sections where each fact is found.
5. Truthfulness: If a specific detail is genuinely not mentioned in any of the excerpts, state that clearly without guessing.

Answer:"""
        )
        eval_resp = (eval_prompt | llm).invoke({
            "context": full_context,
            "question": question,
            "chat_history": history_str,
        })
    else:
        eval_prompt = ChatPromptTemplate.from_template(
            """You are an intelligent document analysis assistant.
Analyze the provided document excerpts and answer the user question thoroughly, accurately, and clearly.

Guidelines:
1. Multi-Document Coverage: If the context contains multiple files or documents, clearly break down your answer document by document.
2. Structure: Present information with clear headings, bullet points, or comparison tables when applicable.
3. Precision: Cite specific document names, page numbers, sheets, or sections where each fact is found.
4. Truthfulness: If a specific detail is genuinely not mentioned in any of the excerpts, state that clearly without guessing.

Context Excerpts:
{context}

User Question: {question}

Answer:"""
        )
        eval_resp = (eval_prompt | llm).invoke({"context": full_context, "question": question})

    return {
        "question": question,
        "answer": eval_resp.content.strip(),
        "sources": sources,
    }
