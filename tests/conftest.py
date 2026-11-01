"""Throwaway local MongoDB (Docker mongo:8) for the A4 design-builder tests. Nothing here touches Atlas."""
import shutil, subprocess, time
import pytest
from pymongo import MongoClient

PORT, NAME = 27020, "a4-mongo-test"
URI = f"mongodb://localhost:{PORT}/"


@pytest.fixture(scope="session")
def local_mongo():
    if not shutil.which("docker") or subprocess.run(["docker", "info"], capture_output=True).returncode:
        pytest.skip("Docker is not running")
    subprocess.run(["docker", "rm", "-f", NAME], capture_output=True)
    subprocess.run(["docker", "run", "-d", "--rm", "--name", NAME, "-p", f"{PORT}:27017", "mongo:8"],
                   check=True, capture_output=True)
    client = MongoClient(URI, serverSelectionTimeoutMS=1000)
    for _ in range(60):
        try:
            client.admin.command("ping"); break
        except Exception:
            time.sleep(0.5)
    yield client
    client.close()
    subprocess.run(["docker", "stop", NAME], capture_output=True)
