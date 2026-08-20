# Design — Écran, visualiseur et couche applicative

**Owner :** François Grzybowski
**Statut :** D7 **tranchée** · D9 (écran) et D14 (couche applicative) **ouvertes**
**Date :** 2026-08-12
**Note mère :** [design-brandt-rk711s.md](design-brandt-rk711s.md)
**Piste :** POSTE

> **À LIRE EN PREMIER.**
> Cette note remplace l'ancienne note « affichage », qui instruisait un arbitrage
> ESP32 / Raspberry Pi / vidéo. **Cet arbitrage est clos** : le poste tourne sur Raspberry Pi
> et **n'affiche aucune vidéo** — l'image est **calculée à partir du son**. Ce qui reste à
> décider est plus modeste : quel moteur de rendu (**D14**) et quel écran (**D9**, bloqué par
> les mesures de la Phase 0).
> La Phase 5 ne démarre pas avant que ces deux points soient tranchés.

---

## 0. Le besoin, en un paragraphe

Le lecteur cassette est déposé ; sa découpe accueille un écran. L'affichage n'est pas un
accessoire : c'est **la partie visible de la modernisation**, la seule chose qui dise, quand on
regarde le poste, qu'il n'est plus de 1985. Il doit être **beau** — pas seulement informatif —
et il doit l'être **sans jamais faire hoqueter le son**, qui reste la fonction principale.

L'objectif exprimé est explicite : **un visualiseur type Winamp**, qui capte le flux joué et
l'interprète en **fractales rythmées**.

---

## 1. D7 — tranchée : visualiseur généré localement, pas de vidéo

**Décision : le poste ne lit aucune vidéo.** Il calcule son image à partir du PCM qu'il joue
déjà.

Ce que ça supprime, d'un coup :

- pas de source vidéo à produire ni à héberger ;
- pas de flux vidéo à transporter (donc pas de contrainte de débit en mobilité) ;
- pas de décodage vidéo, donc pas de dépendance à l'accélération matérielle ;
- pas de stockage média sur le poste ;
- pas de synchronisation son/image à gérer.

Ce que ça préserve intégralement : **l'ambition visuelle**. Un visualiseur MilkDrop est
exactement ce qui a été demandé — c'est *le* visualiseur Winamp.

> Une image générée à partir du son est aussi **toujours pertinente** : elle ne « ne correspond
> pas » à la musique, elle *est* la musique. Un clip vidéo générique aurait été, la plupart du
> temps, un habillage arbitraire.

---

## 2. Le moteur : « visualiseur Winamp » a un nom

| Nom | Ce que c'est |
|---|---|
| **MilkDrop** | Le visualiseur légendaire de Winamp. Ses « presets » sont des programmes de rendu (formes, ondes, équations par pixel) — c'est là que vivent les fractales et les déformations rythmées. |
| **projectM** | Réimplémentation libre de MilkDrop, en C++/OpenGL (GLES supporté). Rejoue les presets MilkDrop. C'est la voie **native**. |
| **Butterchurn** | Réimplémentation de MilkDrop 2 en **WebGL/JavaScript** (le moteur derrière Webamp). Rejoue les mêmes presets, dans un navigateur. C'est la voie **web**. |

Dans les deux cas : **des milliers de presets existants**, réutilisables tels quels, et
modifiables. On ne part pas d'une page blanche pour obtenir des fractales rythmées.

---

## 3. D14 — la couche applicative : deux routes

Le visualiseur ne vit pas seul : il faut l'**incrustation des informations** (radio, titre,
état, Wi-Fi, Bluetooth, batterie), la **navigation**, et à terme de petites **apps**. La
question est : dans quoi tout ça est-il écrit ?

### Route WEB — navigateur en kiosque + Butterchurn

```
flux Icecast ──► <audio> ──► Web Audio (AnalyserNode) ──► Butterchurn (WebGL) ──► écran
                                                        + overlay HTML/CSS
       service local (molette, boutons, batterie) ──WebSocket──┘
```

| | |
|---|---|
| ✅ | Overlay, menus, apps et animations en HTML/CSS/JS : la partie UI devient **triviale** et rapide à itérer. Butterchurn est prêt à l'emploi. Ajouter une app = ajouter une page. Rechargement à chaud pendant le développement. |
| ❌ | Chromium consomme de la RAM et du GPU ; sur un grand écran à cadence élevée, ça peut serrer. **Contrainte réelle : CORS** — l'`AnalyserNode` ne voit rien d'un flux audio cross-origin si le serveur n'envoie pas les bons en-têtes. Le serveur AzuraCast étant le nôtre, c'est réglable, mais c'est **à vérifier explicitement en Phase 2**. |

### Route NATIVE — libprojectM + OpenGL ES

```
lecteur (mpv/GStreamer) ──► PCM ──► libprojectM (GLES) ──► écran
                                  + overlay dessiné dans le même contexte GL
```

