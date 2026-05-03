Documentation Technique : Moteur d'Alerte Météorologique pour Kitesurf


Présentation du système

Ce dépôt contient un moteur de traitement de données météorologiques automatisé. 
Le programme analyse les prévisions de vent pour identifier des créneaux de navigation sécurisés et optimaux sur trois spots spécifiques : Berck, Dunkerque et Wissant. 
Il croise des données de vitesse de vent, de rafales et d'orientation pour générer un rapport synthétique par courrier électronique.

Logique de traitement des données

Le code s'appuie sur la bibliothèque Pandas pour structurer les flux de données temporelles reçus via l'API Open-Meteo. 
La logique métier suit trois étapes principales de filtrage.

D'abord, le filtrage temporel restreint l'analyse aux heures de jour, entre 8h00 et 19h00. 
Ensuite, le filtrage de puissance écarte toute mesure inférieure à 15 nœuds. 
Enfin, le filtrage directionnel vérifie que l'angle du vent est compatible avec la configuration géographique de chaque plage pour éviter les risques liés au vent de terre.

Architecture logicielle

Le script est conçu pour être exécuté dans un environnement virtualisé. 
Il utilise le module smtplib pour la communication sortante et s'appuie sur des variables d'environnement pour l'authentification. 
L'indexation temporelle est reconstruite dynamiquement à partir de timestamps Unix, ce qui permet une précision à l'heure près sur une période de 14 jours.

Pipeline d'automatisation (CI/CD)

L'exécution est pilotée par GitHub Actions. 
Ce pipeline d'intégration et de déploiement continu assure l'installation automatique des dépendances et l'exécution du script selon une planification prédéfinie. 
L'intégrité des données d'accès est préservée par l'utilisation de secrets d'infrastructure injectés lors du runtime.
