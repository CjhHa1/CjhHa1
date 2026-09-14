import sys
from pathlib import Path
import unittest
import xml.etree.ElementTree as ET

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from generate_stats import collect, render


class StatisticsTests(unittest.TestCase):
    def test_pagination_and_public_nonfork_scope(self):
        repo = dict(private=False, fork=False, language='Python', stargazers_count=2)
        calls = []
        def request(path):
            calls.append(path)
            if path == 'users/example':
                return dict(login='example', followers=3)
            if path.startswith('search/'):
                return dict(total_count=7, incomplete_results=False)
            if 'page=2' in path:
                return [dict(repo, private=True), dict(repo, fork=True, stargazers_count=500)]
            return [dict(repo) for _ in range(100)]
        data = collect('example', request)
        self.assertEqual(data['public_repos'], 101)
        self.assertEqual(data['stars'], 200)
        self.assertEqual(data['languages'], {'Python': 100})
        self.assertEqual(data['pull_requests'], 7)
        self.assertEqual(len(calls), 4)

    def test_incomplete_search_fails(self):
        def request(path):
            if path == 'users/example':
                return dict(login='example', followers=0)
            if path.startswith('search/'):
                return dict(total_count=2, incomplete_results=True)
            return []
        with self.assertRaises(RuntimeError):
            collect('example', request)

    def test_svg_escaping_empty_data_and_grouping(self):
        data = dict(username='example', updated='2026-09-14', public_repos=0,
                    stars=0, followers=0, pull_requests=0, languages={})
        for languages in ({}, {'A&B<': 3}, {str(i): 1 for i in range(9)}):
            data['languages'] = languages
            for theme in ('dark', 'light'):
                stats, langs = render(data, theme)
                for svg in (stats, langs):
                    ET.fromstring(svg)
                if len(languages) > 6:
                    self.assertIn('Other: 4 repositories', langs)
                if not languages:
                    self.assertIn('No language data', langs)


if __name__ == '__main__':
    unittest.main()
