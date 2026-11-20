"""Run on Windows: python -m unittest -v test_security.py
Flask test client exercises a fresh TEMPORARY database; real data is untouched.
"""
import os
import tempfile
import unittest
from pathlib import Path

try:
    from app import app, init_db, get_db
except ImportError:
    app = None

@unittest.skipIf(app is None, 'Flask and Pillow are required; install requirements.txt')
class ApiSecurityTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = str(Path(self.tmp.name) / 'test.db')
        self.original = app.config['DATABASE']
        app.config.update(DATABASE=self.db, TESTING=True)
        init_db()
        self.alice = app.test_client()
        self.bob = app.test_client()
        self.guest = app.test_client()
        self.register(self.alice, 'Alice Student', 'alice@example.edu')
        self.register(self.bob, 'Bob Student', 'bob@example.edu')

    def tearDown(self):
        app.config['DATABASE'] = self.original
        self.tmp.cleanup()

    def register(self, client, name, email):
        res = client.post('/api/register', json={'fullName':name,'email':email,
                  'password':'ASecretPass123!', 'confirmPassword':'ASecretPass123!', 'agreement':True})
        self.assertEqual(res.status_code, 201, res.get_json())

    def report(self, client, kind='found'):
        from datetime import date
        res = client.post(
            '/api/reports',
            data={
                'kind': kind,
                'title': 'Gold necklace',
                'category': 'Jewelry',
                'color': 'Gold',
                'location': 'Library',
                'event_date': date.today().isoformat(),
                'description': 'Found a golden necklace near library',
            },
            content_type='multipart/form-data',
        )
        self.assertEqual(res.status_code, 201, res.get_json())
        return res.get_json()['id']
    def test_anonymous_access_blocked(self):
        self.assertEqual(self.guest.get('/api/me').status_code, 401)
        self.assertEqual(self.guest.get('/api/claims').status_code, 401)
        self.assertEqual(self.guest.get('/api/notifications').status_code, 401)
        self.assertEqual(self.guest.get('/api/matches').status_code, 401)

    def test_nonadmin_cannot_moderate(self):
        rid=self.report(self.alice)
        self.assertEqual(self.bob.get('/api/admin/overview').status_code,403)
        res=self.bob.post(f'/api/admin/reports/{rid}/resolve',json={'reason':'Not appropriate'})
        self.assertEqual(res.status_code,403)

    def test_cannot_modify_other_students_report(self):
        rid=self.report(self.alice)
        res=self.bob.patch(f'/api/reports/{rid}',json={'status':'resolved'})
        self.assertEqual(res.status_code,404)
        self.assertEqual(self.alice.get(f'/api/reports/{rid}').get_json()['report']['status'],'open')

    def test_claim_conversation_private(self):
        rid=self.report(self.alice)
        res=self.bob.post(f'/api/reports/{rid}/claims',json={'proof':'I know a hidden scratch on the clasp'})
        self.assertEqual(res.status_code,201,res.get_json())
        claim_id=res.get_json()['id']
        self.assertEqual(self.guest.get(f'/api/claims/{claim_id}').status_code,401)
        self.assertEqual(self.guest.post(f'/api/claims/{claim_id}/messages',json={'body':'hello'}).status_code,401)
        self.assertEqual(self.bob.patch(f'/api/claims/{claim_id}',json={'status':'accepted'}).status_code,403)
        self.assertEqual(self.alice.patch(f'/api/claims/{claim_id}',json={'status':'accepted'}).status_code,200)
        self.assertEqual(self.bob.post(f'/api/claims/{claim_id}/messages',json={'body':'Hello'}).status_code,201)
        self.assertEqual(self.alice.get(f'/api/claims/{claim_id}').get_json()['messages'][0]['body'],'Hello')

    def test_third_party_cannot_read_conversation(self):
        rid=self.report(self.alice)
        claim_id=self.bob.post(f'/api/reports/{rid}/claims',json={'proof':'It has special engraved initials'}).get_json()['id']
        charlie=app.test_client()
        self.register(charlie,'Charlie Student','charlie@example.edu')
        self.assertEqual(charlie.get(f'/api/claims/{claim_id}').status_code,404)
        self.assertEqual(charlie.post(f'/api/claims/{claim_id}/messages',json={'body':'hello'}).status_code,404)

    def test_origin_restriction_and_headers(self):
        res=self.alice.post('/api/logout',json={},headers={'Origin':'https://attacker.example'})
        self.assertEqual(res.status_code,403)
        res=self.alice.get('/api/me')
        self.assertEqual(res.headers.get('X-Content-Type-Options'),'nosniff')
        self.assertEqual(res.headers.get('Cache-Control'),'no-store')
        self.assertEqual(res.headers.get('X-Frame-Options'),'DENY')

    def test_other_students_notifications_hidden(self):
        rid=self.report(self.alice)
        self.bob.post(f'/api/reports/{rid}/claims',json={'proof':'The clasp has distinctive engravings'})
        self.assertGreaterEqual(self.alice.get('/api/notifications').get_json()['unread'],1)
        self.assertEqual(self.bob.get('/api/notifications').get_json()['unread'],0)

if __name__ == '__main__': unittest.main()
