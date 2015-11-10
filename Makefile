PY_FILES = $(shell find thinkhazard_processing -type f -name '*.py' 2> /dev/null)

.PHONY: all
all: help

.PHONY: help
help:
	@echo "Usage: make <target>"
	@echo
	@echo "Possible targets:"
	@echo
	@echo "- install                 Install thinkhazard"
	@echo "- check                   Check the code with flake8"
	@echo "- test                    Run the unit tests"
	@echo

.PHONY: install
install: .build/requirements.timestamp

.PHONY: check
check: flake8

.PHONY: flake8
flake8: .build/dev-requirements.timestamp .build/flake8.timestamp

.PHONY: test
test: .build/dev-requirements.timestamp
	.build/venv/bin/nosetests

.build/venv:
	mkdir -p $(dir $@)
	virtualenv .build/venv
	.build/venv/bin/pip install --upgrade pip

.build/dev-requirements.timestamp: .build/venv dev-requirements.txt
	mkdir -p $(dir $@)
	.build/venv/bin/pip install -r dev-requirements.txt > /dev/null 2>&1
	touch $@

.build/requirements.timestamp: .build/venv setup.py requirements.txt
	mkdir -p $(dir $@)
	.build/venv/bin/pip install -r requirements.txt
	touch $@

.build/flake8.timestamp: $(PY_FILES)
	mkdir -p $(dir $@)
	.build/venv/bin/flake8 $?
	touch $@

.PHONY: clean
clean:
	rm -f .build/flake8.timestamp

.PHONY: cleanall
cleanall:
	rm -rf .build
