CC ?= cc
CFLAGS = -std=c99 -Wall -Wextra -O2 -Iinclude
# make test HERF_DIR=work/herf            (saída do run_all.sh)
# make test MANIFEST=saida/herf/_manifesto.json   (saída do sonic-dump)
MANIFEST ?= $(HERF_DIR)/_manifest.json

test: build/test_hash build/test_language
	./build/test_language
	python3 -I ../analise/tools/manifest_pairs.py $(MANIFEST) | ./build/test_hash

build/test_hash: src/resource_hash.c src/exo_string.c tests/test_hash.c | build
	$(CC) $(CFLAGS) $^ -o $@
build/test_language: src/language.c tests/test_language.c | build
	$(CC) $(CFLAGS) $^ -o $@
build:
	mkdir -p build
clean:
	rm -rf build
.PHONY: test clean
