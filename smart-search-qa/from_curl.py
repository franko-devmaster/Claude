#!/usr/bin/env python3
"""Construit config.json a partir d'un cURL copie depuis les DevTools.

Le contrat de l'API Smart Search n'est pas documente et change avec le tenant.
Plutot que de le retranscrire a la main, on part de l'appel reel: DevTools >
Network > clic droit sur l'appel de recherche > Copy as cURL, puis

    python3 from_curl.py --curl-file appel.txt

Le script isole la requete, remplace le texte cherche par {{query}}, puis — sauf
si --no-probe — envoie une requete de sondage et deduit les chemins d'extraction
en inspectant la reponse. Aucune dependance externe.
"""

import argparse
import json
import re
import shlex
import sys
import urllib.request
from pathlib import Path
from urllib.parse import urlsplit

# En-tetes propres a la capture du navigateur: les rejouer nuit plus qu'il n'aide.
DROP_HEADERS = {
    "content-length", "host", "connection", "accept-encoding", "sec-fetch-dest",
    "sec-fetch-mode", "sec-fetch-site", "sec-ch-ua", "sec-ch-ua-mobile",
    "sec-ch-ua-platform", "priority", "pragma", "cache-control", "te",
}
TITLE_KEYS = ("title", "name", "label", "libelle", "titel", "bezeichnung", "displayname")
ID_KEYS = ("id", "key", "code", "slug", "workflowid", "prestationid")
STATE_KEYS = ("state", "status", "conversationstate", "phase")
TEXT_KEYS = ("text", "message", "answer", "content", "reply")
CONV_KEYS = ("conversationid", "conversation_id", "sessionid", "id")


def parse_curl(command):
    """Extrait URL, methode, en-tetes et corps d'une commande cURL."""
    command = command.strip().lstrip("$ ").replace("\\\n", " ").replace("^\n", " ")
    tokens = shlex.split(command)
    if not tokens or tokens[0] != "curl":
        raise SystemExit("La commande ne commence pas par 'curl'.")

    url, method, headers, body = None, None, {}, None
    index = 1
    while index < len(tokens):
        token = tokens[index]
        if token in ("-H", "--header"):
            index += 1
            name, _, value = tokens[index].partition(":")
            if name.strip().lower() not in DROP_HEADERS:
                headers[name.strip()] = value.strip()
        elif token in ("-X", "--request"):
            index += 1
            method = tokens[index]
        elif token in ("-d", "--data", "--data-raw", "--data-binary", "--data-ascii"):
            index += 1
            body = tokens[index]
        elif token in ("-b", "--cookie"):
            index += 1
            headers["Cookie"] = tokens[index]
        elif token.startswith("-"):
            # Options sans valeur (--compressed, -k, ...) ou options ignorees.
            if token in ("--url",):
                index += 1
                url = tokens[index]
        elif url is None:
            url = token
        index += 1

    if not url:
        raise SystemExit("Aucune URL trouvee dans la commande cURL.")
    parts = urlsplit(url)
    return {
        "base_url": "%s://%s" % (parts.scheme, parts.netloc),
        "path": parts.path + (("?" + parts.query) if parts.query else ""),
        "method": method or ("POST" if body else "GET"),
        "headers": headers,
        "body": body,
    }


def templatize(body, query_text):
    """Remplace le texte cherche par {{query}} dans le corps capture."""
    if not body:
        return None, False
    if query_text and query_text in body:
        return body.replace(query_text, "{{query}}"), True
    # A defaut, reperer la plus longue valeur de chaine du JSON: c'est la question.
    try:
        parsed = json.loads(body)
    except json.JSONDecodeError:
        return body, False
    candidates = [(len(v), k, v) for k, v in parsed.items() if isinstance(v, str)]
    if not candidates:
        return body, False
    _, key, value = max(candidates)
    parsed[key] = "{{query}}"
    return json.dumps(parsed, ensure_ascii=False), True


def walk(node, path=""):
    """Parcourt le JSON en produisant (chemin, valeur) pour chaque noeud."""
    if isinstance(node, dict):
        for key, value in node.items():
            child = "%s.%s" % (path, key) if path else key
            yield child, value
            yield from walk(value, child)
    elif isinstance(node, list) and node:
        yield from walk(node[0], path + "[]")


