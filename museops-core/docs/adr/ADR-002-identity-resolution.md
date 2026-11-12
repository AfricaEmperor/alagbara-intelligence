ADR-002 — Identity Resolution Strategy

Status: Accepted
Version: v0.1
Date: 2026-07-31

---

Context

MuseOps doit être capable de relier plusieurs observations au même objet dans le temps.

Exemple :

Semaine 1 :

Observation:
creator = Stephanie
platform = TikTok
handle = @stephanie

Semaine 2 :

Observation:
creator = Stephanie
platform = TikTok
handle = @stephanie

Ces deux observations doivent pouvoir alimenter le même historique.

Cependant, une identité ne doit pas être déduite trop rapidement.

Cas dangereux :

@stephanie
        ↓
@stephanie_new
        ↓
même personne ?

La réponse ne doit pas être automatiquement "oui".

Une erreur d'identité crée une erreur de graphe, qui peut contaminer :

- Pulse ;
- historique ;
- scoring ;
- décisions futures.

---

Decision

MuseOps sépare deux concepts :

Subject
    +
ExternalIdentity

---

Subject

Responsabilité

Représenter l'identité interne MuseOps.

Un Subject existe indépendamment des plateformes externes.

Exemple :

{
  "id": "sub_001",
  "type": "creator",
  "status": "active"
}

Le Subject est la référence interne utilisée par :

- Observation ;
- ObservationSet ;
- Pulse ;
- Finding.

---

ExternalIdentity

Responsabilité

Représenter une identité observée sur une plateforme externe.

Exemple :

{
  "subject_id": "sub_001",
  "platform": "tiktok",
  "identifier_type": "account_id",
  "value": "123456789",
  "identity_link_status": "confirmed"
}

Une ExternalIdentity peut évoluer sans changer le Subject.

---

Identity Resolution Principles

Principle 1 — Pas de fusion automatique

MuseOps ne décide jamais automatiquement :

Identity A = Identity B

sur la base d'une simple similarité.

Exemples exclus :

- même prénom ;
- même photo ;
- même style ;
- même audience.

---

Principle 2 — Résolution par type d'identité

Chaque type de Subject possède une stratégie adaptée.

---

Creator

Mode

Stable Identifier Resolution

Identifiant primaire

platform_account_id

Priorité :

account_id
    ↓
handle exact

Exemple :

TikTok account_id:
987654

handle:
@stephanie

Un changement de pseudo ne crée pas automatiquement une nouvelle identité si le même account_id est disponible.

---

Hashtag

Mode

Exact Match Resolution

Un hashtag est résolu par valeur normalisée.

Règle v0.1 :

normalized_hashtag =
lowercase(remove("#"))

Exemples :

#Baddie
#baddie
#BADDIE

deviennent :

baddie

Le même Subject est réutilisé.

---

Brand

Sprint 1

Hors scope.

Raison :

L'identifiant primaire n'est pas suffisamment défini.

Problèmes :

- site officiel ;
- handles multiples ;
- variantes de nom.

---

Event

Sprint 1

Hors scope.

Raison :

L'identifiant stable d'événement n'est pas encore défini.

Exemples ambigus :

Baddie of the Week

peut représenter :

- plusieurs éditions ;
- plusieurs plateformes ;
- plusieurs dates.

---

Community

Sprint 1

Hors scope.

Raison :

Le mécanisme d'identité n'est pas suffisamment défini.

---

Identity Resolution Modes

MuseOps utilise trois modes.

---

Exact Resolution

Utilisé quand l'identifiant est intrinsèquement stable.

Exemple :

Hashtag:
#Baddie

Résultat :

existing_subject

ou :

create_subject

---

Stable ID Resolution

Utilisé quand une plateforme fournit un identifiant durable.

Exemple :

TikTok account_id

---

Ambiguous Resolution

Utilisé lorsqu'il existe une possibilité de correspondance mais aucune preuve suffisante.

Exemple :

@stephanie_new

sans account_id connu.

Résultat :

new candidate identity
+
review required

Pas de fusion.

---

Identity Status

Les statuts sont séparés en deux niveaux.

---

SubjectStatus

Décrit l'état interne du Subject.

Valeurs :

new
active
verified

---

IdentityLinkStatus

Décrit la qualité du lien externe.

Valeurs :

observed
confirmed
linked

---

Resolver Flow

Incoming Observation
          |
          ▼
Extract identity candidate
          |
          ▼
Check SubjectType
          |
          ▼
Apply resolution mode
          |
 ┌───────────────┐
 │ Match found ? │
 └───────────────┘
          |
    YES       NO
     |         |
     ▼         ▼
Attach     Create
identity   candidate

---

Explicit MVP Limits

Hors scope v0.1 :

❌ détection automatique de changement de pseudo
❌ fusion cross-platform
❌ reconnaissance faciale
❌ similarité sémantique avancée
❌ résolution automatique de communautés
❌ résolution automatique de marques

---

Consequences

Positives

- identité stable dans le temps ;
- historique fiable ;
- prévention des faux liens ;
- évolution possible vers un Identity Graph avancé.

Négatives

- certaines identités resteront non résolues ;
- intervention humaine nécessaire dans certains cas ;
- moins de couverture initiale.

Ce compromis est accepté.

---

Final Decision

MuseOps adopte une architecture d'identité séparant :

Subject
    +
ExternalIdentity

avec une résolution limitée à :

Creator:
Stable ID Resolution

Hashtag:
Exact Match Resolution

pour le Sprint 1.

Les autres types d'identité seront ajoutés uniquement après définition complète de leur mécanisme de résolution.
