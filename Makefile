CC ?= cc
CFLAGS ?= -std=c11 -O2 -Wall -Wextra -Werror -pedantic
CPPFLAGS ?= -Iinclude -D_POSIX_C_SOURCE=200809L
LDLIBS ?= -lsqlite3

.PHONY: all check clean bench-trajectory
all: build/kotze-core
build:
	mkdir -p build
build/kotze-core: src/main.c src/kotze.c include/kotze.h | build
	$(CC) $(CPPFLAGS) $(CFLAGS) src/main.c src/kotze.c -o $@ $(LDLIBS)
build/test-core: tests/test_core.c src/kotze.c include/kotze.h | build
	$(CC) $(CPPFLAGS) $(CFLAGS) tests/test_core.c src/kotze.c -o $@ $(LDLIBS)
build/test-trajectory: tests/test_trajectory.c src/kotze_trajectory.c include/kotze_trajectory.h | build
	$(CC) $(CPPFLAGS) $(CFLAGS) tests/test_trajectory.c src/kotze_trajectory.c -o $@
build/bench-trajectory: bench/trajectory_bench.c src/kotze_trajectory.c include/kotze_trajectory.h | build
	$(CC) $(CPPFLAGS) $(CFLAGS) bench/trajectory_bench.c src/kotze_trajectory.c -o $@
bench-trajectory: build/bench-trajectory
	./build/bench-trajectory
check: build/test-core build/test-trajectory build/kotze-core
	./build/test-core
	./build/test-trajectory
	python3 -m unittest discover -s tests -p "test_skill_grader.py" -v
	python3 -m unittest discover -s tests -p "test_gemma_worker.py" -v
	python3 -m unittest discover -s tests -p "test_verification_bridge.py" -v
	python3 -m unittest discover -s tests -p "test_verification_bridge_native.py" -v
	python3 -m unittest discover -s tests -p "test_host_controller.py" -v
	python3 -m unittest discover -s tests -p "test_confidential_grader.py" -v
	python3 -m unittest discover -s tests -p "test_receipt_contract.py" -v
	python3 -m unittest discover -s tests -p "test_isolation_probe.py" -v
	python3 -m unittest discover -s tests -p "test_worker_os_boundary.py" -v
	python3 -m unittest discover -s tests -p "test_secure_snapshot.py" -v
clean:
	rm -rf build
