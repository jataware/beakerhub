SHELL=/usr/bin/env bash
BAKE_COMMAND = docker buildx bake

MAKEFLAGS += --no-print-directory
ifndef V
.SILENT:
endif

# Hack to allow splitting strings/variables by commas since commas in make commands are always seen as separators
comma := ,

# Build configuration env variables
export BUILDX_BAKE_ENTITLEMENTS_FS=0


BUILD_TARGETS := $(shell $(BAKE_COMMAND) --print | jq -r '.target | keys | join(" ")')
REQUESTED_BUILD_TARGETS := $(filter $(BUILD_TARGETS),$(MAKECMDGOALS))

.PHONY:build
build:
	$(BAKE_COMMAND)


.PHONY: ${BUILD_TARGETS}
${BUILD_TARGETS}:_build_target
	@true

_build_target:
	$(BAKE_COMMAND) $(REQUESTED_BUILD_TARGETS)

.PHONY:print
print:
	$(BAKE_COMMAND) --print

.PHONY:images
images:
	docker image ls --filter "label=com.jataware.beakerhub"

.PHONY:clean
clean:
	TARGETS=$$(docker image ls -q --filter "label=com.jataware.beakerhub.target=dev"); \
	[[ -n "$$TARGETS" ]] && docker image rm $$TARGETS || true

.PHONY:full-clean
full-clean:
	TARGETS=$$(docker image ls -q --filter "label=com.jataware.beakerhub"); \
	[[ -n "$$TARGETS" ]] && docker image rm $$TARGETS || true