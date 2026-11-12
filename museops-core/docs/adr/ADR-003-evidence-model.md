ADR-003 — Evidence Model

Status: Accepted
Version: v0.1
Date: 2026-07-31

---

Context

MuseOps transforme des signaux bruts en observations structurées puis en findings.

Cependant, plusieurs dimensions différentes existent dans le pipeline :

- la fiabilité intrinsèque de la source ;
- la confiance d'une capability dans sa propre sortie ;
- la force globale d'une conclusion basée sur plusieurs éléments.

Ces dimensions ne doivent pas être fusionnées.

Une architecture précédente utilisait un terme unique :

confidence

pour plusieurs concepts différents.

Cela créait un risque :

Une IA pourrait être très certaine d'une erreur.

Exemple :

Vision model confidence: 0.95

≠

Evidence that a collaboration exists: 0.95

MuseOps sépare donc trois niveaux.

---

Decision

MuseOps utilise trois métriques indépendantes :

Source
  ↓
channel_trust


Capability
  ↓
capability_confidence


Finding
  ↓
evidence_strength

Aucune de ces valeurs ne remplace les autres.

---

1. Channel Trust

Definition

"channel_trust" mesure la fiabilité structurelle du canal d'origine.

Question :

«À quel point cette source est-elle généralement fiable pour fournir ce type d'information ?»

---

Exemple

Source :

Android Notification

peut avoir :

{
  "channel_trust": "high"
}

car la notification provient directement d'une application installée.

---

Valeurs v0.1

high
medium
low

---

Règle

Channel trust est associé au type de source.

Il ne dépend pas d'une interprétation.

---

2. Capability Confidence

Definition

"capability_confidence" mesure la confiance d'un module d'extraction dans son propre résultat.

Question :

«À quel point cette capability pense-t-elle avoir correctement extrait cette information ?»

---

Exemple

Une capability NLP analyse :

Stephanie is LIVE on TikTok

Produit :

{
  "capability": "nlp",
  "capability_confidence": 0.92
}

---

Important

Cette valeur n'est pas une preuve.

Elle représente uniquement :

modèle → résultat

Pas :

résultat → vérité

---

Valeurs

Format MVP :

0.0 → 1.0

---

3. Evidence Strength

Definition

"evidence_strength" mesure la solidité d'un Finding après agrégation.

Question :

«Combien d'éléments indépendants soutiennent cette conclusion ?»

---

Valeurs v0.1

low
medium
high

---

Evidence Rules MVP

High

Conditions :

- plusieurs sources indépendantes ;
- convergence cohérente ;
- absence de contradiction majeure.

Exemple :

Notification:
Stephanie is LIVE

Metadata:
TikTok LIVE page exists

User confirmation:
joined event

Résultat :

evidence_strength = high

---

Medium

Conditions :

- une source fiable ;
- information directe ;
- pas de contradiction.

Exemple :

Android Notification:
Stephanie is LIVE

Résultat :

evidence_strength = medium

---

Low

Conditions :

- source faible ;
- observation isolée ;
- contradiction importante.

Exemple :

OCR:
EASYBOY

sur une image floue.

Résultat :

evidence_strength = low

---

Independence Rule

La convergence ne dépend pas du nombre de capabilities.

Elle dépend du nombre de sources indépendantes.

Incorrect :

OCR + Vision

sur la même image.

Ce sont deux analyses d'une même source.

---

Correct :

Notification
+
Metadata
+
User provided image

Trois sources distinctes.

---

Observation Model Impact

Une Observation contient :

{
  "capability": "nlp",
  "capability_confidence": 0.92
}

mais pas :

evidence_strength

Car une Observation n'est pas encore une conclusion.

---

Finding Model Impact

Un Finding contient :

{
  "evidence_strength": "medium",
  "source_types": [
    "android_notification"
  ]
}

---

Contradictions

Les contradictions sont conservées.

MuseOps ne force pas une résolution artificielle.

Exemple :

Observation 1 :

NLP:
EASYBOY mentioned

Observation 2 :

Metadata:
No EASYBOY reference

Le Finding conserve :

{
 "contradictions": [
   {
    "observations": [
      "obs_001",
      "obs_002"
    ]
   }
 ]
}

---

Source Attribution

Chaque Finding doit permettre de comprendre :

Pourquoi cette force d'évidence existe ?

Chaîne :

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

Capability Mapping Sprint 1

Les extracteurs utilisent les capabilities existantes :

CreatorExtractor
        ↓
capability = nlp


HashtagExtractor
        ↓
capability = nlp

Aucun nouveau type de capability n'est créé pour chaque extracteur.

---

Explicit MVP Limits

Hors scope :

❌ moteur bayésien
❌ calibration statistique avancée
❌ apprentissage automatique des poids
❌ fusion probabiliste automatique
❌ raisonnement métier dans Evidence Layer

---

Consequences

Positives

- évite la fausse certitude ;
- résultats auditables ;
- compatible avec Vision Agent futur ;
- permet une intervention humaine future.

Négatives

- plus de champs ;
- calcul d'évidence plus complexe ;
- certaines conclusions restent faibles même si elles semblent plausibles.

Ce compromis est accepté.

---

Final Decision

MuseOps adopte un modèle d'évidence à trois dimensions :

channel_trust
        +
capability_confidence
        +
evidence_strength

Ces concepts restent séparés dans tout le Core v0.1.

L'évidence décrit la solidité d'un finding.

Elle ne remplace jamais la preuve originale.
