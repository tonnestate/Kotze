CC ?= cc
CFLAGS ?= -std=c11 -O2 -Wall -Wextra -Werror -pedantic -pthread
CPPFLAGS ?= -Iinclude -D_POSIX_C_SOURCE=200809L
LDLIBS ?= -lsqlite3 -pthread

.PHONY: all check clean
all: build/kotze-core
build:
	mkdir -p build
build/kotze-core: src/main.c src/kotze.c src/kotze_dispatch.c src/kotze_register.c src/kotze_async.c include/kotze.h include/kotze_dispatch.h include/kotze_register.h include/kotze_async.h | build
	$(CC) $(CPPFLAGS) $(CFLAGS) src/main.c src/kotze.c src/kotze_dispatch.c src/kotze_register.c src/kotze_async.c -o $@ $(LDLIBS)
build/test-core: tests/test_core.c src/kotze.c src/kotze_dispatch.c include/kotze.h include/kotze_dispatch.h | build
	$(CC) $(CPPFLAGS) $(CFLAGS) tests/test_core.c src/kotze.c src/kotze_dispatch.c -o $@ $(LDLIBS)
build/test-async: tests/test_async.c src/kotze.c src/kotze_register.c src/kotze_async.c include/kotze.h include/kotze_register.h include/kotze_async.h | build
	$(CC) $(CPPFLAGS) $(CFLAGS) tests/test_async.c src/kotze.c src/kotze_register.c src/kotze_async.c -o $@ $(LDLIBS)
build/test-register: tests/test_register.c src/kotze.c src/kotze_register.c include/kotze.h include/kotze_register.h | build
	$(CC) $(CPPFLAGS) $(CFLAGS) tests/test_register.c src/kotze.c src/kotze_register.c -o $@ $(LDLIBS)
build/test-dispatch: tests/test_dispatch.c src/kotze_dispatch.c include/kotze_dispatch.h | build
	$(CC) $(CPPFLAGS) $(CFLAGS) tests/test_dispatch.c src/kotze_dispatch.c -o $@ $(LDLIBS)
build/test-protocol: tests/test_protocol.c src/kotze_protocol.c include/kotze_protocol.h | build
	$(CC) $(CPPFLAGS) $(CFLAGS) tests/test_protocol.c src/kotze_protocol.c -o $@ $(LDLIBS)
check: build/test-core build/test-dispatch build/test-register build/test-async build/test-protocol
	./build/test-core
	./build/test-dispatch
	./build/test-register
	./build/test-async
	./build/test-protocol
	python3 -m unittest discover -s tests -p "test_skill_grader.py" -v
clean:
	rm -rf build
