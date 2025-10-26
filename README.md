## 🧩 Fonctionnalités principales

✅ **Trois niveaux de difficulté :** facile, normal, difficile  
✅ **Option "Bords traversables" (ON/OFF)**  
✅ **Classement dynamique (leaderboard)** filtrable par niveau et par bords  
✅ **Système de pseudo joueur** (sauvegarde locale en base SQLite)  
✅ **Interface responsive** et adaptée à la taille de la fenêtre  
✅ **Sauvegarde persistante des scores**  
✅ **Mode Aide / Pause**  
✅ **Exécutable Windows (.exe)** généré via **PyInstaller**

---

## ⚙️ Technologies utilisées

| Composant | Description |
|------------|--------------|
| **Langage** | Python 3.13 |
| **Librairies principales** | `pygame`, `sqlite3`, `pyinstaller` |
| **IDE** | Visual Studio Code |
| **Base de données** | SQLite (fichier local `snake_scores.db`) |
| **Outils** | Git / GitHub, Paint.NET (pour les images), SQLite Browser |

---

## 📁 Structure du projet

Snake-game/
│
├── Snake.py # Script principal du jeu
├── db.py # Gestion de la base de données (SQLite)
├── images/ # Ressources graphiques (pomme, fond, icône, etc.)
│ ├── apple.png
│ ├── border.png
│ ├── snake.png
│ └── ...
│
├── snake_scores.db # Base de données locale
├── dist/ # Contient l’exécutable généré par PyInstaller
│ └── Snake.exe
│
├── build/ # Dossier temporaire généré lors de la création de l’exe
├── README.md # Documentation du projet
└── requirements.txt # Dépendances Python (optionnel)

---

## 🚀 Installation et lancement

### 🧱 1. Prérequis
- **Windows 10/11**
- **Python 3.10+**
- Les bibliothèques nécessaires (si exécution via code) :
  ```bash
  pip install pygame
▶️ 2. Lancer depuis le code source
bash
python Snake.py

💾 3. Lancer l’exécutable (recommandé)
Le jeu peut être lancé directement depuis le fichier :
dist/Snake.exe
Aucune installation de Python n’est requise.
Toutes les ressources (images, base de données, icônes) sont incluses dans l’exécutable.

🧠 Base de données
La base de données snake_scores.db contient :

La table players → identifiants et pseudos des joueurs

La table scores → score, date, niveau et paramètre des bords

La table settings → préférences de l’utilisateur (vitesse, bords activés, etc.)

Les scores sont persistants entre les sessions : la base n’est pas réinitialisée à chaque lancement.

🏆 Classement des joueurs
Le leaderboard affiche le top 10 des meilleurs scores.
Filtres disponibles :

Par période (jour, semaine, mois)

Par niveau (facile, normal, difficile)

Par type de bords (ON / OFF)

