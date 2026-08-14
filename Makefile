SHELL := bash
PYTHON := env python3

# Keep normal output focused on the tools being run. Use `make V=1` to retain
# the previous recipe-command echo behavior while debugging.
MAKEFLAGS += --no-print-directory
ifndef V
.SILENT:
endif

CLUSTER_NAME = beakerhub-dev
IMAGE_DIR = images
KIND_DIR = helm/kind
HELM_DIR = helm
KIND_VENV_DIR = $(KIND_DIR)/.venv
KIND_VENV_PYTHON = $(KIND_VENV_DIR)/bin/python
KIND_CONTEXT = kind-beakerhub-dev
REGISTRY_STORE = registry-store
REGISTRY_CONTAINER_NAME = beaker-local-registry
REGISTRY_URL = registry.beakerhub.internal

DNSMASQ_CONTAINER_NAME = beaker-local-dns
DNSMASQ_VOLUME_NAME = beaker-local-dns-config
DNSMASQ_PORT = 55353


.PHONY: sync
sync:${KIND_DIR}/kind-config.yaml
	echo "Syncing..."
	$(MAKE) upgrade-dev-cluster
	$(MAKE) build-dev-images
	$(MAKE) pull-images
	$(MAKE) rollout

.PHONY: pull-images
pull-images:
	images=`docker exec -it beakerhub-dev-control-plane crictl images -f "reference=${REGISTRY_URL}" | tail -n+2 | awk '{print $$1":"$$2}' | sort | uniq`; \
	for image in $$images; do \
		if [ ! $$( echo $$image | grep "\<none\>" ) ]; then \
			echo "Updating image on kubernetes node $$image..."; \
			docker exec -it beakerhub-dev-control-plane crictl pull $$image; \
		fi \
	done

$(KIND_VENV_DIR)/bin/activate:
	python3 -m venv $(KIND_VENV_DIR)
	$(KIND_VENV_PYTHON) -m pip install --quiet click pyyaml cryptography

${KIND_DIR}/kind-config.yaml: $(KIND_VENV_DIR)/bin/activate
	@$(KIND_VENV_PYTHON) ${KIND_DIR}/dev-setup.py update-kind-config "$(CLUSTER_NAME)"

${HELM_DIR}/values-secret.yaml: $(KIND_VENV_DIR)/bin/activate
	@VAULT_KEY="`$(KIND_VENV_PYTHON) -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'`"; \
	echo -e "secrets:\n  vaultEncryptionKey: $$VAULT_KEY" > ${HELM_DIR}/values-secret.yaml

.PHONY: dev-setup
dev-setup:${KIND_DIR}/kind-config.yaml ${HELM_DIR}/values-secret.yaml
	$(MAKE) create-dev-cluster DEFER_LOCAL_SUMMARY=1
	$(MAKE) dev-registry
	$(MAKE) dev-dns
	$(MAKE) update-dev-network DEFER_LOCAL_SUMMARY=1
	kubectl config set-context --current --namespace beakerhub >/dev/null
	$(MAKE) sync DEFER_LOCAL_SUMMARY=1
	$(MAKE) dev-setup-summary

.PHONY: dev-setup-summary
dev-setup-summary:
	printf '\nBeakerHub development setup complete.\n\n'
	printf 'Services:\n'
	printf '  BeakerHub:      https://beakerhub.internal\n'
	printf '  Vite server:    http://vite.beakerhub.internal\n'
	printf '  Registry:       https://$(REGISTRY_URL)\n'
	printf '  User sessions:  https://<session>.beakerhub.internal (when subdomain routing is enabled)\n\n'
	printf 'Local authentication (development only; credentials are not verified):\n'
	printf '  Username:       Any valid email address\n'
	printf '  Password:       Any non-empty value\n'
	printf '  Admin username: admin@example.com\n\n'
	printf 'Kubernetes:\n'
	printf '  Context:        $(KIND_CONTEXT)\n'
	printf '  Namespace:      beakerhub\n'
	if [ -f "$(HELM_DIR)/kind/certs.d/rootCA.pem" ]; then \
		printf '\nBrowser trust:\n'; \
		printf '  Import %s into your browser trust store.\n' \
			"$(abspath $(HELM_DIR)/kind/certs.d/rootCA.pem)"; \
		printf '  See docs/local-tls.md.\n'; \
	fi
	printf '\nDNS check:\n'
	printf '  dig @127.0.0.1 -p $(DNSMASQ_PORT) test.beakerhub.internal\n\n'

.PHONY: create-dev-cluster
create-dev-cluster:${KIND_DIR}/kind-config.yaml
	@kind get clusters | grep '^${CLUSTER_NAME}$$' > /dev/null 2>&1 && \
	echo "Skipping creation of the beakerhub cluster as it already exists" || \
	( \
		kind create cluster --config ${KIND_DIR}/kind-config.yaml && \
		$(MAKE) -C ${HELM_DIR} install-local \
	)

.PHONY: upgrade-dev-cluster
upgrade-dev-cluster:${KIND_DIR}/kind-config.yaml
	$(MAKE) -C ${HELM_DIR} upgrade-local

.PHONY: delete-dev-cluster
delete-dev-cluster:
	@echo "This will delete the kind cluster named '${CLUSTER_NAME}'."; \
	read -r -p "Are you sure? [y/N] " response && [[ "$${response:-N}" =~ ^([yY][eE][sS]|[yY])$$ ]] || exit 1; \
	kind delete cluster -n ${CLUSTER_NAME}

