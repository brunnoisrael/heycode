import base64
import datetime as dt
import json

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID

from heycode.relay.alexa_verify import AlexaVerifier, AlexaVerifyError

NOW = 1_800_000_000.0
SKILL = "amzn1.ask.skill.teste"
URL = "https://s3.amazonaws.com/echo.api/echo-api-cert-7.pem"


def _name(cn):
    return x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, cn)])


def _key():
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


def _when(offset_days):
    return dt.datetime.fromtimestamp(NOW, dt.UTC) + dt.timedelta(days=offset_days)


def make_ca():
    key = _key()
    cert = (
        x509.CertificateBuilder()
        .subject_name(_name("CA de teste"))
        .issuer_name(_name("CA de teste"))
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(_when(-30))
        .not_valid_after(_when(3650))
        .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
        .add_extension(x509.KeyUsage(True, False, False, False, False, True, True, False, False), critical=True)
        .add_extension(x509.SubjectKeyIdentifier.from_public_key(key.public_key()), critical=False)
        .sign(key, hashes.SHA256())
    )
    return key, cert


def make_leaf(ca_key, ca_cert, san="echo-api.amazon.com", start=-10, end=300):
    key = _key()
    b = (
        x509.CertificateBuilder()
        .subject_name(_name("echo-api.amazon.com"))
        .issuer_name(ca_cert.subject)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(_when(start))
        .not_valid_after(_when(end))
        .add_extension(x509.SubjectAlternativeName([x509.DNSName(san)]), critical=False)
        .add_extension(x509.ExtendedKeyUsage([ExtendedKeyUsageOID.SERVER_AUTH]), critical=False)
        .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
        .add_extension(x509.SubjectKeyIdentifier.from_public_key(key.public_key()), critical=False)
        .add_extension(x509.AuthorityKeyIdentifier.from_issuer_public_key(ca_key.public_key()), critical=False)
    )
    return key, b.sign(ca_key, hashes.SHA256())


def pem(*certs):
    return b"".join(c.public_bytes(serialization.Encoding.PEM) for c in certs)


