import sys
from pathlib import Path
import unittest
from urllib.parse import parse_qs, urlsplit
import xml.etree.ElementTree as ET

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from generate_stats import collect, contributions, render, project_links


def pr(i, repo='external/project'):
    return dict(id=i, repository_url='https://api.github.com/repos/' + repo)


class StatisticsTests(unittest.TestCase):
    def test_pagination_and_public_nonfork_scope(self):
        repo = dict(private=False, fork=False, stargazers_count=2)
        def request(path):
            if path == 'users/example':
                return dict(login='example', followers=3)
            if path.startswith('search/'):
                if 'is:merged' in parse_qs(urlsplit(path).query)['q'][0]:
                    return dict(total_count=0, incomplete_results=False, items=[])
                return dict(total_count=7, incomplete_results=False)
            if 'page=2' in path:
                return [dict(repo, private=True), dict(repo, fork=True, stargazers_count=500)]
            return [dict(repo) for _ in range(100)]
        data = collect('example', request)
        self.assertEqual(data['public_repos'], 101)
        self.assertEqual(data['stars'], 200)
        self.assertEqual(data['pull_requests'], 7)

    def test_contribution_pagination_and_own_repo_exclusion(self):
        def request(path):
            params = parse_qs(urlsplit(path).query)
            self.assertIn('is:public is:merged author:example -user:example', params['q'][0])
            batch = [pr(i) for i in range(100)] if params['page'] == ['1'] else [pr(100, 'EXAMPLE/own'), pr(101, 'another/project')]
            return dict(total_count=102, incomplete_results=False, items=batch)
        self.assertEqual(contributions('example', request), {'external/project': 100, 'another/project': 1})

    def test_incomplete_capped_and_duplicate_search_fail(self):
        for result in (dict(total_count=1, incomplete_results=True, items=[]),
                       dict(total_count=1001, incomplete_results=False, items=[]),
                       dict(total_count=2, incomplete_results=False, items=[pr(1), pr(1)])):
            with self.assertRaises(RuntimeError):
                contributions('example', lambda _: result)

    def test_svg_empty_data_long_names_and_links(self):
        data = dict(username='example', updated='2026-09-14', public_repos=0,
                    stars=0, followers=0, pull_requests=0, contributions={})
        for projects in ({}, {'org/' + 'long_name' * 6: 3}, {f'org/p{i}': 1 for i in range(7)}):
            data['contributions'] = projects
            for theme in ('dark', 'light'):
                stats, card = render(data, theme)
                for svg in (stats, card):
                    ET.fromstring(svg)
                if len(projects) > 5:
                    root = ET.fromstring(card)
                    visible = ' '.join(e.text or '' for e in root.findall('{http://www.w3.org/2000/svg}text'))
                    self.assertNotIn('org/p5', visible)
                    self.assertIn('org/p6', project_links(data))
                if not projects:
                    self.assertIn('No merged external PRs yet.', card)
                if projects:
                    self.assertIn('https://github.com/', project_links(data))


if __name__ == '__main__':
    unittest.main()
