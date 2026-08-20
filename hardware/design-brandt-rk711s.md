# Design — Brandt RK 711S → web-radio / enceinte Bluetooth autonome

**Owner :** François Grzybowski
**Statut :** Design — **rien n'est construit, rien n'est acheté, aucun outillage possédé**
**Date :** 2026-08-12 (révision 2 — après pivot d'architecture, voir §12)
**Cible :** poste radio-cassette portable **Brandt RK 711S** (entrée secteur IEC C7 d'origine)
**Piste :** POSTE — la piste SERVEUR est décrite dans
[design-serveur-azuracast.md](design-serveur-azuracast.md)

> **À LIRE EN PREMIER — instructions d'exécution.**
> Cette note est un **walkthrough de construction**, exécuté **une phase à la fois, dans
> l'ordre**. Après chaque phase il y a un encadré **STOP / VÉRIFIER** : on ne démarre pas la
> phase suivante tant que la vérification n'est pas passée. Si une vérification échoue, on
> **corrige la phase en cours** — on ne contourne pas, on n'avance pas.
> **On mesure, on ne suppose pas** : toute valeur marquée `?` doit être **relevée sur le poste
> réel ou sur la fiche du composant acheté** avant d'être câblée. Le **bloc de mesures de la
> Phase 0 bloque aujourd'hui la moitié des décisions restantes.**
> La note s'enrichit au fil du projet : les décisions se figent dans le tableau du §3, les
> mesures réelles remplacent les `?`, le journal §12 garde la trace des changements de cap.

**Notes compagnes :** [design-visualiseur.md](design-visualiseur.md) (écran, visualiseur,
couche applicative) · [design-alimentation.md](design-alimentation.md) (batterie, secteur,
sécurité) · [bom.md](bom.md) (nomenclature + outillage).

---

## 0. L'objectif en un paragraphe

Transformer un ghettoblaster Brandt RK 711S en **appareil connecté autonome** en gardant
**l'extérieur intact** : la grosse molette et son aiguille AM/FM sélectionnent des **web
radios** hébergées sur un serveur personnel, les **boutons mécaniques du lecteur cassette**
pilotent la lecture, le **lecteur cassette est remplacé par un écran** qui affiche un
**visualiseur audio réactif façon Winamp/MilkDrop**, le poste se comporte aussi en **enceinte
Bluetooth**, fonctionne **sur batterie** comme **sur son secteur d'origine**, et se connecte
au **hotspot du téléphone** en mobilité. Tout ce qui est visible et manipulable reste d'époque ;
tout ce qui est derrière est neuf.

### Ce que le poste n'est pas

Le poste est un **client**. Les stations sont produites et diffusées par un
**serveur AzuraCast** personnel ([design-serveur-azuracast.md](design-serveur-azuracast.md)) ;
le poste ne stocke ni ne diffuse rien. Il **n'affiche pas de vidéo** : l'image est **générée
localement à partir du son** (§4.7). Ces deux points suppriment deux chantiers entiers —
stockage média embarqué, et production/transport d'un flux vidéo.

Le poste **n'a pas de micro** (tranché au cadrage : pas de commande vocale, pas de talkie —
la question est close, ne pas la rouvrir). Enfin, un projet connexe de **réseau mesh**
(LoRa / Wi-Fi mesh) existe, mais le mesh sera **géré côté serveur** : le poste reste un
simple client Wi-Fi, **aucune carte radio ni antenne supplémentaire** n'est à prévoir ici.

---

## 1. Contraintes dures

1. **L'esthétique d'origine prime.** Aucune commande visible ajoutée, aucune découpe visible
   autre que celle du lecteur cassette (qui devient l'écran) et un port USB **discret**. Une
   solution qui impose un trou ou un bouton en façade est disqualifiée avant d'être évaluée.
2. **Les commandes d'origine sont conservées mécaniquement.** On ne remplace pas la molette
   ni les touches cassette : on **capte** le mouvement existant.
3. **Le secteur 230 V est présent à l'intérieur du poste** (prise C7 d'origine). Sujet de
   sécurité, pas de confort — [design-alimentation.md](design-alimentation.md). **Jamais de
   230 V sur une breadboard.**
4. **Le poste doit rester portable** : batterie + hotspot téléphone, sans manipulation autre
   qu'un interrupteur.
5. **Le poste doit jouer vite après allumage.** C'est une radio. Le temps de démarrage est un
   critère d'acceptation, pas un détail (§7).
6. **Rien n'est acheté avant d'être vérifié.** La BOM est une liste de courses en cours
   d'instruction, pas une commande.
7. **Le budget n'est pas une contrainte.** Cadrage explicite : « indéfini, ne doit pas être
   une limitation », outillage compris. Les arbitrages se font sur la qualité et la
   simplicité, jamais sur le prix.

---

## 2. Architecture cible

```
                              INTERNET
                                 │
                    ┌────────────▼─────────────┐
                    │  Serveur AzuraCast       │  → design-serveur-azuracast.md
                    │  flux Icecast + API      │
                    └────────────┬─────────────┘
                                 │  Wi-Fi (box ou hotspot téléphone)
                                 │
   ENTRÉES                ┌──────▼───────────┐             SORTIES
 ┌───────────┐  I²C       │                  │   DSI    ┌──────────┐
 │ Molette   ├───────────►│  Raspberry Pi 4  ├─────────►│  Écran   │
 │ + aiguille│  ADS1115   │                  │          │visualiseur│
 └───────────┘            │  Linux appliance │          └──────────┘
 ┌───────────┐  GPIO      │  rootfs en       │
 │ Boutons   ├───────────►│  lecture seule   │   I²S    ┌──────────┐   ┌───────────┐
 │ cassette  │  pull-up   │                  ├─────────►│ PCM5102  ├──►│ Ampli D   │
 └───────────┘            │                  │          └──────────┘   └─────┬─────┘
 ┌───────────┐  USB       │                  │                               │
 │ Clavier   ├───────────►│                  │◄──── Bluetooth A2DP sink      ▼
 └───────────┘  natif     └──────┬───────────┘      (BlueZ, téléphone)  HP d'origine
                                 │ I²C
                                 ▼
                          mesure batterie

  ALIMENTATION  →  design-alimentation.md
    IEC C7 ─► chargeur 12,6 V CC/CV ─► BMS 3S ─► pack 3S 18650
                                          ├──► ~12 V : ampli
                                          └──► buck 5 V : Pi, écran, périphériques
```

**Une seule carte, un seul logiciel.** Pas de second cerveau, pas de protocole inter-cartes à
écrire, pas de contrôleur USB host à porter : Linux fournit nativement l'USB, le Bluetooth, le
GPIO, l'I²S et OpenGL ES.

---

## 3. Décisions

| # | Sujet | État | Décision |
|---|---|---|---|
| **D1** | Poste | **Figée** | Brandt RK 711S. |
| **D2** | Cerveau | **Figée (rév. 2)** | **Raspberry Pi 4, 4 Go.** L'ESP32 et Android sont écartés — voir §12. |
| **D3** | Capteur de molette | **Figée** | Potentiomètre linéaire 10 kΩ entraîné par le mécanisme existant, accouplement souple. Lu via **ADS1115** (le Pi n'a pas d'ADC). |
| **D4** | Boutons cassette | **Figée** | Micro-switchs à levier sur les leviers d'origine, contacts secs vers GPIO du Pi avec pull-up interne. |
| **D5** | Chaîne audio | **Figée** | I²S → PCM5102 → ampli classe D → HP d'origine. Sur Linux, l'I²S est un `dtoverlay`, pas un chantier. |
| **D6** | Entrée secteur | **Figée** | Réutiliser le **C7 d'origine**. |
| **D7** | **Affichage** | **Figée (rév. 2)** | **Visualiseur audio réactif généré localement** (projectM / MilkDrop). **Aucune vidéo** : ni source, ni décodage, ni transport. → [design-visualiseur.md](design-visualiseur.md). |
| **D8** | Ampli | **Ouverte** | TPA3110 vs TPA3116D2 — **à trancher après mesure des HP** (Phase 0). |
| **D9** | Écran | **Ouverte** | **Interface DSI** retenue ; taille, résolution et modèle **dépendent de la mesure du logement cassette** (Phase 0). |
| **D10** | Chargeur secteur | **Ouverte** | Chargeur Li-ion 12,6 V CC/CV, référence à valider. |
| **D11** | Pack batterie | **Ouverte** | Cellules, capacité, BMS, agencement — **se décide avec la consommation mesurée**. |
| **D12** | Bluetooth TX | **v2** | Émission vers casque/enceinte externe : hors périmètre v1, facile à ajouter sous Linux. |
| **D13** | Clavier USB | **Figée (rév. 2)** | **USB host natif** sur le Pi. Le MAX3421E disparaît. Reste à décider où sort la prise en façade (Phase 8). |
| **D14** | Couche applicative | **Ouverte** | Route web (kiosque + Butterchurn) vs route native (libprojectM). → [design-visualiseur.md](design-visualiseur.md). |
| **D15** | Modèle de veille | **Ouverte** | Le Pi **ne sait pas se suspendre en RAM** : arrêt complet + démarrage rapide, ou idle permanent écran éteint ? → §7 et [design-alimentation.md](design-alimentation.md). |

---

## 4. Sous-systèmes

### 4.1 Sélecteur de station — la molette

Le mécanisme d'origine (molette + aiguille devant l'échelle AM/FM) est **conservé tel quel** ;
on lui ajoute un potentiomètre entraîné par le mouvement.

