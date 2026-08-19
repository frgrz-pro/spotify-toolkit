# Note d'exploration — Les anciens repos et ce qu'ils apportent à Portal6

> Phase : **exploration**. Le refinement (solution posée) et le walkthrough d'implem viendront
> dans des notes séparées, une fois les arbitrages de fin de note tranchés.

## Contexte

Six repos perso ont été clonés dans `C:\DevLab` à côté de `spotify-toolkit` (futur **Portal6**,
portail multi-espaces dont le premier espace est la musique). Tous sont des projets stoppés —
systématiquement au même moment : celui de structurer le projet, faire une API, brancher l'UI.
Le but de cette note : inventorier ce qu'ils contiennent réellement, en tirer les briques et
patterns réutilisables, et poser les pistes d'intégration dans Portal6.

## État de Portal6 aujourd'hui (point de départ)

- Le renommage spotify-toolkit → portal6 est **entamé mais non commité** (`package.json` dit
  `portal6`, le remote et `package-lock.json` disent encore `spotify-toolkit`). 2 commits au total,
  tout le travail récent est en working tree.
- Ce qui existe : un **pipeline de données mono-domaine sans applicatif**. Vault (`data/`) →
  ETL Python (`plugin/etl/music/`) → référentiel SQLite (`plugin/db/music.db`, 90 758 tracks,
  110 playlists, 88 223 fichiers locaux). `apps/` est vide, aucune API, aucune UI, aucun framework.
- Les points d'ancrage multi-espaces sont déjà posés : `apps/` en attente, le segment `music`
  dans `plugin/etl/music/`, les IDs projet `P6-*`, la table `platform_refs` (vide) pour la sync
  multi-plateformes.
- Faiblesses connues : IDs `P6-*` **réattribués à chaque rebuild** (incompatible avec toute UI qui
  les référencerait), matching local↔Spotify à ~5 % (4 408 titres croisés sur 88 223 fichiers),
  scripts `harvest.sh`/`progress.sh`/`recco_sentinel.sh` cassés par la réorganisation des dossiers
  (`cd` relatif faux d'un niveau), double venv (README dit `~/.venvs/spotify-toolkit`, les `.sh`
  disent `.venv/`), fonction `normalize` dupliquée entre `build_db.py` et `dedup_library.py`.

## Exploration des six repos

### Mapix (mai 2020) — SDK Android Rx pour les API Google Maps

Lib Kotlin multi-module (Directions, Geocoding complets ; Places jamais mergé) destinée à
publication open-source. Ne compile plus (fichier `private.gradle` supprimé, module fantôme,
Bintray mort).

**À retenir :**
- Le **step builder typé** (`RxDirection.withConnection(...).from(...).to(...).execute()`) : l'ordre
  d'appel garanti par le compilateur. Réutilisable pour tout client d'API à paramètres
  obligatoires/optionnels.
- La séparation **Request (façade fluente) / RequestParam (état + sérialisation)** — évite les
  builders monolithiques, testable isolément.

**⚠️ Urgent :** la branche publique `origin/feature/place` contient `scripts/private.gradle` avec
**deux clés API Google Maps et un couple user/key Bintray en clair**. Le repo GitHub est public.
À vérifier/révoquer côté console Google Cloud.

### frgrz-mapix (sept. 2020) — en réalité `frgrz-starter-pack`

Malgré le nom, aucun rapport avec les cartes : un template d'app Android (Dagger, Navigation,
design system) créé depuis l'outillage de Mapix puis réorienté. Un seul commit, ossature complète,
contenu métier à zéro — mort au moment d'écrire la première vraie feature.

**À retenir :**
- Le **Router pattern** (sa meilleure idée, reprise de Budget) : chaque feature déclare une
  interface de navigation vide, le ViewModel la reçoit par injection, et c'est l'hôte qui
  implémente toutes les interfaces. Une feature ne connaît ni le routeur concret ni les autres
  features.
- La séparation **design-core (tokens neutres) / design-app (identité visuelle)** — applicable à
  tout design system, y compris hors Android.

### Budget (juin–juil. 2020) — app de budget 50/30/20

**Le working tree local est trompeur** : le vrai projet (18 commits, +23 600 lignes, 9 modules
supplémentaires) vit sur `origin/feature/transaction-page`, jamais mergée. Clean Architecture
multi-module très disciplinée. Mort de deux refactorings simultanés jamais finis (pivot vers la
comptabilité en partie double + refonte design system Material).

**À retenir :**
- **`domain-accounting`** : un vrai moteur de **comptabilité en partie double** (Ledger, Journal,
  ChartOfAccounts, transactions debit/credit en BigDecimal), **le seul code testé de tous les
  repos**. Fondation correcte si un espace « budget » naît un jour dans Portal6. Attention :
  3 bugs connus, dont `TrialBalanceResult.isBalanced` qui renvoie toujours `true` (accumulation
  sur un `BigDecimal` immuable).
