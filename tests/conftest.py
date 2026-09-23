import os

# Pas de LLM pendant les tests (évite chargement lent / Metal).
os.environ["CISIA_LLM"] = "0"
# Auth désactivée en tests (sessions non requises).
os.environ["CISIA_AUTH"] = "0"
