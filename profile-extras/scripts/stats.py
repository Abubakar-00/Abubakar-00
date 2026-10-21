"""
Generate GitHub stat cards (dark + light SVG) for the profile README.

Runs daily from .github/workflows/stats.yml, so the numbers are always current
and no third-party stats server is involved.

    GITHUB_TOKEN=... python scripts/stats.py <username>
"""

import json
import os
import sys
import urllib.request
from html import escape

# Notebook outputs inflate byte counts, so they would drown out real code.
EXCLUDED_LANGUAGES = {"Jupyter Notebook"}
TOP_LANGUAGES = 6

QUERY = """
query($login: String!) {
  user(login: $login) {
    createdAt
    contributionsCollection {
      contributionCalendar { totalContributions }
    }
    repositories(ownerAffiliations: OWNER, isFork: false, privacy: PUBLIC, first: 100) {
      totalCount
      nodes {
        languages(first: 10, orderBy: {field: SIZE, direction: DESC}) {
          edges { size node { name color } }
        }
      }
    }
  }
}
"""

THEMES = {
    "dark": {"bg": "#0d1117", "border": "#30363d", "title": "#e6edf3", "text": "#9198a1", "value": "#e6edf3", "accent": "#2f81f7"},
    "light": {"bg": "#ffffff", "border": "#d1d9e0", "title": "#1f2328", "text": "#59636e", "value": "#1f2328", "accent": "#0969da"},
}


def fetch(login: str, token: str) -> dict:
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": QUERY, "variables": {"login": login}}).encode(),
        headers={"Authorization": f"bearer {token}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req) as resp:
        payload = json.load(resp)
    if "errors" in payload:
        sys.exit(f"GraphQL error: {payload['errors']}")
    return payload["data"]["user"]


def summarize(user: dict) -> tuple[list[tuple[str, str]], list[tuple[str, str, float]]]:
    repos = user["repositories"]
    cc = user["contributionsCollection"]
    stats = [
        ("Contributions (last year)", f"{cc['contributionCalendar']['totalContributions']:,}"),
        ("Public repositories", str(repos["totalCount"])),
        ("On GitHub since", user["createdAt"][:4]),
    ]

    sizes: dict[str, int] = {}
    colors: dict[str, str] = {}
    for repo in repos["nodes"]:
        for edge in repo["languages"]["edges"]:
            name = edge["node"]["name"]
            if name in EXCLUDED_LANGUAGES:
                continue
            sizes[name] = sizes.get(name, 0) + edge["size"]
            colors[name] = edge["node"]["color"] or "#8b949e"
    total = sum(sizes.values()) or 1
    top = [kv for kv in sorted(sizes.items(), key=lambda kv: kv[1], reverse=True) if kv[1] / total >= 0.001]
    top = top[:TOP_LANGUAGES]
    languages = [(name, colors[name], size / total * 100) for name, size in top]
    return stats, languages


def card(title: str, body: str, height: int, t: dict) -> str:
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="420" height="{height}" viewBox="0 0 420 {height}" role="img" aria-label="{escape(title)}">
  <style>
    .t {{ font: 600 16px 'Segoe UI', Ubuntu, sans-serif; fill: {t['title']}; }}
    .l {{ font: 400 13px 'Segoe UI', Ubuntu, sans-serif; fill: {t['text']}; }}
    .v {{ font: 600 13px 'Segoe UI', Ubuntu, sans-serif; fill: {t['value']}; }}
  </style>
  <rect x="0.5" y="0.5" width="419" height="{height - 1}" rx="8" fill="{t['bg']}" stroke="{t['border']}"/>
  <text x="22" y="34" class="t">{escape(title)}</text>
{body}</svg>
"""


def stats_card(stats, t: dict) -> str:
    rows = "".join(
        f'  <text x="22" y="{68 + i * 26}" class="l">{escape(label)}</text>\n'
        f'  <text x="398" y="{68 + i * 26}" class="v" text-anchor="end">{escape(value)}</text>\n'
        for i, (label, value) in enumerate(stats)
    )
    return card("GitHub activity", rows, 68 + len(stats) * 26, t)


def languages_card(languages, t: dict) -> str:
    bar, x = "", 22.0
    for _, color, pct in languages:
        w = 376 * pct / sum(p for _, _, p in languages)
        bar += f'  <rect x="{x:.1f}" y="52" width="{w:.1f}" height="8" fill="{color}"/>\n'
        x += w
    bar = f'  <clipPath id="c"><rect x="22" y="52" width="376" height="8" rx="4"/></clipPath>\n  <g clip-path="url(#c)">\n{bar}  </g>\n'
    rows = ""
    for i, (name, color, pct) in enumerate(languages):
        cx, cy = 22 + (i % 2) * 196, 88 + (i // 2) * 24
        rows += (
            f'  <circle cx="{cx + 5}" cy="{cy - 4}" r="5" fill="{color}"/>\n'
            f'  <text x="{cx + 16}" y="{cy}" class="l">{escape(name)} <tspan class="v">{pct:.1f}%</tspan></text>\n'
        )
    height = 88 + ((len(languages) + 1) // 2) * 24
    return card("Languages (notebooks excluded)", bar + rows, height, t)


def main():
    login = sys.argv[1] if len(sys.argv) > 1 else "Abubakar-00"
    token = os.environ.get("GITHUB_TOKEN") or sys.exit("GITHUB_TOKEN is not set")
    stats, languages = summarize(fetch(login, token))
    os.makedirs("assets", exist_ok=True)
    for name, t in THEMES.items():
        with open(f"assets/stats-{name}.svg", "w") as f:
            f.write(stats_card(stats, t))
        with open(f"assets/languages-{name}.svg", "w") as f:
            f.write(languages_card(languages, t))
    print(stats, languages, sep="\n")


if __name__ == "__main__":
    main()
