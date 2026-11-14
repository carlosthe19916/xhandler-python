# Contribuir a xhandler-python

xhandler-python es una capa delgada en Python sobre el
[núcleo xhandler](https://github.com/project-openubl/xhandler-rust). Crear, firmar, enrutar,
comprimir, armar las peticiones a la SUNAT y leer sus respuestas ocurre en Rust; Python solo envía
las peticiones HTTP. Los cambios a esa lógica van en xhandler-rust.

## Entorno

[uv](https://docs.astral.sh/uv/) y Python 3.10 o superior. `make sync` necesita además un checkout
de xhandler-rust junto a este (revisa
[su CONTRIBUTING.md](https://github.com/project-openubl/xhandler-rust/blob/main/CONTRIBUTING.md)).

```shell
uv sync
make test                                          # uv run pytest
make lint                                          # ruff check, ruff format --check, mypy
uv run pytest tests/test_xsender.py -k token       # un archivo, los tests que coinciden con un nombre
XHANDLER_E2E=true uv run pytest tests/test_e2e.py  # crea, firma y envía una factura a la SUNAT beta
```

## Estructura

| Ruta | |
|---|---|
| `src/xhandler/_core/` | Ejecuta el `xhandler.wasm` incrustado con [wasmtime](https://github.com/bytecodealliance/wasmtime-py): un pool de instancias y las llamadas JSON (`invoke`); `XhandlerError` y `ErrorKind` |
| `src/xhandler/xbuilder/` | `build`, `enrich`; `models.py` es generado (pydantic v2) |
| `src/xhandler/xsigner/` | `sign` y `SigningKey` |
| `src/xhandler/xsender/` | `FileSender` y `SunatClient` (httpx): timeouts, reintentos, caché de tokens OAuth de las guías; `models.py` tiene las entradas y respuestas |
| `tests/` | pytest; `conformance.py` lee el corpus |
| `testdata/conformance/` | El corpus, copiado desde xhandler-rust |

## Cómo funciona

El núcleo expone un solo punto de entrada JSON: la petición es `{"op", "input"}` y la respuesta
`{"ok": ...}` o `{"error": {"kind", "message"}}`. `_core` compila el módulo una vez y mantiene
instancias libres; una instancia atiende una llamada a la vez y se descarta si falla (un panic en el
núcleo).

`xsender` pide al núcleo la petición HTTP de cada llamada (op `request`), la envía con httpx y le
entrega la respuesta (op `parse`). Se encarga de lo que necesita IO: timeouts (30s/120s), un
reintento si la conexión falla, reintentos tras respuestas `rate_limited` (1s y 2s) y los tokens de
las guías (reutilizados hasta un minuto antes de expirar, un pedido a la vez, reintento con un token
nuevo ante HTTP 401).

## Archivos generados

Vienen de xhandler-rust y no se editan a mano:

- `src/xhandler/_core/xhandler.wasm` y `src/xhandler/_core/VERSION`
- `src/xhandler/xbuilder/models.py`
- `testdata/conformance/`

```shell
make sync RUST_REPO=../xhandler-rust    # corre make -C xhandler-wasm dist allá y los copia
```

Un cambio de modelos o de comportamiento empieza en xhandler-rust; luego `make sync` aquí, corrige
lo que señalen mypy o los tests y abre un PR con los archivos copiados.

## Tests

- `test_core.py`: cada caso del corpus por el punto de entrada JSON.
- `test_xbuilder.py`, `test_xsigner.py`: los casos del corpus a través de los modelos. Los modelos
  rechazan campos desconocidos, así que un modelo desactualizado falla aquí.
- `test_xsender.py`: una SUNAT falsa (`httpx.MockTransport`) responde con las respuestas del corpus:
  CDR, faults, rate limiting, tokens de guías, fallos de conexión.

## Convenciones

- Commits y títulos de PR con [Conventional Commits](https://www.conventionalcommits.org/)
  (`feat:`, `fix:`, `docs:`, `ci:`, `chore:`...); los cambios incompatibles llevan `!`.
- Checks requeridos: `lint` y `test` (Python 3.10 a 3.14 en Linux, 3.14 en macOS y Windows). Los
  PRs de Dependabot se fusionan solos cuando pasan.
- Los nombres siguen a las otras librerías (`FileSender`, `SunatClient`, `SigningKey`...):
  mantenlos alineados con Go y Java.

## Licencia

Al contribuir aceptas que tus contribuciones se distribuyan bajo la
[Apache License, Version 2.0](https://www.apache.org/licenses/LICENSE-2.0).
