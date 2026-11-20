# ReFound — Smart Lost & Found | Decision Tree + NLP

Built on the verified ReFound project, preserving original logo, navbar, UI, claim/chat system, admin modal, bilingual interface, and existing NLP engine. No fake production accuracy numbers.

## Existing security and matching QA
- API security headers: `nosniff`, clickjacking prevention (`DENY`), strict referrer policy, no-store API replies, permission limitations.
- Uploaded image location now follows configured DATABASE parent directory (supports safe, isolated test DBs). Existing `instance/uploads` stays unchanged for standard installs.
- `test_security.py`: seven Flask test-client cases, **fresh temporary SQLite database**, covering login-required API access, admin isolation, report ownership, chat/claim permissions, third-party privacy, Origin filtering, and notifications. Tests NEVER open the user's real `instance/refound.db`.
- `evaluate_matching.py`: 8 handcrafted cross-language retrieval examples and explicit top-1 metric, not a real-world accuracy guarantee; check semantic mode separately.
- Existing `test_matching.py`: 5 matching-regression checks retained.

## Decision Tree extension

See **README_DECISION_TREE.md** for a complete guide to the trained classifier, evaluation, output files and safety limitations. The original NLP-based similarity score is preserved; the decision is an extra advisory indicator.

## Upgrade without deleting your work
1. Stop your previously running ReFound server.
2. Back up your prior project's `instance` directory, including `refound.db` and `uploads`.
3. Extract the current project and copy the backed-up `instance` directory into this folder.
4. Open this folder in VS Code, using Windows PowerShell:

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m unittest -v test_matching.py test_decision_tree.py test_security.py
.\.venv\Scripts\python.exe evaluate_matching.py
.\.venv\Scripts\python.exe app.py
```

Then open http://127.0.0.1:5000

## Optional semantic NLP

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-nlp.txt
$env:REFOUND_ENABLE_SEMANTIC='1'
.\.venv\Scripts\python.exe evaluate_matching.py
.\.venv\Scripts\python.exe app.py
```

First semantic use downloads a language model. Report semantic-vs-lexical results separately. This limited curated benchmark is not a substitute for blinded user-labeled real data.

## Deployment boundaries
For a real campus rollout you still need verified university email ownership, CSRF-token protections against browsers without Origin, login rate limiting, HTTPS + stable SECRET_KEY, and a professional security review. Keep this demo locally hosted for now.
