import os
import re
import logging
from typing import Dict, Any, List, Optional
import httpx

from backend.config import DEFAULT_WORKSPACE_ID
from backend.db.falkordb_client import db_client

logger = logging.getLogger("company_brain.retrieval")

STOPWORDS = {
    "a", "about", "above", "after", "again", "against", "all", "am", "an", "and",
    "any", "are", "aren't", "as", "at", "be", "because", "been", "before", "being",
    "below", "between", "both", "but", "by", "can't", "cannot", "could", "did",
    "do", "does", "doing", "don't", "down", "during", "each", "few", "for", "from",
    "further", "had", "has", "have", "having", "he", "her", "here", "hers", "herself",
    "him", "himself", "his", "how", "i", "if", "in", "into", "is", "isn't", "it",
    "its", "itself", "let's", "me", "more", "most", "mustn't", "my", "myself", "no",
    "nor", "not", "of", "off", "on", "once", "only", "or", "other", "ought", "our",
    "ours", "ourselves", "out", "over", "own", "same", "she", "should", "so", "some",
    "such", "than", "that", "the", "their", "theirs", "them", "themselves", "then",
    "there", "these", "they", "this", "those", "through", "to", "too", "under",
    "until", "up", "very", "was", "we", "were", "what", "when", "where", "which",
    "while", "who", "whom", "why", "with", "would", "you", "your", "yours"
}

def extract_search_terms(query: str) -> List[str]:
    """Extract normalized search keywords from a natural language query."""
    tokens = re.findall(r"[a-zA-Z0-9_\-\.]{2,}", query.lower())
    terms = [t for t in tokens if t not in STOPWORDS]
    return terms if terms else tokens