def suggest_extractors(payload):
    """Devine les chemins d'extraction en inspectant une reponse reelle."""
    found = {}
    lists = []
    for path, value in walk(payload):
        leaf = path.rsplit(".", 1)[-1].replace("[]", "").lower()
        if isinstance(value, list) and value and isinstance(value[0], dict):
            lists.append((len(value), path, value[0]))
        elif isinstance(value, str):
            if leaf in STATE_KEYS and "state" not in found:
                found["state"] = path
            elif leaf in TEXT_KEYS and "answer_text" not in found:
                found["answer_text"] = path
            elif leaf in CONV_KEYS and "." not in path and "conversation_id" not in found:
                found["conversation_id"] = path

    # La liste de prestations est celle dont les elements portent un intitule.
    for _, path, sample in sorted(lists, reverse=True):
        keys = {k.lower(): k for k in sample}
        title = next((keys[k] for k in TITLE_KEYS if k in keys), None)
        if title:
            found["result_titles"] = "%s[].%s" % (path, title)
            ident = next((keys[k] for k in ID_KEYS if k in keys), None)
            if ident:
                found["result_ids"] = "%s[].%s" % (path, ident)
            break
    return found


def probe(config, body):
    request = urllib.request.Request(
        config["base_url"].rstrip("/") + config["path"],
        data=body.encode("utf-8") if body else None,
        method=config["method"],
        headers={"Content-Type": "application/json", **config["headers"]},
    )
    with urllib.request.urlopen(request, timeout=90) as response:
        return json.loads(response.read().decode("utf-8", "replace"))


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--curl-file", help="fichier contenant la commande cURL copiee")
    source.add_argument("--curl", help="la commande cURL entre guillemets")
    parser.add_argument("--query", help="le texte cherche dans l'appel capture (repere le champ question)")
    parser.add_argument("--out", default="config.json", help="fichier de configuration a ecrire")
    parser.add_argument("--no-probe", action="store_true", help="ne pas appeler le portail; chemins a completer a la main")
    args = parser.parse_args()

    raw = Path(args.curl_file).read_text(encoding="utf-8") if args.curl_file else args.curl
    parsed = parse_curl(raw)
    template, substituted = templatize(parsed["body"], args.query)

    config = {
        "base_url": parsed["base_url"],
        "path": parsed["path"],
        "method": parsed["method"],
        "timeout_s": 90,
        "headers": parsed["headers"],
        "body_template": template,
        "extract": {},
    }

    print("Requete reconstruite:")
    print("  %s %s%s" % (config["method"], config["base_url"], config["path"]))
    print("  %d en-tetes conserves: %s" % (len(config["headers"]), ", ".join(sorted(config["headers"])) or "aucun"))
    if not substituted:
        print("  ! le champ de la question n'a pas ete identifie — relancer avec --query \"<texte cherche>\"",
              file=sys.stderr)

    if args.no_probe:
        print("  sondage desactive: completer 'extract' a la main.")
    else:
        probe_body = (template or "").replace("{{query}}", "Hundemarke")
        print("\nSondage avec la requete \"Hundemarke\"...")
        try:
            payload = probe(config, probe_body)
        except Exception as err:  # noqa: BLE001 — on veut le motif exact a l'ecran
            raise SystemExit("Sondage echoue (%r).\nSi c'est un 401/403, la session du cURL a expire: "
                             "recapturer l'appel. Sinon relancer avec --no-probe." % err)
        config["extract"] = suggest_extractors(payload)
        if config["extract"].get("conversation_id"):
            config["followup_body_template"] = json.dumps(
                {**json.loads(template), "conversationId": "{{conversation_id}}"}, ensure_ascii=False
            ) if template else None
        print("Chemins deduits:")
        for key in ("conversation_id", "state", "answer_text", "result_titles", "result_ids"):
            print("  %-16s %s" % (key, config["extract"].get(key, "— a completer a la main")))
        if not config["extract"].get("result_titles"):
            print("\n  ! aucune liste de prestations reconnue. Structure de la reponse:", file=sys.stderr)
            print(json.dumps(payload, ensure_ascii=False, indent=2)[:1500], file=sys.stderr)

    Path(args.out).write_text(json.dumps(config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("\nEcrit: %s" % args.out)
    print("Verifier le fichier, puis: python3 run_tests.py --smoke")


if __name__ == "__main__":
    main()
