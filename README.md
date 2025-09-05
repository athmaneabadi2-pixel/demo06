# Companion Bot (Generated Project)

Ce projet a été généré par **companion-factory**.

## Démarrer en local (démo)
1) Créer un environnement Python 3.11+ et installer :
   ```bash
   pip install -r requirements.txt
   ```
2) Copier `.env.sample` vers `.env` et renseigner les variables.
3) Lancer l'app :
   ```bash
   python app.py
   ```
4) Tester la santé :
   - GET http://localhost:5000/health  → 200

## Structure
- `app.py` : Webhook Flask (Twilio) + endpoints internes
- `config.py` : Variables de l'instance (nom, fuseau, features)
- `core/` : modules (LLM, mémoire, templates, scheduler)
- `infra/monitoring.py` : /health et métriques (exemple)
- `db/schema.sql` : schéma minimal (exemple)

## Variables (config.py)
- `DISPLAY_NAME` : nom affiché au contact (WhatsApp)
- `INSTANCE_LABEL` : étiquette interne (pour toi)
- `TIMEZONE` : ex. "Europe/Paris"
- `FEATURES` : liste de modules activés (strings)
- `PROFILE_PATH` : chemin du fichier profil (JSON)

## Déploiement (idée Render)
- Utiliser `render.yaml` comme point de départ.
- Renseigner les secrets (OPENAI_API_KEY, TWILIO_*, etc.).
- Définir le webhook WhatsApp vers `/whatsapp/webhook`.
