"""Lab 12.2: verify TLS is mandatory and a trusted client certificate can connect."""
import os
from pathlib import Path
from pymongo import MongoClient
from pymongo.errors import PyMongoError, ServerSelectionTimeoutError

ROOT = Path(__file__).resolve().parents[2]
CERTS = Path(os.getenv("LAB12_TLS_CERT_DIR", str(ROOT / "docker" / "tls" / "certs")))
HOST = os.getenv("LAB12_TLS_HOST", "host.docker.internal")
PORT = int(os.getenv("LAB12_TLS_PORT", "27201"))
CA = CERTS / "ca.crt"
CLIENT = CERTS / "client.pem"

def main():
    if not CA.is_file() or not CLIENT.is_file():
        raise SystemExit(f"TLS certificates missing: expected {CA} and {CLIENT}")
    print(f"TLS target: {HOST}:{PORT}", flush=True)
    print("1) Verify plaintext is rejected by the TLS-only server", flush=True)
    try:
        MongoClient(HOST, PORT, serverSelectionTimeoutMS=2500).admin.command("ping")
        raise RuntimeError("Plaintext unexpectedly connected; TLS-only requirement is not enforced.")
    except PyMongoError as exc:
        print(f"   PASS: plaintext rejected ({type(exc).__name__})", flush=True)
    print("2) Verify trusted TLS client connection", flush=True)
    client = MongoClient(HOST, PORT, tls=True, tlsCAFile=str(CA),
                         tlsCertificateKeyFile=str(CLIENT), serverSelectionTimeoutMS=8000)
    try:
        client.admin.command("ping")
        result = client.cti_tls.lab12_verification.insert_one({"test": "tls", "verified": True})
        print(f"   PASS: TLS ping and authenticated certificate connection; inserted id={result.inserted_id}", flush=True)
    finally:
        client.close()
    print("LAB 12.2 PASSED", flush=True)

if __name__ == "__main__":
    main()
