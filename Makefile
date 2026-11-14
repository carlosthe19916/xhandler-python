# The core (src/xhandler/_core/xhandler.wasm, src/xhandler/xbuilder/models.py and
# testdata/conformance) comes from xhandler-rust:
#
#   make sync CORE=<version>   the xhandler-rust v<version> release
#   make sync                  a checkout of xhandler-rust (RUST_REPO), for development
#   make verify-core           checks that the committed core is the one released as its VERSION
#   make verify-release TAG=v<version>
#                              what releasing <version> requires: the core of the xhandler-rust
#                              release of the same version
#
# The package version is the core's (src/xhandler/_core/VERSION).
RUST_REPO ?= ../xhandler-rust
CORE ?=
DIST := $(if $(CORE),.dist,$(RUST_REPO)/dist)

.PHONY: sync dist verify-core verify-release test lint

sync: dist
	cp $(DIST)/xhandler.wasm $(DIST)/VERSION src/xhandler/_core/
	cp $(DIST)/models/python/models.py src/xhandler/xbuilder/models.py
	rm -rf testdata/conformance && cp -r $(DIST)/conformance testdata/conformance
	$(if $(CORE),rm -rf $(DIST))

dist:
ifeq ($(CORE),)
	$(MAKE) -C $(RUST_REPO)/xhandler-wasm dist
else
	./hack/core.sh download $(CORE) $(DIST)
endif

verify-core:
	./hack/core.sh verify src/xhandler/_core/xhandler.wasm src/xhandler/_core/VERSION

verify-release:
	@test "v$$(cat src/xhandler/_core/VERSION)" = "$(TAG)" || { echo "error: the core is $$(cat src/xhandler/_core/VERSION), not $(TAG:v%=%): run make sync CORE=$(TAG:v%=%)" >&2; exit 1; }
	STRICT=true ./hack/core.sh verify src/xhandler/_core/xhandler.wasm src/xhandler/_core/VERSION

test:
	uv run pytest

lint:
	uv run ruff check
	uv run ruff format --check
	uv run mypy src
