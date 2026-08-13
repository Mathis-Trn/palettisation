# Rapport d'analyse du CSV réel (`commande_reelle.csv`)

Fichier source : `CESI_clean.csv` (fourni par l'utilisateur, copié dans
`backend/tests/fixtures/csv/commande_reelle.csv`). `CESI.csv` (non copié) n'est pas un export de
données mais la requête SQL ayant servi à générer le fichier — il ne doit jamais être traité comme
un CSV de données.

## Caractéristiques du fichier

- Encodage : UTF-8 avec BOM (`EF BB BF`) — confirmé par inspection hexadécimale de l'en-tête.
- Séparateur : point-virgule (`;`).
- 31 colonnes, en-têtes strictement conformes au mapping attendu (`DEPXENT`, `CDEXENT`, `MDTXENT`,
  `TYPEPALETTE`, `PALXENT`, `LIGXLIG`, `REFXLIG`, `LIBXART`, `QTCXLIG`, `LIBXARC`,
  `CARTON_DETAIL_1..10`, `QTEXARC`, `PALETTE_DETAIL_1..10`).
- 114 lignes de données (+ 1 ligne d'en-tête).
- Toutes les lignes proviennent du même dépôt `DEPXENT = DIP`.

## Commandes détectées (regroupement par `CDEXENT`)

| CDEXENT | Dépôt | Mode transport | Format palette | PALXENT (historique) | Nb lignes |
|---|---|---|---|---|---|
| SO265669-X82921 | DIP | M | P:80x120x110 | 37 | 19 |
| SO265838-X83118 | DIP | A | P:80x120x160 | 14 | 8 |
| SO265841-X82965 | DIP | M | P:80x120x110 | 8 | 3 |
| SO265875-X83120 | DIP | A | P:80x120x160 | 4 | 7 |
| SO266346-X83375 | DIP | A | P:80x120x160 | 9 | 12 |
| SO266633-X83698 | DIP | M | P:80x120x110 | 0 | 65 |

**6 commandes** au total, jamais mélangées entre elles. Les 114 lignes se répartissent
exactement sur ces 6 groupes (19+8+3+7+12+65 = 114).

## Modes de transport (`MDTXENT`)

`M` (maritime) : 87 lignes — `A` (aérien) : 27 lignes. Aucune valeur inconnue rencontrée dans ce
fichier ; le code prévoit néanmoins un avertissement pour toute valeur hors `{M, A}` plutôt qu'un
rejet, conformément à la consigne "conserver les valeurs inconnues avec avertissement".

**Important** : `MDTXENT` (mode de transport) et `TYPEPALETTE` (format de palette) sont deux champs
**indépendants** dans ce fichier — `TYPEPALETTE` est lu directement depuis la colonne du CSV, jamais
re-dérivé du mode de transport (le SQL historique dans `CESI.csv` le dérivait via
`case when MDTXENT='M' then 'P:80x120x110' else 'P:80x120x160'`, mais cette corrélation n'est
qu'une coïncidence de ce jeu de données — nous ne la reproduisons pas comme règle métier).

## Formats de palette (`TYPEPALETTE`)

- `P:80x120x110` → 87 lignes → converti en 800×1200×1100 mm.
- `P:80x120x160` → 27 lignes → converti en 800×1200×1600 mm.

Convention confirmée : `P:{longueur_cm}x{largeur_cm}x{hauteur_cm}`, conversion ×10 vers mm,
centralisée dans `imports/legacy_csv.py::parse_pallet_format` et testée unitairement. **Cet ordre
est celui de l'exemple de contrat JSON normalisé du cahier des charges** (section 7 :
`"code": "P:80x120x110"` y est associé à `lengthMm: 800, widthMm: 1200`, sans permutation) — il ne
correspond volontairement pas à l'ordre length/width (1200×800) des anciens presets
"routier"/"maritime" du front TypeScript, qui décrivaient la même empreinte physique avec les deux
axes nommés dans l'autre sens. La forme et la surface de la palette sont identiques dans les deux
cas ; seul le nom donné à chaque axe diffère.

## Unités (`LIBXARC`)

100 % des lignes utilisent `PIECE` (114/114).

## Quantités (`QTCXLIG`)

114/114 lignes ont une quantité entière strictement positive (aucune anomalie). `QTEXARC` est
conservé en métadonnées d'audit mais jamais utilisé comme quantité (conformément à la consigne),
sa signification métier exacte n'étant pas confirmée par le cahier des charges.

## Décodage des colonnes `CARTON_DETAIL_1..10` (décimales éclatées)

Algorithme implémenté et validé sur les 114 lignes réelles + les 4 exemples documentés dans le
cahier des charges (qui sont eux-mêmes des lignes réelles du fichier, ex. ligne 3 = `SOAP34B`) :

1. Ne garder que les fragments non vides (n ∈ [6, 10] dans ce fichier — distribution observée :
   6 fragments → 19 lignes, 7 → 22, 8 → 6, 9 → 49, 10 → 18).
2. Chercher toutes les partitions ordonnées en 5 groupes non vides (longueur, largeur, hauteur,
   volume, poids) ; chaque groupe = 1er fragment = partie entière, fragments suivants concaténés =
   partie décimale.
3. Ne retenir un candidat que si : toutes les valeurs sont strictement positives, l'écart relatif
   `|longueur×largeur×hauteur − volume| / volume ≤ 0,5 %`, et la densité implicite
   `poids_kg / (volume_cm³ / 1000)` reste dans une plage physiquement plausible **[0,02 ; 20] kg/L**
   (documentée : couvre des emballages très légers jusqu'à de petits contenants denses type
   verre/métal ; exclut les faux candidats à densité aberrante, ex. 77 à 494 kg/L rencontrés sur
   les petits coffrets/échantillons, plus denses que l'acier).
4. Parmi les candidats survivants, garder celui à l'écart relatif le plus faible ; si deux
   candidats sont à égalité (< 1e-9 d'écart), la ligne est rejetée `AMBIGUOUS_CARTON_DETAILS`.

**Résultat sur le fichier réel : 114/114 lignes décodées sans ambiguïté** (aucun rejet nécessaire
sur ce jeu de données précis). Le code conserve néanmoins le rejet explicite pour tout futur
fichier où un candidat resterait ambigu ou introuvable — voir `tests/unit/test_legacy_csv.py` pour
des cas synthétiques d'ambiguïté/rejet construits à la main.

Note historique importante découverte pendant l'analyse : pour les petits coffrets/échantillons
(ex. `34B7.5V1`, `SHANDSCRUB1`, `SBAINMILK`...), une bande de plausibilité de densité trop stricte
(ex. 0,03–3,5 kg/L, calibrée sur les gros articles liquides) rejetait à tort la bonne
interprétation. La bande retenue (0,02–20 kg/L) a été calibrée en vérifiant qu'elle disqualifie
toujours l'interprétation clairement absurde (densité 39 à 494 kg/L) sans jamais introduire de
nouvelle égalité ambiguë sur les 114 lignes.

## Données historiques (`PALXENT` / `PALETTE_DETAIL_*`)

Conservées séparément dans `legacyExpectedResult`, jamais utilisées comme entrée du solveur :
- `PALXENT` : nombre de palettes historique par commande (colonne fiable, un seul entier par
  commande) — utilisé pour la comparaison historique vs calculé.
- `PALETTE_DETAIL_1..10` : structure non totalement spécifiée par le cahier des charges (le premier
  champ est toujours le littéral `PALETTE`, suivi de valeurs numériques dont le décodage complet
  n'est pas garanti sans confirmation métier supplémentaire — **limite documentée** dans
  `ASSUMPTIONS.md`). Conservées brutes (fragments originaux) pour audit uniquement.

## Anomalies rencontrées

Aucune ligne rejetée sur ce fichier précis. `PALXENT = 0` pour la commande `SO266633-X83698` (65
lignes) est noté comme une valeur historique surprenante (zéro palette attendue pour 65 lignes de
commande) mais n'est pas une erreur de parsing — signalé tel quel dans la comparaison historique
plutôt que corrigé silencieusement.