.PHONY: recreate-dev-cluster
recreate-dev-cluster:
	$(MAKE) delete-dev-cluster
	$(MAKE) dev-setup

CERT_DIR = $(KIND_DIR)/certs.d

.PHONY:dev-registry
dev-registry:
	docker container inspect ${REGISTRY_CONTAINER_NAME} >/dev/null 2>&1 || ( \
		docker run -d \
		-p 5000:5000 \
		-e PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION=python \
		-e DOLL_TLS_CERT=/certs/tls.crt \
		-e DOLL_TLS_KEY=/certs/tls.key \
		-e DOLL_REGISTRY=${REGISTRY_URL} \
		-e DOLL_FILTER_REGISTRY=true \
		-v "/var/run/docker.sock:/var/run/docker.sock" \
		-v "/run/containerd/containerd.sock:/run/containerd/containerd.sock" \
		-v "$(CURDIR)/$(CERT_DIR):/certs:ro" \
		--restart=always \
		--name ${REGISTRY_CONTAINER_NAME} \
		jataware/doll:latest >/dev/null \
	); \
	docker network inspect kind | grep "${REGISTRY_CONTAINER_NAME}" >/dev/null 2>&1 || ( \
		docker network connect --alias "${REGISTRY_URL}" kind ${REGISTRY_CONTAINER_NAME} \
	)

.PHONY: dev-dns
dev-dns:
	@docker volume inspect ${DNSMASQ_VOLUME_NAME} >/dev/null 2>&1 || \
		docker volume create ${DNSMASQ_VOLUME_NAME} >/dev/null
	@docker container inspect ${DNSMASQ_CONTAINER_NAME} >/dev/null 2>&1 || \
		docker run -d \
		-p ${DNSMASQ_PORT}:53/udp \
		-v ${DNSMASQ_VOLUME_NAME}:/etc/dnsmasq.d \
		--restart=always \
		--name ${DNSMASQ_CONTAINER_NAME} \
		andyshinn/dnsmasq \
		--server=8.8.8.8 >/dev/null

.PHONY: update-dev-network
update-dev-network:${KIND_DIR}/kind-config.yaml
	@cd ${KIND_DIR} && \
	DNSMASQ_CONTAINER_NAME=${DNSMASQ_CONTAINER_NAME} \
	DNSMASQ_PORT=${DNSMASQ_PORT} \
	./update-hosts.sh

.PHONY: build-dev-images
build-dev-images:${KIND_DIR}/kind-config.yaml
	REGISTRY="$(REGISTRY_URL)" $(MAKE) -C $(IMAGE_DIR) build

.PHONY: rollout
rollout:${KIND_DIR}/kind-config.yaml
	$(MAKE) -C ${HELM_DIR} rollout

.PHONY: clean-dev-registry
clean-dev-registry:
	@docker rm -f ${REGISTRY_CONTAINER_NAME} || true

.PHONY: clean-dev-dns
clean-dev-dns:
	@docker container inspect ${DNSMASQ_CONTAINER_NAME} >/dev/null 2>&1 && \
		docker rm -f ${DNSMASQ_CONTAINER_NAME} 2>/dev/null || true
	@docker volume inspect ${DNSMASQ_VOLUME_NAME} >/dev/null 2>&1 && \
		docker volume rm ${DNSMASQ_VOLUME_NAME} 2>/dev/null || true
	@echo "Note: You may need to manually remove resolver config:"
	@case "$$(uname -s)" in \
		Darwin*) \
			echo "  sudo rm /etc/resolver/beakerhub.internal" \
			;; \
		Linux*) \
			if systemctl is-active --quiet systemd-resolved 2>/dev/null; then \
				echo "  sudo rm /etc/systemd/resolved.conf.d/beakerhub.conf && sudo systemctl restart systemd-resolved"; \
			else \
				echo "  Remove the beakerhub.internal forwarding config from your DNS server (BIND9, dnsmasq, etc.)"; \
			fi \
			;; \
	esac

# Testing targets
.PHONY: test
test: test-python test-ui

.PHONY: test-python
test-python:
	$(PYTHON) -m pytest tests/unit -v

.PHONY: test-python-cov
test-python-cov:
	$(PYTHON) -m pytest tests/unit --cov=src/beakerhub --cov-report=term-missing

.PHONY: test-ui
test-ui:
	cd ui && npm run test:unit -- --run

.PHONY: test-e2e
test-e2e:
	cd ui && npm run test:e2e

.PHONY: test-integration
test-integration:
	$(PYTHON) -m pytest tests/integration -v

.PHONY: clean
clean:
	$(MAKE) delete-dev-cluster
	$(MAKE) -C ${HELM_DIR} clean
	$(MAKE) -C ${IMAGE_DIR} clean

.PHONY: full-clean
full-clean:
	$(MAKE) delete-dev-cluster
	$(MAKE) -C ${HELM_DIR} full-clean
	$(MAKE) -C ${IMAGE_DIR} full-clean
	$(MAKE) clean-dev-dns
	$(MAKE) clean-dev-registry
	docker image rm -f jataware/doll:latest andyshinn/dnsmasq >/dev/null 2>&1 || true


node_modules:package.json package-lock.json
	npm i

src/beakerhub/ui:node_modules
	npm run ui:build && \
	cp -r ui/dist src/beakerhub/ui

.PHONY: build
build:src/beakerhub/ui pyproject.toml
	hatch build