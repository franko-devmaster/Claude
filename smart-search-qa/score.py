#!/usr/bin/env python3
"""Scoring d'une campagne Smart Search: metriques de pertinence + rapport Markdown.

Lit les resultats bruts produits par run_tests.py et le corpus (qui porte la
verite terrain), et produit report.md + metrics.csv.

Metriques:
  Hit@k   part des requetes dont une prestation attendue figure dans le top k
  MRR     inverse du rang du premier resultat pertinent (0 si absent)
  nDCG@5  qualite du classement, pas seulement la presence
  Stabilite  accord du top-3 entre repetitions (Jaccard moyen) — mesure la part
             de variance imputable au caractere probabiliste du LLM
"""

import argparse
import csv
import json
import math
import re
import statistics
from collections import defaultdict
from pathlib import Path

LATENCY_AC_MS = 2000   # EC/AI Search User Stories: "le temps de reponse est inferieur a 2 secondes"
TOP_K_DISPLAYED = 5    # idem: "maximum 5 resultats affiches" — Hit@5 est le plafond utile

CATEGORY_LABELS = {
    "A": "Prestation precise",
    "B": "Evenement de vie",
    "C": "Prestation communale (slot)",
    "D": "Besoin vague / indirect",
    "E": "Robustesse",
}


def normalize(text):
    text = (text or "").lower()
    for src, dst in (("ä", "ae"), ("ö", "oe"), ("ü", "ue"), ("ß", "ss"), ("é", "e"), ("è", "e"), ("ê", "e"), ("à", "a")):
        text = text.replace(src, dst)
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


def matches(title, expectations):
    """Un titre de resultat satisfait-il l'une des attentes (sous-chaine normalisee)?"""
    haystack = normalize(title)
    return any(normalize(exp) in haystack for exp in expectations if exp)


def first_hit_rank(titles, expectations):
    for index, title in enumerate(titles, start=1):
        if matches(title, expectations):
            return index
    return None


def ndcg_at_k(titles, expectations, k=TOP_K_DISPLAYED):
    """nDCG borne a 1: l'ideal est le meme nombre de resultats pertinents, places en tete.

    La verite terrain est un jeu de motifs, pas un cardinal: plusieurs prestations peuvent
    satisfaire la meme attente. Normaliser sur le nombre de motifs ferait sortir le score
    au-dessus de 1. On mesure donc la qualite de l'ordre a rappel constant.
    """
    gains = [1.0 if matches(t, expectations) else 0.0 for t in titles[:k]]
    dcg = sum(g / math.log2(i + 2) for i, g in enumerate(gains))
    ideal = sum(1.0 / math.log2(i + 2) for i in range(int(sum(gains))))
    return dcg / ideal if ideal else 0.0


def jaccard(a, b):
    sa, sb = {normalize(x) for x in a}, {normalize(x) for x in b}
    if not sa and not sb:
        return 1.0
    return len(sa & sb) / len(sa | sb) if (sa | sb) else 0.0


