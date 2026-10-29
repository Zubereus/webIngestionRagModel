import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from fastapi.testclient import TestClient

from webrag.api import server
from webrag.store.catalog import StorageManager


class CollectionEndpointTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.storage = StorageManager(Path(self.temp_dir.name))
        self.vector_db = Mock()
        self.vector_db.client.list_collections.return_value = []
        self.vector_db.get_collection.side_effect = lambda name: self.vector_db.client.list_collections.return_value.append(
            SimpleNamespace(name=name)
        )
        self.storage_patch = patch.object(server, "storage", self.storage)
        self.vector_db_patch = patch.object(server, "vector_db", self.vector_db)
        self.storage_patch.start()
        self.vector_db_patch.start()
        self.client = TestClient(server.app)

    def tearDown(self):
        self.vector_db_patch.stop()
        self.storage_patch.stop()
        self.temp_dir.cleanup()

    def test_create_collection_and_list_it(self):
        response = self.client.post("/api/collections", json={"name": "Research Notes"})

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json(), {"name": "research_notes"})
        self.assertIn("research_notes", self.client.get("/api/collections").json()["collections"])
        self.vector_db.get_collection.assert_called_once_with("research_notes")

    def test_reject_invalid_collection_name(self):
        response = self.client.post("/api/collections", json={"name": "Bad!Name"})

        self.assertEqual(response.status_code, 400)
        self.vector_db.get_collection.assert_not_called()

    def test_reject_duplicate_collection(self):
        self.client.post("/api/collections", json={"name": "research_notes"})

        response = self.client.post("/api/collections", json={"name": "Research Notes"})

        self.assertEqual(response.status_code, 409)
