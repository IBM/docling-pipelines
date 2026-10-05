# Absolute path to this Makefile's directory — used to invoke docker compose
# with an explicit -f so all targets work correctly regardless of where make
# is called from (repo root, CI, subdirectory, etc.).
MAKEFILE_DIR := $(abspath $(dir $(lastword $(MAKEFILE_LIST))))

# Repo root — two levels up from this Makefile's location.
# All bind-mount directories are created here so they land at the repo root
# after `git clone`, matching the ../../ paths in docker-compose.yml.
ROOT := $(abspath $(MAKEFILE_DIR)/../../)

COMPOSE := docker compose -f $(MAKEFILE_DIR)/docker-compose.yml

.PHONY: setup up down logs clean fix-perms

# Pre-create host-side data directories owned by UID 1000 (the docpipe user).
# Docker creates missing bind-mount directories as root:root, which UID 1000
# cannot write into. Running mkdir here — then chowning to 1000:0 when root —
# guarantees the container can read and write regardless of who runs make.
#
# Note: sample_flows is a source-tracked directory in the repo. The compose
# bind-mount (../../sample_flows) shadows the baked-in container copy with the
# host directory. If the host directory is empty on a fresh clone (e.g. because
# sample_flows/ exists as an empty dir in .gitignore), the bind-mount will hide
# the example flows. A warning is printed when this is detected.
setup:
	mkdir -p \
		$(ROOT)/data/job_stats_store_data \
		$(ROOT)/data/duckdb \
		$(ROOT)/logs \
		$(ROOT)/sample_projects
	@# Only create sample_flows dir if it does not already exist as a git-tracked dir.
	@if [ ! -d "$(ROOT)/sample_flows" ]; then \
		mkdir -p $(ROOT)/sample_flows; \
	elif [ -z "$$(ls -A $(ROOT)/sample_flows 2>/dev/null)" ]; then \
		echo "WARNING: $(ROOT)/sample_flows is empty."; \
		echo "         The compose bind-mount will shadow the container's built-in sample flows."; \
		echo "         Run 'git checkout -- sample_flows/' to restore them, or leave it empty."; \
	fi
	@if [ "$$(id -u)" = "0" ]; then \
		chown -R 1000:0 \
			$(ROOT)/data \
			$(ROOT)/logs \
			$(ROOT)/sample_flows \
			$(ROOT)/sample_projects; \
	fi

# Run setup automatically before bringing services up.
up: setup
	$(COMPOSE) up -d

down:
	$(COMPOSE) down

logs:
	$(COMPOSE) logs -f

# Remove containers, volumes, and generated runtime data directories.
# sample_flows is intentionally excluded — it is source-tracked and deleting it
# would remove committed flow JSON files from the working tree.
clean:
	$(COMPOSE) down -v
	rm -rf $(ROOT)/data $(ROOT)/logs $(ROOT)/sample_projects

# Fix ownership of bind-mount directories when Docker has already created them
# as root:root (e.g. after running docker compose up without make setup first).
# Symptoms: 403 on POST /projects, /flows, or /job_runs write operations.
fix-perms:
	$(COMPOSE) down
	@if [ "$$(id -u)" = "0" ]; then \
		chown -R 1000:0 \
			$(ROOT)/data $(ROOT)/logs $(ROOT)/sample_flows $(ROOT)/sample_projects; \
	else \
		sudo chown -R 1000:0 \
			$(ROOT)/data $(ROOT)/logs $(ROOT)/sample_flows $(ROOT)/sample_projects; \
	fi
	$(COMPOSE) up -d
