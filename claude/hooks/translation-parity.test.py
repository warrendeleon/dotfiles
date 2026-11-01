#!/usr/bin/env python3
"""Tests for translation-parity.py. Run: python3 claude/hooks/translation-parity.test.py"""
import os
import subprocess
import sys
import tempfile
import unittest

HOOK = os.path.join(os.path.dirname(os.path.abspath(__file__)), "translation-parity.py")
BLOG = os.path.expanduser("~/Developer/warrendeleon/warrendeleon.com/.content-repo/src/content/blog")

EN = '''---
title: "Two steps"
description: "A small post."
heroAlt: "A diagram of two steps"
publishDate: 2026-11-01
tags: ["mermaid"]
---

## Install

Install lottie 4.6.0 before you start. See [the docs](https://example.com/docs).

This paragraph is **important** and stays.

This paragraph can go.

```sh
# install the package
npm install lottie
```

## The diagram

```mermaid
%%{init: {"flowchart": {"wrappingWidth": 260}}}%%
flowchart TB
    accTitle: Fetch, check, store
    accDescr: The fetch feeds the check, which stores the map or refuses it.
    subgraph cp["CocoaPods: one pod"]
        direction TB
        A["Fetch,<br/>the map"] -. "symbols resolve at link" .-> B("Check it")
    end
    subgraph sp [Two targets]
        store[("Store it")]
        refuse{"Refuse?"}
    end
    later[[Later]]
    B -- "yes" --> store
    B -->|"no"| refuse
    refuse -- maybe --> later
    later == "after a while" ==> A
    refuse -.->|retry| A
    store --> later --> B
    cp ~~~ sp
```

```mermaid
sequenceDiagram
    accDescr {
        The host asks the CDN for the map
        and the CDN answers.
    }
    participant H as host app
    participant C as CDN
    H->>C: GET the map
    Note over C: signs it
    C-->>H: the signed map
```
'''

TR = '''---
title: "Dos pasos"
description: "Un post pequeño."
heroAlt: "Un diagrama de dos pasos"
locale: es
tags: ["mermaid"]
---

## Instalación

Instala lottie 4.6.0 antes de empezar. Mira [la documentación](https://example.com/docs).

Este párrafo es **importante** y se queda.

Este párrafo puede irse.

```sh
# instala el paquete
npm install lottie
```

## El diagrama

```mermaid
%%{init: {"flowchart": {"wrappingWidth": 260}}}%%
flowchart TB
    accTitle: Descargar, comprobar, guardar
    accDescr: La descarga alimenta la comprobación, que guarda el mapa o lo rechaza.
    subgraph cp["CocoaPods: un pod"]
        direction TB
        A["Descarga,<br/>el mapa"] -. "los símbolos se resuelven<br/>al enlazar" .-> B("Compruébalo")
    end
    subgraph sp [Dos targets]
        store[("Guárdalo")]
        refuse{"¿Rechazar?"}
    end
    later[[Más tarde]]
    B -- "sí" --> store
    B -->|"no"| refuse
    refuse -- quizá --> later
    later == "al cabo de un rato" ==> A
    refuse -.->|reintenta| A
    store --> later --> B
    cp ~~~ sp
```

```mermaid
sequenceDiagram
    accDescr {
        El host pide el mapa a la CDN
        y la CDN responde.
    }
    participant H as app host
    participant C as CDN
    H->>C: GET del mapa
    Note over C: lo firma
    C-->>H: el mapa firmado
```
'''