| | |
|---|---|
| ✅ | Meilleures performances, empreinte mémoire faible, démarrage plus rapide, accès direct au PCM sans détour. |
| ❌ | L'overlay et l'UI se dessinent à la main en GL : chaque écran d'information est du travail. Les futures « apps » n'ont pas de cadre naturel. C++ pour l'essentiel. |

### Recommandation

**Route web pour la v1**, pour trois raisons : l'écran est petit (donc la charge WebGL reste
modeste), l'UI et les apps sont la partie où on veut itérer vite, et Butterchurn donne le
visualiseur voulu sans écrire une ligne de moteur. **La route native est le repli documenté**
si la cadence déçoit en Phase 5 — le visualiseur change, pas le reste de l'architecture.

> **Décider avec des faits.** Une fois la Phase 1 en place (le poste joue une radio), un test
> d'une demi-journée suffit : Butterchurn plein écran sur l'écran retenu, un preset chargé,
> pendant que le son tourne. On regarde la cadence et on écoute. Si ça tient, D14 est close.

---

## 4. Ce que l'écran affiche

**Couche information (obligatoire, permanente ou rappelable) :** nom de la radio · titre de la
piste · état de lecture · Wi-Fi · Bluetooth · batterie · éventuellement la position sur
l'échelle.

```
┌──────────────────────────┐
│                          │
│      VISUALISEUR         │
│   (fractales, rythme)    │
│                          │
│ Radio : XXXXX     ▮▮▮▯ 🔋│
│ Track : YYYYY            │
└──────────────────────────┘
```

**Un raffinement gratuit :** le serveur connaît l'**énergie E1–E5** du créneau en cours
([design-programmation-editoriale.md](design-programmation-editoriale.md)). Le poste peut
l'utiliser pour **choisir la famille de presets et la palette** — calme et contemplatif à E1,
saturé et rapide à E5. C'est peu de code et beaucoup d'effet : l'objet paraît savoir ce qu'il
joue.

---

## 5. D9 — l'écran

**Interface : DSI** (décidée). Nappe fine, pas de connecteur encombrant — le bon choix dans un
logement contraint. Le Raspberry Pi 4 a **un** port DSI.

**Tout le reste dépend de la Phase 0.** L'ordre est : mesurer d'abord, choisir ensuite.

| À mesurer (poste ouvert, mécanisme déposé) | Décide |
|---|---|
| Largeur et hauteur visibles de la découpe cassette | Taille et ratio de la dalle |
| **Profondeur disponible derrière la façade** | Faisabilité tout court — un écran qui rentre en surface mais pas en profondeur est un écran à revendre |
| Place restante après la **platine de reprise des touches** ([design-brandt-rk711s.md](design-brandt-rk711s.md) §4.2) | La contrainte la plus sous-estimée |

**Repli sans risque :** un petit écran **HDMI** fonctionne sans aucune configuration, au prix
d'un connecteur volumineux. À garder en tête si le DSI retenu demandait trop de bricolage.

**Rétroéclairage :** prévoir sa commande dès le début (extinction après délai, réveil sur
action) — c'est autant une question d'autonomie que de discrétion le soir.

---

## 6. Questions ouvertes

1. **Q9 / D14 — route web ou native ?** Test du §3 après la Phase 1.
2. **Q2 / D9 — dimensions de la dalle.** Bloqué par la Phase 0.
3. **CORS sur AzuraCast** — vérifier que l'analyse audio côté navigateur est possible (route
   web). À faire en Phase 2, pas en Phase 5.
4. **Écran au repos** : que voit-on quand rien ne joue ? Visualiseur au ralenti, horloge,
   cadran, ou noir ?
5. **Extinction du rétroéclairage** : après quel délai, réveillé par quoi ?
6. **Les « apps »** : quelles sont les premières envisagées, au-delà de la radio ? (ça oriente
   D14 plus que le visualiseur lui-même)
7. **Presets** : on embarque une sélection figée, ou on en change au fil du temps ? Y a-t-il un
   geste utilisateur pour changer de preset (une touche cassette ?) ?

---

## 7. Liste des interdits (DO-NOT)

1. **Ne pas** réintroduire de la vidéo : D7 est tranchée (§1).
2. **Ne pas** écrire un moteur de visualisation de zéro — projectM et Butterchurn rejouent des
   milliers de presets MilkDrop existants (§2).
3. **Ne pas** commander l'écran avant les mesures de la Phase 0 (§5).
4. **Ne pas** juger l'affichage sur sa seule beauté : le critère d'acceptation de la Phase 5
   inclut **« zéro coupure audio »**.
5. **Ne pas** démarrer le visualiseur avant que la couche information soit affichée et juste —
   c'est elle qui sert tous les jours.
6. **Ne pas** faire dépendre l'état du poste (molette, boutons, batterie) du moteur graphique :
   le panneau est un service séparé qui publie un état
   ([design-brandt-rk711s.md](design-brandt-rk711s.md) §6).
