import unittest
from app import app

class Phase8RoutesTest(unittest.TestCase):
    def setUp(self):
        self.app = app.test_client()
        self.app.testing = True

    def test_notifications_redirect(self):
        response = self.app.get('/notifications/')
        self.assertEqual(response.status_code, 302)

    def test_follow_redirect(self):
        response = self.app.post('/follow/fake-id')
        self.assertEqual(response.status_code, 302)

    def test_typing_redirect(self):
        response = self.app.post('/realtime/typing')
        self.assertEqual(response.status_code, 302)

    def test_home(self):
        response = self.app.get('/')
        self.assertEqual(response.status_code, 200)

    def test_messages(self):
        response = self.app.get('/messages/')
        self.assertEqual(response.status_code, 302)

    def test_marketplace(self):
        response = self.app.get('/marketplace/')
        self.assertEqual(response.status_code, 200)

if __name__ == '__main__':
    unittest.main()