**Mécanique.** Deux voies, à départager en Phase 0 :

- **(a) reprendre l'axe du condensateur variable d'accord** — il est déjà entraîné par la
  cordelette, déjà fixé, déjà doté de butées propres, et sa course (~180°) est compatible avec
  un potentiomètre standard. Remplacer le CV par le potentiomètre au même emplacement est la
  solution la plus propre si l'axe est accessible.
- **(b) accouplement souple ajouté** — poulie + O-ring, tube silicone, pièce imprimée.

Dans les deux cas la règle est la même : **les butées mécaniques du poste ne doivent jamais
forcer sur l'axe du potentiomètre.** C'est le point de fragilité n°1 du sous-système.

**Électrique.** Extrémités sur 3,3 V et GND, curseur vers une entrée de l'**ADS1115** (I²C,
16 bits — bien meilleur que ce qu'aurait donné un ADC de microcontrôleur), avec filtrage RC.

**Logiciel.**

```
lecture ADS1115 (moyenne glissante / médiane sur N échantillons)
        ▼
normalisation → position ∈ [0,1]   (bornes issues de la CALIBRATION, pas de la pleine échelle)
        ▼
recherche de la station dont `dial` est la plus proche
        ▼
hystérésis : changement seulement si la nouvelle station gagne d'une marge M,
             et si la position est stable pendant T ms
        ▼
station sélectionnée → lancement du flux
```

