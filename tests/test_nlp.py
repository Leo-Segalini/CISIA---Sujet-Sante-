from src.nlp.guardrails import hallucination_rate, identity_leak
from src.nlp.masking import mask_text


def test_mask_replaces_name():
    assert "[PATIENT]" in mask_text("Suivi de Martin Monique à domicile.", ["Martin Monique"])
    assert "Martin Monique" not in mask_text("Suivi de Martin Monique à domicile.", ["Martin Monique"])


def test_identity_leak_and_grounding():
    names = ["Dupont Alice"]
    assert identity_leak("Mme Dupont Alice va bien", names)
    assert not identity_leak("Le patient va bien", names)
    # "créatinine" n'est pas dans la source → hallucination
    rate = hallucination_rate("sortie domicile surveillance", "créatinine élevée sortie domicile")
    assert rate > 0
    rate_ok = hallucination_rate("sortie domicile surveillance rapprochée", "surveillance rapprochée à domicile")
    assert rate_ok == 0