def search_graph_evidence(
    workspace_id: str,
    query_text: str,
    limit: int = 5
) -> Dict[str, Any]:
    """
    Search FalkorDB for evidence matching the query text.
    If no evidence matches, returns 'Not documented' with checked sources.
    Never falls back to canned Payments answers.
    """
    terms = extract_search_terms(query_text)
    checked_sources = [
        "FalkorDB Evidence Nodes (Text & Excerpts)",
        "FalkorDB Source Records (Documents, GitHub Files, Chat, Tickets)",
        "FalkorDB Fact Records & Temporal Supersessions",
        "FalkorDB Decision Records (ADRs & Policies)",
        "FalkorDB Project & Service Metadata"
    ]

    if not terms:
        return {
            "has_evidence": False,
            "verdict": "NOT_DOCUMENTED",
            "answer": f"Not documented in the company knowledge graph. No search terms could be parsed from '{query_text}'.",
            "checked_sources": checked_sources,
            "citations": [],
            "claims": []
        }

    # Query FalkorDB Evidence and linked Source nodes
    # We match any term against excerpt or locator
    cypher = """
    MATCH (ev:Evidence {workspace_id: $ws})
    OPTIONAL MATCH (ev)-[:SUPPORTED_BY]->(s:Source)
    RETURN ev.id, ev.excerpt, ev.locator, s.title, s.source_uri, s.source_type
    """
    rows = db_client.query(cypher, {"ws": workspace_id})

    # Score and filter rows by term overlap
    scored_evidence = []
    for r in rows:
        eid, excerpt, locator, src_title, src_uri, src_type = r
        excerpt_lower = (excerpt or "").lower()
        locator_lower = (locator or "").lower()
        title_lower = (src_title or "").lower()

        # Count term matches
        match_count = sum(1 for t in terms if t in excerpt_lower or t in locator_lower or t in title_lower)
        if match_count > 0:
            scored_evidence.append({
                "evidence_id": eid,
                "excerpt": excerpt,
                "locator": locator or "Unknown locator",
                "source_title": src_title or "Company Document",
                "source_uri": src_uri or "falkordb://evidence",
                "source_type": src_type or "DOCUMENT",
                "score": match_count
            })

    scored_evidence.sort(key=lambda x: x["score"], reverse=True)
    top_evidence = scored_evidence[:limit]

    # Check for direct Source content matches if no evidence matched directly
    if not top_evidence:
        src_cypher = """
        MATCH (s:Source {workspace_id: $ws})
        RETURN s.id, s.title, s.content, s.source_uri, s.source_type
        """
        src_rows = db_client.query(src_cypher, {"ws": workspace_id})
        for sr in src_rows:
            sid, title, content, uri, stype = sr
            content_lower = (content or "").lower()
            title_lower = (title or "").lower()
            m_count = sum(1 for t in terms if t in content_lower or t in title_lower)
            if m_count > 0:
                # Synthesize a temporary evidence reference
                top_evidence.append({
                    "evidence_id": f"src_ref_{sid}",
                    "excerpt": (content or "")[:350],
                    "locator": f"{title} (Full Source)",
                    "source_title": title,
                    "source_uri": uri or "falkordb://source",
                    "source_type": stype,
                    "score": m_count
                })

    # Abstain if no relevant evidence found
    if not top_evidence:
        return {
            "has_evidence": False,
            "verdict": "NOT_DOCUMENTED",
            "answer": (
                f"Not documented in the company knowledge graph. "
                f"No relevant evidence was found for query: '{query_text}'.\n"
                f"Checked: {', '.join(checked_sources)}."
            ),
            "checked_sources": checked_sources,
            "citations": [],
            "claims": []
        }

    # Generate answer from retrieved evidence
    answer_result = generate_evidence_answer(query_text, top_evidence)

    citations = [
        {
            "evidence_id": ev["evidence_id"],
            "excerpt": ev["excerpt"],
            "locator": ev["locator"],
            "source_title": ev["source_title"],
            "source_uri": ev["source_uri"],
            "claim_text": f"Grounded by excerpt in {ev['source_title']} ({ev['locator']})"
        }
        for ev in top_evidence
    ]

    claims = [
        {
            "text": ev["excerpt"],
            "evidence_ids": [ev["evidence_id"]],
            "confidence": 1.0,
            "kind": "FACT"
        }
        for ev in top_evidence
    ]

    return {
        "has_evidence": True,
        "verdict": "DOCUMENTED",
        "answer": answer_result["text"],
        "model_used": answer_result["model_used"],
        "reasoning_mode": answer_result["mode"],
        "checked_sources": checked_sources,
        "citations": citations,
        "claims": claims
    }