- **Calibration** : une procédure (butée basse ↔ butée haute) enregistre les valeurs réelles.
  Sans elle, l'aiguille et la station ne coïncident pas.
- **Hystérésis + temporisation** : indispensables, sinon la station saute en permanence près
  d'une frontière et chaque saut relance une connexion.
- **Correspondance aiguille ↔ station** : chaque station porte une position `dial` ∈ [0,1] sur
  l'échelle. C'est ce qui rend le geste crédible.

> **Le cadran ne doit pas être vide.** Le serveur porte 3 stations aujourd'hui, 4+ à terme
> ([design-programmation-editoriale.md](design-programmation-editoriale.md)) : réparties sur
> toute la course, ça donne d'immenses zones mortes et un geste sans récompense. Deux
> corrections quasi gratuites, à intégrer dès la Phase 3 :
> **(1)** occuper le cadran avec plus d'entrées que de stations (variantes, playlists,
> « apps »), **(2)** jouer un **souffle de station** entre deux positions. C'est probablement
> le moment où l'objet cesse d'être fonctionnel pour devenir juste.

### 4.2 Boutons du lecteur cassette

Les leviers d'origine actionnent des micro-switchs, lus sur les GPIO du Pi (pull-up interne
activé en logiciel — pas de résistance externe nécessaire).

| Bouton cassette | Fonction |
|---|---|
| PLAY | Play / Pause |
| FWD | Station suivante |
| RWD | Station précédente |
| STOP | Stop / Mute |
| REC (ou autre) | Changement de mode (Radio ↔ Bluetooth) |

```
GPIO (pull-up interne) ──── micro-switch ──── GND

relâché → HIGH        appuyé → LOW
```

Anti-rebond logiciel (~20–50 ms) obligatoire.

