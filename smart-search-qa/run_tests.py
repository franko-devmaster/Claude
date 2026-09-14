#!/usr/bin/env python3
"""Campagne de mesure de la pertinence Smart Search (eGovHub / BL-Konto).

Rejoue un corpus de requetes contre l'endpoint Smart Search d'un portail et
archive les reponses brutes. Aucune dependance externe: stdlib uniquement.

Le debit est volontairement bas (1 requete toutes les 8s par defaut): l'API
Smart Search est adossee a une inference GPU mutualisee, et l'environnement INT
partage la file de priorite avec la PROD.
"""

import argparse
import json
import random
import re
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_INTERVAL_S = 8.0
DEFAULT_JITTER_S = 2.0
DEFAULT_TIMEOUT_S = 90
MAX_CONSECUTIVE_FAILURES = 3


def extract(payload, path):
    """Extrait une valeur via un chemin pointe. `[]` deplie une liste.

    Exemples: "answer.text", "results[].title", "data.services[].id"
    Retourne toujours une liste quand le chemin contient `[]`, sinon la valeur.
    """
    if not path:
        return None
    current = [payload]
    exploded = False
    for segment in path.split("."):
        key, is_list = (segment[:-2], True) if segment.endswith("[]") else (segment, False)
        nxt = []
        for node in current:
            if not isinstance(node, dict):
                continue
            value = node.get(key)
            if value is None:
                continue
            if is_list:
                nxt.extend(value if isinstance(value, list) else [value])
            else:
                nxt.append(value)
        current = nxt
        exploded = exploded or is_list
        if not current:
            break
    if exploded:
        return current
    return current[0] if current else None


def render(template, variables):
    """Substitue {{cle}} dans un gabarit, en echappant pour insertion JSON."""
    out = template
    for key, value in variables.items():
        encoded = json.dumps(str(value))[1:-1]
        out = out.replace("{{%s}}" % key, encoded)
    return out


class SmartSearchClient:
    def __init__(self, config, interval_s, jitter_s, verbose=False):
        self.cfg = config
        self.interval_s = interval_s
        self.jitter_s = jitter_s
        self.verbose = verbose
        self.last_call = 0.0
        self.consecutive_failures = 0

    def _throttle(self):
        wait = self.interval_s + random.uniform(0, self.jitter_s) - (time.monotonic() - self.last_call)
        if wait > 0:
            time.sleep(wait)

    def call(self, body, attempt=1):
        """Un appel HTTP, avec throttling, backoff et coupe-circuit."""
        self._throttle()
        url = self.cfg["base_url"].rstrip("/") + self.cfg["path"]
        request = urllib.request.Request(
            url,
            data=body.encode("utf-8"),
            method=self.cfg.get("method", "POST"),
            headers={"Content-Type": "application/json", **self.cfg.get("headers", {})},
        )
        started = time.monotonic()
        try:
            with urllib.request.urlopen(request, timeout=self.cfg.get("timeout_s", DEFAULT_TIMEOUT_S)) as response:
                raw = response.read().decode("utf-8", "replace")
                status = response.status
        except urllib.error.HTTPError as err:
            raw, status = err.read().decode("utf-8", "replace"), err.code
        except Exception as err:  # noqa: BLE001 - on veut tracer toute panne reseau
            raw, status = json.dumps({"_transport_error": repr(err)}), 0
        finally:
            self.last_call = time.monotonic()
        latency_ms = round((time.monotonic() - started) * 1000)

        retryable = status in (0, 408, 425, 429, 500, 502, 503, 504)
        if retryable and attempt <= 3:
            backoff = min(60, 5 * 2 ** attempt)
            print("    ! statut %s, nouvelle tentative dans %ss" % (status, backoff), file=sys.stderr)
            time.sleep(backoff)
            return self.call(body, attempt + 1)

        if status == 0 or status >= 500:
            self.consecutive_failures += 1
            if self.consecutive_failures >= MAX_CONSECUTIVE_FAILURES:
                raise SystemExit(
                    "ARRET: %d echecs serveur consecutifs. La campagne est interrompue pour ne pas "
                    "aggraver la charge sur l'inference." % self.consecutive_failures
                )
        else:
            self.consecutive_failures = 0

        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            parsed = {"_unparsed_body": raw[:4000]}
        return {"status": status, "latency_ms": latency_ms, "body": parsed}


