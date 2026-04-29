# LABORATOIRE BETHESDA — Déploiement Railway.app (GRATUIT)
## Accessible partout dans le monde — Cameroun, Europe, international

---

## ÉTAPE 1 — Créer un compte GitHub (5 minutes)

1. Aller sur https://github.com
2. Cliquer "Sign up" → créer un compte gratuit
3. Vérifier votre email

---

## ÉTAPE 2 — Créer un dépôt GitHub (3 minutes)

1. Cliquer le bouton "+" en haut à droite → "New repository"
2. Nom du dépôt : `bethesda-lab`
3. Visibilité : **Private** (données médicales !)
4. Cliquer "Create repository"

---

## ÉTAPE 3 — Pousser le code depuis PyCharm (10 minutes)

Dans le terminal PyCharm :

```powershell
# Aller dans le dossier Bethesda
cd "D:\FRANCE\Mes_Projets\IA _ML\Bethesda"

# Initialiser Git
git init

# Ajouter tous les fichiers (sauf ceux dans .gitignore)
git add .

# Premier commit
git commit -m "Bethesda Lab v2.0 - Déploiement initial"

# Lier à GitHub (remplacer VOTRE_USERNAME par votre nom GitHub)
git remote add origin https://github.com/VOTRE_USERNAME/bethesda-lab.git

# Pousser le code
git push -u origin main
```

---

## ÉTAPE 4 — Déployer sur Railway (5 minutes)

1. Aller sur https://railway.app
2. Cliquer "Start a New Project"
3. Choisir "Deploy from GitHub repo"
4. Autoriser Railway à accéder à GitHub
5. Sélectionner le dépôt `bethesda-lab`
6. Railway détecte Python automatiquement

---

## ÉTAPE 5 — Configurer les variables d'environnement

Dans Railway → votre projet → "Variables" :

```
BETHESDA_SECRET = une-cle-longue-et-secrete-unique-2026
BETHESDA_DEBUG  = false
```

---

## ÉTAPE 6 — Obtenir votre URL publique

Dans Railway → "Settings" → "Domains" → "Generate Domain"

Vous obtenez : `https://bethesda-lab-production.up.railway.app`

Cette URL est accessible depuis :
- Yaoundé, Cameroun
- Paris, France
- New York, USA
- Partout dans le monde !

---

## ÉTAPE 7 — Mettre à jour le dashboard HTML

Ouvrir `bethesda_dashboard.html` et remplacer :

```javascript
const API = 'http://localhost:5000/api/v1';
```

Par :

```javascript
const API = 'https://bethesda-lab-production.up.railway.app/api/v1';
```

---

## VÉRIFICATION FINALE

Ouvrir dans le navigateur :
```
https://bethesda-lab-production.up.railway.app/api/v1/sante
```

Si vous voyez : `"succes": true` → Bethesda est en ligne internationalement !

---

## LIMITES DU PLAN GRATUIT Railway

- 500 heures/mois (suffisant pour usage normal)
- 512 MB RAM
- PostgreSQL gratuit inclus (pour migrer depuis CSV)
- Pas de limite de pays

## POUR PASSER EN PRODUCTION RÉELLE

Quand vous avez des vrais clients :
- Railway Hobby : 5$/mois = illimité
- OVH VPS + PostgreSQL : 6€/mois = contrôle total
