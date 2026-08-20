# Design — Alimentation, batterie et sécurité secteur

**Owner :** François Grzybowski
**Statut :** Design — **Phase 7** de la note mère ; le 230 V n'entre dans le montage qu'ici
**Date :** 2026-08-12 (révision 2 — cible Raspberry Pi, voir §4 et §12)
**Note mère :** [design-brandt-rk711s.md](design-brandt-rk711s.md)
**Piste :** POSTE

> **À LIRE EN PREMIER — sécurité.**
> Le Brandt RK 711S possède une **entrée secteur IEC C7 (« figure 8 »)** d'origine, qu'on
> réutilise (D6). Cela veut dire que **du 230 V est présent en permanence à l'intérieur d'un
> boîtier qu'on ouvre, qu'on transporte et qu'on pose sur ses genoux**. Ce n'est pas un
> sous-système parmi d'autres : c'est le seul du projet qui puisse blesser.
> **Le 230 V n'arrive qu'à la Phase 7, jamais sur une breadboard, jamais sur un montage
> provisoire, jamais sur un module qui n'est pas fixé mécaniquement.** Toutes les phases
> précédentes se font sur **alimentation de laboratoire**.
> Une prise C7 n'a **pas de terre** : le module secteur doit être **classe II / double
> isolation**, certifié, et entièrement capoté.

---

## 0. L'architecture d'alimentation en un schéma

```
                    230 V AC
                       │
                   IEC C7 (origine)
                       │
                  ┌────▼─────┐
                  │ fusible  │  ← côté secteur, avant tout le reste
                  └────┬─────┘
                       │
         ┌─────────────▼──────────────┐
         │ Chargeur AC → 12,6 V CC/CV │  classe II, certifié, capoté (D10)
         │ (pour pack Li-ion 3S)      │
         └─────────────┬──────────────┘
                       │ 12,6 V
                  ┌────▼─────┐
                  │  BMS 3S  │  protection : surcharge / décharge / surintensité / équilibrage
                  └────┬─────┘
                       │
                 ┌─────▼──────┐
                 │ Pack 3S    │  3 × 18650 en série — 11,1 V nominal, 9,0 à 12,6 V utile
                 │ 18650      │
                 └─────┬──────┘
                       │ fusible batterie + interrupteur principal
          ┌────────────┴────────────┐
          │                         │
       ~12 V                    ┌───▼────────┐
          │                     │ Buck 5 V/5A│
    ┌─────▼──────┐              └───┬────────┘
    │ Ampli      │                  │ 5 V
    │ classe D   │      ┌───────────┼───────────┬──────────┐
    └────────────┘      │           │           │          │
                   Raspberry Pi   DAC        écran      ADS1115
                                (I²S)      (+ rétro-    + périphs
                                            éclairage)     USB
```

**Deux rails, une seule source.** Le pack alimente tout ; le secteur ne fait que **recharger
le pack**. Le poste n'a donc qu'un seul comportement électrique, qu'il soit branché ou non —
c'est ce qui rend le fonctionnement « sur secteur » gratuit à concevoir.

---

## 1. Le pack batterie (D11)

- **Configuration :** 3S — trois cellules **18650** Li-ion en série.
- **Tension :** ~9,0 V (vide) à **12,6 V** (pleine charge), 11,1 V nominal.
- **Pourquoi 3S :** ça donne directement le rail ~12 V de l'ampli classe D sans élévateur, et
  un buck vers 5 V est simple et rendementeux.

