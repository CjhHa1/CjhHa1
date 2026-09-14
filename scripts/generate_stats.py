#!/usr/bin/env python3
"""Generate self-contained profile SVGs from public GitHub REST data using gh."""
import argparse
from collections import Counter
from datetime import datetime, timezone
from html import escape
import json
from pathlib import Path
import re
import subprocess
from urllib.parse import urlencode

ROOT = Path(__file__).resolve().parents[1]
COLORS = ['#58a6ff', '#bc8cff', '#3fb950', '#f2cc60', '#f778ba', '#79c0ff']


def api(path):
    result = subprocess.run(['gh', 'api', path], check=True, capture_output=True, text=True)
    return json.loads(result.stdout)


def collect(username, request=api):
    user = request(f'users/{username}')
    repos = []
    page = 1
    while True:
        batch = request(f'users/{username}/repos?type=owner&per_page=100&page={page}')
        repos.extend(r for r in batch if not r['private'])
        if len(batch) < 100:
            break
        page += 1
    original = [r for r in repos if not r['fork']]
    languages = Counter(r['language'] for r in original if r.get('language'))
    pulls = request('search/issues?' + urlencode({'q': f'is:pr is:public author:{username}', 'per_page': 1}))
    if pulls.get('incomplete_results', True):
        raise RuntimeError('GitHub returned incomplete PR search results; keeping previous cards.')
    return {
        'username': user['login'],
        'updated': datetime.now(timezone.utc).strftime('%Y-%m-%d'),
        'public_repos': len(repos),
        'original_repos': len(original),
        'stars': sum(r['stargazers_count'] for r in original),
        'followers': user['followers'],
        'pull_requests': pulls['total_count'],
        'languages': dict(sorted(languages.items(), key=lambda item: (-item[1], item[0]))),
    }


def text(x, y, value, css='body'):
    return f'<text x="{x}" y="{y}" class="{css}">{escape(str(value))}</text>'


def card(title, description, body, updated, theme):
    bg, border, fg, muted = ('#0d1117', '#30363d', '#e6edf3', '#9da7b3') if theme == 'dark' else ('#ffffff', '#d0d7de', '#1f2328', '#59636e')
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="480" height="300" viewBox="0 0 480 300" role="img" aria-labelledby="title desc">
<title id="title">{escape(title)}</title>
<desc id="desc">{escape(description)}</desc>
<style>text{{font-family:-apple-system,BlinkMacSystemFont,Segoe UI,Arial,sans-serif;fill:{fg}}}.heading{{font-size:20px;font-weight:700}}.body{{font-size:13px;fill:{muted}}}.value{{font-size:27px;font-weight:700}}.small{{font-size:11px;fill:{muted}}}</style>
<rect x=".5" y=".5" width="479" height="299" rx="16" fill="{bg}" stroke="{border}"/>
{ text(24, 38, title, 'heading') }
{body}
{ text(24, 279, f'Updated {updated} UTC · Public GitHub data', 'small') }
</svg>
'''


def render(data, theme):
    metrics = [('Public repos', data['public_repos']), ('Stars earned', data['stars']), ('Followers', data['followers']), ('Public PRs authored', data['pull_requests'])]
    body = text(24, 61, '@' + data['username'])
    for i, (label, value) in enumerate(metrics):
        x, y = 24 + (i % 2) * 228, 108 + (i // 2) * 79
        body += text(x, y, f'{value:,}', 'value') + text(x, y + 22, label)
    body += text(24, 244, 'Stars count owned public repositories, excluding forks.', 'small')
    stats = card('GitHub overview', '; '.join(f'{label}: {value}' for label, value in metrics), body, data['updated'], theme)
    items = list(data['languages'].items())
    if len(items) > 6:
        items = items[:5] + [('Other', sum(n for _, n in items[5:]))]
    total = sum(data['languages'].values())
    body = text(24, 61, 'Primary language per owned public non-fork repository', 'small')
    for i, (language, count) in enumerate(items):
        y = 88 + i * 27
        label = language if len(language) <= 22 else language[:21] + '…'
        body += text(24, y, label)
        body += f'<rect x="192" y="{y - 10}" width="{max(1, 155 * count / total):.2f}" height="10" rx="5" fill="{COLORS[i]}"/>'
        body += text(365, y, f'{count / total:.0%} ({count})', 'small')
    if not items:
        body += text(24, 120, 'No language data available yet.')
    body += text(24, 254, f'{total} repositories with a detected language · Not code volume', 'small')
    langs = card('Language distribution', '; '.join(f'{lang}: {n} repositories' for lang, n in items) or 'No language data', body, data['updated'], theme)
    return stats, langs


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--username', default='CjhHa1')
    parser.add_argument('--from-json', type=Path, help='Render an existing snapshot without API calls')
    parser.add_argument('--output', type=Path, default=ROOT / 'assets')
    args = parser.parse_args()
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9-]{0,38}', args.username):
        parser.error('Invalid GitHub username')
    data = json.loads(args.from_json.read_text()) if args.from_json else collect(args.username)
    # Finish all API requests and rendering before touching existing output.
    files = {'profile-data.json': json.dumps(data, indent=2, ensure_ascii=False) + '\n'}
    for theme in ('light', 'dark'):
        stats, langs = render(data, theme)
        files[f'stats-{theme}.svg'] = stats
        files[f'languages-{theme}.svg'] = langs
    args.output.mkdir(parents=True, exist_ok=True)
    for name, content in files.items():
        path = args.output / name
        temporary = path.with_suffix(path.suffix + '.tmp')
        temporary.write_text(content, encoding='utf-8')
        temporary.replace(path)
    print('Generated four SVG cards and a public-data snapshot.')


if __name__ == '__main__':
    main()
