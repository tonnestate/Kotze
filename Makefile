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
check: build/test-core
	./build/test-core
clean:
	rm -rf build