- **`feature-developer`** (branche) : un écran debug de seeding avec actions typées
  (`SEED_ACCOUNTS`, `SEED_MONTH`…) et jeux de données réalistes. Idée transposable à tout projet.
- **`tool-algo`** (branche) : bibliothèque d'algos complète (tris, graphes, Dijkstra, MST) dont
  surtout des **algorithmes de layout de graphes** (Fruchterman-Reingold, Sugiyama,
  Buchheim-Walker) — exactement ce qu'il faut pour visualiser un graphe artistes/genres.
- **`cache-core`** (branche) : `BaseDao<T>` + `BaseDataCache` + `CacheMapper` génériques — la
  correction du boilerplate de triple mapping.
- Le Router centralisé (origine du pattern repris dans frgrz-mapix).

### frgrz-playground (sept. 2020) — le toolkit `com.frgrz.toolkit`

La réaction à Budget : extraire les briques réutilisables en modules. 7 commits **en une seule
soirée**, puis plus rien. Bibliothèque de pièces détachées jamais montée — aucun module `tool-*`
n'est consommé par l'app vitrine.

**À retenir :**
- **`tool-validation`** : le plus directement transposable. `ValidationRule<T>` = un prédicat,
  résultat = map règle→bool, composition triviale. À moderniser (virer Rx) et **renommer** : les
  packages déclarent `com.seloger.android.*` — code copié de l'ex-employeur, à nettoyer avant
  toute réutilisation ou publication.
- `StateDataModel<T>` (LOADING/SUCCESS/ERROR/IDLE) — aujourd'hui un `sealed interface`, mais l'API
  est propre.
- Une copie du moteur `domain-accounting` de Budget (le lien direct entre les deux repos).

### gamemaster (oct. 2024) / KMPGameMaster (oct. 2024) — le même projet, deux générations