**À décider (D11) :** référence exacte des cellules, capacité (elle fixe l'autonomie), forme
du support/assemblage, et **place réelle disponible dans le poste** (mesure Phase 0).

> **Dimensionnement :** l'autonomie ne se calcule pas sur le papier avant la Phase 1. La
> consommation réelle relevée au STOP/VÉRIFIER des Phases 1 et 5 (Raspberry Pi 4 + écran
> compris, cf. [design-visualiseur.md](design-visualiseur.md)) est ce qui
> détermine la capacité à acheter. **Acheter les cellules en dernier**, quand le chiffre
> existe.

**Règles non négociables sur un pack Li-ion assemblé soi-même :** cellules de même
référence, même lot, même état de charge à l'assemblage ; jamais de cellules récupérées
d'origine inconnue ; assemblage mécanique qui ne peut pas court-circuiter par vibration.

---

## 2. Le BMS

**Prévu :** BMS 3S, 10–15 A.

Il protège le pack : surcharge, décharge excessive, surintensité, et équilibrage selon le
modèle.

> **Distinction à ne jamais confondre :**
> ```
> Chargeur → délivre le bon profil de charge (CC/CV, arrêt à 12,6 V)
> BMS      → protège et surveille le pack, coupe en cas d'anomalie
> ```
> Un BMS **n'est pas** un chargeur. Une alimentation 12 V ordinaire **n'est pas** un
> chargeur. Compter sur le BMS pour « arrêter la charge » n'est pas une stratégie de charge,
> c'est une protection de dernier recours.

**À vérifier avant achat :** BMS **common port** (charge et décharge sur le même port) ou
**separate port** — ce choix conditionne tout le câblage du §0, et un separate port ne
permet pas de jouer en charge de la même manière. Le courant de décharge continu doit couvrir
le pic de l'ampli à plein volume, pas la consommation moyenne.

---

## 3. Le chargeur secteur (D10)

**Ce qu'il faut :** un vrai **chargeur Li-ion 3S, 100–240 V AC → 12,6 V CC/CV**, pas une
alimentation 12 V.

Références évoquées comme **pistes de recherche**, à valider :

- `TalentCell 12.6V 2A lithium battery charger`
- `E-Shark 12.6V 2A 3S Li-ion charger`

**Points de validation avant achat :**

| Critère | Pourquoi |
|---|---|
| Profil CC/CV, coupure à 12,6 V | C'est la définition d'un chargeur Li-ion. |
| Courant de charge | 2 A est raisonnable ; à revoir à la hausse si le poste doit **jouer fort en étant branché** (voir l'encadré ci-dessous). |
| Certification, isolation, **classe II** | Le C7 n'a pas de terre. |
| Connectique | Doit se raccorder proprement au BMS/pack, sans adaptateur bricolé. |
| **Aptitude à l'usage permanent en boîtier fermé** | Un chargeur externe est conçu pour être à l'air libre. Enfermé dans un ghettoblaster, il chauffe. Question à poser explicitement / à mesurer. |
| Compatibilité avec le BMS retenu | §2. |

> **Le cas « brancher pour jouer plus fort ».** Si le poste est branché *et* qu'il joue,
> l'ampli tire sur le pack pendant que le chargeur le remplit. Deux conséquences :
> (1) le pack **complète** le chargeur si celui-ci est trop faible — donc il se vide malgré
> la prise ; (2) le courant de charge ne se termine pas proprement, la détection de fin de
> charge CC/CV est **faussée par la consommation**. C'est un vrai point de conception, pas un
> détail : il faut soit un chargeur nettement plus puissant que la consommation maximale, soit
> accepter que « branché » ne veuille pas dire « en charge » quand ça joue fort. **À trancher
> en Phase 7, mesures en main.**

---

## 4. Les rails

### Rail ~12 V — l'ampli

Directement issu du pack (via BMS, fusible et interrupteur). C'est le rail **sale** :
courants forts, transitoires rapides.

### Rail 5 V — la logique

Convertisseur buck **5 V / 5 A minimum** (pistes : MP1584 et LM2596 sont **sous-dimensionnés**
pour un Raspberry Pi 4 — viser un module à découpage synchrone donné pour 5 A en continu ; le
LM2596 dissipe en plus beaucoup, ce qui compte dans un boîtier fermé). Alimente le **Pi**, le
DAC, l'**écran + son rétroéclairage**, l'ADS1115 et les périphériques USB.

> **⚠️ Correction de la révision 1.** Le budget « 5 V / 3 A » avait été écrit pour un ESP32.
> Un **Raspberry Pi 4** réclame à lui seul jusqu'à ~3 A en pointe (alimentation officielle :
> 5,1 V / 3 A), avant l'écran, le rétroéclairage et un clavier USB. **3 A ne suffisent pas.**
> Prévoir 5 A, et surtout **une tension qui ne s'effondre pas en pointe** : le Pi est
> notoirement sensible au sous-voltage, et il se manifeste par des instabilités difficiles à
> diagnostiquer. Câbles courts et de section généreuse entre le buck et le Pi.

**À vérifier en Phase 1 :** la consommation réelle, mesurée, du Pi + écran + DAC dans les
conditions d'usage. C'est ce chiffre — pas une estimation — qui dimensionne le buck **et** le
pack (§1).

---

## 5. Découplage — où et pourquoi

Les condensateurs ne se posent pas au hasard : **c'est leur emplacement physique qui fait
l'effet**, pas leur présence dans la BOM.

| Emplacement | Valeurs | Rôle |
|---|---|---|
| **Aux bornes d'alimentation de l'ampli** — quelques centimètres maximum | **1000 µF / 25 V** électrolytique + **100 nF** céramique | L'ampli classe D appelle des courants brefs et violents. Le condensateur est la **réserve locale** : sans lui, chute de tension, ripple, bruit et parasites audibles dans les HP. |
| **En sortie du buck / rail 5 V** | **220 µF / 10 V** + **100 nF** | Stabilise le rail logique. |
| **Au plus près de chaque circuit** (Pi, DAC, écran, ADS1115) | **100 nF** | Découplage local classique. |

---

## 6. Masse en étoile

```
                Batterie / BMS
                      │
              point de masse unique
                 (en étoile)
            ┌─────────┼─────────┐
            │         │         │
          ampli     buck     logique (Pi / DAC)
```

**Objectif :** que les courants forts de l'ampli **ne traversent jamais** les masses
sensibles du Pi et du DAC. C'est la première cause de bruit audible dans ce genre de
montage, et elle est **impossible à corriger après coup** sans tout recâbler.

Compléments :

- câbles HP **torsadés** ;
- liaison DAC → ampli en **câble blindé**, blindage relié côté source uniquement ;
- séparer physiquement le câblage secteur du câblage audio (ne pas les faire cheminer
  parallèlement).

**Ferrites « snap-on »** — noyaux de ferrite fendus qui se clipsent autour d'un câble, pour
atténuer les parasites haute fréquence (alimentation, HP, câbles vers modules sensibles).
Elles **ne sont pas nécessaires dès le départ** : c'est un outil de dépannage EMI si un bruit
apparaît en Phase 9. Référence évoquée : Fair-Rite 0431176451 — un modèle générique au bon
diamètre suffit pour essayer.

---

## 7. Mesure du niveau de batterie

**Le Raspberry Pi n'a pas d'entrée analogique.** La mesure passe par l'**ADS1115** (I²C,
16 bits), qui sert déjà la molette — une voie pour chacune.

