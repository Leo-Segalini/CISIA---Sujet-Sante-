# Script oral complet — Projet_CISIALSB.pptx

Ce document contient **ce que vous pouvez dire presque mot pour mot** devant le jury, slide par slide.  
Adaptez le ton, mais gardez le fond. Les passages entre *italiques* sont des indications de geste (pas à lire).

**Avant de commencer** : démarrer la démo (`./scripts/lance_environnement.sh` ou webapp locale), avoir un onglet navigateur prêt sur http://127.0.0.1:8000/, et identifier un séjour « à risque ».

**Compte démo** : `demo@cisia.fr` / `Readmit2026`

---

## Slide 1 — Ouverture visuelle

**Démo :** non.

**Texte à dire :**

« Bonjour à toutes et à tous. Je m’appelle Léo Segalini Briant. Aujourd’hui je vous présente CISIA Santé, un projet réalisé dans le cadre de ma certification CIF.

CISIA Santé est une solution d’aide à la décision pour les établissements hospitaliers. Elle vise à prioriser les patients qui, à la sortie d’hospitalisation, présentent un risque élevé de revenir à l’hôpital dans les trente jours.

Je vais d’abord poser le problème métier, puis montrer comment la solution fonctionne, avec une démonstration live, et enfin expliquer les choix techniques, de sécurité et d’éthique. »

*Passer à la slide 2.*

---

## Slide 2 — Titre et pitch

**Démo :** non.

**Texte à dire :**

« Le message principal est simple : priorisez les sorties à risque **avant** la réadmission, pas après.

CISIA produit un score de risque de réadmission à trente jours. Ce score est **explicable** — on sait pourquoi un patient est signalé — et le traitement reste **cent pour cent local** : les données de santé ne partent pas vers un cloud tiers.

Deux précisions importantes pour le jury. Premièrement, toutes les données de cette démonstration sont **synthétiques** : elles ne correspondent à aucun patient réel. Deuxièmement, CISIA est une **aide à la priorisation**, pas un dispositif de diagnostic et pas un substitut au jugement clinique. »

*Passer à la slide 3.*

---

## Slide 3 — Contexte : le défi clinique

**Démo :** non.

**Texte à dire :**

« Le problème que pose le sujet, et que rencontrent les établissements, se résume à une question : après une sortie, **qui** faut-il rappeler ou accompagner en priorité ?

Sans outil adapté, l’établissement perd plusieurs choses chaque jour. D’abord, il n’a pas de vision **objective et homogène** du risque : la priorisation repose surtout sur l’expérience individuelle. Ensuite, on peut sur-investir du temps de suivi sur des patients à faible risque, pendant que des situations plus fragiles passent entre les mailles. Ensuite, quand une alerte est décidée, il y a souvent **peu de traçabilité** pour justifier pourquoi ce patient-là et pas un autre. Enfin, dès qu’on touche aux données de santé, la pression du **RGPD** et du **secret médical** est maximale : on ne peut pas improviser une IA opaque ou externalisée.

C’est exactement le cadre dans lequel s’inscrit CISIA. »

*Passer à la slide 4.*

---

## Slide 4 — Bénéfices pour l’établissement

**Démo :** non.

**Texte à dire :**

« Pour un établissement, CISIA apporte quatre bénéfices concrets.

Premier bénéfice : **prioriser les bonnes sorties**. Le coordinateur ou l’équipe de parcours voit clairement qui nécessite un suivi renforcé dans les trente jours.

Deuxième bénéfice : **prouver la conformité**. Chaque variable utilisée dans le score a un usage documenté ; ce qui est sensible ou hors périmètre est exclu de façon explicite, pas oublié.

Troisième bénéfice : **intégrer sans exposer le dossier patient au cloud**. Le moteur tourne en local, sur le poste ou le serveur de l’établissement.

Quatrième bénéfice : **comprendre chaque alerte**. Derrière le pourcentage, on fournit les facteurs qui poussent le risque, pour que l’équipe puisse discuter et agir, pas seulement “croire” un score. »

*Passer à la slide 5.*

---

## Slide 5 — Comment ça marche

**Démo :** non (schéma uniquement ; la démo arrive à la slide suivante).

