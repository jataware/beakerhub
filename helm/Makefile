SHELL := /bin/bash

MAKEFLAGS += --no-print-directory
ifndef V
.SILENT:
endif

HELM ?= helm
KUBECTL ?= kubectl

CHART_NAME := beakerhub
CHART_DIR := ./$(CHART_NAME)
RELEASE_NAME ?= beakerhub
NAMESPACE ?= beakerhub
LOCAL_CONTEXT ?= kind-beakerhub-dev

LOCAL_VALUES_FILE := ./values-local.yaml
LOCAL_SECRET_VALUES_FILE := ./values-secret.yaml
LOCAL_HELM_FLAGS := \
	--kube-context $(LOCAL_CONTEXT) \
	--namespace $(NAMESPACE) \
	--values $(LOCAL_VALUES_FILE) \
	--values $(LOCAL_SECRET_VALUES_FILE)

CERT_DIR := ./kind/certs.d
CERT_CRT := $(CERT_DIR)/tls.crt
CERT_KEY := $(CERT_DIR)/tls.key
CA_CRT := $(CERT_DIR)/rootCA.pem
CA_KEY := $(CERT_DIR)/rootCA-key.pem

COLOR_RESET := \033[0m
COLOR_BOLD := \033[1m
COLOR_GREEN := \033[32m
COLOR_BLUE := \033[34m

.DEFAULT_GOAL := help

.PHONY: help
help: ## Show available targets
	@echo -e "$(COLOR_BOLD)BeakerHub Helm targets$(COLOR_RESET)"
	@echo ""
	@echo "Usage: make -C helm [target]"
	@echo ""
	@grep -E '^[a-zA-Z0-9_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  $(COLOR_GREEN)%-22s$(COLOR_RESET) %s\n", $$1, $$2}'

# Chart validation and generic release operations

.PHONY: lint
lint: ## Lint the Helm chart
	@echo -e "$(COLOR_BLUE)Linting the Helm chart...$(COLOR_RESET)"
	@$(HELM) lint $(CHART_DIR)

.PHONY: template
template: ## Render manifests with generic defaults
	@$(HELM) template $(RELEASE_NAME) $(CHART_DIR) --namespace $(NAMESPACE)

.PHONY: validate
validate: lint ## Lint and verify that the chart renders
	@$(HELM) template $(RELEASE_NAME) $(CHART_DIR) \
		--namespace $(NAMESPACE) >/dev/null
	@echo -e "$(COLOR_GREEN)Chart validation complete.$(COLOR_RESET)"

.PHONY: dry-run
dry-run: ## Perform a dry-run install with generic defaults
	@$(HELM) upgrade --install $(RELEASE_NAME) $(CHART_DIR) \
		--namespace $(NAMESPACE) \
		--create-namespace \
		--dry-run \
		--debug

.PHONY: install
install: ## Install or upgrade with generic defaults
	@$(HELM) upgrade --install $(RELEASE_NAME) $(CHART_DIR) \
		--namespace $(NAMESPACE) \
		--create-namespace

.PHONY: upgrade
upgrade: ## Upgrade an existing release with generic defaults
	@$(HELM) upgrade $(RELEASE_NAME) $(CHART_DIR) --namespace $(NAMESPACE)

.PHONY: uninstall
uninstall: ## Uninstall the release
	@$(HELM) uninstall $(RELEASE_NAME) --namespace $(NAMESPACE)

.PHONY: package
package: ## Package the chart under helm/packages
	@mkdir -p packages
	@$(HELM) package $(CHART_DIR) --destination packages

# Local kind deployment

.PHONY: check-local-config
check-local-config: ## Verify required local values files exist
	@test -f $(LOCAL_VALUES_FILE) || { \
		echo "Missing $(LOCAL_VALUES_FILE)."; \
		exit 1; \
	}
	@test -f $(LOCAL_SECRET_VALUES_FILE) || { \
		echo "Missing $(LOCAL_SECRET_VALUES_FILE). Run 'make dev-setup' from the repository root."; \
		exit 1; \
	}

.PHONY: check-local-prereqs
check-local-prereqs: check-local-config ## Verify tools required by the local install
	@for tool in $(HELM) $(KUBECTL); do \
		command -v $$tool >/dev/null 2>&1 || { \
			echo "Required command '$$tool' was not found on PATH."; \
			exit 1; \
		}; \
	done
	@if [ ! -f $(CERT_CRT) ] || [ ! -f $(CERT_KEY) ]; then \
		command -v mkcert >/dev/null 2>&1 || { \
			echo "mkcert is required to generate locally trusted development certificates."; \
			echo "Install it before running make dev-setup; see docs/QUICKSTART.md."; \
			exit 1; \
		}; \
		if [ "$$(uname -s)" = "Linux" ] && ! command -v certutil >/dev/null 2>&1; then \
			echo "certutil was not found. mkcert needs the NSS tools to install its CA for browsers."; \
			echo "Debian/Ubuntu: sudo apt install libnss3-tools"; \
			echo "Fedora/RHEL:   sudo dnf install nss-tools"; \
			echo "Arch Linux:    sudo pacman -S nss"; \
			exit 1; \
		fi; \
	fi

.PHONY: install-local
install-local: check-local-prereqs ## Install or upgrade the local kind release
	@if ! $(KUBECTL) get namespace metallb-system >/dev/null 2>&1; then \
		$(MAKE) install-metallb; \
	fi
	@if ! $(KUBECTL) get namespace ingress-nginx >/dev/null 2>&1; then \
		$(MAKE) install-ingress; \
	fi
	@$(KUBECTL) create namespace $(NAMESPACE) \
		--dry-run=client -o yaml | $(KUBECTL) apply -f -
	@$(MAKE) install-certs
	@$(HELM) upgrade --install $(RELEASE_NAME) $(CHART_DIR) \
		$(LOCAL_HELM_FLAGS) \
		--create-namespace
	@if [ "$(DEFER_LOCAL_SUMMARY)" != "1" ]; then \
		echo -e "$(COLOR_GREEN)Local BeakerHub release installed.$(COLOR_RESET)"; \
		echo "Application: https://beakerhub.internal"; \
		echo "Vite:       http://vite.beakerhub.internal"; \
	fi

.PHONY: upgrade-local
upgrade-local: check-local-config ## Upgrade the local kind release
	@$(HELM) upgrade $(RELEASE_NAME) $(CHART_DIR) $(LOCAL_HELM_FLAGS)

.PHONY: rollout
rollout: ## Restart local BeakerHub deployments
	@$(KUBECTL) --context $(LOCAL_CONTEXT) rollout restart deployment \
		--namespace $(NAMESPACE)

# Release inspection

.PHONY: status
status: ## Show release status
	@$(HELM) status $(RELEASE_NAME) --namespace $(NAMESPACE)

.PHONY: list
list: ## List releases in the namespace
	@$(HELM) list --namespace $(NAMESPACE)

.PHONY: get-all
get-all: ## Show all release information
	@$(HELM) get all $(RELEASE_NAME) --namespace $(NAMESPACE)

.PHONY: get-values
get-values: ## Show user-supplied release values
	@$(HELM) get values $(RELEASE_NAME) --namespace $(NAMESPACE)

.PHONY: history
history: ## Show release history
	@$(HELM) history $(RELEASE_NAME) --namespace $(NAMESPACE)

.PHONY: rollback
rollback: ## Roll back to the previous release revision
	@$(HELM) rollback $(RELEASE_NAME) --namespace $(NAMESPACE)

# Kubernetes inspection

.PHONY: pods
pods: ## List BeakerHub pods
	@$(KUBECTL) get pods --namespace $(NAMESPACE)

.PHONY: services
services: ## List BeakerHub services
	@$(KUBECTL) get services --namespace $(NAMESPACE)

.PHONY: logs-hub
logs-hub: ## Follow hub logs
	@$(KUBECTL) logs -l app.kubernetes.io/component=hub \
		--namespace $(NAMESPACE) --tail=100 -f

.PHONY: logs-proxy
logs-proxy: ## Follow proxy logs
	@$(KUBECTL) logs -l app.kubernetes.io/component=proxy \
		--namespace $(NAMESPACE) --tail=100 -f

.PHONY: describe-hub
describe-hub: ## Describe hub pods
	@$(KUBECTL) describe pod -l app.kubernetes.io/component=hub \
		--namespace $(NAMESPACE)

.PHONY: describe-proxy
describe-proxy: ## Describe proxy pods
	@$(KUBECTL) describe pod -l app.kubernetes.io/component=proxy \
		--namespace $(NAMESPACE)

.PHONY: get-url
get-url: ## Print the proxy LoadBalancer address
	@ADDRESS="$$($(KUBECTL) get service beakerhub-proxy \
		--namespace $(NAMESPACE) \
		-o jsonpath='{.status.loadBalancer.ingress[0].ip}' 2>/dev/null)"; \
	if [ -z "$$ADDRESS" ]; then \
		ADDRESS="$$($(KUBECTL) get service beakerhub-proxy \
			--namespace $(NAMESPACE) \
			-o jsonpath='{.status.loadBalancer.ingress[0].hostname}' 2>/dev/null)"; \
	fi; \
	if [ -n "$$ADDRESS" ]; then \
		echo "$$ADDRESS"; \
	else \
		echo "LoadBalancer address is not assigned."; \
		exit 1; \
	fi

.PHONY: port-forward
port-forward: ## Forward the proxy to http://localhost:8080
	@echo "Press Ctrl+C to stop."
	@$(KUBECTL) port-forward service/beakerhub-proxy 8080:80 \
		--namespace $(NAMESPACE)

# Local networking and certificates

.PHONY: install-metallb
install-metallb: ## Install MetalLB in the kind cluster
	@./kind/install-metallb-kind.sh

.PHONY: install-ingress
install-ingress: ## Install ingress-nginx in the kind cluster
	@./kind/install-ingress-kind.sh

.PHONY: install-certs
install-certs: ## Generate mkcert certificates and install the TLS secret
	@if [ ! -f $(CERT_CRT) ] || [ ! -f $(CERT_KEY) ]; then \
		command -v mkcert >/dev/null 2>&1 || { \
			echo "mkcert was not found. Install it before running this target."; \
			exit 1; \
		}; \
		mkdir -p $(CERT_DIR); \
		mkcert -install; \
		mkcert -cert-file $(CERT_CRT) -key-file $(CERT_KEY) \
			"beakerhub.internal" "*.beakerhub.internal"; \
		cp "$$(mkcert -CAROOT)/rootCA.pem" $(CA_CRT); \
	fi
	@$(MAKE) install-certs-secret

.PHONY: openssl-certs
openssl-certs: ## Generate local TLS certificates with OpenSSL
	@command -v openssl >/dev/null 2>&1 || { \
		echo "openssl was not found on PATH."; \
		exit 1; \
	}
	@mkdir -p $(CERT_DIR)
	@if [ ! -f $(CA_CRT) ] || [ ! -f $(CA_KEY) ]; then \
		openssl req -x509 -newkey rsa:4096 -nodes -days 3650 \
			-keyout $(CA_KEY) -out $(CA_CRT) \
			-subj "/CN=BeakerHub Local Dev CA/O=BeakerHub" \
			-addext "basicConstraints=critical,CA:TRUE" \
			-addext "keyUsage=critical,keyCertSign,cRLSign"; \
	fi
	@openssl req -newkey rsa:2048 -nodes \
		-keyout $(CERT_KEY) -out $(CERT_DIR)/tls.csr \
		-subj "/CN=beakerhub.internal"
	@printf 'subjectAltName=DNS:beakerhub.internal,DNS:*.beakerhub.internal\nbasicConstraints=CA:FALSE\nkeyUsage=critical,digitalSignature,keyEncipherment\nextendedKeyUsage=serverAuth\n' \
		> $(CERT_DIR)/leaf.ext
	@openssl x509 -req -in $(CERT_DIR)/tls.csr \
		-CA $(CA_CRT) -CAkey $(CA_KEY) -CAcreateserial \
		-out $(CERT_CRT) -days 825 -extfile $(CERT_DIR)/leaf.ext
	@rm -f $(CERT_DIR)/tls.csr $(CERT_DIR)/leaf.ext
	@if $(KUBECTL) config get-contexts $(LOCAL_CONTEXT) -o name 2>/dev/null | \
		grep -qx $(LOCAL_CONTEXT); then \
		$(MAKE) install-certs-secret; \
	else \
		echo "The local cluster does not exist yet; make dev-setup will install the TLS secret."; \
	fi
	@if [ "$(DEFER_LOCAL_SUMMARY)" != "1" ]; then \
		echo "Import $(abspath $(CA_CRT)) into your browser trust store."; \
		echo "See ../docs/local-tls.md."; \
	fi

.PHONY: install-certs-secret
install-certs-secret: ## Create or update the local TLS Kubernetes secret
	@test -f $(CERT_CRT) -a -f $(CERT_KEY) || { \
		echo "TLS certificate files are missing. Run 'make -C helm install-certs'."; \
		exit 1; \
	}
	@$(KUBECTL) --context $(LOCAL_CONTEXT) create namespace $(NAMESPACE) \
		--dry-run=client -o yaml | \
		$(KUBECTL) --context $(LOCAL_CONTEXT) apply -f -
	@$(KUBECTL) --context $(LOCAL_CONTEXT) create secret tls beakerhub-tls \
		--namespace $(NAMESPACE) \
		--cert=$(CERT_CRT) \
		--key=$(CERT_KEY) \
		--dry-run=client -o yaml | \
		$(KUBECTL) --context $(LOCAL_CONTEXT) apply -f -

.PHONY: update-hosts
update-hosts: ## Update local host mappings
	@./kind/update-hosts.sh

.PHONY: setup-local-dns
setup-local-dns: ## Install ingress, certificates, and local host mappings
	@$(MAKE) install-ingress
	@$(MAKE) install-certs
	@$(MAKE) update-hosts

.PHONY: check-lb
check-lb: ## Show local LoadBalancer status
	@$(KUBECTL) --context $(LOCAL_CONTEXT) get service beakerhub-proxy \
		--namespace $(NAMESPACE)

.PHONY: clean
clean:
	@rm -rf packages/$(CHART_NAME)-*.tgz kind/.venv/

.PHONY: full-clean
full-clean:
	@rm -rf packages/$(CHART_NAME)-*.tgz kind/.venv/ \
		kind/kind-config.yaml values-secret.yaml \
		kind/certs.d/rootCA.pem kind/certs.d/tls.crt kind/certs.d/tls.key \
		kind/certs.d/rootCA-key.pem kind/certs.d/rootCA.srl \
