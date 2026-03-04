# Structured Questionnaire Answering Tool

End-to-end Flask application for automating structured questionnaire responses using reference documents, with review/edit and export.

## Live App

- Live URL: `https://almabase-assignment-phi.vercel.app/`
- Deployment config included: `vercel.json` + `api/index.py`

## Repository

- Source: this repository

## Industry & Fictional Company (Required)

- **Industry:** Fintech SaaS
- **Company:** **BudgetBuddy** is a multi-tenant SaaS platform and API for personal budget tracking, expense categorization, and savings goal planning.  
  It serves SMB finance teams that need audit-friendly records and secure integrations.

## What I Built

- User authentication (signup, login, logout)
- Persistent storage using SQLite + SQLAlchemy
- Upload flow for:
  - Questionnaire files (`.txt`, `.pdf`, `.xlsx`)
  - Reference files (`.txt`, `.pdf`, `.xlsx`)
- Question parsing into individual items
- Retrieval + answer generation per question with citations
- Unsupported answers return exactly: `Not found in references.`
- Review screen to edit answers before export
- Export in the **same file format** as questionnaire input:
  - `.txt` -> `.txt`
  - `.pdf` -> `.pdf`
  - `.xlsx` -> `.xlsx`

## Core User Flow

1. Register/Login
2. Upload questionnaire
3. Upload one or more reference documents
4. Click **Generate**
5. Review generated answers, citations, and confidence
6. Edit answers if needed
7. Export downloadable output

## Grounding Behavior

- Each supported answer includes at least one citation (document filename).
- If support is missing in references, answer is:
  - `Not found in references.`
- Evidence snippet and confidence are displayed per question.

## Nice-to-Have Features Implemented

- Confidence score
- Evidence snippets
- Partial regeneration (per-question regenerate button)
- Coverage summary (total, with citations, not found)

## Mock Data Included

In `samples/`:
- `questionnaire.txt` with 12 realistic questions
- `reference1.txt` to `reference4.txt` as source-of-truth documents

## Assumptions

- For spreadsheet questionnaires, the first non-empty cell in each row is treated as the question.
- For PDF input, text extraction quality depends on PDF text layer quality.
- Retrieval uses token overlap (not embeddings/vector DB).
- Single citation (top matched reference) is attached by default.

## Trade-offs

- Chose simple deterministic retrieval to keep system clear and inspectable.
- Export preserves structure/order and format, but not full visual fidelity of complex PDF layouts.
- SQLite keeps setup easy for assignment scope; not intended for production scale.

## What I Would Improve With More Time

- Semantic retrieval (embeddings + vector store) for better grounding accuracy
- Multi-citation answers with ranking evidence
- Stronger PDF layout-preserving export
- Team collaboration support and run/version comparison UI
- Automated tests for parser/export across document edge cases

## Setup

```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

Create `.env`:

```text
OPENAI_API_KEY=your_key
SECRET_KEY=your_secret
```

Run:

```bash
python runserver.py
```

Open:

`http://127.0.0.1:5000`