> **⚠️ Conflit mécanique à instruire en Phase 0.** Le projet dit deux choses en même temps :
> le lecteur cassette est **déposé** pour loger l'écran, **et** ses touches sont **réutilisées**.
> Or sur un poste de cette génération c'est **la même pièce** : les touches forment un clavier
> « piano » solidaire du bloc transport, avec verrouillage et interverrouillage. Retirer le
> mécanisme, c'est retirer ce qui rappelle et guide les leviers.
> Conséquence probable : conserver la façade du clavier et son axe, **fabriquer une platine de
> reprise** (impression 3D) portant ressorts de rappel et micro-switchs, et libérer la
> profondeur derrière pour l'écran. C'est un poste de travail de la Phase 8 qu'il faut
> reconnaître maintenant, parce qu'il conditionne la profondeur disponible — donc D9.
>
> **À mesurer :** combien de touches sont exploitables, leur course, leur effort, et
> **lesquelles sont à verrouillage** plutôt qu'à rappel. Une touche verrouillée donne un
> **état**, pas un **événement** : « FWD = station suivante » n'a aucun sens sur une touche qui
> reste enfoncée. Le tableau ci-dessus est provisoire tant que ce relevé n'est pas fait.

### 4.3 Chaîne audio

```
flux Icecast → Wi-Fi → Pi (décodage) → I²S → PCM5102 → ampli classe D → HP d'origine
```

- **I²S sur Raspberry Pi** : activé par un `dtoverlay` (famille `hifiberry-dac` pour un
  PCM5102). C'est une ligne de configuration, pas un développement.
- **Repli** : si le PCM5102 pose problème, un **DAC USB** fonctionne nativement — mais l'I²S
  est plus propre et moins encombrant.
- **Ampli** : TPA3110 ou TPA3116D2 — **D8 se tranche après mesure**, pas avant.

> **À mesurer avant tout achat d'ampli :** impédance des HP (4 Ω ? 8 Ω ?), puissance
> admissible, **et si le poste est mono ou stéréo**. Un ghettoblaster d'époque a souvent des HP
> de quelques watts : un ampli surdimensionné n'apporte rien et détruit les HP au premier
> excès. Le critère est **« ne pas dépasser les HP »**, pas « avoir des watts ».

- **Découplage** : 1000 µF / 25 V + 100 nF **au plus près des bornes d'alimentation de
  l'ampli**. Détail dans [design-alimentation.md](design-alimentation.md).
- **Câbles HP** torsadés · liaison DAC → ampli en **câble blindé** · **masse en étoile**
  obligatoire.

### 4.4 Bluetooth

**Mode RX / sink — dans le périmètre v1.**

```
Téléphone ──A2DP──► Pi (BlueZ) ──I²S──► PCM5102 ──► ampli ──► HP
```

Le Pi a deux radios distinctes : **Wi-Fi et Bluetooth fonctionnent simultanément**. La
contrainte « modes exclusifs » qui pesait sur la version ESP32 **n'existe plus** — mais on
garde des **modes d'usage** exclusifs (§7), parce que c'est le comportement attendu d'un poste
de radio, pas parce que le matériel l'impose.

**Option matérielle à garder en tête (liée à D15).** Un **module récepteur Bluetooth
autonome** (~5 €) injecté sur une entrée analogique de l'ampli rendrait le poste enceinte
Bluetooth **même Pi éteint**, en 2 secondes. À réévaluer quand le modèle de veille sera
tranché ; inutile si le poste reste allumé en permanence.

**Mode TX / source (D12) — v2.** Facile sous Linux, hors périmètre v1.

### 4.5 Réseau et stations — le contrat avec le serveur

| Scénario | Usage |
|---|---|
| Wi-Fi domestique | Poste à la maison, réseau connu. |
| Hotspot téléphone | Poste en mobilité. |

Le poste garde une liste de réseaux connus et tente le premier disponible.

**Ce que le poste consomme du serveur** ([design-serveur-azuracast.md](design-serveur-azuracast.md)) :

| Besoin | Source |
|---|---|
| Liste des stations | API AzuraCast (`/api/stations`) |
| Titre en cours, artiste, pochette | API AzuraCast (`/api/nowplaying`) + événements temps réel |
| Flux audio | URLs Icecast des stations |
| Ambiance du visualiseur | Énergie **E1–E5** du créneau en cours (§ éditorial) — **optionnel mais joli** |

**Conséquences directes :**

- **Il n'y a pas de `stations.json` à écrire.** L'API AzuraCast fait le travail. Le poste garde
  un **cache local** de la dernière réponse pour démarrer sans réseau.
- **La question HTTP vs HTTPS est close** : elle n'existait que par contrainte mémoire de
  l'ESP32.
