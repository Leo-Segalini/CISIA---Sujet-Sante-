"""Tests contenu pédagogique choix RF / HistGB."""

from src.model.choix_algorithmes import contenu_choix_modeles


def test_contenu_choix_modeles_complet():
    c = contenu_choix_modeles()
    assert c["decision_actuelle"]["modele"] == "random_forest"
    assert c["rf"]["avantages"] and c["rf"]["inconvenients"]
    assert c["histgb_detail"]["avantages"] and c["histgb_detail"]["inconvenients"]
    assert c["protocole_split"]["ratios_cibles"] == {
        "train": 0.70,
        "val": 0.15,
        "test": 0.15,
    }
    assert "100 %" in c["protocole_split"]["resume"]
    assert any(r["unite"] == "mmHg" for r in c["unites_constantes"]["table"])
    assert c["liens"]["page_web"] == "/cisia/modeles"
