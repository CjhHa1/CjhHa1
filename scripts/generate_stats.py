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


def api(path):
    result = subprocess.run(['gh', 'api', path], check=True, capture_output=True, text=True)
    return json.loads(result.stdout)


def contributions(username, request=api):
    query = f'is:pr is:public is:merged author:{username} -user:{username}'
    items = {}
    page = 1
    expected = None
    while True:
        result = request('search/issues?' + urlencode({
            'q': query, 'per_page': 100, 'page': page,
            'sort': 'created', 'order': 'asc',
        }))
        total = result['total_count']
        if result.get('incomplete_results', True) or total > 1000:
            raise RuntimeError('Incomplete or capped contribution search; keeping previous cards.')
        if expected is not None and total != expected:
            raise RuntimeError('Contribution search changed during pagination; retry later.')
        expected = total
        batch = result['items']
        for item in batch:
            items[item['id']] = item
        if page * 100 >= total:
            break
        if not batch:
            raise RuntimeError('Missing contribution search page; keeping previous cards.')
        page += 1
    if len(items) != expected:
        raise RuntimeError('Contribution search contains missing or duplicate PRs.')
    projects = Counter()
    for item in items.values():
        match = re.fullmatch(r'https://api.github.com/repos/([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)', item['repository_url'])
        if not match:
            raise RuntimeError('Unexpected repository URL in contribution search.')
        repo = match.group(1)
        if repo.split('/')[0].casefold() != username.casefold():
            projects[repo] += 1
    return dict(sorted(projects.items(), key=lambda item: (-item[1], item[0].casefold())))


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
        'contributions': contributions(username, request),
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
    projects = data['contributions']
    total = sum(projects.values())
    body = text(24, 61, 'Merged public PRs in repositories owned by others', 'small')
    body += text(24, 101, f'{total:,}', 'value') + text(24, 121, 'Merged PRs')
    body += text(252, 101, len(projects), 'value') + text(252, 121, 'Projects contributed to')
    for i, (repo, count) in enumerate(list(projects.items())[:5]):
        y = 151 + i * 22
        label = repo if len(repo) <= 42 else repo[:41] + '…'
        body += text(24, y, label) + text(418, y, count, 'small')
    if not projects:
        body += text(24, 166, 'No merged external PRs yet.')
    body += text(24, 254, 'All time · Top projects by merged PRs · Own repos excluded', 'small')
    description = f'{total} merged public PRs across {len(projects)} external projects. '
    description += '; '.join(f'{repo}: {count}' for repo, count in projects.items())
    contribution_card = card('Open source contributions', description, body, data['updated'], theme)
    return stats, contribution_card


def project_links(data):
    lines = ['# Open source contributions', '',
             f"Updated {data['updated']} UTC. Merged public PRs authored by @{data['username']}, excluding their own repositories.", '',
             '| Project | Merged PRs |', '| --- | ---: |']
    for repo, count in data['contributions'].items():
        query = urlencode({'q': f"is:pr is:merged author:{data['username']} repo:{repo}"})
        label = repo.replace('_', r'\_')
        lines.append(f'| [{label}](https://github.com/{repo}) | [{count}](https://github.com/pulls?{query}) |')
    if not data['contributions']:
        lines += ['', 'No merged external PRs yet.']
    return '\n'.join(lines) + '\n'


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
    files = {'profile-data.json': json.dumps(data, indent=2, ensure_ascii=False) + '\n',
             'contributions.md': project_links(data)}
    for theme in ('light', 'dark'):
        stats, contribution_card = render(data, theme)
        files[f'stats-{theme}.svg'] = stats
        files[f'contributions-{theme}.svg'] = contribution_card
    args.output.mkdir(parents=True, exist_ok=True)
    for name, content in files.items():
        path = args.output / name
        temporary = path.with_suffix(path.suffix + '.tmp')
        temporary.write_text(content, encoding='utf-8')
        temporary.replace(path)
    print('Generated four SVG cards and a public-data snapshot.')


if __name__ == '__main__':
    main()