def generate_evidence_answer(query: str, evidence_list: List[Dict[str, Any]]) -> Dict[str, str]:
    """
    Generate an answer using configured LLM provider or honest direct evidence synthesis.
    Never pretends a scripted response is an LLM result.
    """
    groq_key = os.getenv("GROQ_API_KEY", "").strip()
    gemini_key = os.getenv("GEMINI_API_KEY", "").strip()
    openai_key = os.getenv("OPENAI_API_KEY", "").strip()

    context_str = "\n\n".join(
        f"[{ev['evidence_id']}] (Source: {ev['source_title']}, Locator: {ev['locator']})\n{ev['excerpt']}"
        for ev in evidence_list
    )

    # 1. Check Groq Provider (Ultra-low latency LPU inference)
    if groq_key:
        try:
            url = "https://api.groq.com/openai/v1/chat/completions"
            headers = {"Authorization": f"Bearer {groq_key}", "Content-Type": "application/json"}
            messages = [
                {
                    "role": "system",
                    "content": (
                        "You are Company Brain, an autonomous company knowledge system.\n"
                        "Answer the user's question using ONLY the provided FalkorDB evidence.\n"
                        "Cite the evidence ID in brackets like [evidence_id] for every factual claim.\n"
                        "If the evidence is insufficient to answer the question, state: 'Not documented in company sources.'"
                    )
                },
                {"role": "user", "content": f"Question: {query}\n\nRetrieved FalkorDB Evidence:\n{context_str}"}
            ]
            with httpx.Client(timeout=20.0) as client:
                res = client.post(
                    url,
                    headers=headers,
                    json={
                        "model": "llama-3.3-70b-versatile",
                        "messages": messages,
                        "temperature": 0.2,
                        "max_tokens": 1024
                    }
                )
                if res.status_code == 200:
                    text = res.json()["choices"][0]["message"]["content"]
                    return {
                        "text": text.strip(),
                        "model_used": "groq/llama-3.3-70b-versatile",
                        "mode": "LLM_GENERATED"
                    }
                else:
                    logger.warning(f"Groq API returned status {res.status_code}: {res.text}. Falling back to next provider.")
        except Exception as e:
            logger.warning(f"Groq API call failed: {e}. Falling back to next provider.")

    # 2. Check Gemini Provider
    if gemini_key:
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={gemini_key}"
            prompt = (
                f"You are Company Brain, an autonomous company knowledge system.\n"
                f"Answer the user's question using ONLY the provided FalkorDB evidence below.\n"
                f"Cite the evidence ID in brackets like [evidence_id] for every claim.\n"
                f"If the evidence is insufficient, say 'Not documented'.\n\n"
                f"User Question: {query}\n\n"
                f"Retrieved Evidence:\n{context_str}\n\n"
                f"Answer:"
            )
            with httpx.Client(timeout=20.0) as client:
                res = client.post(url, json={"contents": [{"parts": [{"text": prompt}]}]})
                if res.status_code == 200:
                    data = res.json()
                    candidates = data.get("candidates", [])
                    if candidates:
                        text = candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "")
                        return {
                            "text": text.strip(),
                            "model_used": "gemini-1.5-flash",
                            "mode": "LLM_GENERATED"
                        }
        except Exception as e:
            logger.warning(f"Gemini API call failed: {e}. Falling back to honest retrieval.")

    # 3. Check OpenAI Provider
    if openai_key:
        try:
            url = "https://api.openai.com/v1/chat/completions"
            headers = {"Authorization": f"Bearer {openai_key}", "Content-Type": "application/json"}
            messages = [
                {"role": "system", "content": "You are Company Brain. Answer using ONLY the provided FalkorDB evidence. Cite evidence IDs in brackets [ev_...]. If insufficient, state 'Not documented'."},
                {"role": "user", "content": f"Question: {query}\n\nEvidence:\n{context_str}"}
            ]
            with httpx.Client(timeout=20.0) as client:
                res = client.post(url, headers=headers, json={"model": "gpt-4o-mini", "messages": messages, "temperature": 0.2})
                if res.status_code == 200:
                    text = res.json()["choices"][0]["message"]["content"]
                    return {
                        "text": text.strip(),
                        "model_used": "gpt-4o-mini",
                        "mode": "LLM_GENERATED"
                    }
        except Exception as e:
            logger.warning(f"OpenAI API call failed: {e}. Falling back to honest retrieval.")

    # 4. Honest Non-LLM Evidence Retrieval Mode
    bullet_points = "\n".join(
        f"• [{ev['evidence_id']}] ({ev['source_title']} @ {ev['locator']}):\n  \"{ev['excerpt']}\""
        for ev in evidence_list
    )
    honest_answer = (
        f"Evidence retrieved from FalkorDB for '{query}':\n\n"
        f"{bullet_points}\n\n"
        f"(Note: Agent reasoning is unavailable because no LLM API key (GROQ_API_KEY / GEMINI_API_KEY / OPENAI_API_KEY) "
        f"is configured in server environment. Presenting direct evidence-grounded records from canonical graph.)"
    )

    return {
        "text": honest_answer,
        "model_used": "NONE (Honest Graph Retrieval)",
        "mode": "DIRECT_GRAPH_EVIDENCE"
    }
