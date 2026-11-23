# -*- coding: utf-8 -*-
"""
Régénère docs/OUTILS.md à partir des définitions des outils (server/tools/).

    python scripts/generer_doc_outils.py

À relancer après avoir ajouté ou modifié un outil. N'importe quel Python 3.9+ convient.
"""
import io
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "server"))

from tools import DOMAINS, TOOLS  # noqa: E402


def cell(text):
    return str(text or "").replace("|", "\\|").replace("\n", "<br>")


def type_of(prop):
    if "enum" in prop:
        return " / ".join("`%s`" % v for v in prop["enum"])
    t = prop.get("type")
    if isinstance(t, list):
        return " ou ".join(t)
    if t == "array":
        inner = prop.get("items", {}).get("type")
        return "liste" + (" de %s" % inner if inner else "")
    return t or "valeur"


def main():
    lines = [
        "# Outils du MCP Rhino & Grasshopper",
        "",
        "Généré par `scripts/generer_doc_outils.py` à partir de `server/tools/` : ne pas modifier à la main.",
        "",
        "**%d outils** :" % len(TOOLS),
        "",
    ]
    for title, tools in DOMAINS:
        lines.append("- %s : %s" % (title, ", ".join("`%s`" % t["name"] for t in tools)))
    for title, tools in DOMAINS:
        lines += ["", "## " + title]
        for t in tools:
            lines += ["", "### `%s`" % t["name"], "", t["description"]]
            props = t["inputSchema"].get("properties", {})
            required = set(t["inputSchema"].get("required", []))
            if props:
                lines += ["", "| Paramètre | Type | Description |", "|---|---|---|"]
                for name, prop in props.items():
                    default = " (défaut : `%s`)" % prop["default"] if "default" in prop else ""
                    lines.append("| `%s`%s | %s | %s%s |" % (name, " **requis**" if name in required else "",
                                                           cell(type_of(prop)), cell(prop.get("description")),
                                                           default))
    path = os.path.join(ROOT, "docs", "OUTILS.md")
    if not os.path.isdir(os.path.dirname(path)):
        os.makedirs(os.path.dirname(path))
    with io.open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(lines) + "\n")
    print("%s : %d outils." % (os.path.relpath(path, ROOT), len(TOOLS)))


if __name__ == "__main__":
    main()
