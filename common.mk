# ─────────────────────────────────────────────────────────
# common.mk — cibles partagées par les Makefiles de VM
#
# Chaque VM a un Makefile minimal qui définit NET puis inclut ce fichier :
#     NET := lorionXXvel-network
#     include ../common.mk
#
#   make up      : crée le réseau partagé (si absent) + démarre les stacks
#   make down    : arrête les stacks (le réseau reste pour les autres stacks)
#   make purge   : down + supprime le réseau partagé
#   make network : crée uniquement le réseau
#   make subnets : liste les subnets déjà utilisés (docker + routes hôte)
#   make ps      : état des services
#
# Le réseau est déclaré `external: true` dans les compose.yml car il est
# partagé entre plusieurs stacks de la VM — c'est donc make qui gère son
# cycle de vie, pas docker compose.
#
# SUBNET est optionnel : laissé vide, Docker choisit automatiquement un
# bloc libre (aucun service n'utilise d'IP statique, donc pas besoin de
# le fixer). Pour le forcer : make up SUBNET=172.25.0.0/16
# ─────────────────────────────────────────────────────────
ifndef NET
$(error NET n'est pas défini : le Makefile de la VM doit définir NET avant d'inclure common.mk)
endif

SUBNET ?=

# Si SUBNET est défini, on le passe à docker network create ; sinon, on laisse Docker choisir un subnet libre.
SUBNET_FLAG := $(if $(SUBNET),--subnet $(SUBNET),)

.DEFAULT_GOAL := help
# Si vous ajoutez des cibles, n'oubliez pas de les déclarer ici pour qu'elles soient considérées comme "phony" (pas de fichier cible correspondant).
.PHONY: help up down purge network network-rm subnets ps

help: ## affiche cette aide
	@echo "Stack $(NET:-network=) — commandes disponibles :"
	@echo ""
	@awk 'BEGIN {FS = ":.*## "} /^[a-zA-Z0-9_-]+:.*## / \
		{printf "  \033[1;32m%-12s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)
	@echo ""
	@echo "Variable : SUBNET=<cidr> pour forcer le subnet du réseau (ex: SUBNET=172.25.0.0/16)"

network: ## crée le réseau partagé de la VM (si absent)
	@docker network inspect $(NET) >/dev/null 2>&1 || \
		docker network create $(SUBNET_FLAG) $(NET)

up: network ## réseau (si absent) + build + démarre les stacks
	docker compose up -d --build

down: ## arrête les stacks (le réseau partagé reste)
	docker compose down

network-rm: ## supprime le réseau partagé
	-docker network rm $(NET)

purge: down network-rm ## down + suppression du réseau

subnets: ## liste les subnets utilisés (docker + routes hôte)
	@echo "── Réseaux docker ──"
	@docker network ls -q | xargs docker network inspect \
		--format '{{.Name}}: {{range .IPAM.Config}}{{.Subnet}}{{end}}' 2>/dev/null | sort
	@echo "── Routes hôte ──"
	@ip -4 route

ps: ## état des services
	docker compose ps
