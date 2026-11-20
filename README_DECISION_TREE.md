# ReFound — Decision Tree integration

This is the full existing ReFound project, with Decision Tree added to `/api/matches` and the Smart Matches page. All existing pages, authentication, claims, chat, notifications, dashboard, and original logo are retained.

## How it works

1. Existing NLP / keyword matching produces text similarity and weighted similarity score.
2. Five numerical features are created for each Lost–Found pair: text, category, color, location, and date proximity.
3. A trained `DecisionTreeClassifier(criterion="entropy")` makes a **secondary advisory classification** (`potential_match` or `unlikely_match`). The existing score and sorting remain unchanged. A request for an item still requires a human proof-of-ownership process.
4. Both AR and EN Smart Matches views show the advisory decision and disclose that the training examples are illustrative.

**Accuracy disclosure:** the included labeled training dataset is synthetic instructional data, not collected or verified university claims. `decision_tree_metrics.json` reports held-out synthetic accuracy/precision/recall/F1 only. These numbers must **never** be described as real-world prediction accuracy. The decision tree model does not auto-approve ownership or replace NLP.

This implementation uses scikit-learn CART decision tree with entropy criterion; although entropy is also used by ID3, it is **not a literal ID3 implementation**.

## Run (PowerShell)

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m unittest -v test_matching.py test_decision_tree.py test_security.py
.\.venv\Scripts\python.exe app.py
```

Optional semantic NLP can still be enabled:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-nlp.txt
$env:REFOUND_ENABLE_SEMANTIC="1"
.\.venv\Scripts\python.exe app.py
```

To retrain / regenerate the tree and measurements:

```powershell
.\.venv\Scripts\python.exe train_decision_tree.py
```

Outputs: `models/decision_tree.joblib`, `decision_tree_training_pairs.csv`, `decision_tree_metrics.json`, `decision_tree_visualization.png`, `decision_tree_rules.txt`.

## Keep your existing users and messages

Stop the old Flask server. Back up the old `instance` directory and copy it from the previous working version to this project (same relative path). Do not delete or overwrite your current SQLite database. Keep the images in `instance/uploads` as well.

## Next steps for real-world quality

Collect opt-in, manually verified positive and negative report pairs (without personal details), split by item/person/time to prevent leakage, compare against NLP-only baseline, and re-train. Calibrate decision thresholds only after adequate real validation data.