def run_case(client, case, repetition, config):
    """Joue un cas: tour 1, puis un tour de relance si un slot est attendu."""
    turns = []
    variables = {"query": case["q"], "lang": case.get("lang", "de"), "conversation_id": ""}
    turns.append(client.call(render(config["body_template"], variables)))

    conversation_id = extract(turns[0]["body"], config["extract"].get("conversation_id"))
    followup = case.get("followup")
    if followup and config.get("followup_body_template"):
        variables = {"query": followup, "lang": case.get("lang", "de"), "conversation_id": conversation_id or ""}
        turns.append(client.call(render(config["followup_body_template"], variables)))

    final = turns[-1]["body"]
    titles = extract(final, config["extract"]["result_titles"]) or []
    ids = extract(final, config["extract"].get("result_ids")) or []
    return {
        "case_id": case["id"],
        "category": case["cat"],
        "lang": case.get("lang"),
        "query": case["q"],
        "repetition": repetition,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "http_status": [t["status"] for t in turns],
        "latency_ms": sum(t["latency_ms"] for t in turns),
        "turns": len(turns),
        "conversation_state": extract(final, config["extract"].get("state")),
        "assistant_text": extract(final, config["extract"].get("answer_text")),
        "result_titles": [str(t) for t in titles],
        "result_ids": [str(i) for i in ids],
        "raw": [t["body"] for t in turns],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--config", default="config.json", help="fichier de configuration de l'endpoint")
    parser.add_argument("--queries", default="queries.json", help="corpus de requetes")
    parser.add_argument("--out", default="runs", help="repertoire de sortie")
    parser.add_argument("--repeats", type=int, default=3,
                        help="repetitions par requete (>=3 pour mesurer la variance du LLM)")
    parser.add_argument("--interval", type=float, default=DEFAULT_INTERVAL_S, help="secondes entre deux appels")
    parser.add_argument("--jitter", type=float, default=DEFAULT_JITTER_S, help="jitter aleatoire ajoute a l'intervalle")
    parser.add_argument("--category", action="append", help="limiter a une categorie (repetable)")
    parser.add_argument("--case", action="append", help="limiter a un id de cas (repetable)")
    parser.add_argument("--smoke", action="store_true", help="un seul cas, une seule fois: valide le cablage")
    parser.add_argument("--dry-run", action="store_true", help="affiche le plan sans appeler le portail")
    args = parser.parse_args()

    here = Path(__file__).parent
    resolve = lambda name: Path(name) if Path(name).is_absolute() else here / name
    config = json.loads(resolve(args.config).read_text(encoding="utf-8"))
    corpus = json.loads(resolve(args.queries).read_text(encoding="utf-8"))

    cases = corpus["cases"]
    if args.category:
        cases = [c for c in cases if c["cat"] in args.category]
    if args.case:
        cases = [c for c in cases if c["id"] in args.case]
    repeats = 1 if args.smoke else args.repeats
    if args.smoke:
        cases = cases[:1]

    total = len(cases) * repeats
    eta_min = round(total * (args.interval + args.jitter / 2) / 60, 1)
    print("Campagne: %d cas x %d repetitions = %d appels (~%s min a %.1fs d'intervalle)"
          % (len(cases), repeats, total, eta_min, args.interval))

    if args.dry_run:
        for case in cases:
            print("  %s [%s/%s] %s" % (case["id"], case["cat"], case.get("lang"), case["q"]))
        return

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_dir = here / args.out / stamp
    out_dir.mkdir(parents=True, exist_ok=True)
    results_path = out_dir / "results.jsonl"

    client = SmartSearchClient(config, args.interval, args.jitter)
    done = 0
    with results_path.open("w", encoding="utf-8") as sink:
        for repetition in range(1, repeats + 1):
            for case in cases:
                done += 1
                print("[%d/%d] %s (rep %d) %s" % (done, total, case["id"], repetition, case["q"][:60]))
                record = run_case(client, case, repetition, config)
                sink.write(json.dumps(record, ensure_ascii=False) + "\n")
                sink.flush()
                top = ", ".join(record["result_titles"][:3]) or "(aucun resultat)"
                print("    -> %s | %sms | %s" % (record["http_status"], record["latency_ms"], top))

    (out_dir / "run_meta.json").write_text(json.dumps({
        "started": stamp, "cases": len(cases), "repeats": repeats,
        "interval_s": args.interval, "corpus_version": corpus.get("corpus_version"),
        "target": corpus.get("target"),
    }, indent=2), encoding="utf-8")
    print("\nResultats bruts: %s" % results_path)
    print("Scoring: python3 score.py --run %s" % out_dir)


if __name__ == "__main__":
    main()
