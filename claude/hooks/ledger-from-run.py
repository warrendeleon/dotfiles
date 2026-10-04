#!/usr/bin/env python3
"""Extract the claim ledger a review-loop run built, so a later run can re-check it
without discovering afresh.

    ledger-from-run.py <run transcript dir or journal.jsonl> [--types a,b,c] [--result <task output file>] > ledger.json

The journal records agents in launch order ("started" lines) and their return values
("result" lines) by key. Within a round the loop launches one oracle, then one critic
per claim type in the profile's order, so the critics' keys map to types by position.
The discovery round returns the whole ledger for a type; later rounds return only the
entries they re-derived or added, which are merged over the discovery ledger by
location and claim. The output is {claim type: [ {claim, location, check}, ... ],
"refuted": [ {location, claim, reason}, ... ]}. The refuted list comes from the loop's
final result, which the journal does not hold: pass the task output file the harness
wrote (tasks/<id>.output) as --result and its "refuted" entries are carried over, so the
next run's critics are told not to raise them again. Pass the file to the loop as
args.ledgerFile with args.edits (the before/after pairs made since) and it starts in
re-check mode.
"""
import html, json, os, re, sys

args = sys.argv[1:]
types = ["numeric", "existence", "attribution", "inference", "consistency"]
result_file = None
if "--types" in args:
    i = args.index("--types"); types = args[i + 1].split(","); del args[i:i + 2]
if "--result" in args:
    i = args.index("--result"); result_file = args[i + 1]; del args[i:i + 2]
if len(args) != 1:
    sys.exit(__doc__)
p = args[0]
if os.path.isdir(p):
    p = os.path.join(p, "journal.jsonl")

started, results = [], {}
for ln in open(p, encoding="utf-8"):
    try:
        d = json.loads(ln)
    except Exception:
        continue
    if d.get("type") == "started":
        started.append(d["key"])
    elif d.get("type") == "result":
        results[d["key"]] = d.get("result")

def k(entry):
    return f"{entry.get('location', '')}|{re.sub(r'\\s+', ' ', entry.get('claim', '')).strip()[:160]}"

def merge(base, delta):
    """delta entries replace base entries with the same key; new keys are appended."""
    fresh = {k(e) for e in delta}
    return [e for e in base if k(e) not in fresh] + list(delta)

# walk launches: an oracle result ("ran") opens a round; the next len(types) launches
# whose results carry a ledger are that round's critics, in order. The first ledger seen
# for a type is the discovery ledger; every later one is a delta merged over it.
ledger = {}
i = 0
while i < len(started):
    r = results.get(started[i])
    if isinstance(r, dict) and "ran" in r:
        j, t = i + 1, 0
        while j < len(started) and t < len(types):
            rj = results.get(started[j])
            if isinstance(rj, dict) and "ledger" in rj:
                if rj["ledger"]:
                    ledger[types[t]] = merge(ledger.get(types[t], []), rj["ledger"]) if types[t] in ledger else list(rj["ledger"])
                t += 1
            elif isinstance(rj, dict) and ("confirmed" in rj or "applied" in rj):
                break
            j += 1
        i = j
    else:
        i += 1

refuted = []
if result_file:
    # Either the refuted-<target>.json the loop's receipt stage writes under ~/.claude/receipts,
    # or any text holding the loop's final result object ({"clean": ..., "refuted": [...]}).
    text = html.unescape(open(result_file, encoding="utf-8").read())
    final = None
    try:
        final = json.loads(text)
    except Exception:
        start = text.find('{"clean"')
        if start >= 0:
            try:
                final, _ = json.JSONDecoder().raw_decode(text[start:])
            except Exception as e:
                print(f"could not parse the final result in {result_file}: {e}", file=sys.stderr)
    # The harness's tasks/<id>.output wraps the loop's result under "result".
    if isinstance(final, dict) and "refuted" not in final and isinstance(final.get("result"), dict):
        final = final["result"]
    if isinstance(final, dict):
        refuted = [{"location": r.get("location", ""), "claim": r.get("claim", ""), "reason": r.get("reason", "")}
                   for r in final.get("refuted", [])]
        for t, delta in (final.get("ledgerDelta") or {}).items():
            ledger[t] = merge(ledger.get(t, []), delta)
    else:
        print(f"no refuted list or final result found in {result_file}", file=sys.stderr)
if refuted:
    ledger["refuted"] = refuted

json.dump(ledger, sys.stdout, indent=1)
print(*(f"{k_}: {len(v)} entries" for k_, v in ledger.items()), sep="\n", file=sys.stderr)
