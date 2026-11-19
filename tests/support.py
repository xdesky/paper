from unittest.mock import patch
from fastapi.testclient import TestClient as BaseClient
from backend.app import create_app as base_app

def create_app(*args, **kwargs):
    with patch.dict('os.environ', {'PPM_FREE_PROJECT_LIMIT': '1000'}):
        return base_app(*args, **kwargs)

class TestClient(BaseClient):
    __test__ = False
    def __enter__(self):
        super().__enter__()
        credentials = {'email':'pipeline@example.com','password':'pipeline-test-password'}
        r = self.post('/api/auth/register',json={**credentials,'display_name':'Pipeline test'})
        if r.status_code == 409:
            r = self.post('/api/auth/login',json=credentials)
        assert r.status_code in (200,201),r.text
        return self