```
V_batterie ──[ 220 kΩ ]──┬──[ 100 kΩ ]── GND
                         │
                         ├── 100 nF ── GND   (filtrage)
                         │
                         └──► ADS1115 voie A1 ──I²C──► Raspberry Pi
```

- **⚠️ Recalculer le pont avant câblage.** Rapport 220 k / 100 k : 12,6 V → **~3,9 V**, soit
  au-dessus de ce qu'accepte l'entrée alimentée en 3,3 V. Viser confortablement sous la
  tension d'alimentation de l'ADS1115 — par exemple **220 k / 68 k → ~2,97 V** à pleine
  charge — et vérifier la plage d'entrée retenue (l'ADS1115 a un gain programmable : le
  choisir explicitement, ne pas rester sur la valeur par défaut).
- **Ne jamais** relier ce pont directement à un GPIO du Pi : les GPIO sont numériques, en
  3,3 V, et n'ont aucune tolérance.
- Consommation permanente du pont : ~40 µA — négligeable, mais permanente (lié à Q7).

**Conversion en pourcentage :** la courbe de décharge d'un Li-ion **n'est pas linéaire**. On
commence par une approximation affine, puis on passe à une **table de correspondance
tension → pourcentage** relevée sur le pack réel. À afficher avec prudence : mieux vaut une
jauge à 4 barreaux honnête qu'un « 63 % » faux.