**Texte à dire :**

« Le fonctionnement tient en quatre étapes.

On part des **données de séjour** : ce qui a été collecté pendant l’hospitalisation — profil, diagnostics, biologie, constantes, médicaments, et éventuellement le suivi post-sortie pour un second score.

Ensuite, le système **calcule un risque** : une probabilité exprimée en pourcentage.

Si cette probabilité dépasse un **seuil d’alerte** calibré, on déclenche une **alerte de suivi**.

Enfin, l’équipe agit : rappel, visite, renforcement du plan de sortie — selon les protocoles de l’établissement.

En un coup d’œil, l’utilisateur voit trois choses : le pourcentage de risque, le seuil, et une recommandation du type “suivi renforcé”.

Petit point méthodologique : le seuil n’est pas choisi “au feeling”. Il est calé pour maximiser une métrique qui privilégie le **rappel**, c’est-à-dire pour limiter le risque de rater un patient vraiment à risque. »

*Passer à la slide 6 — préparer le navigateur.*

---

## Slide 6 — Écran clé : score et alerte

**Démo :** **OUI — principale.**

**Texte à dire (avant de basculer) :**

« Voici l’écran clé du produit : dès la sortie, on visualise le risque de réadmission et les actions prioritaires.

Sur la diapositive, l’exemple pédagogique montre un patient très au-dessus du seuil. En production calibrée de notre démo, le seuil du score sortie est de l’ordre de vingt pour cent pour le modèle retenu — l’idée reste la même : au-dessus du seuil, badge de suivi renforcé. »

**Pendant la démo, dire :**

« Je bascule sur l’application.  
*Ouvrir http://127.0.0.1:8000/cisia puis Séjours scorés filtrés à risque, ou directement /cisia/sejours?a_risque=true.*

Voici la liste des séjours à risque. Je sélectionne ce patient.  
*Cliquer une fiche.*

Vous voyez la probabilité de réadmission à trente jours, le seuil d’alerte, et la recommandation associée. Ce n’est pas un diagnostic : c’est une **priorisation documentée** pour l’équipe. »

**Après la démo :**

« Je reviens au PowerPoint pour expliquer comment on construit la confiance autour de ce score. »

*Revenir au PPTX, slide 7. Laisser l’onglet fiche patient ouvert.*

---

## Slide 7 — Transparence : pourquoi ce score ?

**Démo :** **OUI** (même fiche patient).

**Texte à dire :**

« Nous ne livrons pas une boîte noire. Chaque alerte s’accompagne d’une explication des facteurs qui influencent le risque. Cela permet de communiquer avec l’équipe de suivi sur des éléments concrets.

Les familles de facteurs couvrent notamment : le **profil patient** — âge, comorbidités, historique ; les **constantes et la biologie** ; le **type et le déroulement du séjour** — durée, motif, services ; et la **médication** — prescriptions et complexité du traitement. »

**Pendant la démo, dire :**

« Sur la fiche, voici les facteurs locaux d’explication — issus notamment de l’analyse SHAP. Par exemple, on voit que tel facteur **augmente** le risque, tel autre le diminue. L’équipe peut ainsi croiser le score avec ce qu’elle sait déjà du dossier. »

*Revenir au PPTX, slide 8.*

---

## Slide 8 — Justification en langage métier (LLM local)

**Démo :** **OUI si le LLM répond** ; sinon expliquer sans forcer.

**Texte à dire :**

« Au-delà des facteurs techniques, nous produisons aussi une justification en **langage métier**, compréhensible par le staff sans jargon statistique.

Trois points de vigilance. Premièrement, l’analyse peut s’appuyer sur des comptes-rendus **masqués**, traités **localement** sur le poste. Deuxièmement, **aucune identité nominative** n’est envoyée sur Internet : conformité RGPD et secret médical. Troisièmement, le résultat est une phrase claire, actionnable.

Important pour le jury : il y a **deux briques d’IA distinctes**. Le **modèle tabulaire** — forêt aléatoire ou régression logistique — calcule le **score en pourcentage**. Le **LLM local**, de type Qwen, sert à reformuler ou briefer du texte clinique masqué. Le LLM **ne calcule pas** le risque de réadmission. »

