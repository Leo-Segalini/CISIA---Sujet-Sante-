"""Client FHIR R4 (stub) — ingestion sandbox vers format tabulaire interne."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any
from urllib.error import URLError
from urllib.request import Request, urlopen

import pandas as pd


@dataclass(frozen=True)
class FhirConfig:
    base_url: str = "https://hapi.fhir.org/baseR4"
    timeout_s: float = 30.0


def _get_json(url: str, *, timeout: float) -> dict[str, Any]:
    req = Request(url, headers={"Accept": "application/fhir+json"})
    with urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def fetch_patient_bundle(config: FhirConfig, patient_id: str) -> dict[str, Any]:
    """Récupère Patient + Encounters depuis un serveur FHIR public (sandbox)."""
    patient_url = f"{config.base_url.rstrip('/')}/Patient/{patient_id}"
    enc_url = (
        f"{config.base_url.rstrip('/')}/Encounter?patient={patient_id}&_count=50"
    )
    try:
        patient = _get_json(patient_url, timeout=config.timeout_s)
        encounters = _get_json(enc_url, timeout=config.timeout_s)
    except URLError as exc:
        raise ConnectionError(f"FHIR inaccessible : {exc}") from exc
    return {"patient": patient, "encounters": encounters}


def bundle_to_sejours_rows(bundle: dict[str, Any]) -> pd.DataFrame:
    """Transforme un bundle FHIR minimal en lignes compatibles pipeline (démo)."""
    patient = bundle.get("patient", {})
    pid = patient.get("id", "FHIR-UNKNOWN")
    entries = bundle.get("encounters", {}).get("entry", [])
    rows: list[dict[str, Any]] = []
    for i, entry in enumerate(entries):
        enc = entry.get("resource", {})
        period = enc.get("period", {})
        rows.append(
            {
                "SejourID": f"FHIR-{pid}-{i+1:03d}",
                "PatientID": f"PAT-{pid}",
                "DateAdmission": (period.get("start") or "")[:10],
                "DateSortie": (period.get("end") or period.get("start") or "")[:10],
                "DureeSejour": 1,
                "Service": enc.get("type", [{}])[0]
                .get("coding", [{}])[0]
                .get("display", "Inconnu"),
                "TypeSejour": "Hospitalisation",
                "GHM": "GHM00",
                "ModeSortie": "Domicile",
                "Readmission30j": 0,
            }
        )
    return pd.DataFrame(rows)


def ingest_fhir_patient(
    patient_id: str,
    *,
    config: FhirConfig | None = None,
) -> pd.DataFrame:
    cfg = config or FhirConfig()
    bundle = fetch_patient_bundle(cfg, patient_id)
    return bundle_to_sejours_rows(bundle)