---

## 7bis. Modèle de veille et arrêt propre (D15)

Le choix du Raspberry Pi introduit une contrainte qui n'existait pas avec un
microcontrôleur : **le Pi ne sait pas se suspendre en RAM.** Il n'y a pas de veille façon
téléphone. On n'a donc que trois modèles, et il faut en choisir un :

| Modèle | Consommation « éteint » | Délai de reprise | Coût logiciel |
|---|---|---|---|
| **Arrêt complet** | nulle | ~10 s de démarrage | faible |
| **Toujours allumé** (écran off, audio coupé) | permanente, à mesurer | instantané | faible |
| **Mixte** : arrêt sur batterie, allumé sur secteur | nulle en mobilité | variable | plus élevé |

**À trancher en Phase 7, la consommation d'idle mesurée en main.** Le critère est simple :
*un poste qui vide sa batterie éteint en une semaine est raté* — mais *un poste qui met dix
secondes à jouer est agaçant*. Le mixte est probablement le bon compromis, et il coûte de la
logique, pas du matériel.

**Ce que l'alimentation doit fournir dans tous les cas :**

1. **Détection de coupure secteur** et **de batterie basse** → le Pi doit être prévenu assez
   tôt pour s'arrêter proprement. Le pack joue le rôle d'onduleur : c'est **lui** qui rend
   l'arrêt propre toujours possible, et qui met le risque de corruption de carte SD à ~zéro
   (avec un rootfs en lecture seule).
2. **Un appui sur l'interrupteur ne doit pas couper l'alimentation immédiatement** : il doit
   *demander* l'arrêt, laisser le système se fermer, puis couper. Un interrupteur qui coupe
   sec est incompatible avec un ordinateur.
3. **Seuil de coupure dure** en dernier recours (protection du pack), assuré par le BMS.

> **Conséquence pour le Bluetooth.** Si le modèle « arrêt complet » l'emporte, un **module
> récepteur Bluetooth autonome** alimenté en permanence (quelques mA) rendrait le poste
> enceinte Bluetooth **sans réveiller le Pi**, en 2 secondes
> ([design-brandt-rk711s.md](design-brandt-rk711s.md) §4.4). C'est le seul cas où ce module
> se justifie.

---

## 8. Sécurité secteur — la liste, pas les intentions

Le C7 change la nature du montage. Sont **obligatoires** :

1. **Fusible côté secteur**, en amont de tout, calibré et accessible.
2. **Fusible côté batterie** — un pack 3S de 18650 en court-circuit délivre des dizaines
   d'ampères.
3. **Interrupteur principal** dimensionné pour le courant réel.
4. Module AC/DC **certifié, isolé, classe II** (pas de terre disponible sur un C7).
5. **Fixation mécanique** de tous les modules — rien qui pende, rien qui vibre, rien qui
   puisse toucher une carte logique en tombant.
6. **Câblage secteur isolé et gainé**, cheminement séparé, distances d'isolement respectées,
   toutes les parties sous 230 V capotées : **aucun conducteur nu accessible, même boîtier
   ouvert**.
7. Aucune partie sous 230 V accessible depuis l'extérieur du poste, dans aucune position.
8. Vérification thermique en boîtier fermé après une heure de charge + lecture.

---

## 9. Vérifications de la Phase 7