- **Le champ `dial`** (position sur l'échelle) n'existe pas dans AzuraCast : il vit **côté
  poste**, dans un fichier de correspondance `station → dial` que le poste maintient.

> **À vérifier au moment du branchement (Phase 2) :** noms exacts des routes API sur la version
> déployée, et **CORS** si la route web est retenue pour la couche applicative (D14) —
> c'est une contrainte réelle, voir [design-visualiseur.md](design-visualiseur.md).

### 4.6 Port USB / clavier

**Résolu par le choix du Pi** : USB host natif, un clavier se branche et fonctionne. Il reste
à décider **où sort la prise en façade** de manière discrète (Phase 8) — un port de panneau
relié en interne, ou l'exploitation d'une ouverture existante.

Le clavier sert à configurer (Wi-Fi, saisie, navigation). Un **portail de configuration servi
par le poste** reste souhaitable en complément : c'est le chemin de récupération quand aucun
réseau connu n'est joignable (Q4).

### 4.7 Écran et visualiseur

Le lecteur cassette est déposé ; l'écran prend sa place et affiche un **visualiseur audio
réactif** — fractales, formes, couleurs, réagissant au rythme, dans l'esprit Winamp/MilkDrop —
avec les informations en incrustation.

**Aucune vidéo n'est décodée ni transportée.** L'image est calculée sur le poste à partir du
PCM qu'il joue déjà. C'est la simplification majeure de la révision 2 : elle supprime la source
vidéo, le transport, le stockage et le décodage.

→ **[design-visualiseur.md](design-visualiseur.md)** pour le choix du moteur, de la couche
applicative (D14) et de l'écran (D9).

Informations à afficher en toutes circonstances : nom de la radio · titre de la piste · état de
lecture · Wi-Fi · Bluetooth · batterie · éventuellement la position sur l'échelle.

```
┌──────────────────────────┐
│                          │
│      VISUALISEUR         │
│    (fractales, rythme)   │
│                          │
│ Radio : XXXXX     ▮▮▮▯ 🔋│
│ Track : YYYYY            │
└──────────────────────────┘
```

### 4.8 Alimentation

Pack 3S 18650 + BMS, rails ~12 V (ampli) et 5 V (Pi + écran), chargeur secteur sur le C7
d'origine, mesure de batterie, masse en étoile, sécurité 230 V.
→ **[design-alimentation.md](design-alimentation.md)**.

---

## 5. Raccordement au Raspberry Pi

> Pas de plan de brochage figé à ce stade : il se fera avec les modules réellement achetés.
> Les principes, eux, sont arrêtés.

| Fonction | Interface | Note |
|---|---|---|
| Molette | **I²C** → ADS1115 | Le Pi n'a **pas d'ADC**. L'ADS1115 (16 bits) donne une résolution très supérieure à ce qu'on visait initialement. |
| Mesure batterie | **I²C** → 2ᵉ voie de l'ADS1115 | Le même composant sert les deux mesures. |
| Boutons cassette | **GPIO** + pull-up interne | 4 à 5 entrées. |
| Écran | **DSI** | Nappe fine, adaptée à l'espace contraint. |
| Audio | **I²S** (GPIO 18/19/21 par défaut) | `dtoverlay` — attention, ces broches deviennent indisponibles pour autre chose. |
| Clavier | **USB** | Natif. |
| Réseau | **Wi-Fi intégré** | Bluetooth intégré également, radios distinctes. |

**Pièges à connaître :**

1. L'activation de l'**I²S réserve des GPIO** — établir le plan de brochage *après* avoir
   choisi le DAC, pas avant.
2. Le **DSI du Pi 4** est unique et occupé dès qu'un écran est branché : pas de second écran.
3. Prévoir les **pull-up externes I²C** si le bus est long (nappe vers l'ADS1115 déporté).
4. Le Pi n'a **pas d'entrée analogique** : toute mesure passe par l'ADS1115. Ne pas
   « improviser » un pont diviseur directement sur un GPIO — il est numérique et en 3,3 V.

---

## 6. Logiciel

**Système :** Raspberry Pi OS (64 bits) en **appliance** :

- **rootfs en lecture seule** (overlayfs) — supprime le risque de corruption de carte SD ;
- services élagués, pas de gestionnaire de session ni de bureau ;
- démarrage direct sur l'application (§7 : le temps de démarrage est un critère) ;
- **mises à jour à distance** prévues dès le départ — le poste sera refermé.

**Services :**

| Service | Rôle |
|---|---|
| Lecture | Flux Icecast → I²S (mpv/mpd/GStreamer ou lecteur intégré à l'app) |
| Panneau | Lecture ADS1115 (molette, batterie), GPIO (boutons), anti-rebond, calibration |
| Visualiseur / UI | Rendu plein écran, incrustation des informations → [design-visualiseur.md](design-visualiseur.md) |
| Bluetooth | BlueZ, profil A2DP sink |
| Réseau | Multi-réseaux, cache API, portail de configuration |

Le découpage exact dépend de D14 (route web ou native). Le principe qui ne bouge pas : **le
panneau physique est un service séparé qui publie un état**, et l'interface le consomme — sinon
tout le poste dépend de la santé du moteur graphique.

---

## 7. Modes, états et démarrage

```
        ┌──────────────┐   MODE    ┌──────────────┐
        │   RADIO      │──────────►│  BLUETOOTH   │
        │ flux + visu  │◄──────────│  A2DP sink   │
        └──────┬───────┘   MODE    └──────────────┘
               │
      molette / FWD / RWD → changement de station
      PLAY → play/pause · STOP → stop/mute

        ┌──────────────┐
        │ CONFIGURATION│  ← clavier USB ou portail web
        │ réseau, cal. │
        └──────────────┘
```

Le mode courant, la dernière station et la calibration survivent à une coupure.

### Le temps de démarrage (D15)

C'est **la seule vraie faiblesse** du choix Raspberry Pi, et elle est frontale pour une radio.
Ordres de grandeur : Raspberry Pi OS standard ~20 s avant l'application ; image appliance
taillée ~8–10 s ; en dessous, c'est de l'orfèvrerie.

**Et le Pi ne sait pas se suspendre en RAM** — il n'y a pas de veille façon téléphone. Les
options réelles :

| Modèle | Conséquence |
|---|---|
| **Arrêt complet + démarrage rapide** | Consommation nulle éteint, mais ~10 s d'attente à chaque allumage. |
| **Jamais éteint** : Pi en veille écran, audio coupé | Réponse instantanée, mais consommation permanente sur batterie. |
| **Mixte** : arrêt sur batterie, toujours allumé sur secteur | Le plus proche de l'usage réel. Plus de logique à écrire. |

**À trancher en Phase 7**, avec la consommation d'idle mesurée en main — pas avant. Si le
modèle « arrêt complet » l'emporte, le module Bluetooth autonome du §4.4 reprend tout son
intérêt.

---

## 8. Plan de réalisation

### PHASE 0 — Relevés sur le poste et outillage (aucun achat électronique)

**C'est la phase bloquante aujourd'hui.** Ouvrir le Brandt et mesurer :

- impédance, puissance et nombre des **haut-parleurs** ; mono ou stéréo → débloque **D8**
- **profondeur, hauteur, largeur** réellement disponibles derrière le logement cassette, une
  fois le mécanisme déposé → débloque **D9**
- **touches cassette** : nombre exploitable, type (poussoir / verrouillage), solidarité avec le
  bloc transport → conditionne §4.2 et la platine de reprise
- **mécanisme d'accord** : cordelette + condensateur variable ? axe accessible ? course ?
  butées franches ? → départage (a) et (b) du §4.1
- **compartiment à piles** d'origine : existe-t-il, quelle taille → logement du pack
- potentiomètre de volume d'origine, autres commandes réaffectables
- état du câblage secteur et du porte-fusible

Acheter l'**outillage** de base ([bom.md](bom.md) §6).

> **STOP / VÉRIFIER (Phase 0) :** toutes les mesures **écrites dans cette note** à la place des
> `?` · D8 et D9 devenues tranchables · le fer chauffe, le multimètre mesure, l'alimentation de
> labo débite.

### PHASE 1 — Audio minimal sur table

`Pi → PCM5102 → ampli → un HP`, sur **alimentation de laboratoire**. Lecture d'un flux
public, en dur.

> **STOP / VÉRIFIER (Phase 1) :** son propre **30 minutes sans coupure ni saturation** à volume
> réel · **consommation relevée** (elle dimensionne batterie, buck et D15).

### PHASE 2 — Réseau et serveur

Multi-réseaux (box + hotspot), lecture des flux du serveur AzuraCast, **API stations +
now-playing** branchée et mise en cache, reconnexion automatique.

> **STOP / VÉRIFIER (Phase 2) :** bascule box → hotspot sans intervention · 30 min de lecture
> d'une station du serveur · titres et pochettes justes en temps réel · coupure Wi-Fi de 60 s →
> reprise automatique.

### PHASE 3 — Sélecteur

ADS1115 au banc, calibration, hystérésis, snap, souffle inter-stations. Puis accouplement
mécanique sur la molette.

> **STOP / VÉRIFIER (Phase 3) :** balayage lent de toute l'échelle → **aucune oscillation
> parasite** · aiguille et station cohérentes aux deux butées · rotation en butée **sans
> contrainte sur l'axe du potentiomètre**.

### PHASE 4 — Boutons

Micro-switchs sur les leviers, anti-rebond, mapping du §4.2 corrigé par les relevés Phase 0.

> **STOP / VÉRIFIER (Phase 4) :** 20 appuis par touche → 20 actions, **zéro double-déclenchement**,
> zéro action fantôme.

### PHASE 5 — Écran et visualiseur

Ne démarre qu'après **D9** (donc après Phase 0) et **D14**. D'abord la couche information,
ensuite seulement le visualiseur.

> **STOP / VÉRIFIER (Phase 5) :** toutes les informations du §4.7 justes en temps réel · le
> visualiseur tient une cadence stable · **aucune coupure audio** — c'est le vrai test.

### PHASE 6 — Bluetooth

BlueZ, A2DP sink, bascule de mode, cohabitation avec le visualiseur.

> **STOP / VÉRIFIER (Phase 6) :** appairage depuis un téléphone · 30 min de lecture · retour en
> mode Radio et **flux qui repart tout seul**.

### PHASE 7 — Alimentation

Batterie, BMS, chargeur secteur, rails, fusibles, condensateurs, masse en étoile. **Le 230 V
n'entre dans le montage qu'ici.** C'est aussi ici que **D15** se tranche.
→ [design-alimentation.md](design-alimentation.md).

> **STOP / VÉRIFIER (Phase 7) :** voir la note dédiée.

### PHASE 8 — Intégration mécanique

Fixation définitive : Pi, DAC, ampli, batterie, BMS, chargeur, écran, prise USB,
potentiomètre, micro-switchs, **platine de reprise du clavier cassette**.

> **STOP / VÉRIFIER (Phase 8) :** poste refermé, **toutes les fonctions des phases 1 à 7 encore
> vertes** · rien qui bouge quand on secoue · aucune pièce sous 230 V accessible, même boîtier
> ouvert.

### PHASE 9 — Finition

Câblage, thermique, parasites audio, calibration finale, esthétique, réglage du temps de
démarrage. Réévaluation des options v2 (Bluetooth TX, apps supplémentaires).

> **STOP / VÉRIFIER (Phase 9) :** une heure d'écoute, sur batterie **et** sur secteur, sans
> qu'on ait envie de rouvrir le poste.

---

## 9. Questions ouvertes

1. **Q1 — Les haut-parleurs.** Impédance, puissance, mono/stéréo ? Bloque **D8**. Phase 0.
2. **Q2 — Le logement cassette.** Dimensions utiles, **profondeur** surtout. Bloque **D9**.
   Phase 0.
3. **Q3 — Les touches cassette.** Nombre, type, solidarité avec le bloc transport (§4.2).
   Phase 0.
4. **Q4 — Configuration réseau hors ligne.** Portail servi par le poste, clavier USB, ou les
   deux ? Quel déclencheur quand aucun réseau connu n'est joignable ?
5. **Q5 — Le cadran.** Que met-on sur l'échelle en plus des 3-4 stations pour qu'elle ne soit
   pas vide (§4.1) ? Et le souffle inter-stations : on le fait ?
6. **Q6 — Modèle de veille (D15).** Arrêt complet, toujours allumé, ou mixte ? Phase 7.
7. **Q7 — Volume.** On garde le potentiomètre d'origine en analogique dans la chaîne, on le lit
   sur l'ADS1115 pour piloter le volume logiciel, ou les deux ?
8. **Q8 — Chargeur secteur, pack, autonomie visée.**
   → [design-alimentation.md](design-alimentation.md).
9. **Q9 — Couche applicative (D14).** Route web ou native ?
   → [design-visualiseur.md](design-visualiseur.md).

---

## 10. Liste des interdits (DO-NOT)

1. **Ne pas** amener du 230 V sur une breadboard, un montage provisoire, ou un module non fixé.
   Phases 1 à 6 : **alimentation de laboratoire uniquement**.
2. **Ne pas** acheter l'ampli avant d'avoir mesuré les haut-parleurs (Q1).
3. **Ne pas** commander l'écran avant d'avoir mesuré la profondeur derrière la façade (Q2).
4. **Ne pas** brancher un pont diviseur ou un potentiomètre directement sur un GPIO du Pi :
   il n'y a pas d'ADC (§5.4).
5. **Ne pas** déposer le bloc transport cassette avant d'avoir compris comment les touches
   seront reprises (§4.2) — c'est irréversible.
6. **Ne pas** faire passer les courants de l'ampli dans les masses du Pi et du DAC — masse en
   étoile.
7. **Ne pas** relier le potentiomètre à la molette par un accouplement rigide (§4.1).
8. **Ne pas** modifier une face visible du poste au-delà du logement cassette et du port USB
   discret (§1.1).
9. **Ne pas** réintroduire de la vidéo dans le périmètre : D7 est tranchée, l'image est générée
   localement (§4.7).
10. **Ne pas** passer à la phase suivante avec une vérification rouge.
11. **Ne pas** figer la BOM ([bom.md](bom.md)).

---

## 11. Ce que le poste attend du serveur

Résumé du contrat, détaillé au §4.5 et côté serveur dans
[design-serveur-azuracast.md](design-serveur-azuracast.md) :

| Le poste a besoin de | Statut côté serveur |
|---|---|
| Flux Icecast stables, joignables depuis Internet | **AzuraCast bloqué** — installation à reprendre |
| API liste des stations | Fournie nativement par AzuraCast |
| API now-playing (titre, artiste, pochette) | Fournie nativement |
| Énergie E1–E5 du créneau (optionnel, pour le visualiseur) | Concept défini, non exposé |
| CORS, si route web retenue (D14) | À configurer |

**Le serveur est sur le chemin critique de la Phase 2.** Tant qu'AzuraCast ne tourne pas, le
poste se teste sur des flux publics.

---

## 12. Journal

| Date | Événement |
|---|---|
| — | Sessions ChatGPT : concept, architecture ESP32 WROVER, choix du poste (Sharp → **Brandt RK 711S**), passage de l'USB-C PD au **secteur C7 d'origine**, ouverture de la question affichage. |
| 2026-08-11 | Reprise. Synthèse convertie en notes de design. Corrections : GPIO 16/17 indisponibles sur WROVER, ADC1/Wi-Fi, exclusivité Wi-Fi/Bluetooth, ajout de la Phase 0 et des encadrés de vérification. |
| 2026-08-12 | **Cadrage — pivot 1 (abandonné).** La vidéo et les apps embarquées étant des objectifs fermes, l'ESP32 est écarté (trop juste) ; passage envisagé à Android sur SBC Rockchip, avec MCU compagnon en USB HID. Motivation du choix Android : François est **dev Android de base** (aisance à créer du code, envie de veille sur la techno). |
| 2026-08-12 | **Cadrage — pivot 2 (retenu). Retour au Raspberry Pi, Android abandonné.** Et surtout : **la « vidéo » était en réalité un visualiseur type Winamp** — donc générée localement à partir du son, sans source ni flux vidéo. Conséquences : D2 = Pi 4 · D7 tranchée (visualiseur, pas de vidéo) · D13 résolu (USB natif) · MAX3421E, ESP32 et MCU compagnon supprimés · PCM5102 conservé (I²S trivial sous Linux) · nouvelles décisions D14 (couche applicative) et D15 (modèle de veille). **Le projet est plus simple qu'au départ, à ambition visuelle intacte.** |

> ⚠️ Le fichier `synthese_brandt_rk711s.md` des anciennes sessions est **incomplet** et **ne
> fait pas référence**.

---

## Liens

- [design-visualiseur.md](design-visualiseur.md) — écran (D9), visualiseur, couche
  applicative (D14).
- [design-alimentation.md](design-alimentation.md) — batterie, chargeur, rails, sécurité 230 V,
  modèle de veille (D15).
- [bom.md](bom.md) — nomenclature et outillage.
- [design-serveur-azuracast.md](design-serveur-azuracast.md) — la piste SERVEUR : ce qui
  produit les flux.
- [design-programmation-editoriale.md](design-programmation-editoriale.md) — les stations,
  l'échelle E1–E5, les grilles.
