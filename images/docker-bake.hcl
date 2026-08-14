# Image targets definitions

variable "services" {
  default = ["server", "proxy"]
}

variable "nodes" {
  default = ["default-node"]
}

variable "task_runners" {
  default = ["task-reporter"]
}

# Configuration variables

variable "TARGET" {
  default = "dev"
}

variable "PREFIX" {
  default = "beakerhub"
}

variable "REGISTRY" {
  default = "docker.io"
}

variable "TAG" {
  default = "latest"
  type = string
}

variable "EXTRA_TAGS" {
  default = []
  type = list(string)
}

variable "TAGS" {
  default = concat([TAG], EXTRA_TAGS)
  type = list(string)
}


# Custom helper functions

function "repository" {
  params = [name]
  result = format(
    join("/", [PREFIX, name])
  )
}

function "tagged" {
  params = [ name, tag ]
  result = formatlist("${REGISTRY}/${PREFIX}/${name}:%s", tag)
}

function "name" {
  params = [ name , tag ]
  result = sanitize("${name}${(tag == "" || tag == TAG ? "" : "-${tag}")}")
}


# Groups

group "default" {
  targets = concat(services, nodes, task_runners)
}


# Cache-only builds
target "_base" {
  labels = {
      "com.jataware.beakerhub" = true
      "com.jataware.beakerhub.target" = TARGET
  }
}

target "base" {
  inherits = ["_base"]
  dockerfile = "base.Dockerfile"
  target = "base"
  contexts = {
    config = "./config_files"
  }
  output = ["type=cacheonly"]
}

target "beakerhub-ui" {
  inherits = ["_base"]
  dockerfile = "beakerhub-ui-build.Dockerfile"
  contexts = {
    base = "target:base"
    src = "../"
  }
  output = ["type=cacheonly"]
}

target "node-base" {
  inherits = ["_base"]
  dockerfile = "base.Dockerfile"
  target = "node-base"
  contexts = {
    base = "target:base"
    config = "./config_files"
  }
  output = ["type=cacheonly"]
}


# Service images

target "proxy" {
  inherits = ["_base"]
  name = name("proxy", tag)
  dockerfile = "proxy.Dockerfile"
  matrix = {
    tag = TAGS
  }
  tags = tagged("proxy", tag)
}

target "server" {
  inherits = ["_base"]
  name = name("server", tag)
  dockerfile = "server.Dockerfile"
  matrix = {
    tag = TAGS
  }
  contexts = {
    base = "target:base"
    src = "../"
    beakerhub-ui = "target:beakerhub-ui"
  }
  tags = tagged("server", tag)
}

# Task Runner images

target "task-reporter" {
  inherits = ["_base"]
  name = name("task-reporter", tag)
  dockerfile = "task-reporter.Dockerfile"
  target = "task-reporter"
  matrix = {
    tag = TAGS
  }
  contexts = {
    base = "target:base"
    config = "./config_files"
  }
  tags = tagged("task-reporter", tag)
}

target "default-node" {
  inherits = ["_base"]
  name = name("default-node", tag)
  dockerfile = "default-node.Dockerfile"
  matrix = {
    tag = TAGS
  }
  contexts = {
    base = "target:node-base"
    beaker-hub-src = "../"
  }
  tags = tagged("default-node", tag)
}
