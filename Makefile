# RUST_REPO is a checkout of xhandler-rust; `make sync` copies what its
# `make -C xhandler-wasm dist` produced: the WebAssembly module, the generated
# models and the conformance corpus.
RUST_REPO ?= ../xhandler-rust
DIST := $(RUST_REPO)/dist

.PHONY: sync dist test lint

dist:
	$(MAKE) -C $(RUST_REPO)/xhandler-wasm dist

sync: dist
	cp $(DIST)/xhandler.wasm $(DIST)/VERSION src/xhandler/_core/
	cp $(DIST)/models/python/models.py src/xhandler/xbuilder/models.py
	rm -rf testdata/conformance && cp -r $(DIST)/conformance testdata/conformance

test:
	uv run pytest

lint:
	uv run ruff check
	uv run ruff format --check
	uv run mypy src
