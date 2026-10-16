"""Servicio LDAP contra un Active Directory simulado (MOCK_SYNC de ldap3):
búsqueda, verificación de contraseña y que cada conexión quede cerrada.
No se conecta a ningún AD real."""
import pytest
from ldap3 import MOCK_SYNC, OFFLINE_AD_2012_R2, Connection, Server
from ldap3.core.exceptions import LDAPBindError, LDAPException

from app.core import ldap as modulo

SERVICIO = "CN=svc-argonavis,OU=Servicios,DC=prueba,DC=pa"
USUARIO  = "CN=Juan Perez,OU=DTI,DC=prueba,DC=pa"


@pytest.fixture
def ad(monkeypatch):
    """ServicioLDAP sobre un AD en memoria. Devuelve (servicio, conexiones abiertas por él)."""
    servidor = Server("ad.prueba.pa", get_info=OFFLINE_AD_2012_R2)
    semilla = Connection(servidor, user=SERVICIO, password="svc", client_strategy=MOCK_SYNC)
    semilla.strategy.add_entry(SERVICIO, {"objectClass": ["top", "user"], "sAMAccountName": "svc-argonavis",
                                          "userPassword": "svc"})
    semilla.strategy.add_entry(USUARIO, {
        "objectClass": ["top", "person", "user"], "objectCategory": "person", "userAccountControl": 512,
        "sAMAccountName": "jperez", "cn": "Juan Perez", "givenName": "Juan", "sn": "Pérez",
        "mail": "jperez@prueba.pa", "department": "DTI", "userPassword": "Clave2026",
    })

    conexiones: list[Connection] = []

    def conexion_simulada(*args, **kwargs):
        c = Connection(*args, client_strategy=MOCK_SYNC, **kwargs)
        conexiones.append(c)
        return c

    monkeypatch.setattr(modulo, "Connection", conexion_simulada)
    for nombre, valor in {"LDAP_BIND_USER": SERVICIO, "LDAP_BIND_PASSWORD": "svc",
                          "LDAP_BASE_DN": "DC=prueba,DC=pa", "LDAP_ALLOWED_OU": ""}.items():
        monkeypatch.setattr(modulo.configuracion, nombre, valor)
    servicio = modulo.ServicioLDAP()
    servicio.servidor = servidor
    return servicio, conexiones


def test_busca_y_autentica(ad):
    servicio, conexiones = ad
    datos = servicio.buscar_usuario("jperez")
    assert datos["dn"] == USUARIO and datos["email"] == "jperez@prueba.pa" and datos["department"] == "DTI"
    assert servicio.buscar_usuario("no.existe") is None
    assert servicio.autenticar(USUARIO, "Clave2026") is True
    assert servicio.autenticar(USUARIO, "incorrecta") is False
    assert servicio.autenticar(USUARIO, "   ") is False
    assert servicio.buscar_usuarios_ad("") == []
    # El simulador no entiende el filtro extensible de AD (userAccountControl:1.2.840…):
    # sirve para comprobar que una búsqueda que falla también cierra su conexión.
    with pytest.raises(LDAPException):
        servicio.buscar_usuarios_ad("per")
    assert conexiones and all(c.closed for c in conexiones), "ninguna conexión queda abierta"


def test_cuenta_de_servicio_rechazada(ad, monkeypatch):
    servicio, conexiones = ad
    monkeypatch.setattr(modulo.configuracion, "LDAP_BIND_PASSWORD", "otra")
    with pytest.raises(LDAPBindError):
        servicio.buscar_usuario("jperez")
    assert all(c.closed for c in conexiones)
