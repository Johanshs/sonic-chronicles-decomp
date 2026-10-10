CC ?= cc
CFLAGS = -std=c99 -Wall -Wextra -O2 -Iinclude
# make test HERF_DIR=work/herf            (saída do run_all.sh)
# make test MANIFEST=saida/herf/_manifesto.json   (saída do sonic-dump)
MANIFEST ?= $(HERF_DIR)/_manifest.json

test: build/test_hash build/test_language build/test_movie_player build/stress_movie_player
	./build/test_language
	./build/test_movie_player
	./build/stress_movie_player
	python3 -I ../analise/tools/manifest_pairs.py $(MANIFEST) | ./build/test_hash

test_movie_player: build/test_movie_player
	./build/test_movie_player

test_stress: build/stress_movie_player
	./build/stress_movie_player

build/test_movie_player: src/movie_player.c tests/test_movie_player.c | build
	$(CC) $(CFLAGS) $^ -o $@

build/stress_movie_player: src/movie_player.c tests/stress_movie_player.c | build
	$(CC) $(CFLAGS) $^ -o $@

build/test_hash: src/resource_hash.c src/exo_string.c tests/test_hash.c | build
	$(CC) $(CFLAGS) $^ -o $@

build/test_language: src/language.c tests/test_language.c | build
	$(CC) $(CFLAGS) $^ -o $@

# Platform-neutral / Windows Smart App Control compatibility targets:
build/test_movie_player.dll: src/movie_player.c tests/test_movie_player.c | build
	$(CC) -shared $(CFLAGS) $^ -o $@

build/stress_movie_player.dll: src/movie_player.c tests/stress_movie_player.c | build
	$(CC) -shared $(CFLAGS) $^ -o $@

test_movie_player_dll: build/test_movie_player.dll
	python -c "import ctypes; dll = ctypes.CDLL(r'./build/test_movie_player.dll'); ret = dll.main(); exit(ret)"

test_stress_dll: build/stress_movie_player.dll
	python -c "import ctypes; dll = ctypes.CDLL(r'./build/stress_movie_player.dll'); ret = dll.main(); exit(ret)"

test_all_dll: test_movie_player_dll test_stress_dll

build:
	mkdir -p build

clean:
	rm -rf build

.PHONY: test test_movie_player test_stress test_movie_player_dll test_stress_dll test_all_dll clean
