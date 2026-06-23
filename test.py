import unittest
import os
from bs4 import BeautifulSoup

class TestJenkinsDashboardHTML(unittest.TestCase):
    
    def setUp(self):
        # Ensure the HTML file is in the same directory and named 'index.html'
        file_path = os.path.join(os.path.dirname(__file__), 'index.html')
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                self.soup = BeautifulSoup(f, 'html.parser')
        except FileNotFoundError:
            self.fail("HTML file 'index.html' not found. Please ensure it is in the same directory.")

    def test_page_title(self):
        """Test if the correct page title is set"""
        title = self.soup.title.string
        self.assertEqual(title, "Jenkins CD Site v2")

    def test_required_badges_exist(self):
        """Test if all 3 pipeline status badges are present in the DOM"""
        badges = self.soup.find_all('span', class_='badge')
        self.assertEqual(len(badges), 3, "Expected exactly 3 badges on the dashboard")
        
        badge_texts = [badge.text.strip() for badge in badges]
        self.assertIn("✅ CI Passing", badge_texts)
        self.assertIn("🐳 Docker", badge_texts)
        self.assertIn("⚡ Auto-Deploy", badge_texts)

    def test_api_endpoints(self):
        """Test if all required Flask and Jenkins endpoint URLs are linked correctly"""
        links = [a['href'] for a in self.soup.find_all('a')]
        
        expected_endpoints = [
            "http://localhost:5000/",
            "http://localhost:5000/health",
            "http://localhost:5000/version",
            "http://localhost:8080"
        ]
        
        for endpoint in expected_endpoints:
            self.assertIn(endpoint, links, f"Missing required endpoint link: {endpoint}")

    def test_footer_text(self):
        """Test if the footer mentions the correct tech stack"""
        # Find the paragraph with the inline style used for the footer
        footer = self.soup.find('p', style=lambda value: value and 'font-size:0.8em' in value.replace(' ', ''))
        self.assertIsNotNone(footer, "Footer paragraph not found")
        self.assertIn("Flask", footer.text)
        self.assertIn("Docker", footer.text)
        self.assertIn("Jenkins", footer.text)

if __name__ == '__main__':
    unittest.main(verbosity=2)