App « maître du jeu » pour le Loup-Garou (et d'autres jeux d'ambiance prévus). V1 Android native
abandonnée en 5 jours (un fichier `Role.kt` de 510 lignes l'a tuée), réécrite intégralement en
**Kotlin Multiplatform + Compose** (Android/iOS/Desktop). La V2 est le repo le plus abouti des
six : parcours complet jouable (joueurs → config → rôles → génération de deck → distribution →
journal), ~9 300 lignes, Clean Architecture stricte. Arrêtée net au moment d'écrire la boucle de
jeu (nuits, votes, victoire). Rien à récupérer en V1 sauf le commentaire d'ordre d'appel des rôles
(la spec métier jamais implémentée).

**À retenir :**
- **Le socle KMP lui-même** : Compose Multiplatform + Voyager (navigation) + Koin (DI) +
  MaterialKolor (thème dynamique), qui compile sur 3 plateformes. Template de démarrage prêt à
  l'emploi — le candidat naturel si `apps/` de Portal6 part sur du Kotlin.
- **Le Rule Pattern** (`RoleCompatibilityRule` : une interface, une liste de règles, un `fold`
  correctif) : moteur de règles composable en 10 lignes, applicable à toute validation métier.
- **Le journal d'événements typé** (`GameLogCache` + `LogEntry.Type` + un use case par type) :
  event-sourcing léger, très lisible.
- `RealmDatabase.kt` : wrapper DB générique propre (`getAllAsFlow<T>`, DSL de contraintes,
  upsert) — transposable à SQLDelight/Room. (Realm lui-même est en fin de vie, ne pas reprendre.)
- L'icon pack `ImageVector` (40 icônes, zéro dépendance) et l'écran debug `ColorsScreen` qui
  affiche la palette Material générée.
- La protection « 5 clics » pour cacher des infos animateur sur un appareil partagé.

## Lecture transverse — pourquoi ces projets sont morts

Les six repos racontent la même histoire, et c'est la donnée la plus importante de cette
exploration :

1. **L'infrastructure était toujours plus intéressante que la feature.** Budget : 17 modules
   Gradle avant le premier écran fini. Playground : une soirée à renommer des modules, zéro
   assemblage. KMPGameMaster : 21 mappers mono-responsabilité et 25 use cases… et zéro test,
   zéro boucle de jeu.
2. **Les chantiers parallèles tuent.** Budget est mort de deux refactorings simultanés non finis
   plus une branche jamais mergée (rendant le travail invisible).
3. **La réécriture-réaction est un piège récurrent** : plutôt que finir, on extrait/refonde
   (Budget→playground, gamemaster→KMP). La V2 est meilleure mais meurt au même endroit — le
   moment où il faut du métier, pas de l'archi.

**Conséquence pour Portal6** : les principes anti-récidive doivent être des règles du repo, pas
des vœux. Proposition à valider au refinement :

- **Une tranche verticale à la fois**, finie et utilisée avant la suivante (l'espace musique
  jusqu'au bout avant tout autre espace).
- **Pas d'abstraction avant le deuxième usage** : on n'extrait un module/pattern partagé que
  quand un deuxième espace en a concrètement besoin.
- **Tout part de `main`** : pas de branche longue vie, le travail non mergé de Budget a coûté
  le projet.
- **La donnée d'abord, l'archi ensuite** — Portal6 a déjà cette culture (le vault est la vérité,
  la DB un artefact) ; la préserver quand l'applicatif arrivera.

## Pistes d'intégration dans Portal6

### Horizon 1 — l'espace musique, maintenant (patterns, pas de code à porter)

Tous les repos sont Android/Kotlin ; Portal6 est Python + SQLite sans applicatif. À court terme
on intègre donc des **idées**, pas des fichiers :

| Idée | Origine | Application musique |
|---|---|---|
| Rule Pattern (liste de règles + fold) | KMPGameMaster | Règles de qualité de données sur `tracks` (tags manquants, doublons de normalisation, incohérences genre/energy déjà ébauchées dans `coherence_check.py`) — les formaliser en règles composables plutôt qu'en scripts ad hoc |
| Journal d'événements typé | KMPGameMaster | Journal des runs ETL (`HARVEST_STARTED`, `QUOTA_HIT`, `DB_REBUILT`…) en table SQLite — remplace la lecture des logs ANSI de `progress.py` et prépare un dashboard |
| Validation par prédicats | playground `tool-validation` | Même usage : contraintes déclaratives sur les lignes du vault avant hydratation de la DB |
| Écran/commande de seeding dev | Budget `feature-developer` | Une commande `npm run seed` qui monte une mini-DB de test (100 tracks) pour développer l'applicatif sans les 63 Mo |
| Layout de graphes (Fruchterman-Reingold…) | Budget `tool-algo` | La killer feature visuelle de l'espace musique : graphe artistes/genres/playlists. Les algos sont en Kotlin mais l'implémentation est simple à porter (ou networkx fait l'affaire côté Python) |

### Horizon 2 — la structure multi-espaces du portail

- **Le Router pattern devient le contrat d'espace.** Transposé : chaque espace (musique, puis
  budget, jeux…) déclare son contrat (ses routes, ses entités, ses jobs ETL) sans rien connaître
  du shell ; le shell Portal6 implémente/agrège. C'est la même inversion de dépendance que
  `XFragmentNavigation` → `MainActivityRouter`, appliquée au portail. À poser dès la première
  ligne de `apps/`.
- **design-core / design-app devient design-portal / design-espace** : tokens partagés du shell,
  identité par espace. À garder en tête pour l'UI, quel que soit le framework.
- **Les IDs `P6-*` sont déjà le bon geste** (préfixe projet, pas domaine). Prérequis absolu avant
  tout applicatif : **les geler** (stables au rebuild), sinon toute référence UI/API casse.

### Horizon 3 — les futurs espaces (matière première disponible)

- **Espace budget** : `domain-accounting` (partie double, testé) est la fondation correcte —
  après correction de ses 3 bugs. Le modèle 50/30/20 + ICEBOX de Budget reste une bonne spec
  produit.
- **Espace jeux** : KMPGameMaster est à ~4 corrections d'être utilisable en soirée
  (`isDebug=false`, 5 rôles sans action, chaînes en dur, remplacer Realm) — il peut vivre comme
  app satellite ou devenir un espace.
- **Choix de stack `apps/`** : si Kotlin/Compose Multiplatform est retenu, KMPGameMaster est le
  template de départ (Voyager + Koin + MaterialKolor éprouvés ensemble). Si web (plus naturel
  pour un « portail » au-dessus d'une DB SQLite sur la tour, cf. roadmap web radio Docker),
  aucun des anciens repos n'apporte de code — seulement les patterns ci-dessus.

## Points d'hygiène (indépendants de Portal6, à traiter vite)

1. **Clés Google Cloud exposées** sur `origin/feature/place` du repo public Mapix → vérifier/révoquer.
2. **Packages `com.seloger.android.*`** dans `frgrz-playground/tool-validation` → renommer avant
   toute réutilisation.
3. Ne rien reprendre de : RxJava2, dagger-android, DataBinding, Realm, Bintray, Stetho (tous
   morts ou dépréciés).

## À trancher au refinement

1. **Stack de `apps/`** : web (API Python/FastAPI + front) vs Kotlin Multiplatform vs autre.
   C'est LA décision structurante ; le repo n'exprime aujourd'hui aucune préférence.
2. **Gel des IDs `P6-*`** : quand et comment (la DB devient-elle référentiel maître, ou le vault
   garde-t-il la vérité avec une table de correspondance persistée ?).
3. **Périmètre de la première tranche verticale** de l'espace musique (candidat : consulter le
   référentiel — recherche, fiche track, statut de matching — avant toute écriture).
4. **Adoption des règles anti-récidive** ci-dessus comme conventions du repo (CLAUDE.md à créer).
