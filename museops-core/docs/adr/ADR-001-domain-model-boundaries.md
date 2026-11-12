ADR-001 — Domain Model Boundaries

Status: Accepted
Version: v0.1
Date: 2026-07-31

Context

MuseOps reçoit des signaux provenant de plusieurs sources potentielles :

- notifications Android ;
- contenus partagés par l'utilisateur ;
- futures images, audio ou API.

Le système doit transformer ces signaux en intelligence exploitable tout en conservant une séparation stricte entre :

1. ce qui est reçu ;
2. ce qui est observé ;
3. ce qui est agrégé ;
4. ce qui est interprété.

Les premières conceptions ont révélé un risque majeur : transformer directement un événement brut en conclusion métier.

Exemple incorrect :

Notification TikTok
        ↓
"Stephanie collabore avec EASYBOY"

Cette sortie mélange :

- une donnée brute ;
- une détection ;
- une hypothèse.

MuseOps doit conserver une chaîne de provenance complète.

---

Decision

Le Core MuseOps adopte le pipeline de domaine suivant :

Source
   ↓
Signal
   ↓
Observation
   ↓
ObservationSet
   ↓
Pulse
   ↓
Finding

Chaque couche possède une responsabilité unique.

---

Source

Responsabilité

Décrire le canal d'origine d'une information.

Exemples :

android_notification
user_upload
api_response

Une Source est une référence stable.

Elle contient :

- type de canal ;
- channel_trust ;
- métadonnées techniques.

Une Source n'est pas un événement.

---

Signal

Responsabilité

Représenter une occurrence brute reçue par MuseOps.

Exemple :

Source:
android_notification

Content:
"Stephanie is LIVE on TikTok"

Un Signal est immuable.

Il conserve :

- source_id ;
- contenu original ;
- timestamp ;
- provenance.

Le Signal ne contient aucune interprétation.

---

Observation

Responsabilité

Transformer un Signal en donnée structurée détectée.

Exemple :

{
  "subject_candidate": "Stephanie",
  "event_type": "live_started",
  "capability": "nlp",
  "capability_confidence": 0.92
}

Une Observation répond uniquement à :

«Qu'est-ce qui semble être présent dans le signal ?»

Elle ne répond pas à :

«Quelle est la signification stratégique ?»

---

ObservationSet

Responsabilité

Regrouper plusieurs Observations appartenant au même contexte.

Le regroupement dépendra de :

- sujet ;
- fenêtre temporelle ;
- contexte.

Sprint 1 :

Le regroupement reste minimal.

---

Pulse

Responsabilité

Créer une agrégation temporelle d'un ObservationSet.

Pulse prépare :

- comparaison historique future ;
- évolution ;
- changement détecté.

Pulse n'effectue aucune interprétation métier.

---

Finding

Responsabilité

Produire une affirmation structurée basée sur un Pulse.

Exemple valide :

{
  "type": "event_detected",
  "value": "tiktok_live_started",
  "subject": "Stephanie",
  "evidence_strength": "medium"
}

Exemple invalide :

Stephanie collabore avec EASYBOY.

Cette phrase nécessite une interprétation qui appartient aux couches supérieures.

---

Rules

Rule 1 — No hidden inference

Aucune couche avant Finding ne produit de conclusion.

---

Rule 2 — Provenance obligatoire

Tout Finding doit être traçable :

Finding
 ↓
Pulse
 ↓
ObservationSet
 ↓
Observation
 ↓
Signal
 ↓
Source

---

Rule 3 — Capability ≠ Truth

Une capability produit une observation.

Elle ne décide pas de la vérité.

Exemple :

Entrée :

OCR détecte EASYBOY

Sortie correcte :

Observation:
visible_text = EASYBOY

Pas :

collaboration = true

---

Rule 4 — Core indépendant des plateformes

Le Core MuseOps ne connaît pas TikTok, Instagram ou Facebook.

Ces plateformes sont uniquement des sources possibles.

Le domaine manipule :

- Source ;
- Signal ;
- Observation ;
- Subject ;
- Finding.

---

Sprint 1 Scope

Inclus :

✅ Source
✅ Signal
✅ Observation
✅ ObservationSet minimal
✅ Pulse minimal
✅ Finding minimal
✅ Identity Resolver limité Creator + Hashtag

Exclus :

❌ Vision Agent
❌ Memory Vision
❌ Ana reasoning
❌ Flynn actions
❌ scoring commercial avancé

---

Consequence

Cette architecture augmente légèrement la complexité initiale mais garantit :

- auditabilité ;
- tests reproductibles ;
- ajout futur de Vision Agent sans refonte du Core ;
- séparation entre perception et intelligence.

---

Final Decision

Le modèle :

Source → Signal → Observation → ObservationSet → Pulse → Finding

est adopté comme fondation du Core MuseOps v0.1.