**Si démo LLM possible :**

« Sur la fiche, voici le brief généré localement. »

**Si LLM indisponible :**

« Si le serveur LLM local n’est pas démarré aujourd’hui, le principe reste le même : traitement local, contenu masqué, pas d’envoi cloud. »

*Passer à la slide 9.*

---

## Slide 9 — Deux modules : Readmit et Flow

**Démo :** **OUI — courte** sur Flow.

**Texte à dire :**

« CISIA s’organise en deux modules sur un socle unique.

**CISIA Readmit** est le cœur de l’offre. Il s’adresse à la coordination, à la direction et à la gouvernance : score de risque, explicabilité, registre, audit des biais.

**CISIA Flow** est l’ancrage terrain, optionnel. Il s’adresse aux soignants : plan d’étage, occupation des lits, alertes temps réel. Dans la démo, certains services sont en monitoring continu machine, d’autres en saisie manuelle des constantes par les infirmières — y compris le poids.

Readmit décide et documente ; Flow ancre dans le quotidien du service. »

**Pendant la démo, dire :**

« Je montre rapidement Flow.  
*Ouvrir http://127.0.0.1:8000/soignant.*

Voici le plan des étages. On voit les lits, les niveaux de vigilance, et si je clique un patient, j’accède à la fiche soignant avec les constantes. »

*Revenir au PPTX, slide 10.*

---

## Slide 10 — Sécurité et conformité

**Démo :** **OUI — rapide** sur le registre.

**Texte à dire :**

« La sécurité n’est pas un chapitre collé après coup : elle structure le produit.

Premier pilier : le **contrôle local**. Le traitement des données de santé reste sous supervision de l’établissement.

Deuxième pilier : l’**exclusion** des proxys socio-économiques individuels non collectés en milieu hospitalier. Sur la slide, le libellé évoque l’exclusion de ces variables sensibles du calcul du score — c’est une exigence éthique et réglementaire du sujet.

Troisième pilier : un **registre traçable**. Chaque colonne a une sensibilité et un usage : autorisé pour le score, signalé seulement, ou exclu.

Quatrième pilier : l’**identité anonymisée**. Le nominatif est isolé dans un coffre ; le moteur de score travaille sur des données pseudonymisées. »

**Pendant la démo, dire :**

« Voici le registre RGPD dans l’interface.  
*Ouvrir /cisia/registre.*

On peut filtrer par usage exclu ou autorisé, et justifier pourquoi une variable entre ou n’entre pas dans le modèle. »

*Passer à la slide 11.*

---

## Slide 11 — Ce qui différencie CISIA

**Démo :** optionnelle (parcours jury `/cisia/jury` si pas encore montré).

**Texte à dire :**

« Quatre différenciateurs résument notre positionnement.

**Local first** : l’IA tourne sur le poste ou le serveur local, ce qui garantit la souveraineté des données.

**Explicable** : chaque score a une explication SHAP et une traduction métier.

**Gouvernable** : registre RGPD et audit des biais sont intégrés au parcours, pas dans un PDF annexe oublié.

**Prêt à démontrer** : un parcours jury en quelques clics permet de dérouler score, fiche, biais et registre sans formation longue.

Ce n’est pas “encore une IA hospitalière générique” : c’est une chaîne complète, du CSV au score, avec conformité et démontrabilité. »

*Passer à la slide 12.*

---

## Slide 12 — Qualité des données

**Démo :** **OUI** sur la page Analyse.

**Texte à dire :**

« Avant même d’appliquer le modèle, on traite la **qualité des données**, parce que des sources cliniques hétérogènes produisent des trous, des valeurs aberrantes et des incohérences.

Nous identifions par exemple des durées de séjour incohérentes, des constantes hors plage physiologique, des signaux d’objets connectés de mauvaise qualité, ou des dates d’actes hors de la fenêtre du séjour — souvent injectées volontairement dans le jeu synthétique pour l’audit pédagogique.

Ce qui n’est pas fiable n’entre pas silencieusement dans le score : on l’exclut, on le corrige, ou on le flag. Résultat attendu côté métier : **moins de fausses alertes**, donc une meilleure adoption par les équipes.

