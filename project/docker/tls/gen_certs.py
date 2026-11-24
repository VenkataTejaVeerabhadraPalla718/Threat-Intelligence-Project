import ipaddress
from datetime import datetime, timedelta, timezone
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

OUT = Path(__file__).parent / "certs"
OUT.mkdir(exist_ok=True)


def new_key():
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


def name(cn):
    return x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, cn)])


def key_pem(k):
    return k.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.TraditionalOpenSSL,
                           serialization.NoEncryption())


def cert_pem(c):
    return c.public_bytes(serialization.Encoding.PEM)


def make(cn, key, issuer_cn, issuer_key, ca=False, san=None):
    now = datetime.now(timezone.utc)
    b = (x509.CertificateBuilder().subject_name(name(cn)).issuer_name(name(issuer_cn))
         .public_key(key.public_key()).serial_number(x509.random_serial_number())
         .not_valid_before(now).not_valid_after(now + timedelta(days=365))
         .add_extension(x509.BasicConstraints(ca=ca, path_length=None), critical=True))
    if san:
        b = b.add_extension(x509.SubjectAlternativeName(san), critical=False)
    return b.sign(issuer_key, hashes.SHA256())


ca_key = new_key()
ca = make("MongoDB-CA", ca_key, "MongoDB-CA", ca_key, ca=True)
srv_key = new_key()
srv = make("localhost", srv_key, "MongoDB-CA", ca_key,
           san=[x509.DNSName("localhost"), x509.IPAddress(ipaddress.ip_address("127.0.0.1"))])
cli_key = new_key()
cli = make("cti-client", cli_key, "MongoDB-CA", ca_key)

(OUT / "ca.crt").write_bytes(cert_pem(ca))
(OUT / "server.pem").write_bytes(key_pem(srv_key) + cert_pem(srv))
(OUT / "client.pem").write_bytes(key_pem(cli_key) + cert_pem(cli))
print("certs written to", OUT, "| chain: MongoDB-CA -> server (localhost), client (cti-client)")