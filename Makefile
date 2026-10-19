# ─────────────────────────────────────────────────────────
# Makefile racine — pilotage multi-VM (enrobe deploy/deploy.sh)
#
# `make` ou `make help` : liste les commandes disponibles.
#
# Seul `deploy` pousse le code ; down/status sont de pures commandes
# de contrôle à distance.
# Prérequis : deploy/hosts.env (copié depuis hosts.env.example).
#
# Variables :
#   VM      : nom de la VM (ex: VM=lorion03vel)
#   SECRETS : si défini, pousse aussi .env/secrets/ (ex: SECRETS=1)
#
# L'aide est générée depuis les commentaires `##` des cibles :
# toute nouvelle cible documentée `cible: ## description` apparaît
# automatiquement dans `make help`.
# ─────────────────────────────────────────────────────────
VM      ?=
SECRETS ?=

# Si SECRETS est défini, on passe --with-secrets à deploy.sh ; sinon, on ne le passe pas.
SECRETS_FLAG := $(if $(SECRETS),--with-secrets,)

.DEFAULT_GOAL := help
# Si vous ajoutez des cibles, n'oubliez pas de les déclarer ici pour qu'elles soient considérées comme "phony" (pas de fichier cible correspondant).
.PHONY: help deploy deploy-all down down-all status

help: ## affiche cette aide
	@echo "Stack Orion — commandes disponibles :"
	@echo ""
	@awk 'BEGIN {FS = ":.*## "} /^[a-zA-Z0-9_-]+:.*## / \
		{printf "  \033[1;32m%-12s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)
	@echo ""
	@echo "Variables : VM=<nom-vm> (requis pour deploy/down, optionnel pour status), SECRETS=1 (pousse .env/secrets)"

deploy: ## déploie une VM (rsync + make up)          — make deploy VM=lorion03vel
	@test -n "$(VM)" || { echo "usage : make deploy VM=lorion03vel"; exit 1; }
	deploy/deploy.sh $(VM) up $(SECRETS_FLAG)

deploy-all: ## déploie toutes les VMs
	deploy/deploy.sh all up $(SECRETS_FLAG)

down: ## arrête la stack d'une VM (réseau conservé)  — make down VM=lorion03vel
	@test -n "$(VM)" || { echo "usage : make down VM=lorion03vel"; exit 1; }
	deploy/deploy.sh $(VM) down

down-all: ## arrête toutes les stacks
	deploy/deploy.sh all down

status: ## état des services (toutes les VMs, ou une seule) — make status [VM=lorion03vel]
	deploy/deploy.sh $(or $(VM),all) ps
