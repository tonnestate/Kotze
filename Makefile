CC ?= cc
CFLAGS ?= -std=c11 -O2 -Wall -Wextra -Werror -pedantic
CPPFLAGS ?= -Iinclude -D_POSIX_C_SOURCE=200809L
LDLIBS ?= -lsqlite3

.PHONY: all check clean
all: build/kotze-core
build:
	mkdir -p build
build/kotze-core: src/main.c src/kotze.c include/kotze.h | build
	$(CC) $(CPPFLAGS) $(CFLAGS) src/main.c src/kotze.c -o $@ $(LDLIBS)
build/test-core: tests/test_core.c src/kotze.c include/kotze.h | build
	$(CC) $(CPPFLAGS) $(CFLAGS) tests/test_core.c src/kotze.c -o $@ $(LDLIBS)
check: build/test-core build/kotze-core
	./build/test-core
	python3 -m unittest discover -s tests -p "test_skill_grader.py" -v
	python3 -m unittest discover -s tests -p "test_gemma_worker.py" -v
	python3 -m unittest discover -s tests -p "test_verification_bridge.py" -v
	python3 -m unittest discover -s tests -p "test_verification_bridge_native.py" -v
clean:
	rm -rf build
