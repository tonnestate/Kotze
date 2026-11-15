CC ?= cc
CFLAGS ?= -std=c11 -O2 -Wall -Wextra -Werror -pedantic
CPPFLAGS ?= -Iinclude -D_POSIX_C_SOURCE=200809L
LDLIBS ?= -lsqlite3

.PHONY: all native check-native check clean bench-trajectory acceptance check-submission check-public-eval submission notebook
all: build/kotze-core
native: build/libkotze-navigation.so build/libkotze-trajectory.so
check-native: native build/test-register build/test-async
	./build/test-register
	./build/test-async
build:
	mkdir -p build
build/kotze-core: src/main.c src/kotze.c include/kotze.h | build
	$(CC) $(CPPFLAGS) $(CFLAGS) src/main.c src/kotze.c -o $@ $(LDLIBS)
build/test-core: tests/test_core.c src/kotze.c include/kotze.h | build
	$(CC) $(CPPFLAGS) $(CFLAGS) tests/test_core.c src/kotze.c -o $@ $(LDLIBS)
build/kotze-register.o: src/kotze_register.c include/kotze_register.h | build
	$(CC) $(CPPFLAGS) $(CFLAGS) -fPIC -c src/kotze_register.c -o $@
build/kotze-async.o: src/kotze_async.c include/kotze_async.h include/kotze_register.h | build
	$(CC) $(CPPFLAGS) $(CFLAGS) -fPIC -pthread -c src/kotze_async.c -o $@
build/libkotze-navigation.a: build/kotze-register.o build/kotze-async.o
	ar rcs $@ build/kotze-register.o build/kotze-async.o
build/libkotze-navigation.so: build/kotze-register.o build/kotze-async.o
	$(CC) -shared -pthread -o $@ build/kotze-register.o build/kotze-async.o $(LDLIBS)
build/libkotze-trajectory.so: src/kotze_trajectory.c include/kotze_trajectory.h | build
	$(CC) $(CPPFLAGS) $(CFLAGS) -fPIC -shared src/kotze_trajectory.c -o $@
build/test-register: tests/test_register.c src/kotze.c src/kotze_register.c include/kotze.h include/kotze_register.h | build
	$(CC) $(CPPFLAGS) $(CFLAGS) tests/test_register.c src/kotze.c src/kotze_register.c -o $@ $(LDLIBS)
build/test-async: tests/test_async.c src/kotze.c src/kotze_register.c src/kotze_async.c include/kotze.h include/kotze_register.h include/kotze_async.h | build
	$(CC) $(CPPFLAGS) $(CFLAGS) -pthread tests/test_async.c src/kotze.c src/kotze_register.c src/kotze_async.c -o $@ $(LDLIBS) -pthread
build/test-trajectory: tests/test_trajectory.c src/kotze_trajectory.c include/kotze_trajectory.h | build
	$(CC) $(CPPFLAGS) $(CFLAGS) tests/test_trajectory.c src/kotze_trajectory.c -o $@
build/bench-trajectory: bench/trajectory_bench.c src/kotze_trajectory.c include/kotze_trajectory.h | build
	$(CC) $(CPPFLAGS) $(CFLAGS) bench/trajectory_bench.c src/kotze_trajectory.c -o $@
bench-trajectory: build/bench-trajectory
	./build/bench-trajectory
check: build/test-core build/test-trajectory build/test-register build/test-async build/libkotze-navigation.so build/libkotze-trajectory.so build/kotze-core
	./build/test-core
	./build/test-trajectory
	./build/test-register
	./build/test-async
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
	python3 -m unittest discover -s tests -p "test_verifier_service.py" -v
	python3 -m unittest discover -s tests -p "test_repair_agent.py" -v
	python3 -m unittest discover -s tests -p "test_turn_assurance.py" -v
	python3 -m unittest discover -s tests -p "test_navigation.py" -v
	python3 -m unittest discover -s tests -p "test_native_navigation.py" -v
	python3 -m unittest discover -s tests -p "test_native_async_recovery.py" -v
	python3 -m unittest discover -s tests -p "test_verified_skill_replay.py" -v
	python3 -m unittest discover -s tests -p "test_pinned_skill_pipeline.py" -v
	python3 -m unittest discover -s tests -p "test_verified_skills.py" -v
	python3 -m unittest discover -s tests -p "test_verified_sft.py" -v
	python3 -m unittest discover -s tests -p "test_trajectory_monitor.py" -v
	python3 -m unittest discover -s tests -p "test_integration_units.py" -v
# Live end-to-end acceptance A-J: root, Linux, Bubblewrap and two dedicated OS
# accounts required; reports BLOCKED (exit 77) instead of mocking isolation.
acceptance: build/kotze-core
	python3 tests/e2e/acceptance.py --provision-accounts
check-submission:
	python3 -m unittest discover -s tests -p 'test_submission_package.py' -v
	python3 -m unittest discover -s tests -p 'test_evaluate_submission.py' -v
check-public-eval:
	python3 -m unittest discover -s tests -p 'test_evaluate_submission.py' -v
submission:
	python3 tools/build_submission.py
notebook: submission
	python3 tools/build_kaggle_notebook.py
clean:
	rm -rf build