# (control, text in TR, replacement, replace every occurrence, classes that must fail)
CONTROLS = [
    ("accTitle reworded", "accTitle: Descargar, comprobar, guardar", "accTitle: Otra cosa", False, set()),
    ("accDescr reworded", "que guarda el mapa o lo rechaza.", "y nada más.", False, set()),
    ("accDescr block reworded", "y la CDN responde.", "y la CDN contesta: vale.", False, set()),
    ("edge label reworded", '"los símbolos se resuelven<br/>al enlazar"', '"se enlaza"', False, set()),
    ("node label reworded", "[[Más tarde]]", "[[Luego]]", False, set()),
    ("sequence text reworded", "GET del mapa", "pide el mapa", False, set()),
    ("comment translated", "# instala el paquete", "# otro comentario", False, set()),
    ("node id renamed", "refuse", "reject", True, {"mermaid #1 node ids", "mermaid #1 edges"}),
    ("edge removed", '    B -->|"no"| refuse\n', "", False, {"mermaid #1 edges"}),
    ("edge retargeted", 'B -- "sí" --> store', 'B -- "sí" --> refuse', False, {"mermaid #1 edges"}),
    ("arrow type changed", "refuse -.->|reintenta| A", "refuse -->|reintenta| A", False, {"mermaid #1 edges"}),
    ("chain middle node removed", "store --> later --> B", "store --> B", False, {"mermaid #1 edges"}),
    ("sequence message retargeted", "H->>C: GET del mapa", "H->>H: GET del mapa", False, {"mermaid #2 edges"}),
    ("heading removed", "## El diagrama\n", "", False, {"heading count", "heading levels"}),
    ("executable token changed", "npm install lottie", "npm install lottie-ios", False, {"executable tokens"}),
    ("version swapped", "lottie 4.6.0", "lottie 4.5.0", False, {"numbers (order-insensitive)"}),
    ("link changed", "https://example.com/docs", "https://example.com/es/docs", False, {"link destinations"}),
    ("paragraph removed", "Este párrafo puede irse.\n\n", "", False, {"paragraph count"}),
    ("bold removed", "**importante**", "importante", False, {"bold count"}),
]


def failures(out):
    names = set()
    for line in out.splitlines():
        if line.startswith("FAIL"):
            name = line[4:].strip()
            names.add("executable tokens" if name.startswith("executable tokens") else name.split(":")[0])
    return names


def run_files(en, tr):
    out = subprocess.run([sys.executable, HOOK, en, tr], capture_output=True, text=True)
    return out.returncode, out.stdout


class TranslationParity(unittest.TestCase):
    def run_hook(self, en_text, tr_text):
        with tempfile.TemporaryDirectory() as d:
            en, tr = os.path.join(d, "en.md"), os.path.join(d, "es.md")
            for path, text in ((en, en_text), (tr, tr_text)):
                with open(path, "w", encoding="utf8") as f:
                    f.write(text)
            return run_files(en, tr)

    def test_translated_labels_acc_text_and_comments_pass(self):
        code, out = self.run_hook(EN, TR)
        self.assertEqual(failures(out), set(), out)
        self.assertIn("RESULT OK", out)
        self.assertEqual(code, 0)

    def test_controls_fail_in_their_own_class(self):
        for name, old, new, every, expected in CONTROLS:
            with self.subTest(name):
                self.assertIn(old, TR)
                _, out = self.run_hook(EN, TR.replace(old, new, -1 if every else 1))
                self.assertEqual(failures(out), expected, out)

    @unittest.skipUnless(os.path.isdir(BLOG), "blog content repo not on this machine")
    def test_cocoapods_spm_pair_passes_mermaid(self):
        slug = "react-native-cocoapods-to-swift-package-manager.md"
        _, out = run_files(os.path.join(BLOG, slug), os.path.join(BLOG, "es", slug))
        self.assertFalse({f for f in failures(out) if f.startswith("mermaid")}, out)
        edges = next(l for l in out.splitlines() if "mermaid #1 edges" in l)
        for edge in ("('A', '-.->', 'B')", "('C', '-.->', 'D')", "('cp', '~~~', 'sp')"):
            self.assertIn(edge, edges)

    @unittest.skipUnless(os.path.isdir(BLOG), "blog content repo not on this machine")
    def test_locked_post_still_passes(self):
        slug = "version-map-signing-react-native.md"
        code, out = run_files(os.path.join(BLOG, slug), os.path.join(BLOG, "es", slug))
        self.assertIn("RESULT OK", out)
        self.assertEqual(code, 0)


if __name__ == "__main__":
    unittest.main()
