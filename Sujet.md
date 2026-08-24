Sujet d'examen
Santé — Prédiction du risque de
réadmission hospitalière à 30 jours
Introduction
Les établissements hospitaliers font face à une pression croissante sur leurs capacités d'accueil,
au vieillissement de la population et à l'augmentation des pathologies chroniques. Dans ce
contexte, les réadmissions non programmées à court terme — retour aux urgences ou nouvelle
hospitalisation dans les trente jours suivant une sortie — constituent à la fois un signal de
détérioration de l'état du patient et une charge évitable pour le système de soins.
Les parcours de soins modernes génèrent des volumes de données hétérogènes réparties dans
plusieurs sources : dossiers administratifs des patients (SIH), codage médical structuré (PMSI /
RIM-P), résultats d'examens biologiques et constantes vitales (DPI), prescriptions
médicamenteuses, comptes-rendus cliniques en texte libre, historique d'utilisation des soins, et
données de télésurveillance post-sortie issues d'objets connectés. Ces données, croisées avec
les caractéristiques territoriales des patients, permettent d'identifier précocement les situations à
risque et d'orienter les dispositifs d'accompagnement vers les patients les plus vulnérables.
L'analyse de ces données par l'intelligence artificielle ouvre des perspectives considérables :
alerter les équipes médicales en sortie d'hospitalisation, cibler les visites à domicile, adapter les
plans de sortie. Mais la mise en place de tels systèmes implique de relever des défis spécifiques
au domaine de la santé : hétérogénéité des sources cliniques et de leurs codages, fiabilité
variable des relevés biologiques et capteurs, trajectoires temporelles lacunaires, saisonnalité des
pathologies, et surtout respect strict du secret médical et protection des données de santé, parmi
les plus sensibles au regard du RGPD.
C'est dans ce cadre que s'inscrit votre mission.
Page 1/5
Sujet
En tant que concepteur de solutions d'Intelligence Artificielle, vous êtes mandaté par un
groupement hospitalier régional pour concevoir et proposer un système de prédiction du risque
de réadmission à 30 jours à partir des données de séjour historiques.
Votre objectif est double :
• analyser les données des patients, de leurs séjours et de leur suivi post-sortie pour distinguer
les sorties à faible risque des situations nécessitant un suivi renforcé,
• proposer une solution opérationnelle pouvant être intégrée au système d'information hospitalier
et capable d'évoluer avec l'ajout de nouvelles sources de données (objets connectés de santé,
télésurveillance, données territoriales externes).
Vous serez particulièrement attentif aux aspects liés à la qualité des données issues de sources
cliniques hétérogènes et de leurs codages, aux biais éventuels liés à l'âge, au territoire (déserts
médicaux) ou au profil d'utilisation des soins, et aux contraintes réglementaires liées au
traitement de données de santé (données à caractère personnel sensibles au titre de l'article 9 du
RGPD, secret médical, traçabilité des décisions, non-utilisation de données socio-économiques
individuelles non collectées en milieu hospitalier).
Page 2/5
Jeu de données mis à disposition
Onze fichiers de données distincts sont fournis, répartis entre sources internes (SIH, PMSI, DPI)
et sources externes (objets connectés, données territoriales agrégées). Toutes les données sont
synthétiques et construites à des fins pédagogiques ; elles ne proviennent d'aucun patient réel et
ne doivent en aucun cas être utilisées pour une décision clinique.
1. Patients (patients.csv)
Chaque ligne correspond à un patient unique enregistré dans le système d'information hospitalier.
• PatientID : identifiant permanent du patient (IPP, clé primaire)
• NomPrenom : nom et prénom du patient
• DateNaissance : date de naissance (permet le calcul de l'âge)
• Sexe : genre (F, M, Non renseigné)
• CodePostal : code postal de résidence collecté à l'admission
• Commune : commune de résidence
• RegimeAssurance : régime de couverture (CPAM, MSA, RSI, AME, Non renseigné)
• MedecinTraitant : identifiant du médecin traitant déclaré
• PersonneAPrevenir : contact ou aidant déclaré
• SituationFamiliale : situation familiale (Vit seul, En couple, En famille, Non renseigné — champ
souvent incomplet)
• PathologiesChroniques : pathologies chroniques codées (Diabète, HTA,
InsuffisanceCardiaque, BPCO, Aucune — plusieurs valeurs séparées par le caractère "|" ;
"Aucune" indique l'absence de pathologie chronique déclarée)
2. Historique d'utilisation des soins (historique.csv)
Chaque ligne correspond à un épisode de soins antérieur au séjour index, pour un patient
identifié par PatientID.
• EvenementID : identifiant unique de l'événement
• PatientID : identifiant du patient (clé étrangère)
• TypeEvenement : nature de l'épisode (Hospitalisation, Urgence, Consultation)
• DateEvenement : date de l'épisode
• DureeJours : durée en jours (manquante pour les consultations)
• CodeEtablissement : établissement de soins
3. Séjours (sejours.csv)
Chaque ligne correspond à un séjour hospitalier d'un patient.
• SejourID : identifiant unique du séjour (clé primaire)
• PatientID : identifiant du patient (clé étrangère)
• DateAdmission : date et heure d'admission
• DateSortie : date et heure de sortie
• DureeSejour : durée de séjour en jours (certaines valeurs incohérentes ou négatives à corriger)
• Service : service d'hospitalisation (Urgences, MédecineInterne, Cardiologie, Pneumologie,
Chirurgie, SoinsContinus)
• TypeSejour : nature du séjour (Programmé, Urgent)
• GHM : Groupe Homogène de Malades (codage hospitalier français)
• ModeSortie : modalité de sortie (Domicile, Transfert, EHPAD, HAD, Deces)
• Readmission30j : variable cible (0 = pas de réadmission, 1 = réadmission à 30 jours)
4. Diagnostics (diagnostics.csv)
Page 3/5
Chaque ligne correspond à un diagnostic codé associé à un séjour (relation 1→N : un séjour peut
avoir plusieurs diagnostics).
• DiagnosticID : identifiant unique
• SejourID : identifiant du séjour (clé étrangère)
• CodeCIM10 : code de la classification internationale des maladies (CIM-10)
• LibelleDiagnostic : libellé du diagnostic
• Role : rôle du diagnostic (Principal, Associe, Complication)
5. Actes médicaux (actes.csv)
Chaque ligne correspond à un acte médical réalisé durant un séjour.
• ActeID : identifiant unique
• SejourID : identifiant du séjour (clé étrangère)
• CodeCCAM : code de la classification commune des actes médicaux (CCAM)
• LibelleActe : libellé de l'acte
• DateActe : date de réalisation
• CodeExecutant : code du professionnel réalisant l'acte
6. Biologie (biologies.csv)
Chaque ligne correspond à un résultat d'examen biologique prélevé durant un séjour (relation
1→N temporelle : plusieurs prélèvements par séjour).
• BiologieID : identifiant unique
• SejourID : identifiant du séjour (clé étrangère)
• DatePrelevement : date et heure du prélèvement
• Panel : type d'analyse (Hemoglobine, Creatinine, CRP, Natremie, GlobulesBlancs)
• Valeur : valeur mesurée (valeurs aberrantes ou manquantes)
• Unite : unité de mesure (unités hétérogènes à harmoniser)
• ValeurReferenceBas : borne basse de la valeur de référence
• ValeurReferenceHaut : borne haute de la valeur de référence
7. Constantes vitales (signes_vitaux.csv)
Chaque ligne correspond à un relevé de constantes vitales au cours d'un séjour (relevés toutes
les 4 heures environ).
• ConstanteID : identifiant unique
• SejourID : identifiant du séjour (clé étrangère)
• Horodatage : date et heure du relevé
• FrequenceCardiaque : fréquence cardiaque en bpm (valeurs aberrantes, capteurs défaillants)
• TensionSystolique : pression artérielle systolique en mmHg
• TensionDiastolique : pression artérielle diastolique en mmHg
• Temperature : température corporelle en °C
• FrequenceRespiratoire : fréquence respiratoire par minute
• SpO2 : saturation en oxygène en pourcentage
8. Médicaments (medications.csv)
Chaque ligne correspond à une prescription médicamenteuse associée à un séjour.
• PrescriptionID : identifiant unique
• PatientID : identifiant du patient (clé étrangère)
• SejourID : identifiant du séjour (clé étrangère)
Page 4/5
• CodeATC : code de la classification anatomique-thérapeutique-chimique (ATC)
• LibelleMedicament : libellé du médicament
• Posologie : posologie prescrite (texte libre court)
• DateDebut : date de début de prescription
• DateFin : date de fin (manquante si traitement en cours)
• Voie : voie d'administration (Orale, IV, Sous-cutanee)
9. Comptes-rendus (comptes_rendus.csv)
Chaque ligne correspond à un compte-rendu clinique associé à un séjour.
• CompteRenduID : identifiant unique
• SejourID : identifiant du séjour (clé étrangère)
• TypeCR : type de document (CRH, NoteSoignante, CourrierSortant)
• DateCR : date du compte-rendu
• TexteCR : texte libre du compte-rendu (formulations cliniques hétérogènes)
10. Objets connectés (objets_connectes.csv)
Chaque ligne correspond à une mesure de télésurveillance post-sortie issue d'un objet connecté
de santé (source externe à l'établissement).
• MesureID : identifiant unique
• PatientID : identifiant du patient (clé étrangère)
• Horodatage : date et heure de la mesure
• TypeMesure : nature de la mesure (FrequenceCardiaque, ActivitePas, Poids, SpO2)
• Valeur : valeur mesurée
• QualiteSignal : qualité du relevé (Bon, CapteurDefaillant, Gap)
11. Territoire (territoire_insee.csv)
Chaque ligne correspond à une commune agrégée (source externe INSEE, jointe sur
CodePostal/Commune). Cette table ne contient aucune donnée individuelle ; elle fournit des
indicateurs territoriaux mobilisables comme proxies socio-économiques.
• Commune : nom de la commune (clé de jointure)
• CodePostal : code postal (clé de jointure)
• IndiceDefavorisation : indice de défavorisation territorial agrégé (type EDI/FDep)
• DensiteMedicale : densité médicale (nombre de médecins pour 100 000 habitants)
• PopulationCommune : population de la commune
Page 5/5