def body_for(app_id=SKILL, ts_offset=0, **extra):
    ts = dt.datetime.fromtimestamp(NOW + ts_offset, dt.UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    return json.dumps(
        {
            "version": "1.0",
            "context": {"System": {"application": {"applicationId": app_id}}},
            "request": {"type": "LaunchRequest", "timestamp": ts, **extra},
        }
    ).encode()


def sign(leaf_key, body):
    sig = leaf_key.sign(body, padding.PKCS1v15(), hashes.SHA256())
    return base64.b64encode(sig).decode()


class Env:
    def __init__(self, **leaf_kw):
        self.ca_key, self.ca = make_ca()
        self.leaf_key, self.leaf = make_leaf(self.ca_key, self.ca, **leaf_kw)
        self.fetched = []

    def fetch(self, url):
        self.fetched.append(url)
        return pem(self.leaf, self.ca)  # cadeia: folha primeiro

    def verifier(self, **kw):
        return AlexaVerifier(SKILL, lambda: NOW, fetch=self.fetch, trust_roots=[self.ca], **kw)

    def headers(self, body, url=URL, signature=None):
        return {"signaturecertchainurl": url, "signature-256": signature or sign(self.leaf_key, body)}


@pytest.fixture
def env():
    return Env()


def test_requisicao_valida_passa_e_devolve_o_json(env):
    body = body_for()
    out = env.verifier().verify(env.headers(body), body)
    assert out["request"]["type"] == "LaunchRequest"


def test_cabecalhos_sao_lidos_sem_diferenciar_caixa(env):
    body = body_for()
    h = {"SignatureCertChainUrl": URL, "Signature-256": sign(env.leaf_key, body)}
    assert env.verifier().verify(h, body)["version"] == "1.0"


@pytest.mark.parametrize(
    "url",
    [
        "http://s3.amazonaws.com/echo.api/c.pem",  # sem TLS
        "https://evil.example.com/echo.api/c.pem",  # host de outro dono
        "https://s3.amazonaws.com.evil.example/echo.api/c.pem",  # host parecido
        "https://s3.amazonaws.com/outro/c.pem",  # caminho errado
        "https://s3.amazonaws.com/echo.api/../evil/c.pem",  # sai do diretorio
        "https://s3.amazonaws.com:8443/echo.api/c.pem",  # porta errada
        "https://user:senha@s3.amazonaws.com/echo.api/c.pem",  # credenciais na URL
        "https://s3.amazonaws.com@evil.example/echo.api/c.pem",  # truque de userinfo
        "ftp://s3.amazonaws.com/echo.api/c.pem",
        "",
    ],
)
def test_url_do_certificado_invalida_recusada_sem_buscar_nada(env, url):
    body = body_for()
    with pytest.raises(AlexaVerifyError) as e:
        env.verifier().verify(env.headers(body, url=url), body)
    assert e.value.code == "bad_cert_url"
    assert env.fetched == []  # nenhuma requisicao de rede para endereco nao confiavel


def test_porta_443_explicita_e_caixa_do_host_sao_aceitas(env):
    body = body_for()
    url = "https://S3.AMAZONAWS.COM:443/echo.api/echo-api-cert-7.pem"
    assert env.verifier().verify(env.headers(body, url=url), body)


def test_certificado_expirado_recusado():
    env = Env(start=-100, end=-1)
    body = body_for()
    with pytest.raises(AlexaVerifyError) as e:
        env.verifier().verify(env.headers(body), body)
    assert e.value.code == "bad_cert"


def test_certificado_ainda_nao_valido_recusado():
    env = Env(start=1, end=100)
    body = body_for()
    with pytest.raises(AlexaVerifyError):
        env.verifier().verify(env.headers(body), body)


def test_certificado_sem_echo_api_nos_nomes_recusado():
    env = Env(san="outro.example.com")
    body = body_for()
    with pytest.raises(AlexaVerifyError) as e:
        env.verifier().verify(env.headers(body), body)
    assert e.value.code == "bad_cert"


def test_cadeia_nao_confiavel_recusada(env):
    outra_ca_key, outra_ca = make_ca()
    v = AlexaVerifier(SKILL, lambda: NOW, fetch=env.fetch, trust_roots=[outra_ca])
    body = body_for()
    with pytest.raises(AlexaVerifyError) as e:
        v.verify(env.headers(body), body)
    assert e.value.code == "bad_cert"


def test_assinatura_sobre_outro_corpo_recusada(env):
    body = body_for()
    adulterado = body_for(app_id="amzn1.ask.skill.outra")
    with pytest.raises(AlexaVerifyError) as e:
        env.verifier().verify(env.headers(body), adulterado)
    assert e.value.code == "bad_signature"


def test_assinatura_de_outra_chave_recusada(env):
    body = body_for()
    outra = _key()
    with pytest.raises(AlexaVerifyError) as e:
        env.verifier().verify(env.headers(body, signature=sign(outra, body)), body)
    assert e.value.code == "bad_signature"


@pytest.mark.parametrize("sig", ["", "isto-nao-e-base64!!", "AAAA"])
def test_assinatura_ausente_ou_malformada_recusada(env, sig):
    body = body_for()
    h = env.headers(body)
    h["signature-256"] = sig
    with pytest.raises(AlexaVerifyError) as e:
        env.verifier().verify(h, body)
    assert e.value.code == "bad_signature"


def test_so_a_assinatura_sha1_antiga_nao_basta(env):
    body = body_for()
    h = {"signaturecertchainurl": URL, "signature": sign(env.leaf_key, body)}
    with pytest.raises(AlexaVerifyError) as e:
        env.verifier().verify(h, body)
    assert e.value.code == "bad_signature"


def test_timestamp_dentro_de_150s_passa_e_fora_e_recusado(env):
    for off in (-149, 149):
        body = body_for(ts_offset=off)
        assert env.verifier().verify(env.headers(body), body)
    for off in (-151, 151):
        body = body_for(ts_offset=off)
        with pytest.raises(AlexaVerifyError) as e:
            env.verifier().verify(env.headers(body), body)
        assert e.value.code == "stale_request"


def test_application_id_de_outra_skill_recusado(env):
    body = body_for(app_id="amzn1.ask.skill.de-outra-pessoa")
    with pytest.raises(AlexaVerifyError) as e:
        env.verifier().verify(env.headers(body), body)
    assert e.value.code == "wrong_application"


def test_application_id_da_sessao_tambem_e_aceito(env):
    ts = dt.datetime.fromtimestamp(NOW, dt.UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    body = json.dumps(
        {
            "session": {"application": {"applicationId": SKILL}},
            "request": {"type": "LaunchRequest", "timestamp": ts},
        }
    ).encode()
    assert env.verifier().verify(env.headers(body), body)["request"]["type"] == "LaunchRequest"


def test_requisicao_sem_application_id_recusada(env):
    ts = dt.datetime.fromtimestamp(NOW, dt.UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    body = json.dumps({"request": {"type": "LaunchRequest", "timestamp": ts}}).encode()
    with pytest.raises(AlexaVerifyError) as e:
        env.verifier().verify(env.headers(body), body)
    assert e.value.code == "wrong_application"


def test_corpo_que_nao_e_json_recusado(env):
    body = b"isto nao e json"
    with pytest.raises(AlexaVerifyError) as e:
        env.verifier().verify(env.headers(body), body)
    assert e.value.code == "bad_body"


def test_falha_ao_buscar_o_certificado_vira_erro_de_verificacao():
    env = Env()

    def quebra(url):
        raise OSError("sem rede")

    v = AlexaVerifier(SKILL, lambda: NOW, fetch=quebra, trust_roots=[env.ca])
    body = body_for()
    with pytest.raises(AlexaVerifyError) as e:
        v.verify(env.headers(body), body)
    assert e.value.code == "bad_cert"


def test_certificado_e_reaproveitado_do_cache(env):
    v = env.verifier()
    for _ in range(3):
        body = body_for()
        v.verify(env.headers(body), body)
    assert len(env.fetched) == 1


def test_certificado_em_cache_nao_vale_depois_de_expirar():
    env = Env(start=-10, end=1)
    clock = {"t": NOW}
    v = AlexaVerifier(SKILL, lambda: clock["t"], fetch=env.fetch, trust_roots=[env.ca])
    body = body_for()
    v.verify(env.headers(body), body)
    clock["t"] = NOW + 3 * 86400  # o certificado em cache venceu
    body2 = json.dumps(
        {
            "context": {"System": {"application": {"applicationId": SKILL}}},
            "request": {
                "type": "LaunchRequest",
                "timestamp": dt.datetime.fromtimestamp(clock["t"], dt.UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
            },
        }
    ).encode()
    with pytest.raises(AlexaVerifyError) as e:
        v.verify(env.headers(body2), body2)
    assert e.value.code == "bad_cert"