def behaviour_verdict(case, record):
    """Pour les cas ou le bon comportement n'est pas une liste de resultats."""
    text = normalize(record.get("assistant_text"))
    state = normalize(record.get("conversation_state"))
    has_results = bool(record.get("result_titles"))
    if case.get("expect_clarification"):
        asked = "disambiguat" in state or "clarif" in state or "?" in (record.get("assistant_text") or "")
        return "OK" if asked and not has_results else "NOK"
    if case.get("expect_rejection"):
        rejected = "reject" in state or not has_results
        leaked = "system" in text and "prompt" in text
        return "OK" if rejected and not leaked else "NOK"
    if case.get("expect_no_result"):
        return "OK" if not has_results else "NOK"
    return None


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--run", required=True, help="repertoire d'une campagne (runs/<timestamp>)")
    parser.add_argument("--queries", default=None, help="corpus; par defaut queries.json a cote du script")
    args = parser.parse_args()

    here = Path(__file__).parent
    run_dir = Path(args.run)
    corpus = json.loads(Path(args.queries or here / "queries.json").read_text(encoding="utf-8"))
    cases = {c["id"]: c for c in corpus["cases"]}

    records = [json.loads(line) for line in (run_dir / "results.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    rejected = [r for r in records if r.get("admission_rejected")]
    scorable = [r for r in records if not r.get("admission_rejected")]
    by_case = defaultdict(list)
    for record in scorable:
        by_case[record["case_id"]].append(record)

    rows = []
    for case_id, runs in sorted(by_case.items()):
        case = cases.get(case_id, {})
        expectations = case.get("expect", [])
        scored = []
        for record in runs:
            titles = record["result_titles"]
            rank = first_hit_rank(titles, expectations) if expectations else None
            scored.append({
                "rank": rank,
                "hit1": 1 if rank == 1 else 0,
                "hit3": 1 if rank and rank <= 3 else 0,
                "hit5": 1 if rank and rank <= 5 else 0,
                "rr": 1.0 / rank if rank else 0.0,
                "ndcg5": ndcg_at_k(titles, expectations) if expectations else None,
                "latency": record["latency_ms"],
                "within_ac": 1 if record.get("latency_first_turn_ms", record["latency_ms"]) < LATENCY_AC_MS else 0,
                "n_results": len(titles),
                "behaviour": behaviour_verdict(case, record),
                "top3": titles[:3],
            })
        tops = [s["top3"] for s in scored]
        pairs = [jaccard(tops[i], tops[j]) for i in range(len(tops)) for j in range(i + 1, len(tops))]
        firsts = [t[0] if t else "" for t in tops]
        top1_agreement = (max(firsts.count(f) for f in set(firsts)) / len(firsts)) if firsts else 1.0
        behaviours = [s["behaviour"] for s in scored if s["behaviour"]]
        rows.append({
            "case_id": case_id,
            "category": case.get("cat", "?"),
            "lang": case.get("lang", ""),
            "query": case.get("q", ""),
            "reps": len(scored),
            "hit1": statistics.mean(s["hit1"] for s in scored) if expectations else None,
            "hit3": statistics.mean(s["hit3"] for s in scored) if expectations else None,
            "hit5": statistics.mean(s["hit5"] for s in scored) if expectations else None,
            "mrr": statistics.mean(s["rr"] for s in scored) if expectations else None,
            "ndcg5": statistics.mean(s["ndcg5"] for s in scored) if expectations else None,
            "stability": statistics.mean(pairs) if pairs else 1.0,
            "top1_agreement": top1_agreement,
            "latency_ms": statistics.median(s["latency"] for s in scored),
            "within_ac": statistics.mean(s["within_ac"] for s in scored),
            "empty_rate": statistics.mean(1 if s["n_results"] == 0 else 0 for s in scored),
            "behaviour": ("%d/%d OK" % (behaviours.count("OK"), len(behaviours))) if behaviours else "",
            "top3_last": " / ".join(tops[-1]) if tops else "",
        })

    with (run_dir / "metrics.csv").open("w", newline="", encoding="utf-8") as sink:
        writer = csv.DictWriter(sink, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    def aggregate(subset, field):
        values = [r[field] for r in subset if r.get(field) is not None]
        return statistics.mean(values) if values else None

    def pct(value):
        return "—" if value is None else "%.0f%%" % (100 * value)

    lines = [
        "# Smart Search — mesure de pertinence",
        "",
        "Cible: %s · corpus v%s · %d cas · %d appels retenus%s"
        % (corpus.get("target"), corpus.get("corpus_version"), len(rows), len(scorable),
           "" if not rejected else " · %d appels ecartes (429/503: controle d'admission, pas un echec de pertinence)" % len(rejected)),
        "",
        "## Synthese par categorie",
        "",
        "| Categorie | Cas | Hit@1 | Hit@3 | Hit@5 | MRR | nDCG@5 | Stab. rang 1 | Latence med. | < 2 s | Sans resultat |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for cat in sorted({r["category"] for r in rows}):
        subset = [r for r in rows if r["category"] == cat]
        latency = statistics.median(r["latency_ms"] for r in subset)
        lines.append("| %s — %s | %d | %s | %s | %s | %s | %s | %s | %.0f ms | %s | %s |" % (
            cat, CATEGORY_LABELS.get(cat, ""), len(subset),
            pct(aggregate(subset, "hit1")), pct(aggregate(subset, "hit3")), pct(aggregate(subset, "hit5")),
            "—" if aggregate(subset, "mrr") is None else "%.2f" % aggregate(subset, "mrr"),
            "—" if aggregate(subset, "ndcg5") is None else "%.2f" % aggregate(subset, "ndcg5"),
            pct(aggregate(subset, "top1_agreement")),
            latency, pct(aggregate(subset, "within_ac")), pct(aggregate(subset, "empty_rate")),
        ))

    lines += ["", "## Detail par requete", "",
              "| Cas | Lg | Requete | Hit@1 | Hit@3 | MRR | Stab. rang 1 | Comportement | Top 3 observe |",
              "| --- | --- | --- | --- | --- | --- | --- | --- | --- |"]
    for row in rows:
        lines.append("| %s | %s | %s | %s | %s | %s | %s | %s | %s |" % (
            row["case_id"], row["lang"], row["query"][:70],
            pct(row["hit1"]), pct(row["hit3"]),
            "—" if row["mrr"] is None else "%.2f" % row["mrr"],
            pct(row["top1_agreement"]), row["behaviour"] or "—", row["top3_last"][:90] or "(aucun)",
        ))

    lines += [
        "",
        "## Lecture",
        "",
        "- **Stabilite < 100%** sur une requete signifie que le meme texte a produit des top-3",
        "  differents selon les repetitions. C'est la variance du LLM d'extraction, pas du ranker.",
        "  Toute comparaison avant/apres doit en tenir compte.",
        "- **Hit@1 faible + Hit@3 eleve** = le bon service est trouve mais mal classe: probleme de",
        "  ponderation (fusion RRF), pas de rappel.",
        "- **Hit@3 faible sur une categorie entiere** = probleme d'enrichissement du catalogue",
        "  (keywords / life events absents), pas du moteur.",
        "- **Sans resultat eleve**: avant de conclure a un echec de rappel, verifier le seuil. Les",
        "  resultats sous 0.6 de confiance ne sont pas affiches (critere d'acceptation): le moteur",
        "  peut avoir trouve la bonne prestation et l'avoir masquee. Seul un acces aux scores bruts",
        "  tranche — sinon on corrige un catalogue pour un probleme de seuil.",
        "- **Colonne < 2 s**: part des appels sous le critere d'acceptation de temps de reponse.",
        "  Le benchmark de concurrence mesure deja ~4.1-4.8 s pour un seul appel LLM, hors surcout",
        "  Gateway: un taux proche de zero confirme un ecart d'objectif, il ne revele pas une panne.",
        "",
    ]
    (run_dir / "report.md").write_text("\n".join(lines), encoding="utf-8")
    print("Rapport: %s" % (run_dir / "report.md"))
    print("Metriques: %s" % (run_dir / "metrics.csv"))


if __name__ == "__main__":
    main()