> **STOP / VÉRIFIER (Phase 7) :**
> 1. Chaîne secteur montée, capotée et fixée **avant** toute mise sous tension — contrôle
>    visuel à deux temps (câblage, puis boîtier fermé).
> 2. Charge complète du pack mesurée : arrêt propre à 12,6 V, aucune cellule déséquilibrée
>    (mesure au multimètre sur chaque élément).
> 3. Autonomie mesurée à volume d'écoute réel — chiffre **écrit dans cette note**.
> 4. Aucun échauffement anormal après 1 h en boîtier fermé (chargeur, buck, ampli, BMS).
> 5. **Aucun bruit d'alimentation audible dans les HP**, ni sur batterie, ni sur secteur, ni
>    pendant la charge.
> 6. Consommation résiduelle poste éteint mesurée (Q7) — et **consommation d'idle** mesurée,
>    qui tranche D15 (§7bis).
> 7. Coupure brutale de l'alimentation → redémarrage sain, calibration et dernière station
>    retrouvées, **système de fichiers intact** (rootfs en lecture seule).
> 8. Appui sur l'interrupteur → arrêt **propre** du Pi, puis coupure — jamais l'inverse.

---

## 10. Questions ouvertes

1. **Q6 — Chargeur (D10).** Référence définitive, tenue thermique en boîtier fermé,
   raccordement au BMS, courant retenu (§3).
2. **Q7 — Comportement à l'extinction.** L'interrupteur coupe quoi exactement : tout, ou
   seulement les rails en laissant le pont diviseur et le BMS consommer ? Quelle
   consommation résiduelle acceptable ? **Un poste qui se vide en une semaine éteint est un
   poste raté.**
3. **Q8 — Jouer en charge (§3).** Chargeur surdimensionné, ou on accepte que le pack se vide
   quand ça joue fort sur secteur ?
4. **Q9 / D15 — Modèle de veille et arrêt propre.** Arrêt complet, toujours allumé, ou mixte
   (§7bis) ? Et par quel mécanisme l'interrupteur *demande*-t-il l'arrêt au lieu de couper
   sec ? Se tranche en Phase 7 avec la consommation d'idle mesurée.
5. **Q10 — Pont diviseur (§7).** Recalculer les valeurs pour rester sous 3,3 V.
6. **Q11 — Capacité du pack.** Se décide avec la consommation mesurée en Phase 1/5, pas avant.

---

## 11. Liste des interdits (DO-NOT)

1. **Ne pas** amener du 230 V sur une breadboard, un montage provisoire, ou un module non
   fixé. Phases 1 à 6 : **alimentation de laboratoire uniquement**.
2. **Ne pas** utiliser une alimentation 12 V ordinaire comme chargeur d'un pack Li-ion (§2).
3. **Ne pas** compter sur le BMS pour terminer une charge.
4. **Ne pas** utiliser un module AC/DC non certifié ou non isolé, ni supposer une terre :
   le C7 n'en a pas.
5. **Ne pas** assembler un pack avec des cellules dépareillées, récupérées, ou d'état de
   charge différent.
6. **Ne pas** câbler le pont diviseur du §7 avant d'avoir recalculé les valeurs (Q10), et
   **jamais** le relier à un GPIO du Pi.
6b. **Ne pas** dimensionner le rail 5 V à 3 A : le Pi 4 seul les consomme en pointe (§4).
6c. **Ne pas** câbler un interrupteur qui coupe l'alimentation du Pi sans arrêt préalable
    (§7bis).
7. **Ne pas** faire passer les courants de l'ampli dans les masses Pi/DAC — masse en
   étoile (§6).
8. **Ne pas** poser les condensateurs de découplage loin des broches qu'ils protègent : hors
   de portée, ils ne servent à rien (§5).
9. **Ne pas** acheter les cellules avant d'avoir la consommation mesurée (Q11).
10. **Ne pas** refermer le poste sans le contrôle visuel du §8.6.