Pour l’entraînement, autre règle métier forte : on ne garde que les sorties à **domicile**. Les décès — et plus largement les modes de sortie hors domicile — sont exclus de la cohorte d’apprentissage, pour éviter toute fuite absurde du type prédire une réadmission après un décès. »

**Pendant la démo, dire :**

« Voici la page d’analyse des données.  
*Ouvrir /cisia/analyse.*

Vous voyez les volumes d’exclus, de valeurs mal notées ou “hallucinations”, d’aberrants, et d’incohérences temporelles, ainsi que le lien pathologies chroniques et retour à trente jours. »

*Passer à la slide 13.*

---

## Slide 13 — Modélisation : Random Forest retenu

**Démo :** optionnelle (`/cisia/modeles`). **Priorité à l’oral technique.**

**Texte à dire :**

« Côté modélisation, nous avons comparé plusieurs algorithmes sur **les mêmes splits patient-level** : une référence naïve, une régression logistique, une forêt aléatoire, LightGBM, un réseau de neurones de type MLP, et également un gradient boosting de type HistGB dans le benchmark.

Le protocole n’utilise **pas** cent pour cent des données pour entraîner et cent pour cent pour tester. Nous découpons au niveau **patient** environ **soixante-dix pour cent** en entraînement, **quinze pour cent** en validation, et **quinze pour cent** en test. Un même patient ne peut pas être à la fois dans le train et dans le test : cela évite la fuite d’information.

Le **critère de sélection** du modèle retenu est le **PR-AUC sur le jeu test**, adapté aux classes déséquilibrées — l’accuracy serait trompeuse. Le **seuil d’alerte** est choisi pour maximiser le **F2 sur la validation**, afin de privilégier le rappel.

Sur ce jeu, la **forêt aléatoire** obtient le meilleur PR-AUC test, de l’ordre de **zéro virgule soixante et un**. C’est pourquoi elle est retenue pour le **score sortie** en production pédagogique. LightGBM peut afficher un F2 un peu plus élevé, mais il perd sur le critère PR-AUC officiel. Le MLP, lui, chute en test : sur un petit effectif, environ quatre cent quatre-vingts séjours, il surapprend facilement.

Pourquoi la forêt est pertinente **ici** : elle est robuste au bruit, interprétable via SHAP, déployable simplement avec scikit-learn, et stable sur un petit jeu. Pour une mise en production future avec un **beaucoup plus grand** volume de données, un HistGradientBoosting ou un LightGBM redeviendrait souvent plus efficace en performance et en scalabilité : nous le documentons explicitement dans l’application et les notebooks, sans l’imposer sur ce volume.

Pour le **score télé** post-sortie, la production actuelle retient plutôt une **régression logistique**, avec un seuil calibré de l’ordre de quinze pour cent, tandis que le score sortie RF utilise un seuil calibré de l’ordre de vingt pour cent.

Dernier point unités : chaque constante a une **unité canonique fixe** — millimètres de mercure pour la tension, degrés Celsius pour la température, pour cent pour la SpO₂, kilogrammes pour le poids. On n’entraîne pas sur un mélange d’unités pour une même mesure ; en revanche on ne convertit pas toutes les constantes vers une seule unité globale : ce sont des colonnes distinctes, normalisées statistiquement si besoin. »

*Passer à la slide 14.*

---

## Slide 14 — Éthique et équité

**Démo :** **OUI** sur l’audit des biais.

**Texte à dire :**

« Sur l’équité, notre ligne est claire : **on mesure, on ne cache pas**.

Nous ne prétendons pas qu’un modèle est automatiquement équitable. Nous fournissons un audit des performances selon le sexe, l’âge et le territoire, pour rendre visibles d’éventuels écarts. Ces écarts doivent pouvoir être discutés en comité qualité ou éthique.

Cette transparence renforce la crédibilité auprès des médecins, des soignants et de la direction : mieux vaut montrer un biais pour le corriger que le dissimuler derrière un score unique. »

**Pendant la démo, dire :**

« Voici la page d’audit des biais.  
*Ouvrir /cisia/biais.*

