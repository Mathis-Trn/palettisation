# Palettisation 3D

Portail web de simulation de palettisation 3D : import ou saisie d'une commande de cartons,
calcul automatique de la répartition sur des palettes (transport routier, maritime ou aérien),
visualisation 3D interactive, export des résultats et estimation du chargement dans un véhicule
ou un conteneur.

Application 100 % locale : aucun compte utilisateur, aucune clé d'API externe, aucune base de
données. Les simulations sont sauvegardées dans le stockage local du navigateur.

## Objectif du projet

Aider un préparateur logistique à déterminer, pour une commande donnée, combien de palettes sont
nécessaires, comment les cartons doivent y être disposés, et combien de palettes chargées peuvent
entrer dans un véhicule ou un conteneur — avec une vue 3D permettant de vérifier visuellement le
plan de chargement avant expédition.

Le moteur de placement est un **moteur d'optimisation combinatoire** (heuristique de type
« points extrêmes » / espaces maximaux), volontairement **pas** qualifié d'intelligence
artificielle. L'architecture (voir plus bas) est conçue pour accueillir plus tard des évolutions
telles que l'apprentissage à partir de plans validés par des opérateurs, la comparaison de
plusieurs heuristiques, un scoring prédictif ou un solveur combinatoire plus avancé.

## ⚠️ Avertissement sur la stabilité physique

Le contrôle de support et de stabilité implémenté dans le moteur (ratio de surface de contact,
centre de gravité projeté) est une **approximation logicielle**. Il ne simule ni les forces
dynamiques du transport (freinage, virages, vibrations), ni le comportement réel des matériaux
d'emballage, ni le calage. **Il ne constitue en aucun cas une certification physique du
chargement.** Toute décision de chargement réel doit être validée par un professionnel qualifié
selon les règles et normes applicables (ex. code de la route, consignes du transporteur).

## Prérequis

