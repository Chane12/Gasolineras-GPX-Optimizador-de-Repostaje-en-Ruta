# 0007 — Cifrado TLS heredado solo para el MITECO

- **Estado**: Aceptada
- **Fecha**: 2026-10-15

## Contexto

La descarga directa de precios del MITECO fallaba **siempre** desde Python con `SSLError: UNEXPECTED_EOF_WHILE_READING`, en local y en producción. Por eso la app dependía en la práctica de proxies públicos de terceros (`corsproxy.io` y otros), que veían y podían alterar los datos.

La causa: el servidor del MITECO solo negocia TLS 1.2 con `AES256-GCM-SHA384`, un cifrado con intercambio de claves RSA y sin secreto hacia adelante. Desde Python 3.10, la configuración TLS por defecto excluye esos cifrados. curl sí los admite, y por eso descarga sin problemas.

## Decisión

Para las peticiones a `https://sedeaplicaciones.minetur.gob.es/` (y solo para ese host), se usa la configuración TLS por defecto de Python **más** el cifrado `AES256-GCM-SHA384`. El certificado y el nombre del host se siguen verificando. Está implementado con un adaptador de `requests` montado solo sobre ese prefijo (`miteco_ssl_context()` en `core/.../ingestion/miteco.py`).

## Alternativas consideradas

- **Seguir con los proxies públicos**: un tercero ve y puede alterar los precios. Además, son frágiles. La API no los usará (ADR 0005).
- **Bajar la seguridad TLS de todo el proceso** (`@SECLEVEL=1` o los cifrados heredados para cualquier host): afectaría a todas las conexiones, no solo al MITECO.
- **Descargar con curl en un subproceso**: añade una dependencia del sistema y complica el manejo de errores.

## Consecuencias

- La conexión con el MITECO no tiene secreto hacia adelante. Es aceptable porque los datos son públicos y no enviamos nada sensible, y la autenticidad la sigue garantizando el certificado.
- La descarga directa tarda unos 3–4 s. Los proxies quedan solo como último recurso de la app Streamlit.
- Si el MITECO moderniza su TLS, este ajuste no molesta: los cifrados por defecto siguen incluidos y tienen prioridad. Se podrá retirar entonces.
- Hay un test con red (`@pytest.mark.network`) que hace la negociación real y avisa si algo cambia.