Les chiffres sont issus de données synthétiques : on les lit comme une **démarche**, pas comme une vérité épidémiologique réelle. »

*Passer à la slide 15.*

---

## Slide 15 — Scénario d’usage : le coordinateur

**Démo :** **OUI si vous n’avez pas déjà tout montré** ; sinon narration seule en rappelant les écrans.

**Texte à dire :**

« Pour coller le produit au quotidien, voici un scénario type côté coordinateur.

À **huit heures trente**, il **filtre** les sorties de la veille ou du jour et ne garde que celles au-dessus du seuil.

Ensuite, il ouvre la fiche pour une **analyse approfondie** : score, facteurs SHAP, éventuellement brief métier.

Puis il déclenche une **action ciblée** : appel, visite à domicile, alerte à l’équipe de parcours, selon le protocole local.

Enfin, le **patient est suivi** : on peut croiser avec Flow pour le signal terrain, ou simplement tracer que le suivi a été engagé.

CISIA ne remplace pas cette chaîne humaine : il la **priorise** et la **documente**. »

*Si démo finale :* rejouer rapidement liste → fiche → (option) étage soignant.

*Passer à la slide 16.*

---

## Slide 16 — Conclusion

**Démo :** non.

**Texte à dire :**

« Pour conclure. CISIA Readmit, c’est trois promesses.

**Moins** de réadmissions découvertes trop tard, parce qu’on priorise à la sortie.

**Plus** de suivi là où le risque est réellement concentré.

Et tout cela **sans compromettre le secret médical** : traitement local, identité isolée, registre, explications, audit des biais.

Je vous remercie pour votre attention. Je suis disponible pour vos questions. »

---

## Annexe A — Réponses complètes aux questions fréquentes

### « Pourquoi avoir choisi la forêt aléatoire ? »

« Parce que, sur notre protocole patient-level, elle obtient le meilleur PR-AUC sur le jeu test, qui est notre critère officiel compte tenu du déséquilibre des classes. Elle reste robuste sur un petit volume, s’explique avec SHAP, et se déploie simplement. LightGBM peut être meilleur sur le F2, mais il n’est pas premier sur le PR-AUC. Sur un plus grand jeu hospitalier, nous envisageons de re-benchmarker et potentiellement de basculer vers un boosting type HistGB. »

### « Avez-vous entraîné sur 100 % des données ? »

« Non. Nous utilisons un découpage patient-level d’environ soixante-dix pour cent entraînement, quinze pour cent validation et quinze pour cent test. La validation sert à caler le seuil et éventuellement Optuna ; le test sert uniquement à mesurer la performance finale. Un patient n’apparaît jamais dans deux jeux. »

### « Les constantes sont-elles toutes dans la même unité ? »

« Non, pas dans une unité unique globale. Chaque constante a son unité canonique — par exemple millimètres de mercure, degrés Celsius, pour cent, kilogrammes. Le modèle n’est pas entraîné sur un mélange d’unités pour une même mesure. Les colonnes restent distinctes et peuvent être normalisées statistiquement. »

### « Le LLM calcule-t-il le score ? »

« Non. Le score vient du modèle tabulaire. Le LLM local produit un texte d’aide à partir de contenus masqués, sans envoyer les données patient sur Internet. »

### « Incluez-vous les décès dans l’entraînement ? »

« Non. La cohorte d’entraînement ne conserve que les sorties à domicile. Les décès et les autres modes hors domicile sont exclus, pour des raisons de sens clinique et d’anti-fuite. »

### « Est-ce utilisable pour une vraie décision clinique ? »

« Non. Les données sont synthétiques et le système est une aide à la priorisation pédagogique. Toute décision clinique réelle reste du ressort des professionnels de santé. »

---

## Annexe B — Enchaînement démo minimal (si le temps est court)

Dire avant de démarrer :

« Je vais maintenant faire une démonstration live de quatre minutes, sur données synthétiques. »

1. Liste à risque → fiche score (slide 6).  
2. Facteurs SHAP (slide 7).  
3. Plan d’étages Flow (slide 9).  
4. Analyse qualité **ou** registre (slide 12 ou 10).  
5. Biais (slide 14).  

Puis : « Je reviens à la conclusion. » → slide 16.