- Node.js **20.9 ou supérieur** (Next.js 16 l'exige — voir `package.json`).
- npm 10+ (fourni avec Node).

## Installation

```bash
npm install
```

## Démarrage

```bash
npm run dev
```

Puis ouvrir [http://localhost:3000](http://localhost:3000). Un jeu de données de démonstration
est chargeable en un clic depuis le tableau de bord (bouton **Démonstration**).

Build de production :

```bash
npm run build
npm run start
```

## Commandes de test

```bash
npm run typecheck   # TypeScript strict, sans émission
npm run lint        # ESLint
npm run test        # Tests unitaires (Vitest) : moteur, CSV, transport-loader
npm run test:watch  # Tests unitaires en mode watch
npm run test:e2e    # Test de parcours principal (Playwright)
```

Le test Playwright démarre automatiquement le serveur de développement (`npm run dev`) si aucun
serveur n'est déjà lancé sur le port 3000 (voir `playwright.config.ts`).

## Structure du projet

```
src/
  domain/            Types, unités, constantes et schémas de validation (Zod).
                      Aucune dépendance à React ni à Three.js.
  optimizer/          Moteur de palettisation pur (déterministe, testable isolément) :
                      expansion des quantités, orientations, tri, heuristique de placement,
                      contrôle de support, scoring, orchestration multi-stratégies.
  transport-loader/   Module indépendant : placement 2D des palettes chargées dans un
                      véhicule ou un conteneur.
  workers/            Exécution du moteur hors du thread principal (Web Worker), avec repli
                      synchrone si les Web Workers ne sont pas disponibles.
  lib/
    import-export/    Import/export CSV (Papa Parse) et JSON.
    demo-data.ts       Jeu de données de démonstration.
    format.ts, utils.ts
  store/               État de l'application (Zustand) et persistance locale versionnée.
  components/
    ui/                Composants d'interface accessibles (boutons, tableaux, dialogues...).
    dashboard/          Tableau de bord (liste des simulations).
    configuration/       Écran de configuration (transport, palette, contraintes).
    order-table/          Tableau de commande éditable + import CSV.
    results/               Résultats, KPI, export, fiche imprimable.
    three/                  Visualisation 3D (React Three Fiber / Drei).
    transport/               Module de chargement transport (plan 2D).
    workspace/                 Assemblage des écrans d'une simulation (onglets).
  app/                 Routes Next.js (App Router) : tableau de bord et espace de simulation.
tests/
  unit/                Tests unitaires Vitest (moteur, CSV, transport-loader).
  e2e/                 Test Playwright du parcours principal.
```

Le cœur d'optimisation (`src/optimizer`, `src/domain`, `src/transport-loader`) ne dépend ni de
React ni de Three.js : il est testable et réutilisable indépendamment de l'interface.

## Format CSV

En-têtes attendus (séparateur virgule ou point-virgule, détecté automatiquement) :

```
sku,longueur_mm,largeur_mm,hauteur_mm,quantite,poids_kg,rotation_autorisee,sens_vertical,fragile,gerbable
BOX-A,400,300,250,12,8.5,true,false,false,true
BOX-B,600,400,300,8,12,true,true,false,true
BOX-C,250,200,150,20,3,true,false,true,true
```

- Colonnes obligatoires : `sku`, `longueur_mm`, `largeur_mm`, `hauteur_mm`, `quantite`.
- Colonnes optionnelles : `poids_kg`, `rotation_autorisee`, `sens_vertical`, `fragile`,
  `gerbable`, `groupe`. Valeurs par défaut si absentes : rotation autorisée = vrai, sens vertical
  = faux, fragile = faux, gerbable = vrai.
- Valeurs booléennes reconnues (insensible à la casse) : `true`, `vrai`, `1`, `oui`, `yes`, `y`,
  `x`. Voir `ASSUMPTIONS.md` pour le détail des conventions retenues.
- Le modèle ci-dessus est téléchargeable directement depuis l'écran **Commande** de l'application.

## Explication de l'algorithme

Le moteur (`src/optimizer`) implémente une heuristique de type **points extrêmes** (Extreme
Points), une approche classique du bin packing 3D :

1. **Expansion** : chaque ligne de commande est développée en instances individuelles de cartons
   (une par unité de quantité), avec un identifiant déterministe.
2. **Orientations** : pour chaque instance, les orientations autorisées sont calculées selon les
   réglages (rotation autorisée ou non, sens vertical obligatoire ou non) — jusqu'à 6 permutations
   possibles des axes longueur/largeur/hauteur.
3. **Tri** : les instances sont triées selon une stratégie (volume décroissant, plus grande
   dimension décroissante, poids décroissant, ou surface au sol décroissante). Le mode rapide
   n'essaie qu'une stratégie ; le mode approfondi les essaie toutes et conserve la meilleure
   solution (moins de palettes, puis meilleur remplissage, puis meilleure stabilité moyenne).
4. **Points candidats** : chaque palette maintient une liste de points extrêmes (positions
   candidates), initialisée au coin de la palette. Après chaque placement, trois nouveaux points
   sont générés sur les faces du carton posé (droite, arrière, dessus).
5. **Placement** : pour chaque instance, toutes les combinaisons (point candidat × orientation
   autorisée) sont testées et validées (limites de la palette, absence de chevauchement, poids,
   gerbage, fragilité, ratio de support). Parmi les combinaisons valides, celle avec le meilleur
   score est retenue — le score combine hauteur résultante, proximité de l'origine, surface de
   support, contact avec les parois/le sol et regroupement des cartons de même SKU.
6. **Nouvelle palette** : si aucune position valide n'existe sur les palettes déjà ouvertes, une
   nouvelle palette est ouverte. Si le carton ne peut tenir sur une palette **vide** (dimensions,
   poids), il est immédiatement marqué non plaçable — ce qui garantit qu'aucune boucle infinie ne
   peut se produire.
7. **Résultat** : chaque carton placé porte ses dimensions d'origine et placées, sa position, son
   orientation et son palier ; chaque carton non placé porte un code (`DIMENSIONS_EXCEED_PALLET`,
   `HEIGHT_EXCEEDED`, `WEIGHT_EXCEEDED`, `ROTATION_FORBIDDEN`, `STACKING_CONSTRAINT`,
   `NO_STABLE_POSITION`, `INVALID_DATA`) et un message explicite.

Le calcul est **déterministe** : à données et réglages identiques, le résultat est rigoureusement
identique d'une exécution à l'autre (aucun aléa, tri stable, identifiants basés sur l'ordre
d'entrée). Il s'exécute dans un **Web Worker** pour ne jamais bloquer l'interface, avec repli
synchrone si les Web Workers ne sont pas disponibles.

## Limites connues

- Le contrôle de support/stabilité est une approximation 2D, pas une simulation physique (voir
  l'avertissement ci-dessus).
- L'heuristique de points extrêmes ne garantit pas la solution optimale (minimum théorique de
  palettes) : c'est un compromis performance/qualité usuel en bin packing 3D.
- Le module de chargement transport n'effectue qu'un placement 2D des empreintes de palettes
  (par étagères), avec un empilage simplifié à un seul niveau — ce n'est pas un solveur complet.
- Les dimensions de véhicules/conteneurs proposées en préréglage sont indicatives et doivent être
  vérifiées auprès du transporteur réel.
- Cible de fluidité : environ 500 instances de cartons. Au-delà, un avertissement s'affiche et le
  mode rapide est recommandé (le calcul reste possible, mais plus lent).
- Aucun compte utilisateur, aucune synchronisation entre appareils : les simulations ne sont
  sauvegardées que dans le navigateur utilisé (`localStorage`).

Voir `ASSUMPTIONS.md` pour le détail complet des hypothèses métier retenues.

## Pistes d'évolution

- Ajout d'un vrai solveur combinatoire (programmation par contraintes ou métaheuristique de type
  recuit simulé / algorithme génétique) pour les commandes complexes, en complément (et non en
  remplacement) de l'heuristique actuelle.
- Apprentissage à partir de plans de palettisation validés par des opérateurs, pour affiner le
  scoring des placements.
- Comparaison automatique de plusieurs heuristiques avec restitution du détail de chacune.
- Solveur dédié pour le module de chargement transport (au-delà du placement 2D par étagères),
  avec empilage multi-niveaux complet.
- API et base de données pour la persistance multi-utilisateurs et multi-appareils (l'architecture
  actuelle — domaine et moteur découplés de l'interface — est conçue pour absorber cette évolution
  sans réécriture du cœur de calcul).
